"""The socket the running instance listens on, and one request over it.

A command typed at a terminal is answered rather than only obeyed: the reply
carries the transcript, the agent's answer, or the reason nothing happened,
which is what lets a script wait for a dictation instead of guessing when it is
done. One JSON object goes each way per connection. A bare verb is still
understood, because that is what earlier versions sent and what a stale KDE
shortcut may still send.
"""

import json
import os
import sys

try:
    from PyQt6.QtNetwork import QLocalSocket
except ImportError:  # pragma: no cover - missing Qt in headless/tests
    QLocalSocket = None  # type: ignore[assignment]

CONNECT_MS = 800


def _uid_suffix():
    """Per-user suffix for the socket/pipe name; Windows has no getuid."""
    if hasattr(os, "getuid"):
        try:
            return str(os.getuid())
        except OSError:
            pass
    # Windows: USERNAME is the closest to a per-user id.
    for var in ("USERNAME", "USER", "LOGNAME"):
        val = os.environ.get(var)
        if val:
            # Sanitize: QLocalServer pipe names must be valid; strip odd chars.
            safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in val)
            return safe[:64] or "user"
    return "user"


SERVER_NAME = "dikte-" + _uid_suffix()

# Long enough for a process that is already running to answer, short enough that
# "nothing is running" is not a noticeable pause in front of a key press.


def server_name(uid=None, username=None, platform=None):
    """Testable server-name construction without touching the real env."""
    plat = platform or sys.platform
    if uid is not None and plat != "win32":
        return f"dikte-{uid}"
    if username is not None:
        safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in username)
        return "dikte-" + (safe[:64] or "user")
    # Fall back to the live value so callers can use this without args on Windows.
    return SERVER_NAME


def script_path():
    return os.path.realpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dikte.py")
    )


def command_for(verb):
    """The command line a KDE shortcut runs for one of the verbs."""
    return f"{sys.executable} {script_path()} {verb}"


def send(cmd, wait=False, timeout=0, **args):
    """Send one request; the reply, or None when no instance is running.

    `wait` asks the instance to hold its reply back until the job the request
    started is over, which is how a terminal gets the transcript rather than
    only the fact that recording began. `timeout` bounds that wait in seconds;
    0 waits for as long as the job takes.
    """
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(CONNECT_MS):
        return None

    request = {"cmd": cmd}
    request.update({key: value for key, value in args.items() if value is not None})
    if wait:
        request["wait"] = True
    # A verb carrying nothing goes as the bare word it used to be, so that an
    # instance still running the older code obeys it: that is the one request
    # that has to work across an update, since it is how you install the update.
    line = cmd if list(request) == ["cmd"] else json.dumps(request)
    sock.write((line + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(CONNECT_MS)
    limit = (int(timeout * 1000) if timeout else -1) if wait else CONNECT_MS
    buffer = b""
    while b"\n" not in buffer:
        if not sock.waitForReadyRead(limit):
            break
        buffer += bytes(sock.readAll())
    sock.disconnectFromServer()

    line = buffer.decode("utf-8", "replace").strip()
    if not line:
        # An instance from before replies existed answers by staying silent, and
        # for a fire-and-forget verb that silence means it went through. A wait
        # that ends this way did not: the run never reported back.
        return ({"ok": False, "legacy": True,
                 "error": "the running instance is too old to answer; "
                          "reload it with: dikte restart"}
                if wait else {"ok": True, "legacy": True})
    try:
        reply = json.loads(line)
    except json.JSONDecodeError:
        return {"ok": True, "legacy": True}
    return reply if isinstance(reply, dict) else {"ok": True, "legacy": True}
