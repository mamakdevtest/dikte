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
        self._language = ""
        self._prompt = ""
        self._stop = threading.Event()
        self._thread = None

    def begin(self, language="", prompt=""):
        """Start a session: empty text, and a worker if none is running."""
        with self._lock:
            self._pending = bytearray()
            self._text = ""
        self._language = language or ""
        self._prompt = prompt or ""
        self.partial.emit("")
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._work, daemon=True)
            self._thread.start()

    def end(self):
        """Forget everything: the pipeline owns the recording from here."""
        with self._lock:
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
        while not self._stop.wait(INTERVAL_SECONDS):
            with self._lock:
                pending = carry + bytes(self._pending)
                self._pending = bytearray()
            if len(pending) < MIN_CHUNK_BYTES:
                carry = pending  # too small to hear anything: wait for more
                continue
            carry = b""
            text = self._probe(pending)
            if not text:
                continue
            with self._lock:
                self._text = f"{self._text} {text}".strip()
                combined = self._text
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
