# Dikte Settings & Stability Implementation Plan

This plan details the resolution of 5 core objectives outlined in `promt-v2.md`:
1. **Fix Critical Settings → Save Crash**: Isolate atomic config saving from runtime application, establish safe Qt slot error boundaries, and provide clear user feedback on apply errors.
2. **Auto-open Settings on Startup**: Automatically present the Settings window on normal GUI startup while preserving headless CLI and verb actions (`toggle`, `ask`, `meeting`).
3. **Optimize Settings Popup Latency**: Defer nonessential disk I/O, device scans, and status queries until after the initial window paint.
4. **Fix Windows Application/Window Icon**: Configure application-level and window-level icons using `icons/dikte.ico` / `icons/dikte.png` and configure Windows AppUserModelID.
5. **Cross-Platform Stability Audit**: Fix duplicate tray signal connections, prevent stdin blocking in headless/test environments, and add comprehensive deterministic regression tests.

---

## User Review Required

> [!NOTE]
> - Normal GUI launch (e.g. running `dikte` with no arguments, or clicking desktop shortcut) will now display the Settings window automatically upon launch.
> - Direct action verbs such as `dikte toggle`, `dikte ask`, `dikte meeting` or headless CLI operations will continue to run without popping up the Settings UI.
> - If settings are saved to disk successfully but runtime changes (like local model server restart or hotkey registration) fail, the user will receive a clear informative warning dialog rather than a crash or false success.

---

## Proposed Changes

### Core Application & UI Lifecycle

#### [MODIFY] [dikte.py](file:///f:/_Work/_MamakGames/MamakHub/projects/Desktop/dikte/dikte.py)
- **App Icon Helper**: Add `app_icon()` helper function that resolves `icons/dikte.ico` (multi-size Windows source) or `icons/dikte.png` gracefully.
- **Application-level Icon & Windows AppUserModelID**: In `run_app()`, call `app.setWindowIcon(app_icon())` and set Windows `SetCurrentProcessExplicitAppUserModelID("mamak.dikte")`.
- **Startup Settings Behavior**: In `run_app()`, when `command in ("", "settings")`, automatically call `dikte.open_settings()`.
- **Tray Signal Cleanup**: In `_build_tray()`, do not re-connect `self.tray.activated.connect(self._tray_clicked)` on every settings apply; connect once during initialization in `__init__`.
- **Apply Settings Error Boundary**: In `_apply_settings()`, wrap server lifecycle transitions, tray updates, and hotkey listeners in robust error handling so operational failures cannot escape the Qt slot or crash the application.

#### [MODIFY] [settings_ui.py](file:///f:/_Work/_MamakGames/MamakHub/projects/Desktop/dikte/settings_ui.py)
- **Window Icon**: In `SettingsWindow.__init__()`, set `self.setWindowIcon(app_icon())`.
- **Save vs Apply Error Handling**: In `SettingsWindow._save()`, wrap `self.applied.emit()` inside a try-catch block. Distinguish between:
  1. Config save failure (`OSError` on disk write) -> warning dialog, abort.
  2. Config save success, but apply error -> warning dialog explaining settings saved to disk but runtime apply encountered error.
  3. Both save and apply success -> information dialog "Saved successfully."
- **Fast First Paint (Deferred Init)**: In `SettingsWindow._load()`, defer heavy non-essential initializations (`self._load_history()`, `self._load_minutes()`, `self._refresh_shortcut_status()`, `self._refresh_assistant_status()`) using `QTimer.singleShot(0, ...)` so the Settings shell renders immediately.
- **Deduplicate Audio Source Listing**: Avoid calling `audio.list_sources()` redundantly.

#### [MODIFY] [cli.py](file:///f:/_Work/_MamakGames/MamakHub/projects/Desktop/dikte/cli.py)
- In `cmd_ask()`, ensure `sys.stdin.read()` is not called when stdin is non-interactive without text unless specifically piped/ready, avoiding test/background hanging.

---

### Regression & Unit Tests

#### [MODIFY] [tests/test_ui.py](file:///f:/_Work/_MamakGames/MamakHub/projects/Desktop/dikte/tests/test_ui.py)
- Add deterministic test verifying that an operational exception in `applied` signal slot does not crash `SettingsWindow._save()`.
- Add test verifying that the persisted-vs-applied error reporting contract functions properly.
- Add test verifying unchanged and repeated Save idempotency.
- Add test verifying deferred loading of history/minutes/status in `SettingsWindow`.
- Add test verifying `setWindowIcon` resolution.

#### [MODIFY] [tests/test_cli.py](file:///f:/_Work/_MamakGames/MamakHub/projects/Desktop/dikte/tests/test_cli.py)
- Add tests verifying startup command decisions: `""` and `"settings"` open Settings, while `"toggle"`, `"ask"`, `"meeting"` and headless commands preserve their intended behaviors.

---

## Verification Plan

### Automated Tests
1. Run full unit test suite:
   ```powershell
   "" | python -m unittest discover --verbose
   ```
2. Run targeted UI & CLI tests:
   ```powershell
   python -m unittest tests.test_ui tests.test_cli tests.test_config -v
   ```
3. Run git diff check:
   ```powershell
   git diff --check
   ```

### Manual & Runtime Verification
1. Launch Dikte GUI (`python dikte.py --gui`) to verify Settings window appears automatically on startup with proper Dikte icon.
2. Verify Settings popup opens swiftly.
3. Test saving with unchanged settings, changed harmless settings, and simulate/test local provider reconfigurations.
4. Verify tray responsiveness and verify closing/reopening Settings.
5. Verify headless CLI commands (`python dikte.py --help`, `python dikte.py status`, etc.) remain headless.

