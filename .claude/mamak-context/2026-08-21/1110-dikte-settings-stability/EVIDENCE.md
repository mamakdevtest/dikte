# EVIDENCE.md

## Test Suite Baseline
- `"" | python -m unittest discover`
- Result: Ran 1009 tests in 39.687s. OK (skipped=48).

## Final Test Suite Verification
- `"" | python -m unittest discover`
- Result: Ran 1016 tests in 38.195s. OK (skipped=48).
- UI Test Suite (`python -m unittest tests/test_ui.py`): 77 tests OK.
- CLI Test Suite (`python -m unittest tests/test_cli.py`): 85 tests OK.

## Discovered Root Causes & Resolutions
1. **Settings Save Crash**:
   - *Cause*: `SettingsWindow._save()` emitted `applied.emit()` directly without catching runtime apply errors; `_apply_settings` in `dikte.py` had no error boundary. Tray `activated.connect` was added repeatedly on each apply.
   - *Fix*: Single tray connection in `Dikte.__init__`, try-except error boundary in `_apply_settings()`, safe emission in `_save()`.
2. **Startup Settings Not Showing**:
   - *Cause*: In `dikte.py` `run_app()`, when `command == ""` on normal launch, `open_settings()` was conditioned on `not conf.transcribe_ready()`.
   - *Fix*: Changed condition to `command in ("", "settings")` to guarantee Settings opens whenever Dikte is launched normally.
3. **Settings Popup Latency**:
   - *Cause*: Synchronous full disk reads (`_load_history`, `_load_minutes`), shortcut status queries, and assistant status checks ran inside `__init__` before first paint.
   - *Fix*: Deferred non-critical initialization via `QTimer.singleShot(0, self._deferred_load)`.
4. **Missing Windows App Icon**:
   - *Cause*: `app.setWindowIcon(...)` and `SettingsWindow.setWindowIcon(...)` were never called. No AppUserModelID set for Windows taskbar grouping.
   - *Fix*: Added `app_icon()` / `_app_icon()` resolution functions, set `SetCurrentProcessExplicitAppUserModelID("mamak.dikte")`, and set window icons on application and dialog.
5. **Graphify Graph Synchronization**:
   - Updated with `graphify update .` -> 2438 nodes, 4374 edges, 148 communities updated.

