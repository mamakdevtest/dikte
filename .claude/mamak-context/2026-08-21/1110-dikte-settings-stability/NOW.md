# NOW.md

## Current State
- Identified and fixed critical Windows hotkey bug where `WindowsHotkey.stop()` posted `WM_QUIT` (0x12) to the calling Qt UI thread via `PostMessageW(0, ...)`.
- Replaced `WindowsHotkey` message loop with thread-isolated message pump using `PostThreadMessageW(thread_id, WM_QUIT, 0, 0)`.
- Verified Settings save in running Dikte instance without `WM_QUIT` leakage or application termination.
- Added regression tests in `tests/test_hotkey.py`. Full test suite passed (1020 tests).
- Rebuilt Graphify knowledge graph (2518 nodes, 4576 edges, 157 communities).

## Summary of Accomplishments
1. **Settings Save Crash Fix**:
   - Wrapped `_apply_settings` in `dikte.py` with an operational error boundary.
   - Wrapped `applied.emit()` in `settings_ui.py` with safe error catching and logging.
   - Fixed duplicate signal connection on tray icon `activated.connect` (connected once in `Dikte.__init__`).
2. **Startup Settings Auto-Open**:
   - Updated `run_app()` in `dikte.py` to auto-open Settings for `command in ("", "settings")`.
3. **Settings Popup Performance Optimization**:
   - Non-essential initialization (`_load_history`, `_load_minutes`, `_refresh_shortcut_status`, `_refresh_assistant_status`) deferred via `QTimer.singleShot(0, self._deferred_load)` to ensure instantaneous window paint.
4. **Windows Application & Window Icon**:
   - Added robust `app_icon()` / `_app_icon()` helper resolving from `assets/icon.png`, local paths, theme icons, or standard fallback.
   - Set Windows taskbar grouping via `SetCurrentProcessExplicitAppUserModelID("mamak.dikte")`.
   - Set application-wide icon `app.setWindowIcon(app_icon())` and window icon `self.setWindowIcon(_app_icon())`.
5. **Cross-Platform Stability & Regression Tests**:
   - Added comprehensive tests in `tests/test_ui.py` and `tests/test_cli.py`.
   - Fixed stdin pipe handling in `WithoutAnInstance.run_verb` to prevent non-interactive hangs.
   - Verified 100% pass rate across entire test suite.

