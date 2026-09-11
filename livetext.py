"""A live look at the words while they are still being spoken.

The real transcript belongs to the pipeline that runs after the recording;
this is only the preview, so it can be rough at the seams. Every few seconds
the newest microphone audio is sent to whatever transcribes dictation anyway
— the same provider, the same key or the same local model — and whatever came
back is appended to the popup. A probe that fails stays quiet: an outage in
the preview must never become an error the user has to deal with.
"""

import os
import tempfile
import threading

from PyQt6.QtCore import QObject, pyqtSignal

import api
import vad

RATE = 16000
SAMPLE_WIDTH = 2

# A probe shorter than this hears too little to be worth its call, and one
# this often would triple the bill for hosted providers.
INTERVAL_SECONDS = 7.0
MIN_CHUNK_SECONDS = 4.0
MIN_CHUNK_BYTES = int(MIN_CHUNK_SECONDS * RATE * SAMPLE_WIDTH)


class LiveTranscriber(QObject):
    """Rolling transcription of the newest microphone audio.

    feed() takes raw mono s16 at 16 kHz — the same bytes the recorders
    already handle — and hands out everything it has not shown yet through
    pending_bytes() on the caller's side; nothing here keeps a second copy
    of the recording alive.
    """

    partial = pyqtSignal(str)

    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self._conf = conf
        self._lock = threading.Lock()
        self._pending = bytearray()
        self._text = ""
        # Which recording the text belongs to. A probe answers seconds after it
        # was sent, so an answer can land in a session that has already ended —
        # and `heard()` is evidence the pipeline acts on, not just words on
        # screen. Every answer carries the generation it was heard in and is
        # dropped when that no longer matches.
        self._generation = 0
        self._language = ""
        self._prompt = ""
        self._stop = threading.Event()
        self._thread = None

    def begin(self, language="", prompt=""):
        """Start a session: empty text, and a worker if none is running."""
        with self._lock:
            self._generation += 1
            self._pending = bytearray()
            self._text = ""
        self._language = language or ""
        self._prompt = prompt or ""
        self.partial.emit("")
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._work, daemon=True)
            self._thread.start()

    def heard(self):
        """The words this session has already read out of the microphone.

        Read before `end()` forgets them: words the preview has already picked
        up are proof that the audio the pipeline is about to judge holds
        speech, heard from the same PCM and with the same provider — evidence
        no level statistic can match, and the reason the silence check does not
        get the last word on a recording the preview has transcribed.
        """
        with self._lock:
            return self._text.strip()

    def end(self):
        """Forget everything: the pipeline owns the recording from here."""
        with self._lock:
            self._generation += 1
            self._pending = bytearray()
            self._text = ""

    def feed(self, pcm):
        if not pcm:
            return
        # Nobody listening (the setting is off, or the session ended): the
        # bytes would pile up in memory for nothing — a four-hour meeting is
        # half a gigabyte nobody asked to keep.
        if self._thread is None or not self._thread.is_alive():
            return
        with self._lock:
            self._pending += pcm

    def _work(self):
        carry = b""
        generation = None
        while not self._stop.wait(INTERVAL_SECONDS):
            with self._lock:
                if generation != self._generation:
                    # Whatever was carried over was spoken into the session
                    # that just ended; it is not this recording's audio.
                    carry = b""
                    generation = self._generation
                pending = carry + bytes(self._pending)
                self._pending = bytearray()
            if len(pending) < MIN_CHUNK_BYTES:
                carry = pending  # too small to hear anything: wait for more
                continue
            carry = b""
            text = self._probe(pending)
            if not text:
                continue
            # A model handed near-silence invents a sentence, and Whisper's
            # inventions are recognisable. On the card that is one thing; as
            # the evidence `heard()` is read for — proof this recording holds
            # speech — it is not, so a stock phrase is never kept as words.
            if vad.stock_phrase(text):
                continue
            with self._lock:
                if generation != self._generation:
                    continue  # heard in a session that has since ended
                self._text = f"{self._text} {text}".strip()
                combined = self._text
                # Emitted under the lock so the session cannot end between the
                # check above and the line reaching the card.
                self.partial.emit(combined)

    def _probe(self, pcm):
        fd, path = tempfile.mkstemp(prefix="dikte-live-", suffix=".wav")
        os.close(fd)
        try:
            import wave
            with wave.open(path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(SAMPLE_WIDTH)
                wav.setframerate(RATE)
                wav.writeframes(pcm)
            text = api.transcribe(
                self._conf.transcribe_target(), path,
                language=self._language, prompt=self._prompt, timeout=60,
            )
            return text.strip()
        except Exception:
            # A preview that cannot run (no provider, no network, an aborted
            # app shutdown) is not the user's problem to read about.
            return ""
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def stop(self):
        self._stop.set()
