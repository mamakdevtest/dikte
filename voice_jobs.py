"""Durable voice jobs: captured audio/transcript is never lost because an AI step failed."""

import json
import os
import pathlib
import threading
import time
import uuid

import config as cfg

_VOICE_JOBS_LOCK = threading.Lock()

# ---- path -----------------------------------------------------------------

VOICE_JOBS_FILE = cfg.DATA_DIR / "voice_jobs.jsonl"

# ---- status + kind ---------------------------------------------------------

STATUS_CAPTURED = "captured"
STATUS_TRANSCRIBED = "transcribed"
STATUS_PROCESSED = "processed"
STATUS_COMPLETED = "completed"
STATUS_FAILED_RETRYABLE = "failed_retryable"

STATUSES = {
    STATUS_CAPTURED,
    STATUS_TRANSCRIBED,
    STATUS_PROCESSED,
    STATUS_COMPLETED,
    STATUS_FAILED_RETRYABLE,
}

KIND_DICTATION = "dictation"
KIND_MEETING = "meeting"
KIND_AGENT = "agent"
KINDS = {KIND_DICTATION, KIND_MEETING, KIND_AGENT}


class PersistenceError(OSError):
    """A voice-job checkpoint could not be made durable.

    Callers must treat this as a hard boundary: derived work must not continue
    after it because there is no recoverable record of its input/state.
    """


def _file():
    """Current file, respecting a patched config path in tests.

    Derives from current DATA_DIR so a DikteTest that patches DATA_DIR
    automatically isolates voice jobs too (VOICE_JOBS_FILE is not patched
    by support.py).
    """
    # Use current DATA_DIR dynamically to stay in sync with patched tests.
    data_dir = getattr(cfg, "DATA_DIR", None)
    if data_dir is not None:
        return pathlib.Path(data_dir) / "voice_jobs.jsonl"
    return getattr(cfg, "VOICE_JOBS_FILE", VOICE_JOBS_FILE)


def _read_rows(path):
    """Read valid rows from *path* without acquiring the jobs lock."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise PersistenceError(str(exc)) from exc
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("id"):
            rows.append(row)
    return rows


def _sync_parent(path):
    """Flush the rename's directory entry where the platform permits it."""
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_rows_locked(rows):
    """Write rows atomically while the caller owns ``_VOICE_JOBS_LOCK``."""
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
        _sync_parent(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PersistenceError(str(exc)) from exc


def _write_voice_jobs(rows):
    """Replace the file atomically and durably."""
    with _VOICE_JOBS_LOCK:
        _write_rows_locked(rows)


def read_voice_jobs():
    """Newest last. Missing/empty file returns []. Bad lines are skipped."""
    return _read_rows(_file())


def get_voice_job(job_id):
    for row in read_voice_jobs():
        if row.get("id") == job_id:
            return row
    return None


def save_voice_job(entry):
    """Insert or replace by id. Generates id/ts if missing. Returns stored row."""
    if not isinstance(entry, dict):
        raise TypeError("entry must be dict")
    row = dict(entry)
    if not row.get("id"):
        row["id"] = uuid.uuid4().hex[:12]
    if not row.get("ts"):
        row["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if not row.get("status"):
        row["status"] = STATUS_CAPTURED
    if row.get("kind") not in KINDS:
        row["kind"] = KIND_DICTATION
    with _VOICE_JOBS_LOCK:
        rows = _read_rows(_file())
        for idx, existing in enumerate(rows):
            if existing.get("id") == row["id"]:
                rows[idx] = row
                break
        else:
            rows.append(row)
        _write_rows_locked(rows)
    return row


def update_voice_job(job_id, **changes):
    """Patch one row by id, return updated row or None."""
    with _VOICE_JOBS_LOCK:
        rows = _read_rows(_file())
        found = None
        for row in rows:
            if row.get("id") == job_id:
                row.update(changes)
                found = row
                break
        if found is None:
            return None
        _write_rows_locked(rows)
        return found


def delete_voice_job(job_id):
    with _VOICE_JOBS_LOCK:
        rows = _read_rows(_file())
        kept = [r for r in rows if r.get("id") != job_id]
        if len(kept) == len(rows):
            return False
        _write_rows_locked(kept)
        return True


# ---- status helpers --------------------------------------------------------

def is_retryable(job):
    """Whether this job can be retried (has a recoverable artifact)."""
    if not isinstance(job, dict):
        return False
    if job.get("status") == STATUS_FAILED_RETRYABLE:
        return True
    # Also retryable if it stopped at a checkpoint with artifact present
    # but not yet completed — failed_retryable is the explicit marker.
    return False


def retry_checkpoint(job):
    """What stage to retry from, based on what artifacts exist.

    Returns one of "transcription", "cleanup", or None (nothing to retry / completed).
    Never claims checkpoint until file is durable — caller must have persisted.
    """
    if not isinstance(job, dict):
        return None
    status = job.get("status")
    if status == STATUS_COMPLETED:
        return None
    has_audio = bool(job.get("audio_path"))
    has_transcript = bool((job.get("raw_transcript") or "").strip())
    # If transcript exists, the next recoverable step is cleanup (don't re-transcribe)
    if has_transcript:
        # transcribed but cleanup never succeeded, or failed_retryable at cleanup stage
        if status in (STATUS_TRANSCRIBED, STATUS_FAILED_RETRYABLE, STATUS_CAPTURED, STATUS_PROCESSED):
            # if failed at transcription, raw would be empty — already handled
            # need to know error_stage to decide, but transcript present → cleanup
            err_stage = job.get("error_stage") or ""
            if err_stage == "transcription" and not has_transcript:
                return "transcription"
            return "cleanup"
        return "cleanup"
    if has_audio:
        return "transcription"
    return None


def should_keep_audio(job, keep_audio_setting=False):
    """Whether the persistent audio copy must be retained.

    - Retryable jobs ALWAYS keep audio regardless of setting.
    - Any failed_retryable keeps audio.
    - Successful processing keeps per new policy (default retain) — if job is
      completed/processed, keep when setting is True or when no explicit setting
      (default retain). Caller passes setting; we honor retryable override.
    """
    if job is not None and is_retryable(job):
        return True
    if job is not None and job.get("status") == STATUS_FAILED_RETRYABLE:
        return True
    # For any job that still has a recoverable checkpoint, don't delete the only copy
    cp = retry_checkpoint(job) if job else None
    if cp is not None:
        return True
    return bool(keep_audio_setting)


# Backwards-compat alias for spec's `is_retryable`/`retry_checkpoint` naming
# already provided.
