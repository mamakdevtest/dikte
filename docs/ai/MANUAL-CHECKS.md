# MANUAL CHECKS — the protocol a person runs, per OS

Phase 5's verification line says: *a downloaded artifact from each OS starts, records,
transcribes, pastes and quits; each run recorded in `VERIFICATION.md` with the OS and
version it was observed on.* This is how that record gets made, and what it has to contain
to be worth anything.

**Why a person and not the CI job.** `packaging/build.py` proves the bundle starts,
imports, diagnoses itself and listens on its own socket. Everything below needs hardware
the runners do not have: a microphone, a desktop session, a permission dialog, another
application to paste into, and a human to notice that the text landed in the wrong window.
The three defects Phase 5 has produced so far (N8's socket theft, N9's invisible output,
T5.1's `NameError`) were all found by *starting the thing*; none of them would have been
found by reading the spec.

## How to record a run

One section per OS in `docs/ai/VERIFICATION.md`, in the form:

    ## <OS> <version> — <artifact> (<commit>)
    Date, who ran it, where the artifact came from (CI artifact name or the command that
    built it). Then, per row below: the observation, not "works".

`✓` alone is not a record. `✓ Ctrl+Space in Kate inserted "hello world"` is. If a step
failed, it stays in the table with what it printed — this project's rule is that a plan
which quietly edits itself is worse than one that shows where it was wrong.

## The rows

| # | Gesture | Expected | Why automation cannot do it |
|---|---|---|---|
| 1 | Install from the artifact alone (no checkout, no `pip install PyQt6`) | The application starts and the tray icon appears | The whole point of T5.1; `build.py` starts the bundle in the developer's environment, which is not the same thing |
| 2 | `dikte doctor` from a terminal | Every missing tool is listed as missing; exit code 0 | Needs a machine that is honestly missing something |
| 3 | Grant the microphone when the OS asks (macOS: TCC prompt; Windows: Settings → Privacy → Microphone) | Recording works *after* the grant, and the prompt names Dikte, not Python | The permission belongs to the bundle's identity, not to the interpreter (T5.5) |
| 4 | Grant Accessibility (macOS only, for the paste path) | Dikte appears in System Settings → Privacy → Accessibility | Nothing on Linux has this step; a missing grant looks like "paste does nothing" |
| 5 | Press the global hotkey from another application (start in Kate/Notepad/TextEdit) | Recording starts without focusing Dikte; the second press pastes into that window | Requires a second application and a window manager |
| 6 | Dictate a real sentence | Text appears in the focused window, transcribed and cleaned per settings | Needs a microphone; the transcription path is only mocked in tests |
| 7 | Start a meeting (macOS needs BlackHole or Loopback) | The minutes are written; the meeting appears in the Meetings list | Needs a loopback audio device (T5.5's note) |
| 8 | Change a setting, quit, relaunch; then `dikte config` in a terminal | The setting is still there, and the two agree | Two processes, one file (the T4.9 locking decision) |
| 9 | Launch the app twice (double click the icon while it runs) | The second launch opens the dashboard of the first and exits 0 | N8's fix, verified on Linux in a sandbox; the desktop-entry path is what changes per OS |
| 10 | Restart from the tray, and quit from the tray | It comes back as the frozen app (not as a Python script); quit leaves no process | The `launch_command` paths, which broke silently in a bundle until T5.1 |
| 11 | Force a failure with a wrong API key, then look for the message | It is visible *somewhere a person can find it*: in the window, and — when there is no terminal — in `DATA_DIR/dikte.log` | N9 is answered: `dikte.keep_a_log()` tees the output into that file and `dikte doctor` prints its path. What this row checks is the part automation cannot: that the file is where a person would actually think to look |
| 12 | Uninstall by the OS's own means (Windows: Settings → Apps; Linux: remove the package; macOS: drag to Trash) | No leftover process, no leftover startup entry | Only the OS's installer knows what it installed |
| 13 | Delete `~/.config/dikte/config.json`, then start the application | The first-run wizard appears; a second start does not show it again; the dashboard's **Set up** button and `dikte setup` bring it back | The wizard's own steps are the manual part: step 1 wants a microphone, step 3 waits for a real dictation, and step 2 downloads a model — none of which CI has |

## Per-OS notes that are not yet answers

- **Linux**: rows 1–10 were run against the frozen bundle on 2026-09-13 in a sandbox
  (`probe_double_start.py`, `packaging/build.py`) except 3, 5, 7, 11, 12 and 13, which need a
  desktop session, a microphone or a package. The `Indicator` page's XWayland fallback
  (X2) is a Linux-only row that belongs here once a Wayland session is available.
- **macOS**: nothing has been run. The `.app` bundle is built by the spec and the
  microphone usage string is in it (`NSMicrophoneUsageDescription`), but no permission
  dialog has ever been seen. Signing and notarisation are not pursued (2026-09-13,
  the user's call), so the image Gatekeeper refuses on a machine that did not build it is
  the intended deliverable.
- **Windows**: nothing has been run. T5.4 is in: `packaging/dikte.spec` produces a
  console-less `diktew.exe` twin next to `dikte.exe`, and `install.ps1` prefers the frozen
  bundle in `dist\dikte\` when one is there (skipping the interpreter discovery, the version
  check and the PyQt6 install in one block) with `-NoLaunch` for CI. What has never run is
  the installer itself — `pwsh` is not on the development machine, so the row above is the
  first real test of it, and `build.yml`'s `windows-latest` step is the first automated one.

## What stays unverified if these are never run

Everything in the rows above, and with them every sentence in the README that promises a
platform. That is the whole reason this file exists rather than a claim in a commit
message.
