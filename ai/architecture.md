# Dikte Architecture (canonical)

Single source of truth for how Dikte is built. Derived from live code on
master @ d84a6cd (2026-08-25). Live source always wins over this file.
Deep module reading order for newcomers: `dikte.py` → `cli.py` → `config.py`
→ `worker.py` → `providers.py`.

## Product identity

Dikte is a local-first voice dictation / transcription / cleanup tool:
press a hotkey, talk, press again; the recording is transcribed locally by
default, a model cleans the text up, and the result is pasted into whatever
window has focus. Targets Windows, Linux (KDE Plasma 6 Wayland first,
GNOME X11 supported), macOS. Daily-driver quality bar: correctness and
repeatability beat quick patches.

## Hard constraints

- Dependencies: Python standard library + PyQt6 only. Python >= 3.11.
  Do not add third-party imports without an explicit user decision.
- Terminal CLI behavior must stay explicit and visible; GUI must never
  leak into headless verbs.
- Linux semantics are preserved when fixing Windows behavior, and vice versa.
- Secrets (API keys, provider tokens) are never logged, printed, or committed.

## Module map

| Module | Responsibility | Key symbols |
|---|---|---|
| `dikte.py` | App shell: tray icon, state machine, IPC socket host, signal handling, excepthook | `Dikte`, `main`, `run_app` |
| `cli.py` | Terminal UI; every verb has a `cmd_*`; argument parser and dispatch | `build_parser`, `run`, `launch_gui`, `out/note/fail` |
| `config.py` | JSON settings + history/meetings store; atomic save; platform dirs; legacy migration | `Config`, `_directories`, defaults |
| `settings_ui.py` | Qt settings dialog (`QDialog`); local-model box; provider dialogs | `SettingsWindow`, `LocalModelBox`, `ProviderDialog` |
| `worker.py` | Dictation chain transcribe→cleanup→clipboard→paste in a daemon thread | `Pipeline` (QObject signals: stage/finished/failed/cancelled) |
| `ggml.py` | whisper.cpp / llama.cpp download + run as local servers | `Server` (lazy process, locks), `download`, `program_path`, `LocalError` |
| `api.py` | HTTP layer for transcription/cleanup/chat/model lists; tracked connections | `transcribe`, `cleanup`, `chat`, `openai_models`, `ApiError`, `Aborter`, `_Sockets` |
| `providers.py` | Provider registry: built-ins + user gateways; credentials; model catalogs | `Provider`, `definitions`, `credential`, `fetch_models`, `test_provider`, `mask` |
| `cleanup.py` | Cleanup dispatch: local llama.cpp vs CLI agent vs user gateway | `run`, `_dispatch`, `_local` |
| `assistant.py` | Agent handoff (`ask`): claude/codex/antigravity/plain-HTTP backends | `ask`, `_ask_claude`, `_ask_codex`, `_ask_antigravity`, `_ask_plain_http` |
| `meeting.py` | Two-channel meeting transcription and document building | `MeetingPipeline`, `merge_turns`, `build_document` |
| `audio.py` | Recording backends per platform; device listing; level chunks | `Recorder`, `MeetingRecorder`, `recording_command`, `sound` |
| `vad.py` | Speech gate: is this recording worth an API call | `analyse`, `is_silent`, `looks_like_hallucination` |
| `filetranscribe.py` | File transcription + SRT export; chunked long files | `FileTranscriber`, `to_srt`, `split_wav` |
| `hotkey.py` | Global shortcuts: evdev (Linux), RegisterHotKey (Windows), Carbon (macOS), KDE/GNOME installers | `EvdevHotkey`, `WindowsHotkey`, `CarbonHotkey`, `listener` |
| `overlay.py` | Corner recording indicator widget | `Overlay(QWidget)` |
| `paste.py` | Clipboard write + synthetic key press per desktop | `desktop`, `press`, `copy`, `read_clipboard` |
| `ipc.py` | Single-instance link: named socket per user | `SERVER_NAME`, `send`, `command_for` |
| `hub.py` | GitHub/HuggingFace catalogs with sha256 verification + cache | `release`, `files`, `Item` |
| `i18n.py` | Code-level translation table (en/tr), locale resolution | `t`, `resolve`, `set_language` |
| `_genicon.py` | Offline icon generator (offscreen Qt) | — |

## Test architecture

- Command: `python -m unittest discover --verbose` (CI: `.github/workflows/tests.yml`,
  Linux + Windows × Python 3.11/3.12/3.13).
- ~1178 tests; only dependency under test is PyQt6; no network, no sound device.
- Offscreen Qt is pinned before any Qt import via
  `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` (tests/__init__.py).
- Sandbox before import: XDG_CONFIG_HOME/XDG_DATA_HOME/HOME redirected to a
  temp dir; env vars that could inject provider keys or change locale are
  scrubbed (tests/__init__.py).
- Fixture base `DikteTest` (tests/support.py): per-test tmp root, path patches
  for CONFIG_FILE/DATA_DIR/HISTORY/RECORDINGS/MEETINGS, blocks `os.execv` and
  network, provides `fake_urlopen` replay, `FakeCompleted`, `only_these_tools`.
- New tests must be deterministic; never depend on pixel rendering, real
  network, audio devices, or wall-clock timing margins.

## Platform split points

- Hotkeys: evdev / Win32 RegisterHotKey / Carbon; GNOME gsettings vs KDE
  kglobalshortcutsrc registration; chooser `hotkey.listener()`.
- Paste: `paste.desktop()` branches win32 SendInput / macOS CoreGraphics /
  Linux xdotool+ydotool.
- Audio: ffmpeg invocation differs per platform (`audio.recording_command`,
  Pulse/PipeWire vs AVFoundation vs DirectShow); Windows subprocess creation
  guards CREATE_NO_WINDOW.
- Dirs: `config._directories` (%APPDATA%/%LOCALAPPDATA% vs XDG).
- IPC name: uid-based on POSIX, sanitized USERNAME on Windows (ipc.py).
- Signals: plain handlers on Windows vs socketpair+wakeup-fd on POSIX (dikte.py).
- Installers: `install.sh`/`uninstall.sh`/`update.sh` and `install.ps1`/
  `uninstall.ps1` at repo root.

## Provider / gateway layer

- Registry in `providers.py`: capabilities TRANSCRIPTION/TEXT; built-ins
  include local, local-llm, deepgram, claude, codex, antigravity; retired
  built-ins ("ghosts" such as openai/groq) resurface only if existing config
  still references them; user-defined OpenAI-compatible gateways persist as
  `user/<uuid>` entries under config `providers`.
- Dispatch: transcription target via `Config.transcribe_target`; cleanup via
  `cleanup._dispatch`; assistant via `assistant.ask` (incl. plain-HTTP
  gateway mode); model catalogs via `providers.fetch_models`.
- Credentials: flat `*_api_key` fields for legacy built-ins; structured
  `providers[].keys[].secret` for registry entries; uppercase env var is a
  fallback read path. Masking (`providers.mask`, CLI `_mask`) is the only
  sanctioned display form. Never log or persist secret values.
- Local servers: `ggml.Server` starts on demand; downloads are executables
  and therefore sha256-verified against hub metadata before use.

## Startup & IPC

- `main()`: argv without `--gui` goes to `cli.run`, else `run_app`.
- Single instance: QLocalServer named per user; one JSON object each way;
  non-win32 sockets restrict access to the current user so only the same
  user can send `quit`.
- Verbs: empty/settings open Settings; toggle/ask/meeting perform their
  action via QTimer; cancel/stop/quit/restart are idempotent CLI verbs.
- Tray: QSystemTrayIcon with context menu; click toggles dictation; shutdown
  hides tray and stops local servers.

## i18n

- `i18n.t(text)` does dictionary lookup + format; source strings are English,
  Turkish table in `i18n.TR`. Languages: en + tr only. Locale resolution:
  LC_ALL/LC_MESSAGES/LANG then Windows API. UI strings added in English must
  get a Turkish entry or they will display untranslated.

## Security-sensitive surfaces (never violate)

1. Any `secret`, `*_api_key` value or its env var: never print/log/persist
   outside the config file itself; mask on display.
2. Third-party config reads are deliberately narrow: Claude settings.json is
   read only for model fields (it also holds tokens), Codex config.toml only
   for top-level `model=`.
3. Downloaded binaries require sha256 match from hub metadata.
4. Tests scrub provider-key env vars at import; keep that list current when
   adding providers.
