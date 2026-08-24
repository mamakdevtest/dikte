# DECISIONS.md

## 1. Settings Save vs Apply Separation
- `Config.save()` handles persistence atomically and catches `OSError`.
- `SettingsWindow._save()` emits `applied` signal within an explicit `try...except` boundary.
- `Dikte._apply_settings()` returns a structured/clean status and catches operational errors (e.g., local server stop/start, hotkey re-binding, evdev errors) so exceptions never escape Qt slots.
- If persistence succeeds but runtime apply encounters an error, the UX shows a clear warning ("Settings were saved, but some settings could not be applied: {error}") rather than a false "Saved successfully" or crashing.

## 2. Startup Settings Auto-Open
- In `run_app()`, when `command` is empty (normal GUI launch) or `"settings"`, `dikte.open_settings()` is called automatically.
- Dedicated action verbs (`toggle`, `ask`, `meeting`) execute their respective single-shot actions without opening Settings.
- Terminal CLI commands run via `cli.py` headlessly without launching the GUI settings.

## 3. Settings Popup Performance
- Defer nonessential initialization (`_load_history`, `_load_minutes`, `_refresh_shortcut_status`, `_refresh_assistant_status`) using `QTimer.singleShot(0, ...)` after the window shell is painted.
- Avoid duplicate calls to audio device listing.

## 4. Window / App Icon
- Introduce `app_icon()` helper function that resolves `icons/dikte.ico` on Windows (with fallback to `icons/dikte.png`) and theme/fallback on Linux.
- Call `app.setWindowIcon(app_icon())` and `SettingsWindow.setWindowIcon(app_icon())`.
- On Windows, set `SetCurrentProcessExplicitAppUserModelID("mamak.dikte")`.

## 5. Cross-Platform Stability
- In `Dikte._build_tray()`, do not connect `self.tray.activated.connect(self._tray_clicked)` repeatedly on every settings apply; connect once in initialization.
- In `cli.py` / `tests/test_cli.py`, ensure stdin reads do not block when run in non-interactive pipes.

