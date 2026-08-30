# DECISIONS — Overlay / Voice Reliability Pass

- **Activity ordering** — chronological top→bottom; oldest `created_order` at top. `OverlayCoordinator.ordered()` returns sorted order. Newest appended at bottom per user example (meeting first → meeting top, dictation second → below, agent third → bottom).
- **Concurrent capture** — `audio.concurrent_capture_info()` / `can_concurrent_capture()` show Pulse/PipeWire, WASAPI shared-mode, and AVFoundation all allow concurrent Recorder + MeetingRecorder (server/HAL duplication). No fan-out hub required; `dikte.py:start_meeting()` keeps live dictation on shared backends, falls back to old stop-on-DirectShow. Documented per-platform rationale.
- **Durable VoiceJobs** — `voice_jobs.py` with `voice_jobs.jsonl`, atomic tmp→replace, statuses CAPTURED/TRANSCRIBED/PROCESSED/COMPLETED/FAILED_RETRYABLE, fields {id,kind,ts,status,audio_path,raw_transcript,error_stage,provider,model,duration,retry_count}; `worker.py` persists before claiming checkpoint (copy audio before CAPTURED), skips re-transcribe when raw exists, retry_checkpoint logic.
- **Audio preservation** — failed processing always retains source audio (voice_jobs.should_keep_audio override); successful keeps per policy (new default retain). History recovery shows retryable state.
- **ai_shortening_freedom migration** — deprecated in DEFAULTS, silently clamped on load, not persisted on save, folded into Editing Level 1..5 descriptions; old configs load without crash.
- **Agent retry idempotency** — `assistant.retry_ask()` checks stored messages for prior identical user turn + assistant reply; returns cached rather than re-executing when already successful (prevents duplicate side-effects).

## Concurrency Hang Fix
- **Meeting abort** — `api.Aborter` added to `MeetingPipeline`; all `transcribe_segments/cleanup` pass `aborter`; `stop()` aborts, `Aborted` mapped to `failed("Stopped.")` so `M_WORKING` never stalls 600/3600 s.
- **Progress visibility** — `M_WORKING` progress always updates overlay+tray even while dictation is busy; dictation `dismiss`/`show_done` suppressed while `M_WORKING`.
- **Live isolation** — `live_meeting_mine` separates meeting mic PCM from dictation `live`.
- **start order** — probe meeting first; drop dictation only on success + exclusive.
- **File locks** — `voice_jobs` TOCTOU closed (read→write under lock), `config` history/meetings serialized.
- **Platform probe** — `concurrent_capture_info` checks tool presence before claiming shared.

---

# DECISIONS (previous)

- **Design system freeze** — `assets/dikte.css` `:root` and `[data-theme=light]` are the single source of truth. Frozen verbatim into `ui/theme.py` as `DARK`/`LIGHT` dicts (keys `canvas`, `sidebar`, `surface`, `surface2`, `field`, `border`, `borderStrong`, `fg`, `fg2`, `fg3`, `terra`, `terraDeep`, `sage`, `sageDark`, `ok`, `warn`, `err`, `info`, `inkBtn`, `onInk`) plus `RADII` {r1:4,r2:6,r3:8,r4:12}. `stylesheet(theme)` emits one global QSS; `apply(theme)` reapplies to `QApplication`.

- **Native PyQt6 translation** — no webview. CSS grid → QHBoxLayout/QVBoxLayout/QFormLayout/QGridLayout; responsive breakpoints → scroll areas + fixed widths where spec pins px; shadows → QSS border/shadow approximations (no QGraphicsDropShadowEffect for performance); backdrop-filter → opaque mixed colour via `_mix()` helper; transitions → QVariantAnimation only for ToggleSwitch knob (140ms cubic) and Overlay tick (33ms).

- **Icon strategy** — reuse shipped assets for app icon (`icons/dikte.png|.ico` + fallback to `design/.../dikte.png`). For glyphs, port `dikte.js` `ICONS` stroke-SVG table verbatim into `ui/icons.py` and render via `QSvgRenderer` to QIcon/QPixmap (no third-party icon pack).

- **Shell architecture** — `ui/shell.py:AppShell` owns a hidden-tab `QTabWidget` (`tabs` exposed as `SettingsWindow.tabs` for test contract). Sidebar fixed 226px, brand badge 34px with terra dot, NAV list from `NAV` constant (9 items, icon + t(label)), engine card (wave 15px sageDark, label, sage chip, dot+Ready+ver). `add_page()` creates nav button + tab; `currentChanged` ↔ nav sync preserves QSS `active=true` property.

- **Theme behaviour** — persisted via `conf["ui_theme"]` written on `SettingsWindow._save()` and read on `__init__` (`dark` fallback). `Config.load` filtered by `DEFAULTS` so key is in-memory only until `DEFAULTS` is extended; documented as runtime-plus-persist intent in VERIFICATION gap. `ui/shell.py:set_theme()` updates button icon/text; `ui/theme.apply()` refreshes global QSS.

- **Config round-trip preservation** — every widget maps to identical keys as before (see `tests/test_ui.py:CHANGED`). `_load()`/`_save()` cover all 60+ settings; file settings (`file_timestamps`/`file_cleanup`) also remember via `file_timestamps.toggled`/`file_cleanup.toggled` signals (`_remember_file_choices`).

- **Provider registry** — `settings_ui.py:_providers_group/_built_in_rows/_rebuild_custom_rows/_refresh_providers` renders one row per provider definition (built-ins + `user/*` gateways). Custom gateways keep keys in `providers[].keys` and models in `providers[].models`; `_testers` holds (button,label) per provider for version/test results off-thread.

- **Page ownership** — one module per prototype screen under `ui/pages/` with `build(window)` returning scrolled widget and installing `window.*` attributes needed by tests/save path. `general.py`, `providers.py`, `cleanup.py`, `agent.py`, `meeting.py`, `minutes.py`, `audiofile.py`, `shortcuts.py`, `history.py` map 1:1 to prototype pages; `overlay.html` maps to `overlay.py` states, not to a settings tab (no provider duplication).

- **Overlay visual equivalence** — `overlay.py` kept lightweight canvas painting; colours mapped to prototype tokens (REC #F04E52 ≈ terra, BUSY #78AAFF ≈ info, OK #50CD8C ≈ ok, etc.). Meeting dual waveform kept; the initial second-pass contract used BARS=17 and HEIGHT=48, with MIN/MAX width and stacking via `below` + GAP=10 preserved.

- **Secrets** — `providers.mask()` is sole display form; `tests/__init__.py` env scrub retained; `_key_fields` for built-ins store in QLineEdit with Password echo, custom keys via `ProviderKeysDialog` (masked list).

- **Out-of-scope deviation** — prototype `history.html` search/seg filter and `minutes.html` rich transcript pane not fully ported; kept as simple QListWidget + viewer to avoid speculative backend invention; noted as explicit fidelity gap rather than hidden.

---

## 2026-08-26 Waveform + pause/resume

- **PCM-session segmentation** — chosen over WAV concat because `audio.Recorder` already holds cumulative `bytearray _buffer` + `list _rms`; pause terminates only the platform `Popen` subprocess and pump thread, keeping buffer/rms/session config. Resume starts a fresh `Popen` with remaining budget (`_max_bytes - len(_buffer)`) and appends into same buffer. Final `stop()` does one `write_wav()` → one `stopped(path,duration,rms)` to preserve downstream pipeline contract. Never byte-concatenate WAV headers.

- **Stale proc / race** — pause/stop capture local `proc` ref + generation token `_gen`; `_pump` validates token before emitting level/rms, deliberate segment end sets `_stopping` so it is not mis-reported as `failed`. No sleeps in happy path.

- **Waveform model** — small `WaveformState` helper in `overlay.py`: `deque(maxlen=BARS)` of `(ts, raw, smoothed)`, silence gate `raw <= 0.045` → target `0.015` baseline, soft-knee to avoid jump, attack `EMA α=0.55` fast, release `α=0.12` softer, center envelope `[0.50,0.58,0.67,0.80,0.93,1.0,0.93,0.80,0.67,0.58…]` * smoothed level, fixed x positions, tiny `0.018` baseline. History only from `push_level()`.

- **Reveal** — cubic ease-out `1-(1-t)^3`, 220ms, clips waveform drawing to expanding `half_width = full * eased`; timer uses accumulated active time only, reveal resets on each new session.

- **Pause timer** — `accumulated_ms` + `active_segment_clock (QElapsedTimer)`; start: `acc=0, clock.restart()`; pause: `acc+=clock.elapsed()`; resume: `clock.restart()`; display `acc/1000 + (clock.elapsed()/1000 if RECORDING else 0)`. `max_seconds` applies to `len(_buffer)/RATE`, not wall clock.

- **Interactive overlay** — `Overlay(interactive_live=True)` for dictation/ask live pills sets `WindowStaysOnTop|Tool|Frameless|DoesNotAcceptFocus|WA_TranslucentBackground` but *not* `WindowTransparentForInput`; hit-test custom rounded rect for Pause/Resume button, hover via `mouseMoveEvent`, emits `pauseRequested/resumeRequested`. Busy/done overlays remain transparent for input. No focus stealing (`NoFocus`, `WA_ShowWithoutActivating`).

## 2026-08-26 Overlay UI/UX + Performance Pass

- **Jank root cause** — the previous 33 ms timer called `update()` for every
  live tick and stayed active for paused and static result states; paint also
  rebuilt bar geometry, display-level lists, fonts, colors, and timer text.
  The previous action control was a 64x24 text button, and resume called
  `show_recording()`, resetting the visual session.
- **Scheduler** — retained one QTimer but made it state-aware: 25 ms for reveal
  or meaningful live changes, 120 ms for quiet live indicator cadence, 90 ms
  for busy, and stopped for hidden/paused/static states. Level signals only
  update the waveform model and dirty flag; paint requests target dirty regions.
- **Geometry/cache** — locked 17 bars, a fixed timer region, and a fixed 38x38
  action hit target. `_layout()` caches logical regions and bar x/width values
  and invalidates on resize/state-slot changes. Timer text is reformatted only
  when the displayed second changes.
- **Icons/visual hierarchy** — reused `ui/icons.py` pause/play SVGs through a
  cached `QSvgRenderer`; the action has a 30x30 visual surface and no label or
  layout-changing animation. Recording is terracotta, paused is sage/neutral,
  and silence stays as a small stable baseline.
- **Resume continuity** — `Overlay.show_resumed()` returns the same visual
  session to live mode without resetting timer, reveal, or overlay geometry;
  `Dikte.resume_recording()` uses this API for dictation and agent recording.

## 2026-08-26 Waveform smoothness follow-up

- **Root cause** — `audio.Recorder` emits one peak per 1024-frame chunk
  (~64 ms), while the overlay paints every 25 ms. The previous model applied
  smoothing only when a signal arrived, so three visual frames could repeat
  exactly the same height.
- **Decision** — keep the lightweight QPainter renderer and split the waveform
  into an audio-updated target plus a render-frame-updated display value. This
  preserves the no-fake-motion and no-conveyor-belt contract while making the
  existing center-weighted bars move continuously.
- **Library review** — PyQtGraph's `PlotDataItem` is designed for general 2D
  data and offers downsampling, but it is not installed and would add a
  third-party plotting stack to this small always-on-top Qt widget. The native
  QPainter/QTimer path is smaller and better matched to this surface.

## 2026-08-26 Wide flowing waveform follow-up

- **Visual direction** — the reference mockup calls for a wider 72 px pill,
  a circular action control, and a waveform that reads as time flowing from
  right to left. The live edge is therefore the rightmost bar; older samples
  remain visible to its left with a subtle age fade.
- **State model** — `WaveformState` now keeps a bounded row of 31 gated sample
  targets and interpolates each bar toward its shifted target row on the one
  visual scheduler. The recording/audio pipeline and pause semantics remain
  unchanged.
- **Preview parity** — `ui/pages/overlay.py` uses the same 520×72 geometry,
  31-bar direction, 76 px timer slot and 40 px circular action surface.

---

## 2026-08-26 Master Stabilization Pass

- **Waveform** — verified existing `WaveformState` (gate 0.045→0.015, attack 0.55/release 0.12, frame steps 0.28/0.14, 31-bar chronological history, per-bar interpolation, 220ms reveal) satisfies decreasing-volume smoothness, silence baseline, bounded history, no fake motion. No constant tuning; kept QPainter single-timer architecture; added regression for volume steps and three-identical-frame check.

- **Dropdown chevrons** — root cause: `QComboBox::drop-down {border:none;width:22px}` hid default arrow and `QComboBox::down-arrow` had no `image`. Fix: generate per-theme 14px chevron PNG via `ui/icons` `chevD` in `config.DATA_DIR/dikte-chevron-*.png` (forward-slash URL, no shipped asset dependency), embed `image: url(...)` in `ui/theme.stylesheet()` for enabled/disabled, width 26px drop-down, re-generated on `apply()`. Keeps editable/disabled/popup behavior; contrast via `fg2`/`fg3`.

- **Theme parity** — audited `ui/theme`, `ui/widgets`, `ui/shell`, `ui/pages/*`, `settings_ui`, `overlay`, `ui/thinking`. Removed hard-coded `#ff6b6b` error color (now `palette()["err"]`), fixed `ui/thinking` inline `#82B9CE`/`#A8BCB5` via `_apply_theme()`, kept global QSS as source of truth. Runtime `SettingsWindow._toggle_theme` now reapplies `theme.apply()`, updates `AppShell`, refreshes top-level `Overlay`/`ThinkingPopup` and in-window widgets via `_refresh_palette`/`_apply_active`/`_apply_theme` plus polish. Provider grid hiding at `<1080` removed (was hiding Deepgram key at default 1000px).

- **Providers / Agent model selection** — `providers.py` remains source of truth. Added `normalize_models()` helper (deduplicate, current first, defaults, natural case-insensitive sort) for generic lists; CLI catalogs keep their own ordering (Claude aliases, Codex current+fixed). `SettingsWindow` now has stashed `_pending_*_provider` guards to drop stale async results, disables button while fetching, preserves custom text, uses `normalize_models` for transcribe/meeting/gateway, keeps per-provider boxes visible via `_assistant_provider_changed`/`_meeting_provider_changed`. Meeting page upgraded: `meeting_model_row` container with `Fetch model list` button and `meeting_models_label`; `agent` gateway now has `refresh_assistant_gateway_models`. Local LLM case uses `installed_llm_models` directly; HTTP gateways use `providers.fetch_models` TEXT.

- **Provider Test** — Deepgram key editor restored (grid column not hidden), test uses `api.deepgram_key_status` low-cost silent WAV and never displays raw key. CLI tests now report `version + (model)` (e.g. `Claude Code found: 2.1.0 (sonnet)`) via `claude_models`/`codex_models`/`agy_models` first entry, without breaking existing version substring checks. Local tests keep `conf.local_whisper_ready()` and `program_path`+model checks.

- **Meeting sorting** — meeting provider change preserves stored/manual model, uses `normalize_models` for deterministic ordering; local uses sorted installed LLM models, HTTP uses TEXT catalog; fetch failure preserves standing list; no silent routing of CLI provider into minutes path.

- **Overlay Stop & larger hit** — `Overlay` now has `_STOP_HIT=48`, `_ACTION_GAP=8`, `_ACTION_SLOT=108` (≈1.5×72), group rect hosts Pause (48) + Stop (48) with 8 gap; `_pause_button_rect` and `_stop_button_rect` share group, fixed geometry across pause/resume, hover/pressed per-button. `stopRequested` signal wired in `dikte.py` to `stop_recording()` (finishes, not discard; retains buffer, proceeds to transcription). No focus stealing, layout clipping avoided via `available` recalculation with new slot; preview updated to show both circles.

- **Thinking panel** — `Overlay` adds `_thinking_text` (max 180, elided), `_THINKING_HEIGHT=36` + `_THINKING_GAP=10`, `set_thinking_status(text)`/`clear_thinking()` + `thinkingChanged` signal, `paintEvent` draws small secondary panel above main pill only when `state=="busy"` and text non-empty (follows corner, no focus, long text elided, no raw stderr). `dikte.py` connects `ask_pipeline.stage` → `_on_ask_thinking` (fallback `Agent is thinking…`, sanitized) → `ask_overlay.set_thinking_status`, and clears on finished/failed/cancelled and in `_finish`/`_conceal`. Existing `ThinkingPopup` kept for detailed log, its `_apply_theme` refreshed on toggle.

- **Markdown export** — `ui/pages/minutes.py` adds `Save as .md` button; `SettingsWindow._save_minutes_md` copies canonical `cfg.meeting_paths(base)[0]` UTF-8 document (not viewer text), uses `QFileDialog.getSaveFileName` with filesystem-safe `title|base` sanitized (`[\\/:*?"<>|]`→`_` plus length 60) default in `MEETINGS_DIR`, handles no selection/missing/permission/cancel, appends `.md` if needed, status label via `t()`.

- **i18n** — added `Stop recording`→`Kaydı bitir`, `Save as .md`→`.md olarak kaydet`, `Markdown files`, `Pick a meeting first.`, `Agent is thinking…`→`Ajan düşünüyor…`, `No models found.` and refreshed `thinking`/`minutes` strings; placeholder parity kept.

- **No new deps** — kept PyQt6+stdlib, no QWebEngine, no PyQtGraph, reused existing `providers.*` discovery, existing `api`/`assistant` stage callbacks.

---

## 2026-08-26 Follow-up — Engine card, wheel, shortcuts centralization

- **Engine card** — `ui/shell.py:AppShell` `_engine_card` changed from `@staticmethod` to instance method storing `_engine_model_label`/`_engine_chip`; added `set_engine_model(provider_label, model_text)` showing `Provider · model` (truncated 28) with tooltip. `settings_ui.SettingsWindow._refresh_engine_card()` reads `transcribe_provider`/`transcribe_model`/`local_whisper` and chosen custom model, called after `_load`, on `transcribe_provider.currentIndexChanged`, `transcribe_model.currentTextChanged`, `local_whisper.changed`, and in `_provider_changed`. Sidebar now reflects selected transcribe target instead of static "Whisper Local".

- **Dropdown wheel** — root cause: `QComboBox` changes value on wheel even when hovered without focus, causing accidental model/shortcut changes. Fix: monkey-patched `QComboBox.wheelEvent` at module import in `settings_ui.py` to ignore wheel when `not hasFocus()` (calls `event.ignore()`), otherwise delegates to original. Applies globally to all combos (settings, providers, shortcuts) without subclassing each instance; preserves keyboard and focused wheel behavior.

- **Shortcuts centralization** — `hotkey.SHORTCUTS` already defines 4 verbs (toggle, cancel, ask, meeting) but `ui/pages/shortcuts.py` only showed 2. Added `ask` ("Ask Claude" placeholder `Ctrl+Alt+A`) and `meeting` ("Record a meeting" placeholder `Ctrl+Alt+M`) rows to `shortcuts.py:build`. `settings_ui._shortcut_row` now handles duplicate `which` (ask/meeting appear both in Agent/Meeting pages and Shortcuts tab) by keeping canonical entry and syncing extra row via `currentTextChanged` bidirectional signals; `_shortcut_rows` keeps canonical, `_shortcut_rows_extra` holds extras, `_refresh_shortcut_status` and save iterate canonical (synced). Ensures all shortcuts are editable centrally and also visible in their feature pages without save divergence.
