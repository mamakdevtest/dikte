# GOAL

## Final goal
Rebuild Dikte's production UX/UI so that it faithfully matches the exported reference prototype in `design/Dikte-Yeniden-Tasarım-Prototipi/` as a native PyQt6 application. The result must be pixel-conscious, preserve all real functionality/config semantics, and pass the existing behavioural tests.

## Source-of-truth design directory
`design/Dikte-Yeniden-Tasarım-Prototipi/` — authoritative visual and interaction contract. Primary entries: `index.html`, `general.html`, `api-models.html`, `cleanup-rules.html`, `agent.html`, `meeting.html`, `minutes.html`, `audio-file.html`, `shortcuts.html`, `history.html`, `overlay.html`, `assets/dikte.css`, `assets/dikte.js`, `DESIGN-HANDOFF.md`, `DESIGN-MANIFEST.json`. Reference screenshots in `docs/settings-*.webp` and `docs/design-reference.md`.

## Scope
- Native PyQt6 shell: titlebar-equivalent, 226px left sidebar, navigation, engine card, theme toggle, main stacked pages
- Design tokens → `ui/theme.py` (`DARK`/`LIGHT`, `RADII`, QSS generator)
- Reusable primitives → `ui/widgets.py`, `ui/icons.py`, `ui/shell.py`, `ui/local_models.py`
- Settings pages (9): General, API and models, Cleanup rules, Agent, Meeting, Minutes, Audio file, Shortcuts, History — each built via `ui/pages/*.py` and wired to real `config.py` fields
- Provider registry UI (built-ins + user gateways, keys, model fetches)
- Overlay in `overlay.py` (recording/asking/meeting/busy/done/warning/error, stacked, dismissable)
- Tray/menu visual alignment where practical
- Dark + light theme switching
- i18n EN/TR parity via `i18n.py`

## Out-of-scope
- Embedding HTML/webview/Electron/QtWebEngine to fake fidelity
- New third-party UI dependencies (PyQt6 + stdlib only)
- Inventing backend features that prototype placeholders imply but production has no real equivalent
- Editing `design/` export or `repomix-output.xml`
- Pixel-perfect CSS effects that Qt cannot render (box-shadow approximations, backdrop-filter → opaque fallback)

## Constraints
- Python ≥3.11, PyQt6 only — no web framework
- Cross-platform (Windows/Linux/macOS) and headless CLI unaffected
- Secrets never logged/displayed/committed; masked display only (`providers.mask`)
- GUI-thread discipline, no drive-by refactors, smallest coherent diff
- Preserve `tests/test_ui.py` round-trip behaviour

## Acceptance criteria
- Navigation, card/panel/row geometry, typography, borders, radii, colours, button/field heights, active/hover/focus/disabled states match `assets/dikte.css` tokens
- Every control reads/writes the same config keys as before (see `CHANGED` in `tests/test_ui.py`)
- Provider/model fetch/test, hotkey, cleanup/meeting/audio-file flows functional
- Theme toggle works, overlay corner persisted
- All `docs/ai/TASKS.md` implementation tasks `[x]` before verification gate

## Definition of Done
- Production UI rebuilt from prototype, recognizably same product
- Native PyQt6, no extra deps, main shell/navigation match export
- Relevant settings pages match exported designs; reusable tokens used consistently
- Dark/light where applicable; overlay presentation matches `overlay.html` where supported
- Real functionality wired; config round-trip intact; provider/model/hotkeys functional
- i18n parity preserved; implementation tasks `[x]`; transition message sent; verification executed
- Full relevant unit suite passes (or failures documented); visual parity reviewed; no debug artifacts; `git diff --check` passes; no accidental unrelated changes; secrets not exposed; `docs/ai/VERIFICATION.md` contains actual results; unavoidable fidelity gaps explicitly listed

---

# Current Task: Dictation waveform + pause/resume (2026-08-26)

## Goal
Improve live dictation recording experience: silence no longer fakes waveform, real mic input drives amplitude with gate + attack/release smoothing, center-out reveal, bounded history, reliable pause/resume at capture-session level, active-time timer, and focusless Pause/Resume control on overlay while preserving existing visual language and downstream pipeline.

## In-scope
- Silence → stable tiny baseline, no sine/random/breathing
- Real `Recorder.level` → gate (silence threshold) → normalized → attack fast / release softer EMA → deterministic center-weighted bars
- Bounded deque(maxlen=BARS) timestamped (timestamp, raw, smoothed) only from push_level()
- _tick() no longer fabricates samples; only reveal progress, pulse phase, reposition, repaint
- Reveal 180-300ms cubic ease-out center→edges masking width
- Recorder: segmented PCM session, pause stops subprocess keeping buffer, resume new subprocess appending same buffer, stop → one WAV, cancel → discard, max_seconds on captured total, RMS cumulative
- Dikte: IDLE/RECORDING/PAUSED/BUSY, active vs capturing distinction, timer accumulated_ms + segment clock, stop/cancel work while paused, toggle remains stop, tray labels updated, ask recording same semantics
- Overlay: interactive_live flag, custom Pause/Resume hit-rect, no focus, signals pauseRequested/resumeRequested, show_paused inactive waveform, white timer
- i18n Pause/Resume/Paused, overlay preview update

## Constraints
- QPainter only, stdlib+PyQt6, no WAV concat, no third-party DSP, preserve platform/meeting, do not rewrite pipeline, minimal diff

## Acceptance criteria
- Waveform checklist (12 items), reveal (6), pause/resume (12), audio output (7), UX/state (9) per task matrix all verified
- Old fake-motion eliminated: _tick does not shift levels with decay

## Definition of Done (current task)
- T0-T5 `[x]`, gate sentence shown, waveform gated+smoothed+bounded+real-only, reveal center-out 220-240ms, pause/resume reliable with one valid WAV, timer active-only, overlay focusless Pause/Resume, relevant tests pass with evidence, no new dep, no debug artifact, git diff clean, VERIFICATION truthful

---

## Current Task: Overlay UI/UX + Performance Pass (2026-08-26)

### Goal
Refine the existing recording overlay into a compact, calm native pill while
reducing unnecessary scheduler wakeups, full-window repaints, hot-path object
creation, and resume-transition visual resets. Preserve the established audio,
pause/resume session, transcription, cleanup, provider, and platform behavior.

### Locked visual contract
- 72 px pill height, 24 px corner radius, 31 flowing bars with the newest
  audio sample entering at the right edge and older samples moving left
- Fixed timer region and fixed 38 px Pause/Resume hit target with a 30 px SVG icon surface
- Recording uses terracotta, paused uses sage/neutral emphasis, silence stays at a tiny stable baseline
- Resume preserves timer text and completed reveal state; it does not start a new visual session

### Performance contract
- One state-aware QTimer: 25 ms during reveal/meaningful live waveform change, 120 ms quiet live cadence, 90 ms busy cadence, stopped while hidden/paused/static
- Audio level signals update the model/dirty flag; they do not directly request a full-window repaint
- Layout bar geometry, timer text, fonts, and SVG renderers are cached outside the hot paint path

### Waveform smoothness follow-up (2026-08-26)
- Audio chunk delivery (~64 ms) is decoupled from visual frames (25 ms).
- `WaveformState.push()` records only the latest gated target; `_tick()` advances
  the display with small attack/release steps and stops the fast cadence after
  convergence.
- Qt's built-in `PreciseTimer` is used for the single 25 ms live scheduler; no
  third-party plotting or DSP dependency was added.

### Wide flowing waveform follow-up (2026-08-26)
- Live and paused recording pills use a 520×72 composition with a 48 px
  pointer target and a 40 px circular visual control.
- The waveform now keeps 31 gated samples in chronological order from left
  (older) to right (newest), with per-bar interpolation and a restrained
  left-to-right age fade so the motion reads right-to-left.
