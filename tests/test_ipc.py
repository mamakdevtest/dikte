"""The request a terminal sends to the running instance, and the reply it reads.

The wire format has to stay backwards compatible in both directions: a stale KDE
shortcut still sends a bare verb, and an instance from before replies existed
answers by saying nothing at all.
"""

import io
import json
import os
import sys
import unittest
from unittest import mock

import ipc


class FakeSocket:
    """QLocalSocket, as much of it as ipc.send() touches."""

    def __init__(self, connected=True, reply=b""):
        self.connected = connected
        self.reply = reply
        self.written = b""
        self.server = ""
        self.disconnected = False
        self.read_limits = []
        self._served = False

    def connectToServer(self, name):
        self.server = name

    def waitForConnected(self, ms):
        return self.connected

    def write(self, data):
        self.written += bytes(data)

    def flush(self):
        pass

    def waitForBytesWritten(self, ms):
        return True

    def waitForReadyRead(self, ms):
        self.read_limits.append(ms)
        if self._served or not self.reply:
            return False
        self._served = True
        return True

    def readAll(self):
        return self.reply

    def disconnectFromServer(self):
        self.disconnected = True


class Paths(unittest.TestCase):
    def test_script_path_points_at_dikte(self):
        self.assertTrue(ipc.script_path().endswith("dikte.py"))
        self.assertTrue(os.path.exists(ipc.script_path()))

    def test_the_shortcut_command_runs_it_with_this_interpreter(self):
        command = ipc.command_for("toggle")
        self.assertTrue(command.startswith(sys.executable))
        self.assertTrue(command.endswith(" toggle"))

    @unittest.skipUnless(hasattr(os, "getuid"),
                         "the socket is named after a user id, which Windows "
                         "has no equivalent of")
    def test_the_socket_is_per_user(self):
        self.assertEqual(ipc.SERVER_NAME, f"dikte-{os.getuid()}")


class Send(unittest.TestCase):
    def send(self, socket, *args, **kwargs):
        with mock.patch.object(ipc, "QLocalSocket", return_value=socket):
            return ipc.send(*args, **kwargs)

    def written_line(self, socket):
        return socket.written.decode("utf-8").strip()

    def test_nothing_running(self):
        sock = FakeSocket(connected=False)
        self.assertIsNone(self.send(sock, "toggle"))
        self.assertEqual(sock.written, b"")

    def test_a_verb_on_its_own_goes_as_the_bare_word(self):
        """An older instance only understands this, and it is how updates land."""
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "restart")
        self.assertEqual(self.written_line(sock), "restart")

    def test_a_verb_with_arguments_goes_as_json(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "ask", text="what time is it")
        self.assertEqual(json.loads(self.written_line(sock)),
                         {"cmd": "ask", "text": "what time is it"})

    def test_arguments_that_are_none_are_left_out(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "record", seconds=None, paste=False)
        self.assertEqual(json.loads(self.written_line(sock)),
                         {"cmd": "record", "paste": False})

    def test_asking_to_be_waited_for_says_so(self):
        sock = FakeSocket(reply=b'{"ok": true, "text": "hello"}\n')
        reply = self.send(sock, "toggle", wait=True)
        self.assertTrue(json.loads(self.written_line(sock))["wait"])
        self.assertEqual(reply["text"], "hello")

    def test_a_wait_with_no_timeout_reads_without_a_deadline(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "toggle", wait=True)
        self.assertEqual(sock.read_limits[0], -1)

    def test_a_timeout_is_passed_on_in_milliseconds(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "toggle", wait=True, timeout=2.5)
        self.assertEqual(sock.read_limits[0], 2500)

    def test_a_fire_and_forget_verb_does_not_wait_around(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "cancel")
        self.assertEqual(sock.read_limits[0], ipc.CONNECT_MS)

    def test_the_reply_comes_back_as_it_was_sent(self):
        sock = FakeSocket(reply=b'{"ok": false, "error": "no microphone"}\n')
        self.assertEqual(self.send(sock, "toggle"),
                         {"ok": False, "error": "no microphone"})

    def test_silence_from_an_old_instance_means_the_verb_went_through(self):
        sock = FakeSocket(reply=b"")
        reply = self.send(sock, "cancel")
        self.assertTrue(reply["ok"])
        self.assertTrue(reply["legacy"])

    def test_silence_during_a_wait_is_a_failure_with_a_way_out(self):
        sock = FakeSocket(reply=b"")
        reply = self.send(sock, "toggle", wait=True)
        self.assertFalse(reply["ok"])
        self.assertIn("dikte restart", reply["error"])

    def test_a_reply_that_is_not_json(self):
        sock = FakeSocket(reply=b"ok\n")
        self.assertEqual(self.send(sock, "toggle"), {"ok": True, "legacy": True})

    def test_a_reply_that_is_json_but_not_an_object(self):
        sock = FakeSocket(reply=b"[1, 2, 3]\n")
        self.assertEqual(self.send(sock, "toggle"), {"ok": True, "legacy": True})

    def test_the_socket_is_always_let_go_of(self):
        sock = FakeSocket(reply=b'{"ok": true}\n')
        self.send(sock, "toggle")
        self.assertTrue(sock.disconnected)


class TheFrozenBuildCanFindItself(unittest.TestCase):
    """T5.1: a bundle must not need a developer's Python, or a source tree.

    Three callers used to build `sys.executable + script_path()` by hand, which is right
    only while Dikte is a checkout. In a frozen build that pair names a file which is not
    on the disk, so the KDE shortcut, the hand-over to a running instance and the
    second-instance spawn would all fail — on the machine nobody tests by hand, which is
    where a packaging bug lives.
    """

    def test_a_checkout_runs_the_script(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual([sys.executable, ipc.script_path(), "record"],
                             ipc.launch_command("record"))

    def test_a_bundle_runs_itself(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual([sys.executable, "record"], ipc.launch_command("record"))

    def test_presence_of_the_flag_is_not_enough(self):
        """`sys.frozen` has to be true, not merely there.

        A checkout that inherits a falsey flag must keep running its script: the slip
        this guards against is truthiness, and it would only appear in a bundle.
        """
        with mock.patch.object(sys, "frozen", 0, create=True):
            self.assertEqual([sys.executable, ipc.script_path(), "record"],
                             ipc.launch_command("record"))

    def test_the_shortcut_command_survives_a_path_with_spaces(self):
        with mock.patch.object(sys, "frozen", False, create=True), \
                mock.patch.object(ipc, "script_path", return_value="/home/a b/dikte.py"):
            cmd = ipc.command_for("record")
        self.assertIn("'/home/a b/dikte.py'", cmd)
        self.assertTrue(cmd.endswith("record"), cmd)

    def test_nothing_else_spells_the_pair_out_by_hand(self):
        """One place knows how to re-run this application: `launch_command`.

        A fourth caller copying the old pair would fail only in a frozen build, which is
        the one build a developer's test run never exercises.
        """
        import ast
        import pathlib

        offenders = []
        files = sorted(pathlib.Path(".").glob("*.py"))
        files += sorted(pathlib.Path("ui").rglob("*.py"))
        for path in files:
            if path.name == "ipc.py" or "__pycache__" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "script_path"):
                    offenders.append(f"{path}:{node.lineno}")
        self.assertEqual([], offenders, (
            "run the application through ipc.launch_command() instead:\n  "
            + "\n  ".join(offenders)))


class TheSecondLaunchStepsAside(unittest.TestCase):
    """N8: a second launch must not steal the running instance's socket.

    `removeServer()` + `listen()` is Qt's way of clearing a stale socket, and it also takes
    the name from a live instance: the first Dikte keeps recording, unreachable, while
    every command now reaches the second. A frozen bundle on a desktop entry makes that one
    double click away.
    """

    def test_something_answering_status_is_an_instance(self):
        self.assertTrue(ipc.running_instance(probe=lambda: {"ok": True, "running": True}))

    def test_silence_is_not_an_instance(self):
        self.assertFalse(ipc.running_instance(probe=lambda: None))

    def test_a_probe_that_cannot_answer_says_so_and_is_not_an_instance(self):
        def broken():
            raise OSError("no socket layer at all")

        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            self.assertFalse(ipc.running_instance(probe=broken))
        self.assertIn("could not ask whether Dikte is already running", err.getvalue())

    def test_the_probe_asks_with_a_timeout(self):
        """A second launch cannot hang waiting for the first one to reply."""
        calls = []

        def fake_send(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return None

        with mock.patch.object(ipc, "send", fake_send):
            ipc.running_instance(timeout=3)
        self.assertEqual([("status", {"timeout": 3})], calls)


if __name__ == "__main__":
    unittest.main()
