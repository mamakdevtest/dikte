# WORKLOG.md

- 2026-08-21 11:05 - Inspected git repository status, branch, and commits.
- 2026-08-21 11:06 - Ran unittest baseline (1009 tests passed).
- 2026-08-21 11:07 - Analyzed Settings Save crash root cause, startup settings logic, popup performance bottlenecks, and window icon resolution.
- 2026-08-21 11:10 - Created context ledger and drafted implementation plan.
- 2026-08-21 11:12 - Implemented `_app_icon()` / `app_icon()`, Windows AppUserModelID, startup Settings auto-open, and deferred load in `settings_ui.py` and `dikte.py`.
- 2026-08-21 11:15 - Fixed tray signal duplication and wrapped `_apply_settings` in try-except boundary.
- 2026-08-21 11:21 - Added regression tests in `test_ui.py` and `test_cli.py`, fixed non-interactive stdin pipe mocking in CLI test runner.
- 2026-08-21 11:22 - Ran full test suite (1016 tests passing, 0 errors, 48 skipped). Ran `graphify update .`. Updated context ledger.
- 2026-08-21 11:35 - Diagnosed startup failure: `app_icon` helper had been declared with 0 indentation in `dikte.py`, accidentally truncating `class Dikte` definition and causing `AttributeError: 'Dikte' object has no attribute '_on_level'`. Moved `app_icon()` to module level before `class Dikte`. Verified application initialization and test suite pass (1016 tests OK). Re-ran `graphify update .`.
- 2026-08-21 11:42 - Diagnosed Settings Save application closure on Windows: `WindowsHotkey.stop()` was calling `PostMessageW(0, 0x0012, 0, 0)` (WM_QUIT), which on Windows posts `WM_QUIT` to the calling thread's message queue (the Qt main UI event loop). When `_save()` ran `applied.emit()` -> `_apply_settings()` -> `WindowsHotkey.start()` (which calls `stop()`), Qt popped `WM_QUIT` and terminated the entire application. Re-implemented `WindowsHotkey` to run in a thread-isolated message queue using `PostThreadMessageW(thread_id, WM_QUIT, 0, 0)`. Added unit tests in `tests/test_hotkey.py`. Re-ran full test suite (1020 tests OK). Re-ran `graphify update .`.

