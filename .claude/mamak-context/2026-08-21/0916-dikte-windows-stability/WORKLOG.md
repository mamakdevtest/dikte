# WORKLOG

00 plan set.
01 wave1 launched: installer, subproc, download, dotcloud + savecrash (alle parallel).
- dotcloud owns only .gitignore (small).
- savecrash owns dikte.py/settings_ui.py/config.py (disjoint).

02 dotcloud COMPLETE:
- .gitignore += `.cloud/` (line 6) and `graphify-out/` (line 7)
- verified: git ls-files -- .cloud = empty; git check-ignore .cloud matches; no local dir existed so nothing to preserve
- git status now: M .gitignore, M assistant.py, M filetranscribe.py, ?? promt.md
  NOTE: assistant.py + filetranscribe.py modified by the subproc agent (in flight). promt.md is the task brief, untracked.

03 subproc COMPLETE (no-console policy, wave B):
- Added `_subprocess_kwargs()` helper (returns `{"creationflags": CREATE_NO_WINDOW}` on Windows nt, else `{}`) to assistant.py, filetranscribe.py, cleanup.py, hotkey.py, paste.py.
- Applied `**_subprocess_kwargs()` at every subprocess call site in owned files: assistant.py(_stream), filetranscribe.py(_ffmpeg), cleanup.py(run), hotkey.py(_gsettings + 2x kwriteconfig6), paste.py(6 sites incl _run_copy, osascript, open, read_command).
- audio.py already had equivalent `_popen_kwargs()`/`_run_kwargs()` — verified, no change needed.
- Verified: all edited files parse; full suite `python -m unittest discover` -> 1003 tests OK (48 skipped).

03 subproc COMPLETE (no-console):
- added _subprocess_kwargs() helper (CREATE_NO_WINDOW on nt) to each owned module: assistant.py, cleanup.py, filetranscribe.py, hotkey.py, paste.py; applied to every Popen/run site. audio.py already had it.
- decision: small per-module helper (reuse over central shared helper — keeps modules decoupled, matches repo style).
- verify: py_compile OK; unittest tests.test_audio/..._filetranscribe/..._cleanup/..._assistant = 240 tests, OK.

04 savecrash COMPLETE (Save crash):
- ROOT CAUSE: settings_ui.py::_save() called conf.save() unguarded; PyQt turns an unhandled exception in a slot into a terminated process -> Save "closed" the app on an OSError (read-only dir / full disk / AV lock on Windows).
- FIX: wrap conf.save() in try/except OSError -> QMessageBox.warning + return early (history reload + applied + saved-dialogue never run on failed save). No blanket except. config.py/dikte.py untouched.
- regression test: tests/test_ui.py::Settings::test_a_failed_write_warns_and_does_not_kill_the_app.
- verify: py_compile OK; unittest tests.test_ui.Settings = 24 OK incl new test; tests.test_ui + tests.test_config = 167 OK (1 skip).

05 installer VERIFIED-by-lead + corrected:
- Agent added: HKCU Apps&Features registration (uninstall key Dikte), UninstallString -> install-dir uninstall.ps1 copy, pythonw GUI shortcuts via New-GuiShortcut, symmetric PATH, -Purge, running-instance quit.
- LEAD FIX (real bug): `& $cmdline` with `py -3`/`pyw -3` as one space-string never resolves (call operator treats it as a single executable name). Reworked interpreter resolution: $PY/$GUI_PY as bare token + $PY_VER/$GUI_VER avoid-array splatted separately; pyw fallback; pyw -3 + pythonw beside python; .cmd shim and shortcut Arguments render selectors. Verified via pwsh harness: py -3 (split) => True (was False); parse errors 0.

06 download VERIFIED:
- ggml.py: .zip extraction for Windows releases (zipfile) with zip-slip guard; tar.gz path unchanged; Windows _is_ours_windows via QueryFullProcessImageNameW (no tasklist console). tests/test_ggml.py: +3 good tests (zip unpack, zip-slip escape, Windows pid decision via FakeKernel).
- verify: py_compile OK; unittest tests.test_ggml = 66 tests, 2 skip, 1 FAIL (test_the_last_thing_it_printed_is_available).
- FLAKY (pre-existing, environmental): fails only in full-suite on Windows (WinError 10054 ConnectionReset real socket), PASSES in isolation (ran 3x OK) and passes on base without ggml diff. Not caused by agent change.

07 verifier + final:
- Fresh verifier (verifier agent) inspected full diff, edited README.md/README.tr.md to document new Windows install/uninstall/purge. Verifier idle-notified; its report body not pulled (transcript-based). README diffs accurate vs code.
- LEAD final suite: python -m unittest discover -s tests = 1009 tests OK (48 skip; no failures; the once-flaky ggml socket test passed this run).
- Hygiene: .cloud not tracked; graphify-out/, .claude/mamak-context/, __pycache__/ ignored; no secrets in diff; git diff --check clean (only CRLF warns).
- Graphify refresh: installed CLI (0.9.14) exposes NO update/scan subcommand (only install/uninstall/query); not forced. Existing graphify-out/ left; noted honestly.
08 COMMIT+PUSH:
- Commit 95bf03d (14 files, +551/-61) on master.
- Pushed: 6fc19e7..95bf03d master -> origin/master (verified synced).
- promt.md kept untracked (task brief). .cloud/graphify-out/mamak-context/__pycache__ not staged.

09 ROUND 2 (verification-driven fixes on top of 95bf03d):
- ggml-fix: ggml.py Server._launch Popen gains creationflags=CREATE_NO_WINDOW on win32 (was 0 elsewhere). Verified 66 ggml tests OK + full 1009 OK.
- ps-fix (lead-authored after agent sandbox failed): install.ps1 copies uninstall.ps1 into install dir + UninstallString points at the COPY + InstallLocation=source; GUI shortcut uses full pythonw path. uninstall.ps1: reads InstallLocation before deleting key; python probe splits py/-3 into separate args; quit uses srcDir; PATH removal preserves other/empty entries; guarded self-copy deletion; idempotent.
- ROUND-TRIP TEST (temp dirs, real env untouched): install -> Windows-style uninstall (cmd /c UninstallString) -> idempotent 2nd uninstall = 23/23 PASS. Shortcut target = full pythonw.exe. PS parse 0 errors both files.
