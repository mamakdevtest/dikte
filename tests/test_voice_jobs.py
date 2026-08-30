"""Voice job durability, retry checkpoints, and audio preservation."""

import json
import os
import unittest
from unittest import mock

import api
import assistant
import config as cfg
import paste
import voice_jobs
import worker
from tests.support import DikteTest, make_wav, speech
from tests.test_cleanup import gateway


class Crud(DikteTest):
    def test_save_and_read(self):
        row = voice_jobs.save_voice_job({"kind": "dictation", "audio_path": "/tmp/a.wav"})
        self.assertTrue(row["id"])
        self.assertEqual(row["status"], "captured")
        self.assertEqual(len(voice_jobs.read_voice_jobs()), 1)

    def test_save_replaces_same_id(self):
        row = voice_jobs.save_voice_job({"id": "abc123", "kind": "dictation", "status": "captured"})
        voice_jobs.save_voice_job({"id": "abc123", "kind": "dictation", "status": "transcribed", "raw_transcript": "hi"})
        rows = voice_jobs.read_voice_jobs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "transcribed")

    def test_update_patches(self):
        voice_jobs.save_voice_job({"id": "u1", "status": "captured"})
        updated = voice_jobs.update_voice_job("u1", status="transcribed", raw_transcript="hello")
        self.assertEqual(updated["status"], "transcribed")
        self.assertEqual(voice_jobs.get_voice_job("u1")["raw_transcript"], "hello")

    def test_update_missing_returns_none(self):
        self.assertIsNone(voice_jobs.update_voice_job("nope", status="transcribed"))

    def test_delete(self):
        voice_jobs.save_voice_job({"id": "d1", "status": "captured"})
        voice_jobs.save_voice_job({"id": "d2", "status": "captured"})
        self.assertTrue(voice_jobs.delete_voice_job("d1"))
        self.assertEqual([r["id"] for r in voice_jobs.read_voice_jobs()], ["d2"])
        self.assertFalse(voice_jobs.delete_voice_job("d1"))

    def test_get_missing(self):
        self.assertIsNone(voice_jobs.get_voice_job("missing"))

    def test_migration_empty_file(self):
        # fresh sandbox has no file
        self.assertEqual(voice_jobs.read_voice_jobs(), [])

    def test_broken_lines_skipped(self):
        cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (cfg.DATA_DIR / "voice_jobs.jsonl").write_text(
            json.dumps({"id": "good", "status": "captured"}) + "\n"
            + "{bad json\n"
            + json.dumps({"status": "no id"}) + "\n",
            encoding="utf-8",
        )
        rows = voice_jobs.read_voice_jobs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "good")

    def test_kind_defaults_to_dictation(self):
        row = voice_jobs.save_voice_job({"id": "k1", "kind": "unknown"})
        self.assertEqual(row["kind"], "dictation")

    def test_status_constants(self):
        self.assertEqual(voice_jobs.STATUS_CAPTURED, "captured")
        self.assertEqual(voice_jobs.STATUS_TRANSCRIBED, "transcribed")
        self.assertEqual(voice_jobs.STATUS_PROCESSED, "processed")
        self.assertEqual(voice_jobs.STATUS_COMPLETED, "completed")
        self.assertEqual(voice_jobs.STATUS_FAILED_RETRYABLE, "failed_retryable")


class StatusTransitions(DikteTest):
    def test_captured_to_transcribed_to_completed(self):
        row = voice_jobs.save_voice_job({"id": "s1", "status": "captured", "audio_path": "/tmp/a.wav"})
        self.assertEqual(row["status"], "captured")
        voice_jobs.update_voice_job("s1", status="transcribed", raw_transcript="hello")
        voice_jobs.update_voice_job("s1", status="processed")
        voice_jobs.update_voice_job("s1", status="completed")
        self.assertEqual(voice_jobs.get_voice_job("s1")["status"], "completed")

    def test_failed_retryable(self):
        voice_jobs.save_voice_job({"id": "s2", "status": "captured", "audio_path": "/tmp/a.wav"})
        voice_jobs.update_voice_job("s2", status="transcribed", raw_transcript="hi")
        voice_jobs.update_voice_job("s2", status="failed_retryable", error_stage="cleanup", error_message="rate limited")
        job = voice_jobs.get_voice_job("s2")
        self.assertTrue(voice_jobs.is_retryable(job))
        self.assertEqual(job["error_stage"], "cleanup")


class AtomicWrite(DikteTest):
    def test_no_tmp_left_behind(self):
        voice_jobs.save_voice_job({"id": "a1", "status": "captured"})
        voice_jobs.save_voice_job({"id": "a2", "status": "captured"})
        leftovers = list(cfg.DATA_DIR.glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_write_is_atomic_tmp_replace(self):
        # ensure file exists and is valid jsonl after each write
        for i in range(5):
            voice_jobs.save_voice_job({"id": f"aw{i}", "status": "captured"})
        rows = voice_jobs.read_voice_jobs()
        self.assertEqual(len(rows), 5)


class RetryCheckpoint(DikteTest):
    def test_transcript_exists_means_cleanup_retry(self):
        job = {"id": "r1", "status": "failed_retryable", "audio_path": "/tmp/a.wav", "raw_transcript": "hello", "error_stage": "cleanup"}
        self.assertEqual(voice_jobs.retry_checkpoint(job), "cleanup")

    def test_transcribed_means_cleanup(self):
        job = {"status": "transcribed", "audio_path": "/tmp/a.wav", "raw_transcript": "hello"}
        self.assertEqual(voice_jobs.retry_checkpoint(job), "cleanup")

    def test_audio_only_means_transcription(self):
        job = {"status": "captured", "audio_path": "/tmp/a.wav", "raw_transcript": ""}
        self.assertEqual(voice_jobs.retry_checkpoint(job), "transcription")

    def test_audio_only_failed_retryable_transcription(self):
        job = {"status": "failed_retryable", "audio_path": "/tmp/a.wav", "raw_transcript": "", "error_stage": "transcription"}
        self.assertEqual(voice_jobs.retry_checkpoint(job), "transcription")

    def test_completed_has_no_checkpoint(self):
        job = {"status": "completed", "audio_path": "/tmp/a.wav", "raw_transcript": "hi"}
        self.assertIsNone(voice_jobs.retry_checkpoint(job))

    def test_no_artifacts_returns_none(self):
        job = {"status": "captured", "audio_path": "", "raw_transcript": ""}
        self.assertIsNone(voice_jobs.retry_checkpoint(job))

    def test_none_job(self):
        self.assertIsNone(voice_jobs.retry_checkpoint(None))
        self.assertFalse(voice_jobs.is_retryable(None))


class AudioPreservation(DikteTest):
    def test_retryable_always_keeps_audio(self):
        job = {"status": "failed_retryable", "audio_path": "/tmp/a.wav"}
        self.assertTrue(voice_jobs.should_keep_audio(job, keep_audio_setting=False))

    def test_transcribed_checkpoint_keeps_audio(self):
        job = {"status": "transcribed", "audio_path": "/tmp/a.wav", "raw_transcript": "hi"}
        self.assertTrue(voice_jobs.should_keep_audio(job, keep_audio_setting=False))

    def test_captured_with_audio_keeps(self):
        job = {"status": "captured", "audio_path": "/tmp/a.wav"}
        self.assertTrue(voice_jobs.should_keep_audio(job, keep_audio_setting=False))

    def test_completed_without_checkpoint_respects_setting(self):
        job = {"status": "completed", "audio_path": "", "raw_transcript": ""}
        self.assertFalse(voice_jobs.should_keep_audio(job, keep_audio_setting=False))
        self.assertTrue(voice_jobs.should_keep_audio(job, keep_audio_setting=True))

    def test_is_retryable_only_failed_retryable(self):
        self.assertTrue(voice_jobs.is_retryable({"status": "failed_retryable"}))
        self.assertFalse(voice_jobs.is_retryable({"status": "captured"}))
        self.assertFalse(voice_jobs.is_retryable({"status": "transcribed"}))


class WorkerDurableCheckpoints(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(providers=[gateway()], cleanup_provider="user/abc123")
        self.wav = make_wav(self.path("clip.wav"), speech(1.0))
        # Silence check is relative: speech must rise above noise floor, so need mixed RMS
        self.rms = [0.0005] * 10 + [0.2] * 20

    def test_capture_creates_voice_job_with_persistent_audio(self):
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe", return_value="hello"), \
             mock.patch.object(api, "cleanup", return_value="Hello."), \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda s: None):
            pipe._work(self.wav, 1.0, self.rms, False, None)
        jobs = voice_jobs.read_voice_jobs()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["raw_transcript"], "hello")
        # durable audio_path points to recordings dir
        self.assertIn("recordings", job["audio_path"])

    def test_transcription_failure_marks_retryable_and_keeps_audio(self):
        pipe = worker.Pipeline(self.conf)
        # keep temp wav path to check durable copy survives
        with mock.patch.object(api, "transcribe", side_effect=api.ApiError("no credit")), \
             mock.patch.object(paste, "copy"):
            pipe._work(self.wav, 1.0, self.rms, False, None)
        jobs = voice_jobs.read_voice_jobs()
        self.assertEqual(len(jobs), 1)
        job = jobs[0]
        self.assertEqual(job["status"], "failed_retryable")
        self.assertEqual(job["error_stage"], "transcription")
        self.assertTrue(os.path.exists(job["audio_path"]))

    def test_cleanup_failure_marks_retryable_and_keeps_audio(self):
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe", return_value="hello"), \
             mock.patch.object(api, "cleanup", side_effect=api.ApiError("rate limited")), \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda s: None):
            pipe._work(self.wav, 1.0, self.rms, False, None)
        job = voice_jobs.read_voice_jobs()[0]
        self.assertEqual(job["status"], "failed_retryable")
        self.assertEqual(job["error_stage"], "cleanup")
        self.assertTrue(os.path.exists(job["audio_path"]))

    def test_retry_cleanup_only_does_not_retranscribe(self):
        # create a job that failed at cleanup
        wav_copy = make_wav(self.path("persist.wav"), speech(0.5))
        job = voice_jobs.save_voice_job({
            "id": "retry1",
            "kind": "dictation",
            "status": "failed_retryable",
            "audio_path": wav_copy,
            "raw_transcript": "hello world",
            "error_stage": "cleanup",
            "provider": "openai",
            "model": "whisper-1",
            "duration": 1.0,
        })
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe") as tr, \
             mock.patch.object(api, "cleanup", return_value="Hello world.") as cl, \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda s: None):
            ok = pipe.retry_from_job("retry1")
            self.assertTrue(ok)
            # wait for thread
            pipe._thread.join(timeout=5)
            tr.assert_not_called()
            cl.assert_called_once()
        job2 = voice_jobs.get_voice_job("retry1")
        self.assertEqual(job2["status"], "completed")

    def test_retry_transcription_from_audio(self):
        wav_copy = make_wav(self.path("persist2.wav"), speech(0.5))
        voice_jobs.save_voice_job({
            "id": "retry2",
            "kind": "dictation",
            "status": "failed_retryable",
            "audio_path": wav_copy,
            "raw_transcript": "",
            "error_stage": "transcription",
            "provider": "openai",
            "model": "whisper-1",
            "duration": 1.0,
        })
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe", return_value="hi there") as tr, \
             mock.patch.object(api, "cleanup", return_value="Hi there.") , \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda s: None):
            ok = pipe.retry_from_job("retry2")
            self.assertTrue(ok)
            pipe._thread.join(timeout=5)
            tr.assert_called_once()
        job2 = voice_jobs.get_voice_job("retry2")
        self.assertEqual(job2["status"], "completed")
        self.assertEqual(job2["raw_transcript"], "hi there")

    def test_retry_busy_returns_false(self):
        pipe = worker.Pipeline(self.conf)
        pipe._thread = mock.Mock(is_alive=lambda: True)
        voice_jobs.save_voice_job({"id": "busy1", "status": "failed_retryable", "audio_path": "/tmp/a.wav", "raw_transcript": "hi", "error_stage": "cleanup"})
        self.assertFalse(pipe.retry_from_job("busy1"))

    def test_retry_missing_job_returns_false(self):
        pipe = worker.Pipeline(self.conf)
        self.assertFalse(pipe.retry_from_job("nope"))

    def test_retry_completed_returns_false(self):
        voice_jobs.save_voice_job({"id": "done1", "status": "completed", "audio_path": "/tmp/a.wav", "raw_transcript": "hi"})
        pipe = worker.Pipeline(self.conf)
        self.assertFalse(pipe.retry_from_job("done1"))

    def test_failed_processing_keeps_audio_regardless_of_setting(self):
        self.conf["keep_audio"] = False
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe", side_effect=api.ApiError("boom")), \
             mock.patch.object(paste, "copy"):
            pipe._work(self.wav, 1.0, self.rms, False, None)
        job = voice_jobs.read_voice_jobs()[0]
        # durable file must still exist even though keep_audio is False
        self.assertTrue(os.path.exists(job["audio_path"]))

    def test_successful_processing_retains_durable_audio(self):
        self.conf["keep_audio"] = False
        pipe = worker.Pipeline(self.conf)
        with mock.patch.object(api, "transcribe", return_value="hello"), \
             mock.patch.object(api, "cleanup", return_value="Hello."), \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda s: None):
            pipe._work(self.wav, 1.0, self.rms, False, None)
        job = voice_jobs.read_voice_jobs()[0]
        # Per new policy durable audio is retained even on success (pruning by age, not per-run delete)
        self.assertTrue(os.path.exists(job["audio_path"]))


if __name__ == "__main__":
    unittest.main()
