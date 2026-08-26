# DECISIONS

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
