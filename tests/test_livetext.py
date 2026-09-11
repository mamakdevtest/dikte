"""The rolling live preview: feed bytes, hear words back, stay quiet on failure."""

import io
import os
import threading
import time
import unittest
from unittest import mock

from PyQt6.QtWidgets import QApplication

import api
import livetext
from tests.support import DikteTest, pcm


class LiveTranscriber(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])
        self.transcriber = livetext.LiveTranscriber(self.config())
        self.parts = []
        self.transcriber.partial.connect(self.parts.append)
        self.enterContext(mock.patch.object(livetext, "INTERVAL_SECONDS", 0.02))

    def wait_for(self, condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # partial() rides a queued connection from the probe thread
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    def test_fed_audio_comes_back_as_words(self):
        with mock.patch.object(api, "transcribe", return_value="merhaba dünya"):
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            self.assertTrue(self.wait_for(lambda: any(self.parts)))
        self.transcriber.stop()
        self.assertEqual(self.parts[-1], "merhaba dünya")

    def test_probes_append_without_losing_the_older_words(self):
        answers = iter(["bir", "iki"])
        with mock.patch.object(api, "transcribe",
                               side_effect=lambda *a, **k: next(answers)):
            self.transcriber.begin()
            for _seen in (1, 2):
                self.transcriber.feed(pcm([100] * livetext.RATE * 5))
                self.assertTrue(self.wait_for(
                    lambda: len([p for p in self.parts if p]) >= _seen))
                self.transcriber.feed(pcm([100] * livetext.RATE * 5))
                self.assertTrue(self.wait_for(
                    lambda: len([p for p in self.parts if p]) >= 2))
        self.transcriber.stop()
        self.assertEqual([p for p in self.parts if p], ["bir", "bir iki"])

    def test_a_failing_probe_stays_quiet(self):
        with mock.patch.object(api, "transcribe",
                               side_effect=api.ApiError("network down")):
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            time.sleep(0.15)
        self.transcriber.stop()
        self.assertEqual([p for p in self.parts if p], [])

    def test_too_little_audio_is_carried_not_dropped(self):
        with mock.patch.object(api, "transcribe", return_value="kelime") as call:
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * 100))  # far below one second
            time.sleep(0.15)
        self.transcriber.stop()
        call.assert_not_called()
        self.assertEqual([p for p in self.parts if p], [])

    def test_bytes_fed_without_a_session_are_not_stockpiled(self):
        self.transcriber.feed(pcm([100] * livetext.RATE * 30))
        self.assertEqual(self.transcriber._pending, bytearray())
        self.transcriber.begin()
        self.transcriber.feed(pcm([100] * 100))
        self.assertGreater(len(self.transcriber._pending), 0)
        self.transcriber.stop()

    def test_begin_clears_and_end_forgets(self):
        self.transcriber.feed(b"\x00\x00")
        self.transcriber.begin()
        with mock.patch.object(api, "transcribe", return_value="x"):
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            self.assertTrue(self.wait_for(lambda: any(self.parts)))
        # The pipeline reads this before end(): afterwards there is nothing
        # left to read, and each recording starts from a clean sheet.
        self.assertEqual(self.transcriber.heard(), "x")
        self.transcriber.end()
        self.assertEqual(self.transcriber._pending, bytearray())
        self.assertEqual(self.transcriber._text, "")
        self.assertEqual(self.transcriber.heard(), "")
        self.transcriber.stop()


    def test_an_answer_that_lands_after_the_recording_ended_is_not_heard(self):
        """A probe that answers late belongs to the recording that is over."""
        started, released, calls = threading.Event(), threading.Event(), []
        answers = iter(["eski kayıt", "yeni kayıt"])

        def probe(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                started.set()
                released.wait(timeout=5)
            return next(answers, "yeni kayıt")

        with mock.patch.object(api, "transcribe", side_effect=probe):
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            self.assertTrue(self.wait_for(started.is_set))
            self.transcriber.end()     # the pipeline has taken the recording
            self.transcriber.begin()   # and the next one is under way
            released.set()             # the old answer lands now
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            # The second answer arriving proves the first was taken and judged
            # stale rather than kept as this recording's words.
            self.assertTrue(self.wait_for(
                lambda: self.transcriber.heard() == "yeni kayıt"))
        self.transcriber.stop()
        self.assertEqual([p for p in self.parts if p], ["yeni kayıt"])

    def test_a_tail_too_small_to_hear_is_not_carried_into_the_next_recording(self):
        seen = []

        def remember(_target, path, **_kwargs):
            seen.append(os.path.getsize(path))
            return "yeni kayıt"

        with mock.patch.object(api, "transcribe", side_effect=remember):
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * 100))   # below one probe's worth
            self.transcriber.end()
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            self.assertTrue(self.wait_for(
                lambda: self.transcriber.heard() == "yeni kayıt"))
        self.transcriber.stop()
        # The new recording's audio alone: the last one's fragment was dropped.
        self.assertEqual(seen[0], 44 + livetext.RATE * 5 * 2)

    def test_a_stock_phrase_never_becomes_evidence_of_speech(self):
        """A hallucinated line must not vouch for a recording the silence
        check has already called room tone — at any window length, since the
        windows the preview probes are longer than the discard cap."""
        started = threading.Event()
        answers = iter(["Altyazı M.K.", "kayıt başladı"])

        def probe(*_args, **_kwargs):
            started.set()
            return next(answers, "kayıt başladı")

        with mock.patch.object(api, "transcribe", side_effect=probe):
            self.transcriber.begin()
            self.transcriber.feed(pcm([100] * livetext.RATE * 7))
            self.assertTrue(self.wait_for(started.is_set))
            self.transcriber.feed(pcm([100] * livetext.RATE * 5))
            self.assertTrue(self.wait_for(
                lambda: self.transcriber.heard() == "kayıt başladı"))
        self.transcriber.stop()
        self.assertEqual([p for p in self.parts if p], ["kayıt başladı"])


class Probe(unittest.TestCase):
    def test_the_probe_writes_a_wav_and_takes_it_away(self):
        transcriber = livetext.LiveTranscriber(mock.Mock())
        transcriber._conf.transcribe_target = lambda: "local"
        transcriber._language = "tr"
        transcriber._prompt = "sözlük"
        written = {}

        def fake_transcribe(target, path, language="", prompt="", timeout=300,
                            aborter=None):
            written.update(path=path, language=language, prompt=prompt)
            import wave
            with wave.open(path, "rb") as wav:
                written.update(rate=wav.getframerate(),
                               channels=wav.getnchannels())
            return "  duyuldum \n"

        tempdir = None
        with mock.patch.object(api, "transcribe", side_effect=fake_transcribe):
            text = livetext.LiveTranscriber._probe(transcriber, pcm([500] * 100))
        self.assertEqual(text, "duyuldum")
        self.assertEqual(written["language"], "tr")
        self.assertEqual(written["prompt"], "sözlük")
        self.assertEqual(written["rate"], livetext.RATE)
        self.assertEqual(written["channels"], 1)
        self.assertFalse(os.path.exists(written["path"]))
        del tempdir


if __name__ == "__main__":
    unittest.main()
