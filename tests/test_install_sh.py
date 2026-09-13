"""What install.sh points at, with a bundle beside it and without one.

The launchers this script writes are what the user's desktop actually runs, and a
launcher pointed at a file that is not there fails on their machine rather than in a
test. Both modes are checked, because the frozen branch is the one that can silently
break the source install.

The frozen case builds its own tiny bundle directory instead of using the real
`dist/` — which is gitignored and therefore absent on a fresh checkout, so a test
that needed it would pass here and vanish in CI.
"""

import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
INSTALLER = REPO / "install.sh"


def _run_installer(script, home):
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_RUNTIME_DIR": str(home / "run"),
        "XDG_SESSION_TYPE": "wayland",
    })
    (home / "run").mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(script)], env=env, capture_output=True,
                          text=True, timeout=180)


@unittest.skipIf(sys.platform == "win32", "install.sh is the Unix installer")
class WhatTheLaunchersPointAt(unittest.TestCase):

    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp(prefix="dikte-inst-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.checkout = pathlib.Path(tempfile.mkdtemp(prefix="dikte-checkout-"))
        self.addCleanup(shutil.rmtree, self.checkout, ignore_errors=True)
        shutil.copy(INSTALLER, self.checkout / "install.sh")
        (self.checkout / "icons").mkdir()
        (self.checkout / "icons" / "dikte.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.checkout / "dikte.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (self.checkout / "dikte.py").chmod(0o755)

    def bundle(self, body="#!/bin/sh\necho 'a frozen dikte'\n"):
        target = self.checkout / "dist" / "dikte"
        target.mkdir(parents=True)
        exe = target / "dikte"
        exe.write_text(body, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        return exe

    def desktop(self, path=None):
        path = pathlib.Path(path or (self.home / ".local/share/applications/dikte.desktop"))
        lines = path.read_text(encoding="utf-8").splitlines()
        return {ln.split("=", 1)[0]: ln.split("=", 1)[1]
                for ln in lines if "=" in ln}

    @property
    def menu_entry(self):
        return self.desktop()

    @property
    def autostart_entry(self):
        return self.desktop(self.home / ".config/autostart/dikte.desktop")

    def test_a_bundle_beside_the_script_is_what_gets_installed(self):
        exe = self.bundle()
        result = _run_installer(self.checkout / "install.sh", self.home)
        self.assertEqual(0, result.returncode, msg=result.stderr[-800:])
        self.assertEqual(f'"{exe}"', self.menu_entry["Exec"])
        self.assertEqual(str(self.checkout / "icons" / "dikte.png"),
                         self.menu_entry["Icon"])
        self.assertEqual(f'"{exe}"', self.autostart_entry["Exec"])
        command = self.home / ".local/bin/dikte"
        self.assertTrue(command.is_symlink())
        self.assertEqual(str(exe), os.readlink(command),
                         "the command must be the bundle, not the script")

    def test_without_a_bundle_the_checkout_is_still_what_gets_installed(self):
        """The branch that must not break: no bundle, exactly what was there before."""
        result = _run_installer(self.checkout / "install.sh", self.home)
        self.assertEqual(0, result.returncode, msg=result.stderr[-800:])
        self.assertEqual(f'"{self.checkout / "dikte.py"}"', self.menu_entry["Exec"])
        self.assertEqual("audio-input-microphone", self.menu_entry["Icon"])
        command = self.home / ".local/bin/dikte"
        self.assertEqual(str(self.checkout / "dikte.py"), os.readlink(command))

    def test_the_exec_line_survives_a_path_with_spaces(self):
        """A .desktop file is read by a shell: an unquoted path is two arguments."""
        spaced = pathlib.Path(tempfile.mkdtemp(prefix="dikte with spaces-"))
        self.addCleanup(shutil.rmtree, spaced, ignore_errors=True)
        shutil.copy(INSTALLER, spaced / "install.sh")
        exe = spaced / "dist" / "dikte" / "dikte"
        exe.parent.mkdir(parents=True)
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        exe.chmod(0o755)
        result = _run_installer(spaced / "install.sh", self.home)
        self.assertEqual(0, result.returncode, msg=result.stderr[-800:])
        self.assertEqual(f'"{exe}"', self.menu_entry["Exec"],
                         "the path has to arrive as one argument")


if __name__ == "__main__":
    unittest.main()
