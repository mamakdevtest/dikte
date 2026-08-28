"""MeetingRecorder's WASAPI road, against fake endpoints.

Nothing here touches a real device: the endpoints are bytes in a list, and
what is under test is the pairing of the two sides into one stereo file, the
padding that keeps a quiet loopback from stalling the microphone, and what
the recorder says when a device goes away.
"""

import array
import contextlib
import io
import os
import sys
import time
import unittest
import wave
from unittest import mock

from PyQt6.QtWidgets import QApplication

import audio
import wasapi
from tests.support import DikteTest, pcm, stereo


class FakeSource:
    """A WASAPI endpoint reduced to a script of byte deliveries."""

    def __init__(self, chunks, error=None):
        self.chunks = list(chunks)
        self.error = error
        self.closed = False

    def read(self):
        if self.chunks:
            return self.chunks.pop(0)
        if self.error is not None:
            raise self.error
        return b""

    def close(self):
        self.closed = True


def mono_chunk(value, frames=None):
    return pcm([value] * (frames or audio.CHUNK_FRAMES))


class OnWindows:
    """Run as if the machine ran Windows, wherever the tests execute.

    The WASAPI road is entered on sys.platform alone; with the endpoints
    faked, the mixer itself is portable, so Linux CI exercises it too.
    """

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(sys, "platform", "win32"))


class RecorderWasapi(OnWindows, DikteTest):
    """The two-endpoint mixer: who lands on which channel, and what ends it."""

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.recorder = audio.MeetingRecorder()
        self.events = {"levels": [], "stopped": [], "died": [], "failed": []}
        self.recorder.levels.connect(lambda m, t: self.events["levels"].append((m, t)))
        self.recorder.stopped.connect(
            lambda p, d: self.events["stopped"].append((p, d)))
        self.recorder.died.connect(lambda: self.events["died"].append(True))
        self.recorder.failed.connect(lambda e: self.events["failed"].append(e))
        self.path = os.path.join(self.root, "meet.wav")

    def wire(self, mic, loop):
        sources = (mic, loop)
        self.enterContext(mock.patch.object(
            audio, "_wasapi_sources", return_value=sources))
        return sources

    # Levels and died are emitted from the mixer thread, so the signals ride
    # a queued connection: without pumping the loop they would never land.
    def wait_for(self, condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    def frames_of(self, path):
        with contextlib.closing(wave.open(path, "rb")) as wav:
            self.assertEqual(wav.getnchannels(), 2)
            self.assertEqual(wav.getframerate(), audio.RATE)
            left = array.array("h")
            right = array.array("h")
            while True:
                data = wav.readframes(audio.RATE)
                if not data:
                    break
                samples = array.array("h")
                samples.frombytes(data)
                left.extend(samples[0::2])
                right.extend(samples[1::2])
        return list(left), list(right)

    def test_each_side_lands_on_its_own_channel(self):
        sources = self.wire(FakeSource([mono_chunk(16384) for _ in range(8)]),
                            FakeSource([mono_chunk(8192) for _ in range(8)]))
        self.recorder.start(self.path, "Mic", "Loop")
        self.assertTrue(self.recorder.active)
        self.assertTrue(self.wait_for(
            lambda: self.recorder._frames >= 8 * audio.CHUNK_FRAMES))
        self.recorder.stop()
        self.assertEqual(len(self.events["stopped"]), 1)
        path, duration = self.events["stopped"][0]
        self.assertEqual(path, self.path)
        self.assertAlmostEqual(duration, 8 * audio.CHUNK_FRAMES / audio.RATE,
                               places=2)
        self.assertTrue(sources[0].closed and sources[1].closed)
        left, right = self.frames_of(self.path)
        self.assertEqual(left[:4], [16384] * 4)
        self.assertEqual(right[:4], [8192] * 4)
        self.assertEqual(left[-1], 16384)
        self.assertEqual(right[-1], 8192)

    def test_levels_carry_both_sides(self):
        self.wire(FakeSource([mono_chunk(16384) for _ in range(4)]),
                  FakeSource([mono_chunk(8192) for _ in range(4)]))
        self.recorder.start(self.path, "Mic", "Loop")
        self.assertTrue(self.wait_for(lambda: len(self.events["levels"]) >= 1))
        self.recorder.stop()
        mine, theirs = self.events["levels"][0]
        self.assertAlmostEqual(mine, 0.5, places=2)
        self.assertAlmostEqual(theirs, 0.25, places=2)

    def test_a_silent_loopback_pads_zeros_and_keeps_recording(self):
        """No app is playing: the far side is silence, not a stalled file."""
        sources = self.wire(FakeSource([mono_chunk(16384) for _ in range(8)]),
                            FakeSource([]))
        self.recorder.start(self.path, "Mic", "Loop")
        self.assertTrue(self.wait_for(
            lambda: self.recorder._frames >= 8 * audio.CHUNK_FRAMES,
            timeout=10.0),
            "the microphone must keep writing while the loopback is quiet")
        self.recorder.stop()
        self.assertEqual(self.events["failed"], [])
        self.assertEqual(len(self.events["stopped"]), 1)
        left, right = self.frames_of(self.path)
        self.assertTrue(any(v != 0 for v in left))
        self.assertEqual(set(right), {0})
        self.assertTrue(sources[0].closed and sources[1].closed)

    def test_a_device_that_dies_ends_the_run(self):
        self.wire(FakeSource([mono_chunk(16384) for _ in range(2)]),
                  FakeSource([], error=wasapi.WasapiError("device invalidated")))
        self.recorder.start(self.path, "Mic", "Loop")
        self.assertTrue(self.wait_for(lambda: bool(self.events["died"])))
        self.assertFalse(self.events["stopped"])

    def test_nothing_recorded_at_all_fails(self):
        self.wire(FakeSource([]), FakeSource([]))
        self.recorder.start(self.path, "Mic", "Loop")
        self.recorder.stop()
        self.assertEqual(len(self.events["failed"]), 1)
        self.assertFalse(os.path.exists(self.path))

    def test_an_unwritable_recording_reports_failure(self):
        self.wire(FakeSource([]), FakeSource([]))
        with mock.patch.object(audio.MeetingRecorder, "_open_wav",
                               side_effect=OSError("disk full")):
            self.recorder.start(self.path, "Mic", "Loop")
        self.assertEqual(len(self.events["failed"]), 1)
        self.assertIn("disk full", self.events["failed"][0])
        self.assertFalse(self.recorder.active)

    def test_max_seconds_stops_on_its_own(self):
        self.wire(FakeSource([mono_chunk(16384) for _ in range(20)]),
                  FakeSource([mono_chunk(8192) for _ in range(20)]))
        self.recorder.start(self.path, "Mic", "Loop", max_seconds=0.5)
        self.assertTrue(self.wait_for(lambda: not self.recorder.active))
        self.recorder.stop()
        self.assertEqual(len(self.events["stopped"]), 1)
        _, duration = self.events["stopped"][0]
        self.assertAlmostEqual(duration, 0.5, places=1)


class RecorderWasapiFallback(OnWindows, DikteTest):
    """When WASAPI cannot serve both sides, the ffmpeg road still stands."""

    def test_wasapi_failure_falls_back_to_ffmpeg(self):
        self.enterContext(mock.patch.object(
            audio, "_wasapi_sources",
            side_effect=wasapi.WasapiError("no device matching Loop")))
        self.enterContext(mock.patch.object(audio, "_cached_which",
                                            return_value=True))
        frames = stereo(mono_chunk(16384), mono_chunk(8192)) * 8

        class Popen:
            cmd = None

            def __init__(self, cmd, **kwargs):
                Popen.cmd = cmd
                self.stdout = io.BytesIO(frames)
                self.stderr = io.BytesIO(b"")
                self.returncode = 0
                self._alive = True

            def poll(self):
                return None if self._alive else 0

            def terminate(self):
                self._alive = False

            def kill(self):
                self._alive = False

            def wait(self, timeout=None):
                self._alive = False
                return 0

        self.enterContext(mock.patch.object(audio.subprocess, "Popen", Popen))
        recorder = audio.MeetingRecorder()
        stopped = []
        recorder.stopped.connect(lambda p, d: stopped.append((p, d)))
        path = os.path.join(self.root, "meet.wav")
        recorder.start(path, "Mic X", "Loop Y")
        recorder.stop()
        self.assertEqual(len(stopped), 1)
        cmd = Popen.cmd
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("audio=Mic X", cmd)
        self.assertIn("audio=Loop Y", cmd)


class DeviceNameMatching(unittest.TestCase):
    """How a stored device name finds its endpoint."""

    ENDPOINTS = [("Hoparlör (USB PnP Audio Device)", "id-usb"),
                 ("Mikrofon (Realtek Audio)", "id-realtek")]

    def test_an_empty_name_means_the_default(self):
        self.assertEqual(wasapi._pick("", self.ENDPOINTS, "id-default"),
                         "id-default")

    def test_matching_is_a_case_blind_substring(self):
        self.assertEqual(
            wasapi._pick("usb pnp audio", self.ENDPOINTS, "id-default"),
            "id-usb")

    def test_a_stored_name_may_be_shorter_or_longer(self):
        self.assertEqual(wasapi._pick("Realtek", self.ENDPOINTS, "x"),
                         "id-realtek")

    def test_no_match_raises(self):
        with self.assertRaises(wasapi.WasapiError):
            wasapi._pick("Sound Blaster", self.ENDPOINTS, "id-default")


class DictationWasapi(OnWindows, DikteTest):
    """Dictation records through WASAPI too: the default endpoint, not the
    first device enumeration lists."""

    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.recorder = audio.Recorder()
        self.events = {"level": [], "stopped": [], "failed": []}
        self.recorder.level.connect(lambda v: self.events["level"].append(v))
        self.recorder.stopped.connect(
            lambda p, d, r: self.events["stopped"].append((p, d)))
        self.recorder.failed.connect(lambda e: self.events["failed"].append(e))

    def wait_for(self, condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    def test_the_default_microphone_is_recorded_and_written_out(self):
        source = FakeSource([mono_chunk(16384) for _ in range(6)])
        self.enterContext(mock.patch.object(audio, "_dictation_source",
                                            return_value=source))
        path = os.path.join(self.root, "dictation.wav")
        self.recorder.start("", max_seconds=60)
        self.assertTrue(self.recorder.active)
        self.assertTrue(self.wait_for(lambda: len(self.events["level"]) >= 1))
        self.recorder.stop()
        self.assertEqual(self.events["failed"], [])
        self.assertEqual(len(self.events["stopped"]), 1)
        got_path, duration = self.events["stopped"][0]
        self.assertTrue(os.path.exists(got_path))
        self.assertGreater(duration, 0.2)
        self.assertTrue(source.closed)
        self.assertFalse(self.recorder.active)
        os.unlink(got_path)

    def test_pause_closes_and_resume_reopens_the_microphone(self):
        first, second = FakeSource([mono_chunk(16384) for _ in range(3)]), \
            FakeSource([mono_chunk(16384) for _ in range(3)])
        self.enterContext(mock.patch.object(
            audio, "_dictation_source", side_effect=[first, second]))
        path = os.path.join(self.root, "dictation.wav")
        self.recorder.start("")
        self.assertTrue(self.wait_for(lambda: self.recorder._buffer))
        self.assertTrue(self.recorder.pause())
        self.assertTrue(first.closed)
        self.assertTrue(self.recorder.paused)
        self.assertTrue(self.recorder.resume())
        self.assertTrue(self.wait_for(lambda: self.recorder._source is second))
        self.recorder.stop()
        self.assertEqual(self.events["failed"], [])
        self.assertEqual(len(self.events["stopped"]), 1)
        os.unlink(self.events["stopped"][0][0])

    def test_a_wasapi_failure_still_offers_the_ffmpeg_road(self):
        self.enterContext(mock.patch.object(
            audio, "_dictation_source",
            side_effect=wasapi.WasapiError("no default endpoint")))
        self.enterContext(mock.patch.object(audio, "recording_command",
                                            return_value=["ffmpeg", "fake"]))
        frames = pcm([16384] * audio.CHUNK_FRAMES) * 8

        class Popen:
            def __init__(self, cmd, **kwargs):
                self.stdout = io.BytesIO(frames)
                self.stderr = io.BytesIO(b"")
                self.returncode = 0
                self._alive = True

            def poll(self):
                return None if self._alive else 0

            def terminate(self):
                self._alive = False

            def kill(self):
                self._alive = False

            def wait(self, timeout=None):
                self._alive = False
                return 0

        self.enterContext(mock.patch.object(audio.subprocess, "Popen", Popen))
        path = os.path.join(self.root, "dictation.wav")
        self.recorder.start("")
        self.recorder.stop()
        self.assertEqual(len(self.events["stopped"]), 1)
        os.unlink(self.events["stopped"][0][0])

    def test_a_stale_device_name_falls_back_to_the_default(self):
        default = FakeSource([])
        with mock.patch.object(
                audio.wasapi, "open_capture",
                side_effect=[wasapi.WasapiError("no match"), default]) as open_:
            got = audio._dictation_source("Old Virtual Mic")
        self.assertIs(got, default)
        self.assertEqual(open_.call_args_list,
                         [mock.call("Old Virtual Mic"), mock.call("")])

    def test_an_empty_name_that_fails_raises(self):
        with mock.patch.object(
                audio.wasapi, "open_capture",
                side_effect=wasapi.WasapiError("no default endpoint")):
            with self.assertRaises(wasapi.WasapiError):
                audio._dictation_source("")

    def test_meeting_sources_fall_back_per_side(self):
        mic, loop = FakeSource([]), FakeSource([])
        with mock.patch.object(
                audio.wasapi, "open_capture",
                side_effect=[wasapi.WasapiError("stale"), mic]), \
                mock.patch.object(audio.wasapi, "open_loopback",
                                  return_value=loop):
            got_mic, got_loop = audio._wasapi_sources("Stale Mic", "")
        self.assertIs(got_mic, mic)
        self.assertIs(got_loop, loop)


class DeviceLists(OnWindows, DikteTest):
    """Windows offers real endpoints when WASAPI can, dshow when it can't."""

    def test_wasapi_endpoints_are_preferred(self):
        self.enterContext(mock.patch.object(audio.wasapi, "available",
                                            return_value=True))
        self.enterContext(mock.patch.object(
            audio.wasapi, "render_outputs",
            return_value=[("Hoparlör (USB)", "id-1"), ("Kulaklık", "id-2")]))
        self.enterContext(mock.patch.object(
            audio.wasapi, "capture_inputs",
            return_value=[("Mikrofon (USB)", "id-3")]))
        self.enterContext(mock.patch.object(
            audio.wasapi, "default_render_name", return_value="Kulaklık"))
        self.assertEqual([n for n, _ in audio.cached_list_monitors()],
                         ["Hoparlör (USB)", "Kulaklık"])
        self.assertEqual([n for n, _ in audio.cached_list_sources()],
                         ["Mikrofon (USB)"])
        self.assertEqual(audio.default_monitor(), "Kulaklık")

    def test_dshow_remains_the_fallback(self):
        self.enterContext(mock.patch.object(audio.wasapi, "available",
                                            return_value=False))
        dshow_out = [("Stereo Mix (Realtek Audio)", "Stereo Mix (Realtek Audio)")]
        dshow_in = [("Stereo Mix (Realtek Audio)", "Stereo Mix (Realtek Audio)")]
        self.enterContext(mock.patch.object(audio, "_dshow_outputs",
                                            return_value=dshow_out))
        self.enterContext(mock.patch.object(audio, "_dshow_inputs",
                                            return_value=dshow_in))
        self.enterContext(mock.patch.object(
            audio, "_dshow_default_output",
            return_value="Stereo Mix (Realtek Audio)"))
        self.assertEqual(audio._win_outputs(), dshow_out)
        self.assertEqual(audio._win_inputs(), dshow_in)
        self.assertEqual(audio.default_monitor(),
                         "Stereo Mix (Realtek Audio)")


if __name__ == "__main__":
    unittest.main()
