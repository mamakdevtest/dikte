"""Build the frozen application, then prove it runs.

    python packaging/build.py            # build, then every check
    python packaging/build.py --check    # check whatever is already in dist/

T5.2 asks for jobs that launch the frozen artifact and assert it starts, on every
platform. This is that job's body, written once and shared: CI calls it, and a person can
run it without having to know the checks exist. Three checks, each proving more than the
last:

  --help           the interpreter, the argument parser and the module imports are inside
  --json doctor    the application's own diagnosis runs end to end inside the bundle
  a real window    the GUI starts, reaches its event loop and is still alive afterwards

The third is the one that proves Qt travelled with it, and it asserts on the line the
application itself prints when there is no system tray ("no system tray found, running
anyway") rather than only on the process staying up: a frozen build that dies during
construction would look identical to one waiting for a keypress.

All three run with the data, config and runtime directories pointed at a temporary
directory. A bundle that writes into the developer's real settings is not a test, it is
an incident.

Exits non-zero, with the failure's own output, when anything does not hold.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "dikte.spec"
DIST = ROOT / "dist"
READY_LINE = "no system tray found, running anyway"


def bundle_executable():
    """Where the frozen application ended up, per platform."""
    if sys.platform == "darwin":
        app = DIST / "dikte.app" / "Contents" / "MacOS" / "dikte"
        if app.exists():
            return app
    name = "dikte.exe" if sys.platform == "win32" else "dikte"
    return DIST / "dikte" / name


def sandbox_env(extra=None):
    """A run that cannot touch the real settings, history or socket.

    `TMPDIR` matters as much as the XDG variables: Qt puts a `QLocalServer` socket in
    `QDir::tempPath()` on Unix, and Dikte's server name is per user, so a check that
    starts a second instance without moving the temp directory talks to the *running*
    application — it forwards a request instead of starting. That is not hypothetical:
    the first version of this script did exactly that, and the request it forwarded was
    "open the settings window".
    """
    home = pathlib.Path(tempfile.mkdtemp(prefix="dikte-frozen-"))
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "XDG_RUNTIME_DIR": str(home / "run"),
        "TMPDIR": str(home / "tmp"),
        "QT_QPA_PLATFORM": "offscreen",
    })
    (home / "run").mkdir(parents=True, exist_ok=True)
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    if extra:
        env.update(extra)
    return env


def build():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(DIST), "--workpath", str(ROOT / "build"),
           str(SPEC)]
    print("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller failed with {result.returncode}")
    return DIST


def make_dmg(app_path, out=None):
    """A disk image holding the `.app` — what a macOS user actually downloads.

    `hdiutil` is macOS's own tool, so this is the one step that leans on a platform
    command rather than on PyInstaller. The image is *not* signed: signing and
    notarisation need an Apple Developer identity and credentials a build machine should
    not hold by default, and that half of T5.5 is still open. An unsigned image installs
    and then Gatekeeper refuses to open it on a machine that did not build it — a fact
    about the artifact, not a bug in this step.
    """
    app = pathlib.Path(app_path)
    if not app.exists():
        raise SystemExit(f"no .app to package at {app}")
    staging = pathlib.Path(tempfile.mkdtemp(prefix="dikte-dmg-"))
    # The convention every macOS user knows: drag the app onto the folder beside it.
    (staging / "Applications").symlink_to("/Applications")
    subprocess.run(["cp", "-R", str(app), str(staging / app.name)], check=True)
    image = pathlib.Path(out) if out else DIST / "dikte.dmg"
    image.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", "Dikte", "-srcfolder", str(staging),
                    "-ov", "-format", "UDZO", str(image)],
                   check=True, capture_output=True)
    return image


def check_dmg(image):
    """Mount it, look inside, detach. An image that will not mount is not a download."""
    mount = pathlib.Path(tempfile.mkdtemp(prefix="dikte-mnt-"))
    result = subprocess.run(["hdiutil", "attach", str(image), "-nobrowse", "-readonly",
                             "-mountpoint", str(mount)], capture_output=True, text=True)
    try:
        if result.returncode != 0:
            return False, f"hdiutil attach failed: {(result.stderr or result.stdout)[:300]}"
        contents = sorted(p.name for p in mount.iterdir())
        if not (mount / "dikte.app").exists():
            return False, f"the image mounted but holds no dikte.app: {contents}"
        return True, f"mounts and holds {contents}"
    finally:
        subprocess.run(["hdiutil", "detach", str(mount), "-quiet"], capture_output=True)


def check_help(exe):
    """The bundle can run at all, and its argument parser came along."""
    result = subprocess.run([str(exe), "--help"], capture_output=True, text=True,
                            env=sandbox_env(), timeout=120)
    if result.returncode != 0:
        return False, f"--help exited {result.returncode}\n{result.stderr[-800:]}"
    if "Voice dictation" not in result.stdout:
        return False, "--help printed no usage; the parser or a module is missing"
    verbs = [v for v in ("record", "doctor", "transcribe", "meeting")
             if v in result.stdout]
    return True, f"usage printed, {len(verbs)}/4 verbs present"


def check_doctor(exe):
    """The application's own diagnosis, inside the bundle.

    `doctor` reports what is missing rather than failing over it (a runner without
    `pw-record` is a normal runner), so the assertion is on the report's contents: a
    bundle that cannot import the application's own modules cannot produce it.
    """
    result = subprocess.run([str(exe), "--json", "doctor"], capture_output=True,
                            text=True, env=sandbox_env(), timeout=180)
    if result.returncode != 0:
        return False, (f"doctor exited {result.returncode}\n"
                       f"{(result.stderr or result.stdout)[-800:]}")
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return False, f"doctor printed no JSON: {result.stdout[:300]!r}"
    if not payload.get("ok"):
        return False, f"doctor reported not-ok: {payload}"
    programs = payload.get("programs")
    if not isinstance(programs, dict) or not programs:
        return False, f"doctor reported no programs: {payload}"
    found = sum(1 for path in programs.values() if path)
    return True, f"doctor reported ok, {found}/{len(programs)} programs found"


def check_window(exe):
    """Start the instance, offscreen, and prove it *is* an instance.

    `--gui` is the argument that means "there is no instance to talk to, so be one". With
    no argument the program forwards "open the settings window" to whatever is already
    running and exits, which is the opposite of a startup check.

    The assertion is the socket. Qt puts a `QLocalServer` socket in the temp directory
    named by `TMPDIR`, so a socket appearing *there* — while this process is still alive —
    says three things at once: Qt came along, the application got as far as listening, and
    it is the process doing it rather than a request forwarded to the real application.

    Not the startup line, which is what a first attempt used and why it failed: a frozen
    application's stdout is block-buffered when it is not a terminal, and `PYTHONUNBUFFERED`
    did not change that, so "no system tray found, running anyway" sits in the buffer until
    the process exits. A signal that arrives only on exit cannot prove anything about a
    process that is supposed to still be running.

    On Windows the socket is a named pipe and leaves no file to look at; the process
    staying alive for the whole window is all that is checked there, and this says so
    instead of implying a proof it does not have.
    """
    env = sandbox_env()
    proc = subprocess.Popen([str(exe), "--gui"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, env=env)
    tmp = pathlib.Path(env["TMPDIR"])
    deadline = time.time() + 30
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                return False, f"exited {proc.returncode} during startup"
            if sys.platform == "win32":
                time.sleep(2)
                break
            if list(tmp.iterdir()):
                break
            time.sleep(0.2)
        if proc.poll() is not None:
            return False, f"exited {proc.returncode} during startup"
        if sys.platform == "win32":
            return True, "still running after two seconds (named pipe, not inspectable)"
        sockets = list(tmp.iterdir())
        if not sockets:
            return False, ("alive but listening on nothing: no socket appeared in its own "
                           f"temp directory ({tmp}) in {30} s")
        return True, f"listening as itself on {sockets[0].name}, still running"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the frozen application and prove it runs.")
    parser.add_argument("--check", action="store_true",
                        help="verify the existing dist/ instead of building it")
    parser.add_argument("--dmg", action="store_true",
                        help="macOS only: package dist/dikte.app into a disk image and "
                             "prove it mounts")
    args = parser.parse_args(argv)

    if not args.check:
        build()

    exe = bundle_executable()
    if not exe.exists():
        raise SystemExit(f"no frozen application at {exe}; build first")

    size = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file())
    print(f"\nfrozen application: {exe}")
    print(f"bundle size: {size / 1e6:.1f} MB")

    failures = []
    checks = [("--help", check_help), ("doctor", check_doctor), ("window", check_window)]
    # The console-less twin is a separate executable with its own copy of the archive, so
    # it can fail on its own: start it too, where it exists (T5.4).
    if sys.platform == "win32":
        twin = exe.parent / "diktew.exe"
        if twin.exists():
            checks.append(("window (console-less)", lambda _exe: check_window(twin)))
        else:
            failures.append("diktew.exe")
            print("  FAIL  diktew.exe: the bundle has no console-less twin")
    if args.dmg:
        if sys.platform != "darwin":
            raise SystemExit("--dmg is a macOS step: hdiutil is the only tool that writes a disk image")
        image = make_dmg(DIST / "dikte.app")
        print(f"disk image: {image} ({image.stat().st_size / 1e6:.1f} MB)")
        checks.append(("dmg", lambda _e: check_dmg(image)))
    for name, check in checks:
        ok, detail = check(exe)
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: {detail}")
        if not ok:
            failures.append(name)
    if failures:
        raise SystemExit(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
    print("\nall checks passed: the bundle starts, diagnoses and runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
