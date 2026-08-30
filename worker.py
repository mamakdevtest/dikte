"""The dictation chain: transcribe → clean up → clipboard → paste.

The same chain also carries the other thing a dictation can be. Asked to, it
hands the transcript to Claude Code instead of pasting it, and pastes back
whatever came of it: an answer to a question, or a sentence saying what was
done.
"""

import os
import pathlib
import shutil
import sys
import threading
import time
import traceback
import uuid

from PyQt6.QtCore import QObject, pyqtSignal

import api
import assistant
import audio
import cleanup
import config as cfg
import i18n
import paste
import vad
import voice_jobs
from i18n import t

CHUNK_SECONDS = audio.CHUNK_FRAMES / audio.RATE

# A dictation and a command to the agent run side by side and can finish at the
# same moment. Pasting is not one step but three that must not interleave: read
# what is on the clipboard, put ours there, press the key. Two runs doing that
# at once would paste one answer and restore the other's clipboard over it.
_paste_lock = threading.Lock()


def _persistent_audio_copy(wav_path, job_id=""):
    """Copy wav to DATA_DIR/recordings/<job_id>.wav and return that path (or '').

    Durable before claiming checkpoint: caller persists job after this succeeds.
    """
    try:
        cfg.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        base = job_id or time.strftime("%Y%m%d-%H%M%S")
        dst = cfg.RECORDINGS_DIR / f"{base}.wav"
        # avoid collision
        if dst.exists():
            dst = cfg.RECORDINGS_DIR / f"{base}-{uuid.uuid4().hex[:6]}.wav"
        shutil.copy2(wav_path, str(dst))
        return str(dst)
    except OSError:
        return ""


def _should_keep_audio_for_job(job, conf):
    """Audio preservation rule: retryable ALWAYS keeps audio regardless of setting."""
    if job is None:
        # No job means nothing durable to keep; fall back to setting.
        return bool(conf.get("keep_audio", False))
    # voice_jobs helpers already encode retryable override
    return voice_jobs.should_keep_audio(job, bool(conf.get("keep_audio", False)))


class Pipeline(QObject):
    stage = pyqtSignal(str)          # human-readable progress line
    finished = pyqtSignal(str, str, str)  # raw transcript, final text, warning
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    partialTranscript = pyqtSignal(str)  # live interim transcript (if provider supports streaming)

    def __init__(self, conf, parent=None):
        super().__init__(parent)
        self.conf = conf
        self._thread = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()  # not paused

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return not self._pause.is_set()

    def pause(self):
        self._pause.clear()

    def resume(self):
        self._pause.set()

    def _wait_if_paused(self):
        while not self._pause.is_set() and not self._stop.is_set():
            time.sleep(0.15)

    def run(self, wav_path, duration, rms_values=(), ask=False, paste=None):
        """`paste` overrides the setting for this one run, which is what a
        dictation asked for from a terminal wants: the text comes back down the
        socket, and pasting it into whatever had focus is nobody's intention."""
        if self.busy:
            return
        self._stop.clear()
        self._pause.set()
        self._thread = threading.Thread(
            target=self._work,
            args=(wav_path, duration, list(rms_values), ask, paste),
            daemon=True,
        )
        self._thread.start()

    def retry_from_job(self, job_id):
        """Retry a failed/retryable voice job from its durable checkpoint.

        - If raw transcript exists but cleanup failed → retry cleanup only from
          stored raw (NOT re-transcribe).
        - If transcription failed but audio exists → retry transcription from
          stored audio.
        - Uses stored checkpoint, does not redo successful stages.
        - Returns True if a retry was scheduled, False otherwise.
        """
        if self.busy:
            return False
        job = voice_jobs.get_voice_job(job_id)
        if job is None:
            return False
        cp = voice_jobs.retry_checkpoint(job)
        if cp is None:
            return False
        # Don't retry completed jobs
        if job.get("status") == voice_jobs.STATUS_COMPLETED:
            return False
        self._stop.clear()
        self._pause.set()
        # Increment retry count durably before work
        try:
            cur = int(job.get("retry_count") or 0)
        except Exception:
            cur = 0
        voice_jobs.update_voice_job(job_id, retry_count=cur + 1)
        self._thread = threading.Thread(
            target=self._retry_work,
            args=(job_id,),
            daemon=True,
        )
        self._thread.start()
        return True

    def _retry_work(self, job_id):
        """Thread entry for retry_from_job: resume from durable checkpoint."""
        job = voice_jobs.get_voice_job(job_id)
        if job is None:
            self.failed.emit(t("Voice job not found"))
            return
        cp = voice_jobs.retry_checkpoint(job)
        if cp == "cleanup":
            raw = (job.get("raw_transcript") or "").strip()
            if not raw:
                self.failed.emit(t("Nothing to retry: transcript is empty"))
                return
            # Re-use stored job's kind to pick cleanup/ask path; store wav path for audio keep
            self._retry_cleanup_only(job, raw)
            return
        if cp == "transcription":
            audio_path = job.get("audio_path") or ""
            if not audio_path or not os.path.exists(audio_path):
                # fall back to any persistent copy we can find or original
                self.failed.emit(t("Audio no longer available for retry"))
                try:
                    voice_jobs.update_voice_job(
                        job_id, status=voice_jobs.STATUS_FAILED_RETRYABLE,
                        error_stage="transcription",
                        error_message="audio missing",
                    )
                except Exception:
                    pass
                return
            duration = float(job.get("duration") or 0) or 1.0
            ask = bool(job.get("kind") == voice_jobs.KIND_AGENT)
            # retry full pipeline but transcription will repopulate raw_transcript
            self._work(audio_path, duration, (), ask=ask, paste_override=None,
                       _job_id=job_id, _retry_mode="transcription")
            return
        self.failed.emit(t("Nothing to retry"))

    def _retry_cleanup_only(self, job, raw):
        """Retry cleanup/agent from stored raw without re-transcribing."""
        conf = self.conf
        job_id = job.get("id")
        ask = bool(job.get("kind") == voice_jobs.KIND_AGENT)
        started = time.monotonic()
        text = raw
        warning = ""
        try:
            self._wait_if_paused()
            # Determine whether cleanup is expected for this kind
            wants_cleanup = (conf["assistant_cleanup"] if ask else conf["cleanup_enabled"])
            if wants_cleanup:
                self.stage.emit(t("Cleaning up…"))
                try:
                    text = cleanup.run(raw, conf, conf.cleanup_prompt())
                    # durable: checkpoint after cleanup
                    try:
                        voice_jobs.update_voice_job(
                            job_id, status=voice_jobs.STATUS_PROCESSED,
                            provider=job.get("provider") or "",
                            model=job.get("model") or "",
                            error_stage="", error_message="",
                        )
                    except Exception:
                        pass
                except api.ApiError as exc:
                    text = raw
                    warning = str(exc)
                    print(f"dikte: cleanup failed: {exc}", file=sys.stderr)
                    try:
                        voice_jobs.update_voice_job(
                            job_id, status=voice_jobs.STATUS_FAILED_RETRYABLE,
                            error_stage="cleanup", error_message=str(exc),
                        )
                    except Exception:
                        pass
                    # Still preserve source audio; do not delete
                    self.finished.emit(raw, text, warning)
                    return
            # Agent step if ask
            if ask:
                question = text
                self.stage.emit(t("Asking {name}…", name=i18n.name(
                    assistant.display_name(conf), "dative")))
                def should_stop():
                    self._wait_if_paused()
                    return self._stop.is_set()
                try:
                    text, denied = assistant.ask(
                        question, conf,
                        on_stage=lambda s: (self._wait_if_paused(), self.stage.emit(s))[1],
                        should_stop=should_stop,
                    )
                    warning = "\n".join(x for x in (warning, denied) if x)
                    if denied:
                        try:
                            voice_jobs.update_voice_job(
                                job_id, status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                error_stage="agent", error_message=denied,
                            )
                        except Exception:
                            pass
                        self.finished.emit(raw, text, warning)
                        return
                except assistant.Cancelled:
                    self.cancelled.emit()
                    return
                except (assistant.AssistantError, api.ApiError) as exc:
                    try:
                        voice_jobs.update_voice_job(
                            job_id, status=voice_jobs.STATUS_FAILED_RETRYABLE,
                            error_stage="agent", error_message=str(exc),
                        )
                    except Exception:
                        pass
                    print(f"dikte: {exc}", file=sys.stderr)
                    self.failed.emit(str(exc))
                    return

            # Paste/copy
            wants_paste = (conf["assistant_paste"] if ask else conf["auto_paste"])
            self._wait_if_paused()
            with _paste_lock:
                previous = None
                try:
                    if conf["restore_clipboard"] and wants_paste:
                        previous = paste.read_clipboard()
                except Exception:
                    previous = None
                try:
                    paste.copy(text)
                    if wants_paste:
                        self.stage.emit(t("Pasting…"))
                        paste.press(conf["paste_shortcut"])
                finally:
                    if previous is not None:
                        time.sleep(0.35)
                        try:
                            paste.copy_bytes(previous)
                        except Exception:
                            pass

            # History + job completion — claim COMPLETED only after durable writes
            is_cleanup = wants_cleanup
            target = None
            try:
                target = conf.transcribe_target()
            except Exception:
                target = None
            try:
                cfg.append_history({
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": float(job.get("duration") or 0),
                    "elapsed": round(time.monotonic() - started, 1),
                    "transcribe_provider": getattr(target, "provider", job.get("provider") or ""),
                    "model": getattr(target, "model", job.get("model") or ""),
                    "cleanup_provider": conf["cleanup_provider"] if is_cleanup else "",
                    "cleanup_model": cleanup.model(conf) if is_cleanup else "",
                    "cleanup_error": warning,
                    "mode": "ask" if ask else "",
                    "question": question if ask else "",
                    "assistant_model": conf["assistant_model"] if ask else "",
                    "assistant_provider": assistant.provider(conf) if ask else "",
                    "language": conf["language"],
                    "raw": raw,
                    "text": text,
                })
                cfg.trim_history(conf["history_limit"])
            except OSError as exc:
                print(f"dikte: could not trim the history: {exc}", file=sys.stderr)
            # Mark completed durably before signalling success
            try:
                voice_jobs.update_voice_job(job_id, status=voice_jobs.STATUS_COMPLETED,
                                            error_stage="", error_message="")
            except Exception:
                pass
            self.finished.emit(raw, text, warning)
        except assistant.Cancelled:
            self.cancelled.emit()
        except (api.ApiError, paste.PasteError, assistant.AssistantError) as exc:
            print(f"dikte: {exc}", file=sys.stderr)
            try:
                voice_jobs.update_voice_job(job_id, status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                            error_stage="retry", error_message=str(exc))
            except Exception:
                pass
            self.failed.emit(str(exc))
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(t("Unexpected error: {error}", error=exc))

    def cancel(self):
        """Give up on a job already under way.

        Only the Claude call can honour this, and it is the only one long enough
        to be worth interrupting: a transcription is over in seconds, a command
        that went looking through the web is not.
        """
        self._pause.set()
        self._stop.set()

    def _work(self, wav_path, duration, rms_values, ask, paste_override=None, _job_id=None, _retry_mode=None):
        conf = self.conf
        started = time.monotonic()
        raw = ""
        job = None
        # job_id is either the retry target or a new id for this capture
        job_id = _job_id

        # Room tone only: don't spend an API call, and don't invite a
        # hallucinated sentence back. Skipped on retry (durable audio already validated).
        if _retry_mode is None and conf["skip_silent"]:
            stats = vad.analyse(rms_values, CHUNK_SECONDS, conf["speech_margin_db"])
            if vad.is_silent(stats, conf["silence_db"], conf["speech_margin_db"],
                             conf["min_voiced_seconds"]):
                self._discard(wav_path, job)
                self.failed.emit(
                    t("No speech detected ({level} dB)", level=round(stats["speech_db"]))
                )
                return

        # Durable checkpoint: after capture, before transcription
        # Never claim checkpoint until file is durable (persistent copy succeeds).
        if job_id is not None:
            job = voice_jobs.get_voice_job(job_id)
            # _retry_mode == "transcription" uses stored audio; otherwise job already has transcript
            # For normal _work without retry, job_id None, so this branch not taken.
        if job is None and _job_id is None:
            # New capture — create durable job now
            try:
                new_id = uuid.uuid4().hex[:12]
                persistent = _persistent_audio_copy(wav_path, new_id)
                # durable audio_path: prefer persistent copy, else temp path (only recoverable copy)
                audio_path = persistent or wav_path
                try:
                    t0 = conf.transcribe_target()
                    prov = getattr(t0, "provider", conf.get("transcribe_provider", "local"))
                    mdl = getattr(t0, "model", "")
                except Exception:
                    prov = conf.get("transcribe_provider", "local")
                    mdl = ""
                kind = voice_jobs.KIND_AGENT if ask else voice_jobs.KIND_DICTATION
                entry = {
                    "id": new_id,
                    "kind": kind,
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": voice_jobs.STATUS_CAPTURED,
                    "audio_path": audio_path,
                    "raw_transcript": "",
                    "error_stage": "",
                    "error_message": "",
                    "provider": prov,
                    "model": mdl,
                    "duration": duration,
                    "retry_count": 0,
                }
                job = voice_jobs.save_voice_job(entry)
                job_id = job["id"]
            except Exception as exc:
                print(f"dikte: voice job capture failed: {exc}", file=sys.stderr)
                job = None
                job_id = None
        elif job is not None:
            job_id = job.get("id")

        try:
            # If retrying transcription, reuse stored audio; otherwise transcribe normally.
            # For a new job, always transcribe.
            # For transcription retry, _retry_mode == "transcription" and job has audio_path.
            transcribe_needed = True
            if _retry_mode == "transcription" and job is not None:
                # Will transcribe from job audio_path below
                transcribe_needed = True
            elif _retry_mode is None:
                transcribe_needed = True
            else:
                transcribe_needed = False

            target = None
            if transcribe_needed:
                self._wait_if_paused()
                self.stage.emit(t("Transcribing…"))
                # Choose wav source: on retry, use durable audio_path
                src = wav_path
                if _retry_mode == "transcription" and job is not None:
                    src = job.get("audio_path") or wav_path
                target = conf.transcribe_target()
                try:
                    raw = api.transcribe(
                        target,
                        src,
                        language=conf["language"],
                        prompt=conf["transcribe_prompt"],
                    )
                except (api.ApiError, OSError) as exc:
                    # Transcription failed but audio exists → retryable
                    if job_id:
                        try:
                            voice_jobs.update_voice_job(
                                job_id,
                                status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                error_stage="transcription",
                                error_message=str(exc),
                            )
                            job = voice_jobs.get_voice_job(job_id)
                        except Exception:
                            pass
                    raise

                if conf["filter_hallucinations"] and vad.looks_like_hallucination(raw, duration):
                    self._discard(wav_path, job)
                    self.failed.emit(t("Discarded a stock phrase: “{text}”", text=raw[:60]))
                    return

                # Durable checkpoint after transcription
                if job_id:
                    try:
                        voice_jobs.update_voice_job(
                            job_id,
                            status=voice_jobs.STATUS_TRANSCRIBED,
                            raw_transcript=raw,
                            provider=getattr(target, "provider", ""),
                            model=getattr(target, "model", ""),
                            error_stage="",
                            error_message="",
                        )
                        job = voice_jobs.get_voice_job(job_id)
                    except Exception:
                        pass
            else:
                # Should not reach here for cleanup-only retry (handled via _retry_cleanup_only)
                raw = (job.get("raw_transcript") or "") if job else ""

            # For retry transcription path, raw is now set; continue to cleanup/agent
            text = raw
            warning = ""
            # Claude reads through “eee” and “hani” without help, so a dictation
            # on its way there is normally sent as it was heard, one API call and
            # a second or two lighter.
            self._wait_if_paused()
            if (conf["assistant_cleanup"] if ask else conf["cleanup_enabled"]):
                self.stage.emit(t("Cleaning up…"))
                try:
                    text = cleanup.run(raw, conf, conf.cleanup_prompt())
                    if job_id:
                        try:
                            voice_jobs.update_voice_job(
                                job_id,
                                status=voice_jobs.STATUS_PROCESSED,
                                error_stage="",
                                error_message="",
                            )
                            job = voice_jobs.get_voice_job(job_id)
                        except Exception:
                            pass
                except api.ApiError as exc:
                    # Keep the transcript, but never let the failure pass unseen:
                    # a rejected key would otherwise look like working dictation.
                    text = raw
                    warning = str(exc)
                    print(f"dikte: cleanup failed: {exc}", file=sys.stderr)
                    if job_id:
                        try:
                            voice_jobs.update_voice_job(
                                job_id,
                                status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                error_stage="cleanup",
                                error_message=str(exc),
                            )
                            job = voice_jobs.get_voice_job(job_id)
                        except Exception:
                            pass

            self._wait_if_paused()
            question = ""
            if ask:
                question = text
                self.stage.emit(t("Asking {name}…", name=i18n.name(
                    assistant.display_name(conf), "dative")))
                # combine pause+stop check for assistant
                def should_stop():
                    self._wait_if_paused()
                    return self._stop.is_set()
                try:
                    text, denied = assistant.ask(
                        question, conf,
                        on_stage=lambda s: (self._wait_if_paused(), self.stage.emit(s))[1],
                        should_stop=should_stop,
                    )
                    warning = "\n".join(x for x in (warning, denied) if x)
                    if denied and job_id:
                        try:
                            voice_jobs.update_voice_job(
                                job_id,
                                status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                error_stage="agent",
                                error_message=denied,
                            )
                            job = voice_jobs.get_voice_job(job_id)
                        except Exception:
                            pass
                except assistant.Cancelled:
                    raise
                except (assistant.AssistantError, api.ApiError) as exc:
                    if job_id:
                        try:
                            voice_jobs.update_voice_job(
                                job_id,
                                status=voice_jobs.STATUS_FAILED_RETRYABLE,
                                error_stage="agent",
                                error_message=str(exc),
                            )
                            job = voice_jobs.get_voice_job(job_id)
                        except Exception:
                            pass
                    raise

            wants_paste = (conf["assistant_paste"] if ask else conf["auto_paste"])
            if paste_override is not None:
                wants_paste = paste_override

            self._wait_if_paused()
            with _paste_lock:
                previous = None
                try:
                    if conf["restore_clipboard"] and wants_paste:
                        previous = paste.read_clipboard()
                except Exception:
                    previous = None
                try:
                    paste.copy(text)
                    if wants_paste:
                        self.stage.emit(t("Pasting…"))
                        paste.press(conf["paste_shortcut"])
                finally:
                    if previous is not None:
                        # Let the focused application consume the temporary
                        # transcription before putting every old clipboard type
                        # back.  This also runs when key injection fails.
                        time.sleep(0.35)
                        try:
                            paste.copy_bytes(previous)
                        except Exception:
                            pass

            is_cleanup = conf["assistant_cleanup"] if ask else conf["cleanup_enabled"]
            # target may be None if we came from retry path without transcribing
            if target is None:
                try:
                    target = conf.transcribe_target()
                except Exception:
                    target = None
            cfg.append_history({
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": round(duration, 1),
                "elapsed": round(time.monotonic() - started, 1),
                "transcribe_provider": getattr(target, "provider", conf["transcribe_provider"]) if target else conf.get("transcribe_provider", ""),
                "model": getattr(target, "model", "") if target else "",
                "cleanup_provider": conf["cleanup_provider"] if is_cleanup else "",
                "cleanup_model": cleanup.model(conf) if is_cleanup else "",
                "cleanup_error": warning,
                "mode": "ask" if ask else "",
                "question": question,
                "assistant_model": conf["assistant_model"] if ask else "",
                "assistant_provider": assistant.provider(conf) if ask else "",
                "language": conf["language"],
                "raw": raw,
                "text": text,
            })
            try:
                cfg.trim_history(conf["history_limit"])
            except OSError as exc:
                print(f"dikte: could not trim the history: {exc}", file=sys.stderr)
            # Durable checkpoint: claim COMPLETED only after history is durable
            # If cleanup warned (non-retried path: original behavior still pastes raw but warns), we keep warning but still complete.
            # However if we had marked failed_retryable earlier for cleanup, don't overwrite to completed.
            if job_id:
                try:
                    # Re-read current job status — if it's failed_retryable at cleanup, keep it
                    cur_job = voice_jobs.get_voice_job(job_id)
                    if cur_job and cur_job.get("status") == voice_jobs.STATUS_FAILED_RETRYABLE:
                        # cleanup failed_retryable: we still pasted raw but we are in retryable state; don't mark completed
                        # For the non-retryable cleanup-failed path we already set failed_retryable above, so skip completion
                        job = cur_job
                        self.finished.emit(raw, text, warning)
                    else:
                        voice_jobs.update_voice_job(
                            job_id,
                            status=voice_jobs.STATUS_COMPLETED,
                            error_stage="",
                            error_message="",
                        )
                        job = voice_jobs.get_voice_job(job_id)
                        self.finished.emit(raw, text, warning)
                except Exception:
                    self.finished.emit(raw, text, warning)
            else:
                self.finished.emit(raw, text, warning)

        except assistant.Cancelled:
            self.cancelled.emit()
        except (api.ApiError, paste.PasteError, assistant.AssistantError) as exc:
            print(f"dikte: {exc}", file=sys.stderr)
            # If we haven't already marked retryable for this stage, ensure it
            if job_id and job is not None:
                # Only override if not already failed_retryable for a more specific stage
                cur = voice_jobs.get_voice_job(job_id)
                if cur and cur.get("status") != voice_jobs.STATUS_FAILED_RETRYABLE:
                    stage = "transcription" if isinstance(exc, api.ApiError) and not raw else "processing"
                    try:
                        voice_jobs.update_voice_job(
                            job_id,
                            status=voice_jobs.STATUS_FAILED_RETRYABLE,
                            error_stage=stage,
                            error_message=str(exc),
                        )
                    except Exception:
                        pass
            self.failed.emit(str(exc))
        except Exception as exc:  # never fail silently
            traceback.print_exc()
            self.failed.emit(t("Unexpected error: {error}", error=exc))
        finally:
            self._discard(wav_path, job)

    def _discard(self, wav_path, job=None):
        # Job-aware discard: never delete the durable audio copy
        if job is not None:
            durable = (job.get("audio_path") or "") if isinstance(job, dict) else ""
            # If wav_path is the durable file itself, apply preservation rule
            if durable and wav_path:
                try:
                    if os.path.abspath(wav_path) == os.path.abspath(durable):
                        if voice_jobs.should_keep_audio(job, bool(self.conf.get("keep_audio", False))):
                            return
                        # Even for completed jobs, default is retain — don't delete durable here
                        # Retention is handled by age-based pruning, not per-run delete
                        return
                except Exception:
                    pass
            # wav_path is temp distinct from durable — delete temp, keep durable
            if wav_path and durable and wav_path != durable:
                if os.path.exists(wav_path):
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        pass
                return
            # durable == "" or wav_path == durable case already handled; if durable missing, fall through
            if wav_path and durable == "" and os.path.exists(wav_path):
                # No durable copy was made (e.g. copy failed): wav_path IS the only copy
                if voice_jobs.should_keep_audio(job, bool(self.conf.get("keep_audio", False))):
                    # Keep it by moving to recordings
                    try:
                        cfg.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
                        # If wav_path already under RECORDINGS_DIR, keep it
                        if cfg.RECORDINGS_DIR in pathlib.Path(wav_path).parents or pathlib.Path(wav_path).parent == cfg.RECORDINGS_DIR:
                            return
                        shutil.move(wav_path, cfg.RECORDINGS_DIR / (time.strftime("%Y%m%d-%H%M%S") + ".wav"))
                        return
                    except OSError:
                        pass
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
                return
        # No job — legacy behavior, but keep retryable override if job was transient None
        if not wav_path or not os.path.exists(wav_path):
            return
        if self.conf["keep_audio"]:
            try:
                cfg.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(wav_path, cfg.RECORDINGS_DIR / (time.strftime("%Y%m%d-%H%M%S") + ".wav"))
                return
            except OSError:
                pass
        try:
            os.unlink(wav_path)
        except OSError:
            pass
