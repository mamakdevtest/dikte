"""Deciding whether a recording actually contains speech.

Absolute thresholds don't travel between machines: one laptop's built-in mic
sits at -70 dBFS when the room is quiet, another clips the same room at -35.
So the main test is relative: speech has to rise clearly above *this
recording's own* noise floor, and it has to last long enough to be a word.

The transcription models are the reason this matters: fed near-silence they
don't return an empty string, they invent one. Whisper is famous for it
("Thanks for watching", "Altyazı M.K."), which is what the phrase list below
catches as a second line of defence.
"""

import math
import re
import unicodedata

# Stock phrases the models produce when handed silence. Kept deliberately
# narrow: only sentences nobody dictates on purpose in a two-second clip.
HALLUCINATIONS = {
    "altyazi mk", "altyazi m k", "altyazi", "altyazilar",
    "abone olmayi unutmayin", "izlediginiz icin tesekkurler",
    "izlediginiz icin tesekkur ederim", "izlediginiz icin tesekkur ederiz",
    "kanalima abone olmayi unutmayin", "altyazi mk altyazi mk",
    "thanks for watching", "thank you for watching", "thanks for watching!",
    "please subscribe", "subscribe to my channel", "you", "bye",
    "mbc masr", "sous titres realises par la communaute damara org",
    "amara org community", "sous titrage st 501",
}
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def to_db(value):
    return 20 * math.log10(value) if value > 0 else -120.0


def _percentile(values, fraction):
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(len(values) * fraction)))
    return values[index]


def analyse(rms_values, chunk_seconds, margin_db=10.0, peak_values=None):
    """Turn per-chunk RMS levels into the numbers the decision needs.

    Speech is the loudest chunk, the floor the quiet end: a word counts
    even when it is most of a short clip, instead of being averaged away
    by the percentile that used to stand in for it.
    """
    if not rms_values:
        return {"noise_db": -120.0, "speech_db": -120.0,
                "dynamic_db": 0.0, "voiced_seconds": 0.0,
                "voiced_run_seconds": 0.0, "peak_db": -120.0}

    ordered = sorted(rms_values)
    noise = _percentile(ordered, 0.10)
    speech = max(rms_values)
    noise_db, speech_db = to_db(noise), to_db(speech)

    # Anything this far above the recording's own floor counts as voice.
    gate_db = noise_db + margin_db
    voiced_flags = [to_db(value) >= gate_db for value in rms_values]
    voiced = sum(voiced_flags)

    # The longest unbroken run above the gate: a single word is one run,
    # scattered fan-noise spikes are not.
    longest = current = 0
    for flag in voiced_flags:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    if peak_values:
        peak_db = to_db(max(peak_values))
    else:
        peak_db = -120.0

    return {
        "noise_db": noise_db,
        "speech_db": speech_db,
        "dynamic_db": speech_db - noise_db,
        "voiced_seconds": voiced * chunk_seconds,
        "voiced_run_seconds": longest * chunk_seconds,
        "peak_db": peak_db,
    }


def is_silent(stats, silence_db=-55.0, margin_db=10.0, min_voiced_seconds=0.3):
    """True when the recording holds no speech worth sending to the API.

    The loud end below the absolute floor is still an instant no. Past that,
    speech is a sustained run above the recording's own noise floor — a word
    is one unbroken run, scattered spikes are not — with a loud-peak escape
    hatch for plosive-heavy speech whose RMS never climbs far.
    """
    if stats["speech_db"] < silence_db:
        return True
    run = stats.get("voiced_run_seconds",
                    stats.get("voiced_seconds", 0.0))
    # A single unbroken run is a word even when short: one syllable is
    # ~0.15s, and rejecting it means "I said hey!" comes back as silence.
    # Scattered spikes totalling long are the opposite — fan noise — and
    # only count when they also form a run.
    if run >= 0.15:
        return False
    # Loud peaks with no sustained run: a sharp "hey!" over a noisy floor.
    # The bar is high on purpose — this must not invite fan noise in.
    peak_db = stats.get("peak_db", -120.0)
    if peak_db >= silence_db + 18 and run >= 0.12:
        return False
    # Only distrust flat dynamics near the floor; a loud, evenly-spoken
    # sentence legitimately has a narrow range.
    if stats["speech_db"] < silence_db + 12 and stats["dynamic_db"] < margin_db * 0.6:
        return True
    # The tail: scattered voice with no run is fan noise, not a sentence.
    return run < min_voiced_seconds


def _normalise(text):
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    return _SPACES.sub(" ", _PUNCTUATION.sub("", folded)).strip()


def stock_phrase(text):
    """True when an answer is one of the lines models invent for silence.

    `looks_like_hallucination` without the length cap: the live preview's words
    are read as evidence that a recording holds speech, and the windows it
    probes are longer than the cap a discard decision may use, so the phrase
    itself has to be asked about rather than the clip it came from.
    """
    return looks_like_hallucination(text, 0.0)


def looks_like_hallucination(text, duration_seconds, max_duration=6.0):
    """A stock phrase returned for a short clip is almost certainly invented."""
    if duration_seconds > max_duration:
        return False
    normalised = _normalise(text)
    if not normalised:
        return True
    if normalised in HALLUCINATIONS:
        return True
    # "Altyazı M.K. Altyazı M.K. Altyazı M.K.": the same stock line repeated.
    words = normalised.split()
    for phrase in HALLUCINATIONS:
        parts = phrase.split()
        if len(parts) >= 2 and words and len(words) % len(parts) == 0:
            if " ".join(words) == " ".join(parts * (len(words) // len(parts))):
                return True
    return False
