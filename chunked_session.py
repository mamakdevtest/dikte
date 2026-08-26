"""Background chunked recording: seamless 1-minute slices, incremental persist.

Goal: record continuously but slice every `chunk_seconds` (default 60) without
gaps, transcribe each slice immediately, and append to a session file so that
a token failure / crash never loses earlier slices. The UI sees an uninterrupted
recording; underneath it is N independent transcriptions.

Design mirrors existing stack (std lib + PyQt6 only):
- `audio.recording_command` + subprocess → raw PCM (same as Recorder)
- `QTimer` every chunk_seconds checks buffer under lock, copies slice
- `threading.Thread` transcribes slice via `api.transcribe` (or cached target)
- Each result appended to `DATA_DIR / "chunked_sessions" / f"{base}.jsonl"`
  and `f"{base}.txt"` immediately (flush), so `max_total=600` (10 min) of
  1-min slices survives any later failure.
- `token-safe`: if a slice fails, previous slices are already on disk; next
  slice retries independently. No single giant request that can time out and
  lose 10 minutes.

This module is intentionally small and does not change existing
`audio.Recorder` / `MeetingRecorder`; it reuses their helpers.
"""

import os
import threading
import time
import tempfile
import wave
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

import audio
import api
import config as cfg
from i18n import t


def _write_temp_wav(pcm: bytes, rate=audio.RATE, channels=audio.CHANNELS, width=audio.SAMPLE_WIDTH):
    fd, path = tempfile.mkstemp(prefix="dikte-chunk-", suffix=".wav")
    with os.fdopen(fd, "wb") as raw, wave.open(raw, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return path


class ChunkedLiveRecorder(QObject):
    """Continuous recorder that emits a transcript slice every chunk_seconds."""

    level = pyqtSignal(float)
    chunkReady = pyqtSignal(int, str, str)  # index (1-based), raw, cleaned
    chunkFailed = pyqtSignal(int, str)
    sessionFinished = pyqtSignal(str)       # full concatenated text
    sessionFailed = pyqtSignal(str)

    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.conf = conf
        self._proc = None
        self._thread = None
        self._timer = None
        self._buffer = bytearray()
        self._offset = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()
        self._chunk_idx = 0
        self._chunk_seconds = 60
        self._max_total = 600
        self._full_parts = []
        self._base = ""
        self._session_txt = None  # pathlib.Path
        self._session_jsonl = None

    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return not self._pause.is_set()

    def pause(self):
        self._pause.clear()

    def resume(self):
        self._pause.set()

    def start(self, mic_target="", chunk_seconds=60, max_total=600):
        if self.active:
            return False
        cmd = audio.recording_command(mic_target or self.conf.get("mic_target", ""))
        if not cmd:
            self.sessionFailed.emit(t("No audio recorder found."))
            return False

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                **audio._popen_kwargs(),
            )
        except OSError as exc:
            self.sessionFailed.emit(t("Could not start recording: {error}", error=exc))
            return False

        self._buffer = bytearray()
        self._offset = 0
        self._chunk_idx = 0
        self._full_parts = []
        self._stop.clear()
        self._pause.set()
        self._chunk_seconds = max(10, int(chunk_seconds))
        self._max_total = max(self._chunk_seconds, int(max_total))
        self._base = time.strftime("%Y%m%d-%H%M%S")
        # incremental persist files
        sess_dir = cfg.DATA_DIR / "chunked_sessions"
        try:
            sess_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._session_txt = sess_dir / f"{self._base}.txt"
        self._session_jsonl = sess_dir / f"{self._base}.jsonl"
        # seed files
        try:
            self._session_txt.write_text("", encoding="utf-8")
            self._session_jsonl.write_text("", encoding="utf-8")
        except OSError:
            pass

        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

        # chunk timer (Qt, lives on GUI thread)
        self._timer = QTimer(self)
        self._timer.setInterval(self._chunk_seconds * 1000)
        self._timer.timeout.connect(self._on_chunk_timer)
        self._timer.start()
        return True

    def stop(self):
        self._stop.set()
        self._pause.set()
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
        # flush final partial chunk if any
        self._emit_chunk(is_final=True)
        # terminate recorder
        if self._proc and self._proc.poll() is None:
            try:
                audio._terminate_process(self._proc, timeout=1.5)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._proc = None
        # emit session finished
        full = "\n".join(self._full_parts).strip()
        self.sessionFinished.emit(full)
        return full

    # ---- internals ----
    def _pump(self):
        proc = self._proc
        stdout = proc.stdout
        while not self._stop.is_set():
            # pause support
            while not self._pause.is_set() and not self._stop.is_set():
                time.sleep(0.15)
            if self._stop.is_set():
                break
            try:
                chunk = stdout.read(audio.CHUNK_BYTES)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            # level
            try:
                peak, _ = audio.chunk_levels(chunk)
                self.level.emit(peak)
            except Exception:
                pass
            with self._lock:
                self._buffer.extend(chunk)
                # enforce max_total
                max_bytes = self._max_total * audio.RATE * audio.SAMPLE_WIDTH * audio.CHANNELS
                if len(self._buffer) > max_bytes + audio.CHUNK_BYTES:
                    # keep tail only, but we have already sliced earlier, so trim old
                    excess = len(self._buffer) - max_bytes
                    # do not trim offset slices already emitted
                    if excess > self._offset:
                        # drop oldest un-emitted? keep offset pointer valid
                        pass
            # auto-stop at max_total
            if self._chunk_idx * self._chunk_seconds >= self._max_total:
                self._stop.set()
                break

    def _on_chunk_timer(self):
        if self._stop.is_set() or self.paused:
            return
        self._emit_chunk(is_final=False)

    def _emit_chunk(self, is_final=False):
        # copy slice under lock without blocking pump for long
        with self._lock:
            total = len(self._buffer)
            chunk_bytes = self._chunk_seconds * audio.RATE * audio.SAMPLE_WIDTH * audio.CHANNELS
            if not is_final:
                # need at least one full chunk of new data
                if total - self._offset < chunk_bytes:
                    return
                end = self._offset + chunk_bytes
            else:
                # final partial
                if total <= self._offset:
                    return
                end = total
            pcm = bytes(self._buffer[self._offset:end])
            start_off = self._offset
            self._offset = end
            idx = self._chunk_idx + 1
            self._chunk_idx = idx
        if not pcm or len(pcm) < audio.MIN_FRAMES * audio.SAMPLE_WIDTH * audio.CHANNELS:
            # too short, skip transcribe but advance offset already
            return

        # transcribe off GUI thread, but incrementally persist result when done
        def work(pcm_bytes=pcm, index=idx):
            wav_path = None
            try:
                wav_path = _write_temp_wav(pcm_bytes)
                target = self.conf.transcribe_target()
                raw = api.transcribe(
                    target, wav_path,
                    language=self.conf.get("language", "tr"),
                    prompt=self.conf.get("transcribe_prompt", ""),
                )
                # optional cleanup per slice (light)
                text = raw
                # do not run heavy cleanup on every slice if disabled; keep raw
                # for chunked session we keep raw to avoid extra latency
                self._append_persist(index, raw, text, start_off)
                self._full_parts.append(text)
                self.chunkReady.emit(index, raw, text)
            except Exception as exc:
                self.chunkFailed.emit(index, str(exc))
                # still persist raw failure marker so gap is visible
                try:
                    self._append_persist(index, "", f"[chunk {index} failed: {exc}]", start_off, error=str(exc))
                except Exception:
                    pass
            finally:
                if wav_path:
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        pass
                # if we hit max_total, auto-stop
                if self._chunk_idx * self._chunk_seconds >= self._max_total:
                    try:
                        self.stop()
                    except Exception:
                        pass

        threading.Thread(target=work, daemon=True).start()

    def _append_persist(self, idx, raw, text, offset, error=""):
        """Append one chunk to session files immediately (token-safe)."""
        import json
        # txt: concatenated
        try:
            with open(self._session_txt, "a", encoding="utf-8") as fh:
                fh.write(text + ("\n" if not text.endswith("\n") else ""))
        except OSError:
            pass
        # jsonl: structured
        try:
            row = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "chunk": idx,
                "offset": offset,
                "seconds": self._chunk_seconds,
                "raw": raw[:4000],
                "text": text[:8000],
                "error": error,
            }
            with open(self._session_jsonl, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def session_files(self):
        return self._session_txt, self._session_jsonl
