"""Loss-prevention contracts at the capture-to-derived-work boundary."""

import os
from unittest import mock

import api
import config as cfg
import paste
import voice_jobs
import worker
from tests.support import DikteTest, make_wav, speech
from tests.test_cleanup import gateway


class PersistentCaptureFailure(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(providers=[gateway()], cleanup_provider="user/abc123")
        self.conf["skip_silent"] = False
        self.wav = make_wav(self.path("only-copy.wav"), speech(0.5))

    def test_copy_failure_stops_before_transcription_and_never_indexes_temp_audio(self):
        pipeline = worker.Pipeline(self.conf)
        failures = []
        pipeline.failed.connect(failures.append)

        with mock.patch.object(worker, "_persistent_audio_copy", return_value=""), \
             mock.patch.object(api, "transcribe", return_value="ignored") as transcribe, \
             mock.patch.object(worker.cleanup, "run", return_value="ignored"), \
             mock.patch.object(paste, "copy"):
            pipeline._work(self.wav, 0.5, (), False, None)

        # A temp-file path is not a capture checkpoint. Once persistence has
        # failed, downstream model calls are forbidden and the failure is
        # explicit rather than being represented as a retryable job whose only
        # source is about to be discarded.
        transcribe.assert_not_called()
        self.assertEqual(voice_jobs.read_voice_jobs(), [])
        self.assertEqual(failures, ["Could not preserve recording safely"])


class DurableCompletion(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(providers=[gateway()], cleanup_provider="user/abc123")
        self.conf["skip_silent"] = False
        self.wav = make_wav(self.path("clip.wav"), speech(0.5))

    def test_completion_write_failure_never_emits_success_or_claims_completed(self):
        pipeline = worker.Pipeline(self.conf)
        done, failures = [], []
        pipeline.finished.connect(lambda *args: done.append(args))
        pipeline.failed.connect(failures.append)
        real_update = voice_jobs.update_voice_job

        def fail_only_completed(job_id, **changes):
            if changes.get("status") == voice_jobs.STATUS_COMPLETED:
                raise OSError("disk full")
            return real_update(job_id, **changes)

        with mock.patch.object(api, "transcribe", return_value="hello"), \
             mock.patch.object(api, "cleanup", return_value="Hello."), \
             mock.patch.object(paste, "copy"), \
             mock.patch.object(paste, "press"), \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda _seconds: None), \
             mock.patch.object(voice_jobs, "update_voice_job", side_effect=fail_only_completed):
            pipeline._work(self.wav, 0.5, (), False, None)

        job = voice_jobs.read_voice_jobs()[0]
        self.assertEqual(done, [])
        self.assertEqual(failures, ["disk full"])
        self.assertNotEqual(job["status"], voice_jobs.STATUS_COMPLETED)
        self.assertEqual(job["raw_transcript"], "hello")
        self.assertTrue(os.path.exists(job["audio_path"]))


class AgentRetryConfirmation(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(assistant_provider="claude")
        self.wav = make_wav(self.path("spoken-command.wav"), speech(0.5))
        voice_jobs.save_voice_job({
            "id": "agent-unknown-outcome",
            "kind": voice_jobs.KIND_AGENT,
            "status": voice_jobs.STATUS_FAILED_RETRYABLE,
            "audio_path": self.wav,
            "raw_transcript": "send the invoice",
            "error_stage": "agent",
            "agent_outcome": "unknown",
        })

    def test_unknown_cli_agent_outcome_requires_confirm_before_resending(self):
        pipeline = worker.Pipeline(self.conf)
        with mock.patch.object(worker.threading, "Thread") as thread:
            started = pipeline.retry_from_job("agent-unknown-outcome")

        self.assertFalse(started)
        thread.assert_not_called()
        job = voice_jobs.get_voice_job("agent-unknown-outcome")
        self.assertTrue(job["retry_requires_confirmation"])

    def test_confirmed_unknown_cli_agent_retry_can_be_scheduled(self):
        pipeline = worker.Pipeline(self.conf)
        with mock.patch.object(worker.threading, "Thread") as thread:
            started = pipeline.retry_from_job("agent-unknown-outcome",
                                              confirm_agent=True)

        self.assertTrue(started)
        thread.assert_called_once()


class RetryDeliveryIdempotency(DikteTest):
    def setUp(self):
        super().setUp()
        self.conf = self.config(providers=[gateway()], cleanup_provider="user/abc123")
        self.wav = make_wav(self.path("delivered.wav"), speech(0.5))
        voice_jobs.save_voice_job({
            "id": "already-delivered",
            "kind": voice_jobs.KIND_DICTATION,
            "status": voice_jobs.STATUS_FAILED_RETRYABLE,
            "audio_path": self.wav,
            "raw_transcript": "hello",
            "result_text": "Hello.",
            "delivery_state": "delivered",
            "error_stage": "persistence",
        })
        cfg.append_history({
            "ts": "2026-08-30 10:00:00",
            "voice_job_id": "already-delivered",
            "raw": "hello",
            "text": "Hello.",
        })

    def test_retry_after_delivery_does_not_paste_or_duplicate_history(self):
        pipeline = worker.Pipeline(self.conf)
        with mock.patch.object(worker.cleanup, "run", return_value="Hello.") as cleanup_run, \
             mock.patch.object(paste, "copy") as copy, \
             mock.patch.object(paste, "press") as press, \
             mock.patch.object(paste, "read_clipboard", return_value=None), \
             mock.patch.object(worker.time, "sleep", lambda _seconds: None):
            pipeline._retry_work("already-delivered")

        cleanup_run.assert_not_called()
        copy.assert_not_called()
        press.assert_not_called()
        self.assertEqual(len(cfg.read_history()), 1)
        self.assertEqual(
            voice_jobs.get_voice_job("already-delivered")["status"],
            voice_jobs.STATUS_COMPLETED,
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
