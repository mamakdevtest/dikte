"""Raw PCM capture with a live level meter.

Dictation records one source. A meeting records two of them at once, the
microphone and what comes out of the speakers. On Windows the pair comes
from WASAPI (see wasapi.py), which records the speakers without needing a
driver-provided loopback device; everywhere else, and on Windows whenever
WASAPI can't serve both sides, it goes through ffmpeg: one process reading
both devices and merging them into the two channels of a single stream,
which is the only way the two stay aligned with each other over an hour.

Which programs do the capturing is a property of the machine, not of the code
above: PulseAudio or PipeWire on Linux, AVFoundation through ffmpeg on macOS,
DirectShow through ffmpeg on Windows. They are gathered into one group each
near the bottom of this file, and a chooser picks between them.
"""

import array
import collections
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave

from PyQt6.QtCore import QObject, pyqtSignal

import wasapi
from i18n import t

RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # s16
CHUNK_FRAMES = 1024
CHUNK_BYTES = CHUNK_FRAMES * SAMPLE_WIDTH * CHANNELS
CHUNK_LATENCY_MS = round(CHUNK_FRAMES / RATE * 1000)
MIN_FRAMES = int(RATE * 0.25)

# --- module-level cache for Settings first open <300ms -----------------
# Subprocess probes (pactl json, ffmpeg dshow/avfoundation) cost 5-8s each
# and were run 3× per SettingsWindow (general + meeting). Cache so the
# second call is <1ms. Which lookups are memoized too.
_audio_cache_lock = threading.Lock()
_cached_pactl_json = None
_cached_pactl_platform = None
_cached_sources = None
_cached_monitors = None
_cached_dshow_devices = None
_cached_dshow_platform = None
_cached_av_devices = None
_cached_av_platform = None
_cached_wasapi = {}
_which_cache = {}
_real_which = shutil.which
_real_run = subprocess.run


def _cached_which(name):
    """Memoized shutil.which; bypassed when shutil.which is patched (tests)."""
    if shutil.which is not _real_which:
        return shutil.which(name)
    with _audio_cache_lock:
        if name in _which_cache:
            return _which_cache[name]
    result = _real_which(name)
    with _audio_cache_lock:
        _which_cache[name] = result
    return result


def invalidate_audio_cache():
    """Clear all cached audio probes and which lookups."""
    global _cached_pactl_json, _cached_pactl_platform, _cached_sources
    global _cached_monitors, _cached_dshow_devices, _cached_dshow_platform
    global _cached_av_devices, _cached_av_platform
    with _audio_cache_lock:
        _cached_pactl_json = None
        _cached_pactl_platform = None
        _cached_sources = None
        _cached_monitors = None
        _cached_dshow_devices = None
        _cached_dshow_platform = None
        _cached_av_devices = None
        _cached_av_platform = None
        _cached_wasapi.clear()
        _which_cache.clear()
    wasapi.reset_cache()


class Recorder(QObject):
    """Runs the available sound-server recorder and reads raw PCM from stdout."""

    level = pyqtSignal(float)              # 0.0 - 1.0, for the waveform
    stopped = pyqtSignal(str, float, object)  # wav path, duration (s), per-chunk RMS
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._source = None
        self._thread = None
        self._buffer = bytearray()
        self._rms = []
        self._cancelled = False
        self._stopping = False
        self._lock = threading.Lock()
        self._gen = 0
        self._session_active = False
        self._paused = False
        self._target = ""
        self._max_bytes = 0
        self._drained = 0

    def pending_bytes(self):
        """The raw PCM recorded since the last call, for the live preview.

        A peek, not a take: stop() still writes the whole session, this only
        hands out what has arrived since the last hand-out.
        """
        with self._lock:
            chunk = bytes(self._buffer[self._drained:])
            self._drained = len(self._buffer)
        return chunk

    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def capturing(self):
        return self.active

    @property
    def paused(self):
        return self._session_active and self._paused

    @property
    def session_active(self):
        return self._session_active

    def start(self, target="", max_seconds=300):
        if self._session_active:
            return
        # WASAPI first on Windows: the default endpoint is the microphone the
        # system actually uses, where enumeration order used to hand dictation
        # a virtual device nobody speaks into. ffmpeg remains the fallback.
        self._source = None
        proc = None
        if sys.platform == "win32":
            try:
                self._source = _dictation_source(target)
            except (wasapi.WasapiError, OSError, ValueError):
                self._source = None
        if self._source is None:
            cmd = recording_command(target)
            if not cmd:
                self.failed.emit(t(sound().missing))
                return

        self._target = target
        self._gen += 1
        gen = self._gen
        self._session_active = True
        self._paused = False
        self._buffer = bytearray()
        self._drained = 0
        self._rms = []
        self._cancelled = False
        self._stopping = False
        self._max_bytes = int(max_seconds * RATE * SAMPLE_WIDTH * CHANNELS)

        if self._source is None:
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                    **_popen_kwargs()
                )
            except OSError as exc:
                self.failed.emit(t("Could not start recording: {error}", error=exc))
                self._session_active = False
                self._proc = None
                return
        self._proc = proc

        self._thread = threading.Thread(target=self._pump, args=(gen,), daemon=True)
        self._thread.start()

    def _pump(self, gen=None):
        if gen is None:
            gen = self._gen
        proc = self._proc
        source = self._source
        if proc is None and source is None:
            return
        stdout = proc.stdout if proc is not None else None
        try:
            while True:
                if gen != self._gen:
                    break
                if stdout is not None:
                    chunk = stdout.read(CHUNK_BYTES)
                else:
                    # A shared-mode microphone delivers silence as real
                    # samples, so a quiet read is a momentary gap, not the
                    # end of the recording.
                    chunk = source.read()
                    if not chunk:
                        time.sleep(0.01)
                        continue
                if not chunk:
                    break
                if gen != self._gen:
                    break
                peak, rms = chunk_levels(chunk)
                with self._lock:
                    self._buffer.extend(chunk)
                    self._rms.append(rms)
                    too_long = len(self._buffer) >= self._max_bytes
                self.level.emit(peak)
                if too_long:
                    self._terminate()
                    break
        except (OSError, ValueError, wasapi.WasapiError):
            pass
        if gen != self._gen:
            return
        # Nobody asked it to end and it captured nothing: the recorder is not
        # installed properly, or the device was refused. Said out loud here,
        # because stop() would otherwise report it as a recording that was too
        # short, which sends the user looking in the wrong place.
        with self._lock:
            captured = bool(self._buffer)
        if self._stopping or self._cancelled or captured:
            return
        if proc is not None:
            try:
                detail = proc.stderr.read().decode("utf-8", "replace").strip()
            except (AttributeError, OSError):
                detail = ""
            detail = detail or f"exit code {proc.returncode}"
        else:
            detail = "the microphone stopped responding"
        self.failed.emit(t(
            "Audio recorder stopped before receiving sound: {error}",
            error=detail,
        ))

    def _terminate(self):
        self._stopping = True
        proc = self._proc
        if proc and proc.poll() is None:
            _terminate_process(proc, timeout=1.5)
        if self._source is not None:
            self._source.close()

    def pause(self):
        if not self._session_active or self._paused:
            return False
        if not self.active:
            return False
        proc = self._proc
        self._stopping = True
        self._gen += 1
        if proc is not None and proc.poll() is None:
            _terminate_process(proc, timeout=1.5)
        if self._source is not None:
            self._source.close()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._proc = None
        self._source = None
        self._stopping = False
        self._paused = True
        return True

    def resume(self):
        if not self._session_active or not self._paused:
            return False
        with self._lock:
            buffered = len(self._buffer)
        remaining = self._max_bytes - buffered
        if remaining <= 0:
            self.failed.emit(t("max duration reached"))
            return False
        self._source = None
        proc = None
        if sys.platform == "win32":
            try:
                self._source = _dictation_source(self._target)
            except (wasapi.WasapiError, OSError, ValueError):
                self._source = None
        if self._source is None:
            cmd = recording_command(self._target)
            if not cmd:
                self.failed.emit(t(sound().missing))
                return False
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                    **_popen_kwargs()
                )
            except OSError as exc:
                self.failed.emit(t("Could not start recording: {error}", error=exc))
                return False
        self._proc = proc
        self._gen += 1
        gen = self._gen
        self._paused = False
        self._stopping = False
        self._cancelled = False
        self._thread = threading.Thread(target=self._pump, args=(gen,), daemon=True)
        self._thread.start()
        return True

    def cancel(self):
        if not self._session_active:
            return
        self._cancelled = True
        self._stopping = True
        self._gen += 1
        proc = self._proc
        if proc and proc.poll() is None:
            _terminate_process(proc, timeout=1.5)
        if self._source is not None:
            self._source.close()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._proc = None
        self._source = None
        with self._lock:
            self._buffer = bytearray()
            self._rms = []
        self._session_active = False
        self._paused = False
        self._stopping = False
        self._cancelled = False

    def stop(self):
        """End the recording and write the WAV file."""
        if not self._session_active:
            return
        if self.active:
            self._terminate()
            if self._thread:
                self._thread.join(timeout=2)
            self._thread = None
            self._proc = None
            self._source = None
        else:
            # paused: nothing to terminate, just clear handles
            self._thread = None
            self._proc = None
            self._source = None

        with self._lock:
            pcm = bytes(self._buffer)
            rms = list(self._rms)
            self._buffer = bytearray()
            self._rms = []

        was_cancelled = self._cancelled
        self._gen += 1
        self._session_active = False
        self._paused = False
        self._stopping = False
        self._cancelled = False

        if was_cancelled:
            return

        frames = len(pcm) // (SAMPLE_WIDTH * CHANNELS)
        if frames < MIN_FRAMES:  # a stray keypress, not speech
            self.failed.emit(t("Recording too short, speak for at least 0.3 s"))
            return

        path = write_wav(pcm)
        self.stopped.emit(path, frames / RATE, rms)


def write_wav(pcm, rate=RATE, channels=CHANNELS, width=SAMPLE_WIDTH):
    fd, path = tempfile.mkstemp(prefix="dikte-", suffix=".wav")
    with open(fd, "wb") as raw, wave.open(raw, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return path


def recording_command(target=""):
    """A raw-s16 capture command for the sound system on this machine."""
    return sound().record(target)


def meeting_command(mic_target, system_target):
    """One ffmpeg reading both devices and merging them into two channels."""
    return sound().meeting(mic_target, system_target)


def _dictation_source(target=""):
    """The microphone dictation records through, straight from WASAPI.

    An empty name means the default capture endpoint — the one the system
    panel would use — rather than the first device enumeration happens to
    list, which on many machines is a virtual or streaming microphone that
    never hears anybody. A stored name that matches nothing falls back to
    that same default: recording on the default mic beats not recording.
    """
    try:
        return wasapi.open_capture(target)
    except wasapi.WasapiError:
        if not target:
            raise
        return wasapi.open_capture("")


def _open_or_default(open_fn, name):
    """Open a meeting endpoint, falling back to the default on a stale name."""
    try:
        return open_fn(name)
    except wasapi.WasapiError:
        if not name:
            raise
        return open_fn("")


def _wasapi_sources(mic_target, system_target):
    """(microphone, speakers) endpoints for a meeting, straight from WASAPI.

    An empty target means the default endpoint, so with nothing configured a
    meeting still records the other side: whatever Discord, Zoom or the
    browser plays lands on the default output, and loopback hears it there.
    """
    mic = _open_or_default(wasapi.open_capture, mic_target)
    try:
        loop = _open_or_default(wasapi.open_loopback, system_target)
    except wasapi.WasapiError:
        mic.close()
        raise
    return mic, loop


class MeetingRecorder(QObject):
    """Microphone and speaker output into one stereo file: left is you, right is
    everyone else.

    Who said what then needs no guessing at all, because the two voices never
    shared a channel to begin with. The recording is written to disk as it
    arrives rather than held in memory, so length is not a problem and a crash
    costs the tail of the meeting instead of all of it.
    """

    levels = pyqtSignal(float, float)      # mine, theirs
    stopped = pyqtSignal(str, float)       # wav path, duration (s)
    died = pyqtSignal()                    # ffmpeg quit on its own
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._thread = None
        self._wav = None
        self._log = None
        self._path = ""
        self._frames = 0
        self._cancelled = False
        self._stopping = False
        self._lock = threading.Lock()
        self._wasapi_mode = False
        self._sources = ()
        self._queues = ()
        self._readers = ()
        self._mic_tap = bytearray()
        self._tap_drained = 0
        self._theirs_tap = bytearray()
        self._theirs_drained = 0
        self._mic_received = 0

    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def mic_received(self):
        """Bytes the microphone has delivered since the run started.

        Zero well into a recording means the endpoint is not delivering at
        all — a dead device, not a quiet user, since a shared-mode
        microphone delivers silence as real samples.
        """
        with self._lock:
            return self._mic_received

    def start(self, path, mic_target="", system_target="", max_seconds=14400):
        if self.active:
            return
        if sys.platform == "win32":
            try:
                self._start_wasapi(path, mic_target, system_target, max_seconds)
                return
            except wasapi.WasapiError:
                pass  # below, the ffmpeg road gets its own say
            except (OSError, wave.Error) as exc:
                # A recording file nobody can write would fail ffmpeg's road
                # the same way; say so instead of dropping it on the caller.
                self.failed.emit(t("Could not open the audio devices for the "
                                   "meeting: {error}", error=exc))
                return
        self._start_ffmpeg(path, mic_target, system_target, max_seconds)

    def _open_wav(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        wav = wave.open(path, "wb")
        wav.setnchannels(2)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(RATE)
        return wav

    def _reset_run(self, path, max_seconds):
        self._path = path
        self._frames = 0
        self._cancelled = False
        self._stopping = False
        self._wasapi_mode = False
        self._max_frames = int(max_seconds * RATE)
        with self._lock:
            self._mic_tap = bytearray()
            self._tap_drained = 0
            self._theirs_tap = bytearray()
            self._theirs_drained = 0
            self._mic_received = 0

    def pending_mic(self):
        """The microphone's half recorded since the last call, for the live
        preview during a meeting."""
        with self._lock:
            chunk = bytes(self._mic_tap[self._tap_drained:])
            self._mic_tap = bytearray()
            self._tap_drained = 0
        return chunk

    def pending_theirs(self):
        """The other side's half recorded since the last call, so the live
        preview can say who is speaking."""
        with self._lock:
            chunk = bytes(self._theirs_tap[self._theirs_drained:])
            self._theirs_tap = bytearray()
            self._theirs_drained = 0
        return chunk

    def _start_wasapi(self, path, mic_target, system_target, max_seconds):
        """Both sides straight from WASAPI, no subprocess in the middle.

        The microphone and the speakers are separate endpoints here rather
        than two inputs of one process, so the pump pairs them frame by
        frame and pads whichever side falls quiet — a loopback endpoint
        delivers nothing at all while no app plays sound.
        """
        mic_src, loop_src = _wasapi_sources(mic_target, system_target)
        try:
            wav = self._open_wav(path)
        except (OSError, wave.Error):
            mic_src.close()
            loop_src.close()
            raise
        self._wav = wav
        self._reset_run(path, max_seconds)
        self._wasapi_mode = True
        self._sources = (mic_src, loop_src)
        self._queues = (collections.deque(), collections.deque())
        self._readers = tuple(
            threading.Thread(target=self._reader, args=(src, queue, side), daemon=True)
            for side, (src, queue) in enumerate(zip(self._sources, self._queues))
        )
        for reader in self._readers:
            reader.start()
        self._thread = threading.Thread(target=self._mix, daemon=True)
        self._thread.start()

    def _start_ffmpeg(self, path, mic_target="", system_target="", max_seconds=14400):
        if not _cached_which("ffmpeg"):
            self.failed.emit(t("ffmpeg not found. Install it to record a meeting."))
            return
        if not system_target:
            system_target = default_monitor()
        if not system_target:
            self.failed.emit(t("Could not work out which speaker output to record. "
                               "Pick one in Settings → Meeting."))
            return

        cmd = meeting_command(mic_target, system_target)

        try:
            self._wav = self._open_wav(path)
            # ffmpeg keeps talking to stderr for as long as it runs; a pipe
            # nobody drains would eventually block it, so it writes to a file.
            self._log = tempfile.TemporaryFile()
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=self._log, bufsize=0,
                **_popen_kwargs()
            )
        except (OSError, wave.Error) as exc:
            self._close_file()
            self._drop_log()
            try:
                os.unlink(path)   # an empty header nobody will ever read
            except OSError:
                pass
            self.failed.emit(t("Could not start recording: {error}", error=exc))
            return

        self._reset_run(path, max_seconds)
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _reader(self, src, queue, side):
        """Drain one WASAPI endpoint into its queue until told to stop.

        A failing read means the device went away mid-meeting; the queue
        ends and the pump reports it, the same way a vanished ffmpeg did.
        The microphone's half is also tapped for the live preview.
        """
        while not self._stopping:
            try:
                chunk = src.read()
            except wasapi.WasapiError:
                queue.append(None)
                return
            if chunk:
                if side == 0:
                    with self._lock:
                        self._mic_tap += chunk
                        self._mic_received += len(chunk)
                else:
                    with self._lock:
                        self._theirs_tap += chunk
                queue.append(chunk)
            else:
                time.sleep(0.01)

    def _mix(self):
        """Pair the two queues frame by frame into the stereo file.

        Whichever side has no data for over a quarter of a second while the
        other does gets zeros: silence is a real thing a meeting records,
        and a starved loopback must never stall the microphone's half. A
        reader that reports its device is gone ends the run outright, the
        way a vanished ffmpeg always has — at most a few hundred
        milliseconds of tail go unwritten.
        """
        block = CHUNK_FRAMES * SAMPLE_WIDTH  # mono bytes per side
        pending = [bytearray(), bytearray()]
        last_data = [time.monotonic(), time.monotonic()]
        try:
            while True:
                for side in (0, 1):
                    while len(pending[side]) < block:
                        try:
                            chunk = self._queues[side].popleft()
                        except IndexError:
                            break
                        if chunk is None:
                            # device went away; the tail is lost, but the run
                            # must be reported the way a vanished ffmpeg was
                            if not self._stopping:
                                self.died.emit()
                            return
                        pending[side] += chunk
                        last_data[side] = time.monotonic()
                have = min(len(pending[0]), len(pending[1])) // block
                now = time.monotonic()
                if not have:
                    for side in (0, 1):
                        starved = (now - last_data[side] > 0.25
                                   and len(pending[1 - side]) >= block)
                        if starved:
                            room = min(len(pending[1 - side]) // block, RATE)
                            pending[side] += b"\x00" * (room * block)
                            last_data[side] = now
                            have = min(len(pending[0]),
                                       len(pending[1])) // block
                    if not have:
                        if self._stopping:
                            return
                        time.sleep(0.01)
                        continue
                take = min(have, 8)  # ≤ 0.5 s per lap keeps stops snappy
                left = pending[0][:take * block]
                right = pending[1][:take * block]
                del pending[0][:take * block]
                del pending[1][:take * block]
                stereo = bytearray()
                for index in range(0, len(left), SAMPLE_WIDTH):
                    stereo += left[index:index + SAMPLE_WIDTH]
                    stereo += right[index:index + SAMPLE_WIDTH]
                stereo = bytes(stereo)
                with self._lock:
                    if self._wav is None:
                        return
                    self._wav.writeframes(stereo)
                    self._frames += len(stereo) // (SAMPLE_WIDTH * 2)
                    too_long = self._frames >= self._max_frames
                # One level pair per block, not one per lap: a lap can carry
                # half a second of catch-up at once, and the overlay's
                # waveform needs the steady block cadence to keep both sides
                # moving evenly.
                step = block * 2
                for index in range(0, len(stereo), step):
                    mine, theirs = stereo_levels(stereo[index:index + step])
                    self.levels.emit(mine, theirs)
                if too_long:
                    self._stop_wasapi()
                    return
        except (OSError, ValueError, wave.Error):
            pass
        if not self._stopping:
            self.died.emit()

    def _stop_wasapi(self):
        self._stopping = True
        for src in self._sources:
            src.close()
        for reader in self._readers:
            reader.join(timeout=2)
        if self._thread is not threading.current_thread():
            if self._thread:
                self._thread.join(timeout=3)
        self._thread = None
        self._sources = ()
        self._readers = ()

    def _pump(self):
        stdout = self._proc.stdout
        block = CHUNK_FRAMES * SAMPLE_WIDTH * 2
        try:
            while True:
                chunk = stdout.read(block)
                if not chunk:
                    break
                mine, theirs = stereo_levels(chunk)
                usable = len(chunk) - (len(chunk) % (SAMPLE_WIDTH * 2))
                if usable:
                    samples = array.array("h")
                    samples.frombytes(chunk[:usable])
                    left = samples[0::2].tobytes()
                    right = samples[1::2].tobytes()
                else:
                    left = right = b""
                with self._lock:
                    if self._wav is None:
                        break
                    self._wav.writeframes(chunk)
                    self._frames += len(chunk) // (SAMPLE_WIDTH * 2)
                    self._mic_received += len(chunk) // 2
                    if left:
                        self._mic_tap += left
                    if right:
                        self._theirs_tap += right
                    too_long = self._frames >= self._max_frames
                self.levels.emit(mine, theirs)
                if too_long:
                    self._terminate()
                    break
        except (OSError, ValueError, wave.Error):
            pass
        # Nobody asked it to end: the sound device went away, or ffmpeg fell
        # over. An hour into a meeting that has to be said out loud rather than
        # discovered afterwards.
        if not self._stopping:
            self.died.emit()

    def _terminate(self):
        self._stopping = True
        proc = self._proc
        if proc and proc.poll() is None:
            _terminate_process(proc, timeout=2)

    def _close_file(self):
        with self._lock:
            wav, self._wav = self._wav, None
        if wav is not None:
            try:
                wav.close()
            except (OSError, wave.Error):
                pass

    def _error_tail(self):
        if self._log is None:
            return ""
        try:
            self._log.seek(0)
            text = self._log.read().decode("utf-8", "replace").strip()
        except OSError:
            return ""
        lines = [line for line in text.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    def _finish_run(self):
        """Shut whichever backend is running down, and say which."""
        if self._wasapi_mode:
            self._stop_wasapi()
            self._close_file()
            self._wasapi_mode = False  # a second stop() must be a no-op
            return 0
        self._terminate()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        code = self._proc.poll() if self._proc else 0
        self._proc = None
        self._close_file()
        return code

    def cancel(self):
        self._cancelled = True
        self._finish_run()
        self._drop_log()
        try:
            os.unlink(self._path)
        except OSError:
            pass

    def stop(self):
        if not self._proc and not self._wasapi_mode and not self._thread:
            return
        # The count is read after the join: the pump thread is still appending
        # the last blocks up to the moment it ends.
        code = self._finish_run()
        frames = self._frames
        if self._cancelled:
            self._drop_log()
            return

        # SIGINT is how the recording ends, and ffmpeg reports being interrupted
        # as a failure; only complain when nothing was captured either.
        if frames < MIN_FRAMES:
            tail = self._error_tail()
            self._drop_log()
            try:
                os.unlink(self._path)
            except OSError:
                pass
            self.failed.emit(
                t("Nothing was recorded: {error}", error=tail or f"ffmpeg → {code}")
                if tail or code else t("Recording too short, speak for at least 0.3 s")
            )
            return
        self._drop_log()
        self.stopped.emit(self._path, frames / RATE)

    def _drop_log(self):
        if self._log is not None:
            try:
                self._log.close()
            except OSError:
                pass
            self._log = None


def chunk_levels(chunk):
    """(peak, rms) in 0..1. Peak drives the waveform, RMS drives the silence check."""
    samples = array.array("h")
    usable = len(chunk) - (len(chunk) % 2)
    if usable <= 0:
        return 0.0, 0.0
    samples.frombytes(chunk[:usable])
    peak = max(abs(min(samples)), abs(max(samples))) / 32768.0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
    return min(1.0, peak), min(1.0, rms)


def stereo_levels(chunk):
    """(left peak, right peak) in 0..1 from interleaved stereo s16."""
    samples = array.array("h")
    usable = len(chunk) - (len(chunk) % 4)
    if usable <= 0:
        return 0.0, 0.0
    samples.frombytes(chunk[:usable])
    left, right = samples[0::2], samples[1::2]
    return _peak(left), _peak(right)


def _peak(samples):
    if not samples:
        return 0.0
    return min(1.0, max(abs(min(samples)), abs(max(samples))) / 32768.0)


# --- the sound system, one group per machine -------------------------------

# Both meeting commands merge the same way: each input down to mono at our own
# rate, then the two of them into the left and right of one stream.
MERGE_FILTER = (
    f"[0:a]aresample={RATE}:async=1,aformat=sample_fmts=s16:channel_layouts=mono[m];"
    f"[1:a]aresample={RATE}:async=1,aformat=sample_fmts=s16:channel_layouts=mono[s];"
    "[m][s]amerge=inputs=2[out]"
)


def _popen_kwargs():
    """Hide the console window that Windows otherwise flashes for each ffmpeg."""
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _run_kwargs():
    if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _terminate_process(proc, timeout):
    """SIGINT on POSIX (lets ffmpeg flush its header), TerminateProcess on Windows."""
    if sys.platform == "win32":
        try:
            proc.terminate()
            proc.wait(timeout=timeout)
            return
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
            except OSError:
                pass
            return
    # POSIX path keeps the original behaviour: SIGINT so ffmpeg finalises cleanly
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        try:
            proc.kill()
        except OSError:
            pass


def _pulse_record(target):
    """parec, or pw-record where PulseAudio's tools were left out.

    parec works with both PulseAudio and PipeWire's PulseAudio compatibility
    service, and its source names are the same ones shown by list_sources().
    Keep pw-record as the fallback for minimal native-PipeWire installations.
    """
    if _cached_which("parec"):
        cmd = [
            "parec", "--record", "--raw", f"--rate={RATE}",
            f"--channels={CHANNELS}", "--format=s16le",
            # Left alone, parec holds about two seconds before handing anything
            # over, and then hands over all of it at once: the level meter sits
            # still and jumps, and the tail of a recording can be lost on the
            # way out. A chunk of the meter is the unit the rest of this file
            # is measured in, so ask for that.
            f"--latency-msec={CHUNK_LATENCY_MS}",
        ]
        if target:
            cmd.append(f"--device={target}")
        return cmd
    if _cached_which("pw-record"):
        cmd = [
            "pw-record", *_pw_record_raw_option(), f"--rate={RATE}",
            f"--channels={CHANNELS}", "--format=s16",
        ]
        if target:
            cmd.append(f"--target={target}")
        cmd.append("-")
        return cmd
    return []


def _pw_record_raw_option():
    """Use --raw only on pw-record releases that provide it.

    PipeWire gained --raw in 1.4, and in the same release stopped treating a
    filename of "-" as raw on its own: before it, the option is refused and the
    recorder dies before any sound arrives; after it, leaving the option out
    wraps the stream in a container the rest of this file would read as noise.
    Ubuntu 24.04 and anything else still on 1.0 or 1.2 sit on the near side of
    that line, so ask the installed binary which form it understands.
    """
    try:
        result = subprocess.run(
            ["pw-record", "--help"], capture_output=True, text=True, timeout=2
        )
        help_text = (result.stdout or "") + (result.stderr or "")
    except (subprocess.SubprocessError, OSError):
        return ["--raw"]  # preserve the existing command when probing itself fails
    if not help_text.strip():
        return ["--raw"]
    return ["--raw"] if "--raw" in help_text else []


def _pulse_meeting(mic_target, system_target):
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "pulse", "-thread_queue_size", "4096", "-i", mic_target or "default",
        "-f", "pulse", "-thread_queue_size", "4096", "-i", system_target,
        "-filter_complex", MERGE_FILTER, "-map", "[out]",
        "-f", "s16le", "-ar", str(RATE), "-",
    ]


def _pactl_sources(refresh=False):
    """Parsed pactl JSON, cached. refresh=True forces re-probe (5s timeout)."""
    global _cached_pactl_json, _cached_pactl_platform
    # Tests patch subprocess/shutil: bypass cache to keep mocks honest
    if subprocess.run is not _real_run or shutil.which is not _real_which:
        if not shutil.which("pactl"):
            return []
        try:
            out = subprocess.run(
                ["pactl", "-f", "json", "list", "sources"],
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout
            return json.loads(out)
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
            return []
    with _audio_cache_lock:
        if not refresh and _cached_pactl_json is not None and _cached_pactl_platform == sys.platform:
            return list(_cached_pactl_json)
    if not _cached_which("pactl"):
        return []
    try:
        out = subprocess.run(
            ["pactl", "-f", "json", "list", "sources"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        data = json.loads(out)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return []
    with _audio_cache_lock:
        _cached_pactl_json = data
        _cached_pactl_platform = sys.platform
    return list(data)


def _pulse_inputs(refresh=False):
    return [
        (src.get("name", ""), src.get("description") or src.get("name", ""))
        for src in _pactl_sources(refresh=refresh)
        if not src.get("name", "").endswith(".monitor")
    ]


def _pulse_outputs(refresh=False):
    return [
        (src.get("name", ""), src.get("description") or src.get("name", ""))
        for src in _pactl_sources(refresh=refresh)
        if src.get("name", "").endswith(".monitor")
    ]


def _pulse_default_output():
    if not _cached_which("pactl"):
        return ""
    try:
        sink = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""
    if not sink:
        return ""
    monitor = f"{sink}.monitor"
    names = {name for name, _ in _pulse_outputs()}
    return monitor if not names or monitor in names else ""


# macOS hands out no monitor of its own: what the speakers are playing is not
# an input, and the only way to record it is a driver that pretends to be one.
# These are the three people install.
LOOPBACK_DEVICES = ("blackhole", "loopback", "soundflower")


def _avfoundation_record(target):
    if not _cached_which("ffmpeg"):
        return []
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        # AVFoundation names an input "video:audio", so the empty half in front
        # of the colon is what says this recording has no picture in it.
        "-f", "avfoundation", "-i", f":{target or 'default'}",
        "-ac", str(CHANNELS), "-ar", str(RATE), "-f", "s16le", "-",
    ]


def _avfoundation_meeting(mic_target, system_target):
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-thread_queue_size", "4096",
        "-f", "avfoundation", "-i", f":{mic_target or 'default'}",
        "-thread_queue_size", "4096",
        "-f", "avfoundation", "-i", f":{system_target}",
        "-filter_complex", MERGE_FILTER, "-map", "[out]",
        "-f", "s16le", "-ar", str(RATE), "-",
    ]


def _avfoundation_inputs(refresh=False):
    """[(index, name)] for every capture device AVFoundation offers.

    The index is what the recorder is given, because that is what ffmpeg takes;
    it changes when devices are plugged in, which is why the name is shown.
    Cached (8s probe) unless refresh=True.
    """
    global _cached_av_devices, _cached_av_platform
    if subprocess.run is not _real_run or shutil.which is not _real_which:
        if not shutil.which("ffmpeg"):
            return []
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-f", "avfoundation",
                 "-list_devices", "true", "-i", ""],
                capture_output=True, text=True, timeout=8, check=False,
            )
        except (subprocess.SubprocessError, OSError):
            return []
        devices, listing = [], False
        for line in result.stderr.splitlines():
            if "AVFoundation audio devices:" in line:
                listing = True
                continue
            if not listing:
                continue
            match = re.search(r"\[(\d+)\]\s+(.+)$", line)
            if match:
                devices.append((match.group(1), match.group(2).strip()))
        return devices
    with _audio_cache_lock:
        if not refresh and _cached_av_devices is not None and _cached_av_platform == sys.platform:
            return list(_cached_av_devices)
    if not _cached_which("ffmpeg"):
        return []
    try:
        # Listing devices is not a thing ffmpeg can do without an input, so it
        # is asked for one it cannot open: the list comes out on stderr and the
        # command then fails, which is the documented way of doing this.
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation",
             "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    devices, listing = [], False
    for line in result.stderr.splitlines():
        if "AVFoundation audio devices:" in line:
            listing = True
            continue
        if not listing:
            continue
        match = re.search(r"\[(\d+)\]\s+(.+)$", line)
        if match:
            devices.append((match.group(1), match.group(2).strip()))
    with _audio_cache_lock:
        _cached_av_devices = devices
        _cached_av_platform = sys.platform
    return list(devices)


def _avfoundation_default_output():
    for name, description in _avfoundation_inputs():
        if any(word in description.lower() for word in LOOPBACK_DEVICES):
            return name
    return ""


Sound = collections.namedtuple(
    "Sound",
    # How to capture one source and two at once, the two device lists, which
    # device a meeting records the far side from, and what to say when the
    # programs for any of it are not installed.
    "record meeting inputs outputs default_output missing",
)

PULSE = Sound(
    record=_pulse_record,
    meeting=_pulse_meeting,
    inputs=_pulse_inputs,
    outputs=_pulse_outputs,
    default_output=_pulse_default_output,
    missing="No audio recorder found. Install pulseaudio-utils or pipewire-audio.",
)

COREAUDIO = Sound(
    record=_avfoundation_record,
    meeting=_avfoundation_meeting,
    inputs=_avfoundation_inputs,
    # Every macOS capture device is offered as the far side of a meeting, the
    # loopback driver among them: there is no way to tell them apart, and an
    # empty list would leave nothing to pick.
    outputs=_avfoundation_inputs,
    default_output=_avfoundation_default_output,
    missing="ffmpeg not found. Install it with: brew install ffmpeg",
)


# --- Windows (DirectShow via ffmpeg) -----------------------------------


def _dshow_audio_devices(refresh=False):
    """[(name, description)] of every DirectShow audio capture device.

    ffmpeg DirectShow enumeration goes to stderr and the command exits non-zero;
    that's the documented way to list devices.
    Typical lines look like:
      [dshow @ 000...]  "Microphone (Realtek Audio)" (audio)
      [dshow @ 000...]  "Stereo Mix (Realtek Audio)" (audio)
    Cached (8s probe) unless refresh=True.
    """
    global _cached_dshow_devices, _cached_dshow_platform
    if subprocess.run is not _real_run or shutil.which is not _real_which:
        if sys.platform != "win32":
            return []
        if not shutil.which("ffmpeg"):
            return []
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-list_devices", "true",
                 "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=8, check=False,
                **_run_kwargs(),
            )
        except (subprocess.SubprocessError, OSError):
            return []
        devices = []
        for line in result.stderr.splitlines():
            m = re.search(r'"([^"]+)"\s*\(audio\)', line)
            if m:
                name = m.group(1).strip()
                devices.append((name, name))
        return devices
    with _audio_cache_lock:
        if not refresh and _cached_dshow_devices is not None and _cached_dshow_platform == sys.platform:
            return list(_cached_dshow_devices)
    if sys.platform != "win32":
        return []
    if not _cached_which("ffmpeg"):
        return []
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-list_devices", "true",
             "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, timeout=8, check=False,
            **_run_kwargs(),
        )
    except (subprocess.SubprocessError, OSError):
        return []
    devices = []
    for line in result.stderr.splitlines():
        # The "(audio)"/"(video)" suffix distinguishes capture devices; the
        # "DirectShow audio/video devices" headings older ffmpeg printed are
        # gone in 9.0, so we can't gate on them.
        m = re.search(r'"([^"]+)"\s*\(audio\)', line)
        if m:
            name = m.group(1).strip()
            devices.append((name, name))
    with _audio_cache_lock:
        _cached_dshow_devices = devices
        _cached_dshow_platform = sys.platform
    return list(devices)


def _dshow_record(target):
    if not _cached_which("ffmpeg"):
        return []
    devices = _dshow_audio_devices()
    chosen = target or (devices[0][0] if devices else "")
    if not chosen:
        return []
    # Named helper so hotkey/paste call-sites that log the backend name read
    # "windows" rather than the resolved program.
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "dshow", "-i", f"audio={chosen}",
        "-ac", str(CHANNELS), "-ar", str(RATE), "-f", "s16le", "-",
    ]


def _dshow_meeting(mic_target, system_target):
    """Two DirectShow inputs merged into stereo.

    The fallback road a meeting takes when WASAPI can't serve both sides.
    Like pulse, it needs a second device that carries what the speakers
    play — a loopback capture device (Stereo Mix or VB-CABLE) — and MeetingRecorder
    refuses to start without one rather than hand ffmpeg a name that will fail.
    """
    if not system_target:
        # Unreachable through MeetingRecorder (it refuses an empty target
        # first); kept because sound().meeting() is also a public surface.
        return _dshow_record(mic_target)
    if not mic_target:
        _devices = _dshow_audio_devices()
        mic_target = _devices[0][0] if _devices else ""
        if not mic_target:
            return []
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-thread_queue_size", "4096",
        "-f", "dshow", "-i", f"audio={mic_target}",
        "-thread_queue_size", "4096",
        "-f", "dshow", "-i", f"audio={system_target}",
        "-filter_complex", MERGE_FILTER, "-map", "[out]",
        "-f", "s16le", "-ar", str(RATE), "-",
    ]


def _dshow_inputs(refresh=False):
    return _dshow_audio_devices(refresh=refresh)


def _dshow_outputs(refresh=False):
    # Only expose obvious loopback / what-you-hear devices on Windows.
    keywords = ("stereo mix", "what u hear", "loopback", "vb-cable",
                "virtual", "cable output", "wave out mix")
    out = []
    for name, desc in _dshow_audio_devices(refresh=refresh):
        low = name.lower()
        if any(kw in low for kw in keywords):
            out.append((name, desc))
    return out


def _dshow_default_output():
    outputs = _dshow_outputs()
    return outputs[0][0] if outputs else ""


def _win_wasapi_lists(kind):
    """[(name, description)] from WASAPI, or () when it can't serve.

    WASAPI enumerates the real endpoints; DirectShow only ever saw capture
    devices, which is why the far side of a meeting used to depend on a
    Stereo-Mix-style device existing at all.
    """
    try:
        if not wasapi.available():
            return ()
        items = wasapi.render_outputs() if kind == "outputs" else wasapi.capture_inputs()
    except (wasapi.WasapiError, OSError, ValueError):
        return ()
    return [(name, name) for name, _ in items]


def _win_inputs(refresh=False):
    return _win_wasapi_lists("inputs") or _dshow_inputs(refresh=refresh)


def _win_outputs(refresh=False):
    return _win_wasapi_lists("outputs") or _dshow_outputs(refresh=refresh)


def _win_default_output():
    try:
        if wasapi.available() and wasapi.default_render_name():
            return wasapi.default_render_name()
    except (wasapi.WasapiError, OSError, ValueError):
        pass
    return _dshow_default_output()


WINDOWS = Sound(
    record=_dshow_record,
    meeting=_dshow_meeting,
    inputs=_win_inputs,
    outputs=_win_outputs,
    default_output=_win_default_output,
    missing=(
        "No microphone found. Install ffmpeg and add it to PATH "
        "(winget install Gyan.FFmpeg)."
    ),
)


def sound():
    """The programs this machine records through."""
    if sys.platform == "darwin":
        return COREAUDIO
    if sys.platform == "win32":
        return WINDOWS
    return PULSE


def cached_list_sources(refresh=False):
    """Cached [(name, description)] for every real input source.

    Reuses the pactl/dshow/avfoundation JSON when available; 5-8s probe
    runs once, subsequent calls are <1ms. Pass refresh=True to re-probe.
    Thread-safe via _audio_cache_lock.
    """
    global _cached_sources
    # Tests patch shutil.which/subprocess.run: bypass generic cache there
    if subprocess.run is not _real_run or shutil.which is not _real_which:
        if sys.platform == "darwin":
            return _avfoundation_inputs(refresh=refresh)
        if sys.platform == "win32":
            return _win_inputs(refresh=refresh)
        return _pulse_inputs(refresh=refresh)
    with _audio_cache_lock:
        if not refresh and _cached_sources is not None:
            return list(_cached_sources)
    if sys.platform == "darwin":
        result = _avfoundation_inputs(refresh=refresh)
    elif sys.platform == "win32":
        result = _win_inputs(refresh=refresh)
    else:
        result = _pulse_inputs(refresh=refresh)
    with _audio_cache_lock:
        _cached_sources = result
    return list(result)


def cached_list_monitors(refresh=False):
    """Cached [(name, description)] for the other side (monitors/loopback)."""
    global _cached_monitors
    if subprocess.run is not _real_run or shutil.which is not _real_which:
        if sys.platform == "darwin":
            return _avfoundation_inputs(refresh=refresh)
        if sys.platform == "win32":
            return _win_outputs(refresh=refresh)
        return _pulse_outputs(refresh=refresh)
    with _audio_cache_lock:
        if not refresh and _cached_monitors is not None:
            return list(_cached_monitors)
    if sys.platform == "darwin":
        result = _avfoundation_inputs(refresh=refresh)
    elif sys.platform == "win32":
        result = _win_outputs(refresh=refresh)
    else:
        result = _pulse_outputs(refresh=refresh)
    with _audio_cache_lock:
        _cached_monitors = result
    return list(result)


def list_sources_cached(refresh=False):
    """Wrapper for settings_ui deferral; same as cached_list_sources."""
    return cached_list_sources(refresh=refresh)


def list_monitors_cached(refresh=False):
    """Wrapper for settings_ui deferral; same as cached_list_monitors."""
    return cached_list_monitors(refresh=refresh)


def list_sources():
    """[(name, description)] for every real input source.

    Thin wrapper for backwards compat; prefers cached value when present
    to avoid 5-8s subprocess probe on Settings open.
    """
    return cached_list_sources(refresh=False)


def list_monitors():
    """[(name, description)] for whatever can be recorded as the other side.

    On Linux that is the monitor of an output, and recording it is recording
    whatever is being played: in a meeting the other participants, and nothing
    of your own microphone.
    Thin wrapper over cached_list_monitors.
    """
    return cached_list_monitors(refresh=False)


def default_monitor():
    """The device the far side of a meeting comes from, or ''."""
    return sound().default_output()


def default_input():
    """The device dictation records from when nothing is named, or ''.

    Only Windows can say which one that is without a probe subprocess; the
    other platforms record from the sound system's default and name it
    there, so '' is honest rather than missing.
    """
    if sys.platform == "win32":
        try:
            if wasapi.available():
                return wasapi.default_capture_name()
        except (wasapi.WasapiError, OSError, ValueError):
            return ""
    return ""
