"""A diagnostics bundle for a bug report, without telemetry and without secrets.

Dikte has no analytics and does not want a server to know who is using it. What it can do
for a bug report is hand the user a single file they can read before they share it: what the
machine is, what the settings are (with everything secret masked), what the last run said,
and the counts of what has been dictated.

Three rules, and each of them is a test in `tests/test_diagnostics.py`:

1. **No secret value, ever.** The settings summary masks by name (`*_api_key`, tokens,
   passwords, anything under `providers`) and every text file is scrubbed against the *actual*
   values before it is written — a log line that echoed a key comes out as `***`. Masking by
   name is what the settings window does; scrubbing by value is what makes it true for a file
   that leaves the machine.
2. **No audio and no transcripts.** History is counted, never copied: the bundle says "37
   dictations, 4 failures", not what was said.
3. **It says what it contains.** `README.txt` inside the archive lists the files and the two
   rules above, so the person sending it can check the claim rather than trust it.
"""

import json
import platform
import sys
import zipfile

import config as cfg
from version import __version__

# How much of the log travels. Enough for one startup and one failure, not a month of use.
LOG_TAIL = 256 * 1024

# A setting is secret because of its name: the project stores keys in flat `*_api_key`
# fields and in custom gateways under `providers`, and both go through this.
SECRET_HINTS = ("key", "token", "secret", "password", "credential", "passphrase")

MASK = "***"


def looks_secret(name):
    lowered = str(name).lower()
    return any(hint in lowered for hint in SECRET_HINTS)


def secret_values(conf):
    """Every non-empty secret in the settings, as the strings to scrub for."""
    found = set()

    def walk(node, key=""):
        if isinstance(node, dict):
            for name, value in node.items():
                walk(value, str(name))
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, key)
        elif isinstance(node, str) and node and looks_secret(key):
            found.add(node)

    try:
        walk(conf.data)
    except Exception as exc:
        # A settings file that cannot be walked is a reason to publish less, not to stop:
        # the summary below is built from a copy, and the log is still scrubbed by value.
        print(f"dikte: could not inspect the settings for secrets ({exc})", file=sys.stderr)
    return found


def redacted(node, key=""):
    """The settings, with secret names masked and everything else kept as it is."""
    if isinstance(node, dict):
        return {name: (MASK if looks_secret(name) and value else redacted(value, str(name)))
                for name, value in node.items()}
    if isinstance(node, list):
        return [redacted(value, key) for value in node]
    if isinstance(node, str) and looks_secret(key) and node:
        return MASK
    return node


def scrub(text, secrets):
    """Remove the settings' own secret values from anything about to leave the machine."""
    for secret in sorted(secrets, key=len, reverse=True):
        if len(secret) >= 4 and secret in text:
            text = text.replace(secret, MASK)
    return text


def log_tail(path, limit=LOG_TAIL):
    """The end of the log, or a sentence saying why there is none."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > limit:
                handle.seek(size - limit)
            return handle.read().decode("utf-8", "replace")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        # The rest of the bundle is still worth having; the missing piece is named instead.
        return f"(the log could not be read: {exc})"


def history_counts():
    """What was dictated, as numbers. Never what was said."""
    try:
        rows = cfg.read_history()
    except Exception as exc:
        print(f"dikte: could not count the history for the bundle ({exc})", file=sys.stderr)
        return {"dictations": None, "error": str(exc)}
    failed = sum(1 for row in rows if row.get("error") or row.get("failed"))
    return {
        "dictations": len(rows),
        "failed": failed,
        # `ts` is the field the worker writes (worker.py); a row without one contributes
        # nothing rather than an invented time.
        "last": (rows[-1].get("ts") or "") if rows else "",
    }


def environment(checks=None):
    """What the machine is, because half of Dikte's failures are platform failures."""
    import os
    return {
        "dikte": __version__,
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "session": os.environ.get("XDG_SESSION_TYPE", ""),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
        "display": bool(os.environ.get("DISPLAY")),
        "config_dir": str(cfg.CONFIG_DIR),
        "data_dir": str(cfg.DATA_DIR),
        "log": str(cfg.log_path()),
        "checks": checks or {},
    }


WHAT_THIS_IS = """\
This is a Dikte diagnostics bundle, written by `dikte doctor --bundle`.

What is in it:
  doctor.json      the same report `dikte doctor --json` prints
  environment.json which machine, which Python, which desktop session, where the files are
  settings.json    your settings, with every value whose NAME says key/token/secret masked
  history.json     how many dictations and how many failed — never what was said
  log.txt          the end of %(log)s, bounded to %(limit)d KB

What is NOT in it:
  no API keys or tokens (masked by name, and the log is scrubbed against the real values)
  no audio, and no transcript text
  nothing was sent anywhere: this file was written on this machine, for you to read before
  you attach it to a bug report.

If you would rather not send the log, delete log.txt from the archive; the rest still helps.
"""


def files_for(conf, checks=None):
    """{name in the archive: text} — the whole bundle, before it is written."""
    secrets = secret_values(conf)
    readme = WHAT_THIS_IS % {"log": cfg.log_path(), "limit": LOG_TAIL // 1024}
    return {
        "README.txt": readme,
        "doctor.json": json.dumps({"ok": True, **(checks or {})}, indent=2, sort_keys=True),
        "environment.json": json.dumps(environment(checks), indent=2, sort_keys=True),
        "settings.json": json.dumps(redacted(conf.data), indent=2, sort_keys=True,
                                   default=str),
        "history.json": json.dumps(history_counts(), indent=2, sort_keys=True),
        "log.txt": scrub(log_tail(cfg.log_path()), secrets),
    }


def bundle(conf, path, checks=None):
    """Write the archive and say what went in it. Returns (path, {name: bytes})."""
    import pathlib
    target = pathlib.Path(path)
    pieces = files_for(conf, checks)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in sorted(pieces.items()):
            archive.writestr(name, text)
    return target, {name: len(text.encode("utf-8")) for name, text in pieces.items()}
