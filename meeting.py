"""From a two-channel meeting recording to a set of minutes.

The recording arrives with your microphone on the left channel and everything
the other participants said on the right, so attribution is settled before any
model sees the audio: each channel is transcribed on its own, and the two are
then interleaved on one timeline. What a model is asked for is only what models
are good at, turning the words into readable prose and then into minutes.

Every stage the run reaches is written to disk, so a failure in the last one
does not cost the transcription of an hour of audio.
"""

import array
import contextlib
import difflib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave

from PyQt6.QtCore import QObject, pyqtSignal

import api
import cleanup
import config as cfg
import filetranscribe
import providers
import vad
from filetranscribe import Cancelled, format_timestamp
from i18n import language, t

# Where the document stops being prose and starts being the transcript. It is a
# comment, so it never shows up in a rendered document, and it is what a retry
# reads the transcript back out of.
TRANSCRIPT_MARKER = "<!-- dikte:transcript -->"

# A microphone that hears the other side through the speakers puts the same
# sentence on both channels. Ours is the copy to drop, and it is a copy when it
# lands on top of theirs in time and says nearly the same thing.
ECHO_OVERLAP = 0.5
ECHO_SIMILARITY = 0.72

# A pause this long inside one person's turn starts a new line instead.
TURN_GAP = 8.0

# How much of a channel is read at a time when levels are measured, matched to
# the block the dictation level meter uses so the silence thresholds mean the
# same thing here.
LEVEL_FRAMES = 1024

# The title step keeps its own budget: a short reply over the first page and
# a half of the transcript, nothing more.
TITLE_CHARS = 1500
TITLE_MAX = 80

# How much of the first audible chunk the language probe hears. Long enough
# that the answer rests on real speech, short enough that it costs pennies.
PROBE_SECONDS = 40.0

TITLE_PROMPT = (
    "A meeting transcript follows. Reply with one short professional title "
    "for it, at most eight words, in the same language the transcript is "
    "written in. No quotes, no markup, no sentence period: the title alone "
    "and nothing else.\n\n"
)

# Localised calendar names, because strftime would name the months in whatever
# C locale the process inherited rather than in the language Dikte speaks.
_MONTHS = {
    "tr": (("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
            "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"),
           ("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem",
            "Ağu", "Eyl", "Eki", "Kas", "Ara")),
    "en": (("January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December"),
           ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
            "Aug", "Sep", "Oct", "Nov", "Dec")),
}


class MeetingPipeline(QObject):
    """Transcribe, clean up and summarise a recorded meeting."""

    progress = pyqtSignal(str, str)     # base, message
    finished = pyqtSignal(str, str)     # base, title
    failed = pyqtSignal(str, str)       # base, error

    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.conf = conf
        self._thread = None
        self._stop = threading.Event()
        self._base = ""
        self._aborter = None

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def running_base(self):
        return self._base if self.busy else ""

    def run(self, entry):
        """Take a meeting row onwards from wherever it stopped."""
        if self.busy:
            return False
        self._stop.clear()
        try:
            self._aborter = api.Aborter()
        except Exception:
            self._aborter = None
        self._base = entry.get("base", "")
        self._thread = threading.Thread(target=self._work, args=(dict(entry),),
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        aborter = self._aborter
        if aborter is not None:
            try:
                aborter.abort()
            except Exception:
                pass

    def _check(self):
        if self._stop.is_set():
            raise Cancelled
        aborter = self._aborter
        if aborter is not None:
            try:
                aborter.check()
            except api.Aborted:
                raise Cancelled from None

    def _say(self, message):
        self.progress.emit(self._base, message)

    # ---- the chain -------------------------------------------------------

    def _work(self, entry):
        base = entry["base"]
        doc_path, wav_path = cfg.meeting_paths(base)
        workdir = None
        try:
            transcript = self._stored_transcript(entry, doc_path)
            if not transcript:
                if not wav_path.exists():
                    raise api.ApiError(t("The recording is gone: {path}", path=wav_path))
                workdir = tempfile.mkdtemp(prefix="dikte-meeting-")
                transcript = self._transcribe(str(wav_path), workdir)
                if self.conf["meeting_cleanup"]:
                    self._check()
                    self._say(t("Cleaning up…"))
                    transcript = self._cleanup(transcript)
                # On disk before the summary is attempted: if the summary fails,
                # a retry starts from here instead of from the audio.
                self._write(doc_path, "", transcript, entry)
                cfg.update_meeting(base, status="transcribed", error="")

            self._check()
            if not entry.get("title"):
                generated = self._title(transcript)
                if generated:
                    entry["title"] = generated
                    # In the index while the minutes are still being written,
                    # so the list says what the meeting was before it says it
                    # is done.
                    cfg.update_meeting(base, title=generated)
            minutes, minutes_style = self._minutes(
                transcript, entry.get("style"))
            minutes_model = self._minutes_model()
            title = self._write(doc_path, minutes, transcript, entry)
            cfg.update_meeting(base, status="done", error="", title=title,
                               model=minutes_model, style=minutes_style)
            self._discard_audio(wav_path)
            self.finished.emit(base, title)

        except api.Aborted:
            cfg.update_meeting(base, error=t("Stopped."))
            self._say(t("Stopped."))
            self.failed.emit(base, t("Stopped."))
        except Cancelled:
            cfg.update_meeting(base, error=t("Stopped."))
            self._say(t("Stopped."))
        except (api.ApiError, OSError, subprocess.SubprocessError, wave.Error) as exc:
            # Preserve transcript checkpoint for retry: if _work already wrote a
            # transcript-only doc (checkpoint at status=transcribed) and minutes
            # or title failed afterward, keep status=transcribed. Pre-checkpoint
            # failures (transcription itself, silent audio, missing wav) stay failed.
            _keep_transcribed = False
            try:
                # Probe: does a transcript checkpoint already exist on disk?
                if doc_path.exists():
                    txt = doc_path.read_text(encoding="utf-8")
                    if TRANSCRIPT_MARKER in txt and read_transcript(txt).strip():
                        _keep_transcribed = True
            except Exception:
                pass
            if _keep_transcribed:
                cfg.update_meeting(base, status="transcribed", error=str(exc))
            else:
                cfg.update_meeting(base, status="failed", error=str(exc))
            self.failed.emit(base, str(exc))
        finally:
            if workdir:
                shutil.rmtree(workdir, ignore_errors=True)

    def _stored_transcript(self, entry, doc_path):
        """The transcript an earlier run already paid for, or ''.

        Also trusts a transcript marker on disk even when status is still
        'failed'/'recorded' (orphan transcript from a minutes-stage failure)
        so retry does not re-pay transcription of an hour.
        """
        # Fast path: status already signals transcript exists
        if entry.get("status") in ("transcribed", "done"):
            try:
                return read_transcript(doc_path.read_text(encoding="utf-8"))
            except OSError:
                return ""
        # Legacy/orphan: minutes-stage failure leaves transcript on disk but status=failed/recorded
        try:
            txt = doc_path.read_text(encoding="utf-8")
            if TRANSCRIPT_MARKER in txt:
                t = read_transcript(txt)
                if t.strip():
                    return t
        except OSError:
            pass
        return ""

    def _transcribe(self, wav_path, workdir):
        conf = self.conf
        mine, theirs = split_channels(wav_path, workdir)
        target = conf.transcribe_target()
        hint = conf.meeting_hint()

        sides = []
        for path, speaker in ((mine, "mine"), (theirs, "theirs")):
            # A directory each: the chunk files are named by their index, and
            # the second channel would otherwise write over the first one's.
            chunk_dir = os.path.join(workdir, speaker)
            os.makedirs(chunk_dir, exist_ok=True)
            sides.append((path, speaker,
                          filetranscribe.split_wav(path, chunk_dir)))
        languages = self._resolve_languages(target, sides, workdir, hint)

        segments = []
        skipped = []
        for path, speaker, chunks in sides:
            side = t("you") if speaker == "mine" else t("the others")
            heard = []
            for index, (chunk_path, offset) in enumerate(chunks, start=1):
                self._check()
                self._say(t("Transcribing {side}: {index}/{count}…",
                            side=side, index=index, count=len(chunks)))
                # Nobody spoke on this side for these ten minutes: an API call
                # would cost money to be told so, and can invent a sentence.
                if self._silent(chunk_path):
                    skipped.append((speaker, chunk_path, offset))
                    continue
                # The chunks overlap, so what the cut fell in the middle of is
                # in two of them; stitch keeps the one that heard it whole.
                heard = filetranscribe.stitch(heard, [
                    (start + offset, end + offset, text)
                    for start, end, text in api.transcribe_segments(
                        target, chunk_path, language=languages[speaker],
                        prompt=hint, aborter=self._aborter
                    )
                ])
            segments.extend((start, end, text, speaker) for start, end, text in heard)
        if not segments and skipped and not self._both_silent(mine, theirs):
            # The silence gate judged every chunk quiet, yet the file carries
            # sound — a quiet microphone or a low system volume reads as
            # silence to the thresholds. An hour of meeting does not get to
            # die on a guess: the loudest skipped part of each side gets one
            # call, and whatever the model hears there is the truth that
            # counts.
            self._say(t("The silence check may have missed the speech; trying "
                        "the loudest parts…"))
            by_side = {}
            for speaker, chunk_path, offset in skipped:
                loudness = self._loudness(chunk_path)
                if speaker not in by_side or loudness > by_side[speaker][0]:
                    by_side[speaker] = (loudness, chunk_path, offset)
            for speaker, (_, chunk_path, offset) in sorted(by_side.items()):
                self._check()
                heard = filetranscribe.stitch([], [
                    (start + offset, end + offset, text)
                    for start, end, text in api.transcribe_segments(
                        target, chunk_path, language=languages[speaker],
                        prompt=hint, aborter=self._aborter
                    )
                ])
                segments.extend((start, end, text, speaker)
                                for start, end, text in heard)
        if not segments:
            if self._both_silent(mine, theirs):
                raise api.ApiError(t(
                    "The recording came back silent on both sides. Check the "
                    "microphone and the speaker output in Settings → Meeting."))
            raise api.ApiError(t("Neither side of the recording had any speech in it."))

        names = conf.speaker_names()
        return render_turns(merge_turns(segments), *names)

    def _resolve_languages(self, target, sides, workdir, hint):
        """{side: language}: what each channel is transcribed as.

        A side pinned by hand keeps its word; a side left to detection is
        heard out on its own first stretch of speech, because the two sides
        of a meeting may not share a language. A side the probe cannot hear
        borrows the other side's answer — it had nothing audible to argue
        with — and only when no answer exists anywhere does the run stop:
        an hour sent through the wrong language is a bill paid for a
        document nobody can read.
        """
        resolved = {}
        for _path, speaker, _chunks in sides:
            language = self.conf.meeting_language_for(speaker)
            resolved[speaker] = "" if language in ("", "auto") else language
        waiting = {speaker for speaker, code in resolved.items() if not code}
        if waiting:
            self._say(t("Listening for the language…"))
        for index, (_path, speaker, chunks) in enumerate(sides):
            if speaker not in waiting:
                continue
            code = self._probe_language(target, chunks, workdir, hint,
                                        offset=index * 2)
            if code:
                resolved[speaker] = code
                self._say(t("Language detected: {language}.", language=code))
        found = [code for code in resolved.values() if code]
        if waiting and not found:
            raise api.ApiError(t(
                "The spoken language could not be detected from the recording. "
                "Pick a speech language in Settings → Meeting."))
        for speaker in waiting:
            if not resolved[speaker]:
                resolved[speaker] = found[0]
        return resolved

    def _probe_language(self, target, chunks, workdir, hint, offset=0):
        """The language a side's first audible stretches say, or '' for none.

        The probe runs on stretches that actually carry speech, so the answer
        rests on heard words rather than on silence. A provider that cannot
        say gets one more stretch to listen to, then hands back nothing.
        """
        probed = 0
        for chunk_path, _offset in chunks:
            if self._silent(chunk_path):
                continue
            probed += 1
            _, code = api.transcribe_auto(
                target, cut_probe(chunk_path, workdir, offset + probed),
                prompt=hint)
            if code:
                return code
            if probed >= 2:
                break
        return ""

    def _loudness(self, path):
        try:
            return max(rms_series(path), default=0.0)
        except (OSError, wave.Error):
            return 0.0

    def _both_silent(self, mine, theirs):
        """Was anything captured at all?

        A device picked wrong records a faithful file full of nothing, and
        "no speech in it" would send the user hunting through the wrong
        settings page.
        """
        for path in (mine, theirs):
            try:
                if max(rms_series(path), default=0.0) > 0.01:
                    return False
            except (OSError, wave.Error):
                return False
        return True

    def _silent(self, path):
        if not self.conf["skip_silent"]:
            return False
        conf = self.conf
        stats = vad.analyse(rms_series(path), LEVEL_FRAMES / wav_rate(path),
                            conf["speech_margin_db"])
        return vad.is_silent(stats, conf["silence_db"], conf["speech_margin_db"],
                             conf["min_voiced_seconds"])

    def _cleanup(self, transcript):
        conf = self.conf
        prompt = conf.cleanup_prompt(with_timestamps=True, with_speakers=True)
        out = []
        blocks = filetranscribe.split_text(transcript, True)
        for index, block in enumerate(blocks, start=1):
            self._check()
            if len(blocks) > 1:
                self._say(t("Cleaning up {index}/{count}…",
                            index=index, count=len(blocks)))
            out.append(cleanup.run(block, conf, prompt, timeout=600, aborter=self._aborter))
        return "\n".join(out)

    def _title(self, transcript):
        """A short professional title, or '' when nobody can be asked.

        A failure here must never fail the run — the fallback names the
        meeting by its date, which is honest even when it is plain.
        """
        conf = self.conf
        head = (transcript or "").strip()[:TITLE_CHARS]
        if not head:
            return ""
        try:
            out = self._ask_model(head, TITLE_PROMPT)
        except (api.ApiError, OSError, subprocess.SubprocessError,
                wave.Error, ValueError):
            return ""
        return clean_title(out)

    def _ask_model(self, text, prompt):
        """One cleanup-shaped request to whoever writes the minutes."""
        conf = self.conf
        provider = conf["meeting_provider"]
        if provider == "local":
            return cleanup._local(text, conf, prompt, 600, aborter=self._aborter)
        who = providers.provider(conf, provider)
        if who is not None and who.transport == "http":
            model = (providers.custom_model(conf, provider, "minutes")
                     if who.custom else conf["meeting_model"])
            if not model:
                return ""
            return api.cleanup(
                text, providers.credential(conf, provider), model, prompt,
                reasoning=conf["meeting_reasoning"],
                base_url=providers.base_url(conf, provider), timeout=600,
                provider=provider, service=who.name, aborter=self._aborter,
            )
        raise api.ApiError(t("Unknown provider."))

    def _minutes(self, transcript, style=None):
        """Whoever the meeting provider is set to, handed the whole transcript.
        The local default takes the same road a local cleanup does — llama.cpp
        on this machine, no key and no bill — so a meeting configured on
        nothing still gets its minutes when a model has been downloaded. The
        hosted gateways all answer the one OpenAI-shaped request; which key,
        which address and which model is the registry's to say, a user's own
        gateway included. The CLIs are not offered the job: a minutes run is
        one long request, not a session.

        Returns (minutes, style): the produced text and the style key that
        actually generated it — "auto" resolves to one of the twelve styles
        before the model writes a single section.
        """
        conf = self.conf
        provider = conf["meeting_provider"]
        style = style or conf["meeting_style"] or "auto"
        if style == "auto":
            style = self._pick_style(transcript)
        prompt = conf.meeting_prompt(style)
        if provider == "local":
            return (cleanup._local(transcript, conf, prompt, 600,
                                   aborter=self._aborter), style)
        who = providers.provider(conf, provider)
        if who is not None and who.transport == "http":
            model = (providers.custom_model(conf, provider, "minutes")
                     if who.custom else conf["meeting_model"])
            if not model:
                raise api.ApiError(t(
                    "{service} has no minutes model chosen. Pick one in "
                    "Settings.", service=who.name))
            text = api.cleanup(
                transcript, providers.credential(conf, provider), model, prompt,
                reasoning=conf["meeting_reasoning"],
                base_url=providers.base_url(conf, provider), timeout=600,
                provider=provider, service=who.name, aborter=self._aborter,
            )
            return text, style
        raise api.ApiError(t("Unknown provider."))

    def _pick_style(self, transcript):
        """Ask once which of the twelve styles fits this transcript best.

        The question rides on a short head of the transcript — enough to hear
        what kind of meeting it was, a fraction of the cost of a full pass.
        The reply is parsed to a known style key; anything unrecognisable
        falls back to the executive summary rather than failing the write-up.
        """
        conf = self.conf
        head = (transcript or "").strip()[:1800]
        if not head:
            return "executive"
        prompt = cfg.meeting_auto_pick_prompt()
        try:
            answer = self._ask_model(head, prompt)
        except (api.ApiError, OSError, subprocess.SubprocessError, wave.Error):
            return "executive"
        text = (answer or "").strip().lower()
        for token in re.findall(r"[a-z_0-9]+", text):
            if token in cfg.STYLE_KEYS and token != "auto":
                return token
        return "executive"

    def _minutes_model(self):
        """The name the history row records for whoever wrote the minutes."""
        provider = self.conf["meeting_provider"]
        if provider == "local":
            return self.conf["local_llm_model"]
        who = providers.provider(self.conf, provider)
        if who is not None and who.custom:
            return providers.custom_model(self.conf, provider, "minutes")
        return self.conf["meeting_model"]

    def _write(self, doc_path, minutes, transcript, entry):
        """Write the document, and hand back the title it ended up with.

        A generated title wins; the minutes' own first heading is the second
        choice and still gets stripped from the body, so the document never
        carries two of them; the calendar names the meeting last.
        """
        head, body = split_title(minutes)
        title = (entry.get("title") or head
                 or fallback_title(entry.get("ts", "")))
        participants = (self.conf["meeting_participants"] or "").strip()
        text = build_document(
            title, entry.get("ts", ""), entry.get("duration", 0.0), body,
            transcript, participants=participants,
        )
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = doc_path.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(doc_path)
        return title

    def _discard_audio(self, wav_path):
        if self.conf["meeting_keep_audio"]:
            return
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass


# --- audio ----------------------------------------------------------------

def split_channels(path, workdir):
    """Pull the stereo recording apart into (mine, theirs) mono files."""
    with contextlib.closing(wave.open(path, "rb")) as src:
        if src.getnchannels() != 2 or src.getsampwidth() != 2:
            raise api.ApiError(t("This recording is not a two-channel meeting."))
        rate = src.getframerate()
        mine = os.path.join(workdir, "mine.wav")
        theirs = os.path.join(workdir, "theirs.wav")
        with contextlib.closing(wave.open(mine, "wb")) as left, \
                contextlib.closing(wave.open(theirs, "wb")) as right:
            for out in (left, right):
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(rate)
            while True:
                frames = src.readframes(rate)  # a second at a time
                if not frames:
                    break
                samples = array.array("h")
                samples.frombytes(frames)
                left.writeframes(samples[0::2].tobytes())
                right.writeframes(samples[1::2].tobytes())
    return mine, theirs


def rms_series(path):
    """Per-block RMS in 0..1, the input vad.analyse expects."""
    out = []
    with contextlib.closing(wave.open(path, "rb")) as wav:
        while True:
            frames = wav.readframes(LEVEL_FRAMES)
            if not frames:
                break
            samples = array.array("h")
            samples.frombytes(frames[:len(frames) - (len(frames) % 2)])
            if not samples:
                continue
            total = sum(s * s for s in samples) / len(samples)
            out.append(min(1.0, (total ** 0.5) / 32768.0))
    return out


def wav_rate(path):
    with contextlib.closing(wave.open(path, "rb")) as wav:
        return wav.getframerate()


def cut_probe(chunk_path, workdir, index):
    """The first PROBE_SECONDS of a chunk, as its own small wav for a probe."""
    with contextlib.closing(wave.open(chunk_path, "rb")) as src:
        rate = src.getframerate()
        channels, width = src.getnchannels(), src.getsampwidth()
        frames = src.readframes(int(PROBE_SECONDS * rate))
    out = os.path.join(workdir, f"probe-{index}.wav")
    with contextlib.closing(wave.open(out, "wb")) as dst:
        dst.setnchannels(channels)
        dst.setsampwidth(width)
        dst.setframerate(rate)
        dst.writeframes(frames)
    return out


# --- the timeline ----------------------------------------------------------

def merge_turns(segments, gap=TURN_GAP):
    """[(start, speaker, text)] on one timeline, echo dropped, turns joined."""
    ordered = sorted(segments, key=lambda seg: (seg[0], seg[1]))
    theirs = [seg for seg in ordered if seg[3] == "theirs"]
    kept = [seg for seg in ordered if seg[3] == "mine" and not _is_echo(seg, theirs)]
    kept.extend(theirs)
    kept.sort(key=lambda seg: seg[0])

    turns = []
    for start, end, text, speaker in kept:
        if turns and turns[-1][1] == speaker and start - turns[-1][3] <= gap:
            turns[-1][2] += " " + text
            turns[-1][3] = max(turns[-1][3], end)
            continue
        turns.append([start, speaker, text, end])
    return [(start, speaker, text) for start, speaker, text, _ in turns]


def _is_echo(segment, theirs):
    """Did the microphone just pick up the other side through the speakers?"""
    start, end, text, _ = segment
    span = max(end - start, 0.01)
    mine = _normalise(text)
    if not mine:
        return True
    for their_start, their_end, their_text, _ in theirs:
        if their_start > end:
            break
        overlap = min(end, their_end) - max(start, their_start)
        if overlap / span < ECHO_OVERLAP:
            continue
        ratio = difflib.SequenceMatcher(None, mine, _normalise(their_text)).ratio()
        if ratio >= ECHO_SIMILARITY:
            return True
    return False


def _normalise(text):
    return re.sub(r"[^\w\s]", "", text.strip().lower())


def render_turns(turns, mine_label, theirs_label):
    labels = {"mine": mine_label, "theirs": theirs_label}
    return "\n".join(
        f"[{format_timestamp(start)}] {labels[speaker]}: {text.strip()}"
        for start, speaker, text in turns
    )


# --- the document ----------------------------------------------------------

def split_title(minutes):
    """('Title', 'rest of it') from a document whose first line is a heading."""
    text = (minutes or "").strip()
    if not text:
        return "", ""
    head, _, rest = text.partition("\n")
    if head.startswith("#"):
        return head.lstrip("#").strip(), rest.strip()
    return "", text


def build_document(title, when, duration, minutes, transcript, participants=""):
    minutes = (minutes or "").strip()
    parts = [f"# {title}", ""]
    meta = []
    if when:
        meta.append(f"{t('Date')}: {format_when(when)}")
    meta.append(f"{t('Duration')}: {length_label(duration)}")
    participants = (participants or "").strip()
    if participants:
        meta.append(f"{t('Participants')}: {participants}")
    parts += [f"*{' · '.join(meta)}*", ""]
    if minutes:
        parts += [minutes, "", "---", ""]
    parts += [TRANSCRIPT_MARKER, f"## {t('Transcript')}", "", transcript.strip(), ""]
    return "\n".join(parts)


def format_when(ts, short=False):
    """"2026-08-28 14:30" said the way people write it, in our language.

    An unparseable or empty stamp comes back as it arrived: the raw form is
    still information, just not dressed up.
    """
    try:
        stamp = time.strptime(ts, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return ts or ""
    long_names, short_names = _MONTHS.get(language(), _MONTHS["en"])
    month = (short_names if short else long_names)[stamp.tm_mon - 1]
    return (f"{stamp.tm_mday} {month} {stamp.tm_year} "
            f"{stamp.tm_hour:02d}:{stamp.tm_min:02d}")


def fallback_title(ts):
    """The name a meeting gets when no model offered a better one."""
    when = format_when(ts, short=True)
    if when:
        return t("Meeting — {when}", when=when)
    return t("Meeting")


def clean_title(text):
    """Whatever the model answered, reduced to a usable one-line title."""
    out = (text or "").strip()
    out = out.strip("'\"“”„«»").strip()
    out = re.sub(r"^[#*\-\s]+", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    if not out:
        return ""
    if len(out) > TITLE_MAX:
        cut = out[:TITLE_MAX]
        space = cut.rfind(" ")
        out = (cut[:space] if space > 0 else cut).rstrip()
    return out.rstrip(".").strip()


def read_transcript(document):
    """The transcript back out of a document written by build_document."""
    _, marker, rest = document.partition(TRANSCRIPT_MARKER)
    if not marker:
        return ""
    lines = rest.strip().splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def length_label(seconds):
    minutes = int(seconds) // 60
    if minutes < 60:
        return t("{minutes} min", minutes=minutes)
    return t("{hours} h {minutes} min", hours=minutes // 60, minutes=minutes % 60)


def new_base():
    """The stem the recording, the document and the index row all share."""
    return time.strftime("%Y%m%d-%H%M%S")


def new_entry(base, duration):
    """The index row for a meeting that has just been recorded."""
    return {
        "base": base,
        "ts": f"{base[:4]}-{base[4:6]}-{base[6:8]} {base[9:11]}:{base[11:13]}",
        "title": "",
        "duration": round(duration, 1),
        "status": "recorded",
        "error": "",
        "model": "",
    }


def retry_meeting(base, conf):
    """Convenience: retry a meeting from its latest safe checkpoint.

    Reads the meetings index, finds the row with the given ``base`` and asks a
    fresh MeetingPipeline to pick it up from wherever it stopped.  The pipeline
    itself owns the checkpoint logic:

    * no transcript yet (status ``recorded`` / ``failed`` before the
      transcript) — transcribes + cleans + writes the ``transcribed``
      checkpoint.
    * transcript already on disk (status ``transcribed`` / ``done`` with a
      readable document) — skips the audio/transcription entirely and
      re-runs only title + minutes (see MeetingPipeline._stored_transcript
      and the ``status="transcribed"`` write).

    Returns True when the pipeline was started, False when there is no such
    meeting or the pipeline is already busy.  The caller should listen to the
    returned pipeline's ``finished`` / ``failed`` signals for the outcome.
    """
    rows = cfg.read_meetings()
    entry = next((row for row in rows if row.get("base") == base), None)
    if entry is None:
        return False
    pipe = MeetingPipeline(conf)
    started = pipe.run(entry)
    if not started:
        return False
    # Hand the pipeline back via the truthy return so a UI layer can wire
    # signals even though this helper created it; callers that only need the
    # boolean can ignore the object identity and just check truthiness.  To
    # keep the simple ``if retry_meeting(base, conf):`` shape, attach the
    # pipeline to the boolean via a tiny wrapper.
    return pipe  # truthy; caller may do ``pipe = retry_meeting(base, conf)``


def retry_meeting_entry(entry, conf):
    """Same as retry_meeting(), but the entry dict is already in hand.

    Useful when the caller has just read the index and does not want to read
    it again.  Hands the entry straight to MeetingPipeline.run(), which
    consults MeetingPipeline._stored_transcript / the on-disk document to
    decide whether to resume from transcription or from the
    ``status="transcribed"`` checkpoint.
    """
    pipe = MeetingPipeline(conf)
    ok = pipe.run(dict(entry))
    return pipe if ok else False


def prune_audio(days):
    """Recordings older than the retention go; the minutes stay forever.

    A kept recording is a second chance at the minutes, not an archive —
    past the retention it is only disk someone forgot about.
    Never prune a recording that is the only recovery source (status not done/transcribed).
    """
    if days <= 0:
        return 0
    # Build set of bases whose status is still recoverable — never prune their wav
    try:
        rows = cfg.read_meetings()
        recoverable = {r.get("base") for r in rows if r.get("status") not in ("done", "transcribed")}
    except Exception:
        recoverable = set()
    cutoff = time.time() - days * 86400
    removed = 0
    for wav in cfg.MEETINGS_DIR.glob("*.wav"):
        try:
            base = wav.stem
            if base in recoverable:
                continue
            if wav.stat().st_mtime < cutoff:
                wav.unlink()
                removed += 1
        except OSError:
            pass  # a file that will not leave today can leave tomorrow
    return removed
