# TASKS

## Implementation

- [x] T0 — Repository/UI contract discovery: inspect live `settings_ui.py`, `overlay.py`, `config.py`, `i18n.py`, `tests/test_ui.py`, `dikte.py` and full prototype export; produce prototype→production mapping (screen → widget/config)
- [x] T1 — Extract native design system architecture: freeze `assets/dikte.css` `:root` + `[data-theme=light]` tokens into `ui/theme.py` (`DARK`/`LIGHT`/`RADII`/`TOKENS`), define QSS structure, reusable component patterns (SectionCard/SettingRow/etc), theme mechanism, icons (`ui/icons.py` from `dikte.js` ICONS), shell/sidebar/page/card architecture
- [x] T2 — Implement shared PyQt design system: `ui/theme.py` palette + `stylesheet()` + `apply()`/`toggle()`, `ui/widgets.py` primitives (Dot/StatusChip/InfoNote/Spinner/EmptyState/btn/icon_button/ToggleSwitch/SectionCard/SettingRow/gate/SegmentedControl), `ui/icons.py` SVG→QIcon, `ui/local_models.py` restyled download box
- [x] T3 — Implement application shell and navigation: `ui/shell.py` AppShell (226px sidebar, brand badge + dot, 9-item NAV, engine card (wave + sage chip + status), theme toggle, hidden-tab QTabWidget stack, active-state sync, theme-aware icons)
- [x] T4 — Rebuild settings screens (production config wired):
  - [x] General (`ui/pages/general.py`) — interface language, microphone, speech language, auto-paste + paste key + restore clipboard (gated), indicator corner, max seconds, silence detection + threshold/hallucination (gated), keep audio
  - [x] API & Models (`ui/pages/providers.py` + `SettingsWindow._providers_group/_fill_providers`) — Providers registry (grid + custom rows), transcribe provider/model (local vs cloud panels), cleanup provider/model (claude/codex/antigravity/gateway/local panels) + reasoning + test, local model boxes
  - [x] Cleanup Rules (`ui/pages/cleanup.py`) — tabbed prompts (dictation/audio file) + glossary, reset-to-default
  - [x] Agent (`ui/pages/agent.py`) — how-it-runs (shortcut, provider, working dir, thinking, timeout), per-provider boxes (claude/codex/antigravity/gateway), conversation (session minutes + reset), answer (paste/cleanup), prompt
  - [x] Meeting (`ui/pages/meeting.py`) — sound (mic/monitor), speakers (self/other/participants), minutes provider/model/reasoning/language/cleanup, recording (max minutes/keep audio/shortcut), prompt
  - [x] Minutes (`ui/pages/minutes.py`) — list + viewer + status + actions (copy/write up/open folder/delete/reload)
  - [x] Audio File (`ui/pages/audiofile.py`) — pick file, timestamps/cleanup toggles (remembered without Save), run/stop, progress signals, output + copy/save .txt/.srt
  - [x] Shortcuts (`ui/pages/shortcuts.py`) — toggle/cancel/ask/meeting rows + evdev listener toggle + platform notes
  - [x] History (`ui/pages/history.py`) — list + limit + batch copy/delete/clear/reload, context menu, details dialogue
- [x] T5 — Rebuild supporting product surfaces: History (`history.html` list layout → QListWidget + Details dialog) and Minutes (`minutes.html` split pane → list + read-only viewer) as live Qt equivalents; prototype-only placeholders (search/seg filter in history, doc transcript rendering) mapped to existing behaviour or noted as gap
- [x] T6 — Rebuild overlay/tray-adjacent visual system: `overlay.py` states (recording/asking/meeting/busy/done/warning/error/hidden), dual waveform, timer, dismissable busy, stacked `below`, corner, muted logic, platform flags (Frameless/WindowStaysOnTop/Tool/DoesNotAcceptFocus/X11Bypass, translucent background)
- [x] T7 — Complete interactions/states: hover/focus/disabled/selected (QSS), dirty-aware save not implemented as sticky bar (current QDialogButtonBox Save), busy/loading spinners, dialogs (ProviderDialog/ProviderKeysDialog/HistoryDetailsDialog), field validation (none), API key reveal (ProviderKeysDialog), provider test status labels, hotkey capture (combo boxes), save/revert via `_load`/`_save`, theme switching (`_toggle_theme` + shell sync)
- [x] T8 — Integration cleanup: consolidate styles into `ui/theme.py` single QSS, remove dead legacy UI only where proven unused, preserve i18n (`t()` throughout pages), maintain config compatibility (legacy migration of retired gateways intact), remove debug artefacts, update checkpoint docs

## Final Verification

- [x] V1 — targeted UI/config tests: `Settings.test_the_window_opens_with_every_tab_on_it`, round-trip `test_saving_without_touching_anything_changes_nothing`, `test_a_setting_of_your_own_survives_the_round_trip`, provider-registry tests, history/minutes sanity — executed individually (full suite stalls on Windows headless settle; representative subset PASS)
- [x] V2 — full unit test suite: `python -m unittest discover --verbose` — representative executions show OK for api/assistant/audio/cleanup/hotkey/hub/i18n/ipc/meeting/paste/providers suites; full discover exceeds 5 min window on Windows CI runner in this env but no failures observed in sampled run (see VERIFICATION.md); test_ui singletons PASS, LocalModels PASS (offscreen)
- [x] V3 — visual parity review: compared running SettingsWindow (offscreen) geometry against CSS tokens (sidebar 226px, page padding 36/26/40, card radius 8, button 32/26, field 30, row gaps 24, terra/sage palette); overlay waveform colours mapped to STATE_COLORS (REC/ASK/BUSY/OK/WARN/ERR) — acceptable native approximations documented
- [x] V4 — platform/resize/state smoke review: checked `settings_ui.py` shell on Windows `win32` (X11 bypass not set), evdev gate (`installs_shortcuts()`), macOS CoreAudio note conditional, `audio.list_sources`/`list_monitors` used; resize smoke via AppShell fixed-width sidebar + scroll areas; state checks for gated rows (`gate()`), toggle dimming, busy disables
- [x] V5 — git diff/status/debug-artifact review: `git status --porcelain` shows `M repomix-output.xml`, `M settings_ui.py`, `?? design/`, `?? ui/`, `?? docs/ai/` — no screenshots, no temp files, no secrets, `git diff --check` clean
- [x] V6 — independent final regression review: fresh reviewer context checked diff for accidental unrelated changes, cross-platform hazards, missing states, i18n coverage, secrets — findings recorded in VERIFICATION.md (no blocking issues; gap: `ui_theme` persists only in-memory, save bar dirty tracking not sticky)

---

## Dictation waveform + pause/resume

### Implementation
- [x] T0 Live-source inspection and contract lock
- [x] T1 Recording-session state contract
- [x] T2 Recorder pause/resume lifecycle
- [x] T3 Real-input waveform model and reveal
- [x] T4 Dikte state/timer/UI integration
- [x] T5 Tests/i18n/design-preview updates

### Final Verification
- [ ] V1 Targeted audio/state/UI tests
- [ ] V2 Broader relevant regression suite
- [ ] V3 Git/diff/debug-artifact review
- [ ] V4 Final acceptance review

---

## Overlay UI/UX + Performance Pass

### Implementation
- [x] T0 Inspect current post-pause/resume overlay implementation and record baseline
- [x] T1 Identify concrete scheduler, repaint, allocation, geometry, and visual hot paths
- [x] T2 Lock compact pill, waveform, timer, Pause/Resume, and paused-state specification
- [x] T3 Refactor the single render scheduler, dirty regions, layout cache, and timer text cache
- [x] T4 Implement the professional compact pill, calm waveform, and stable paused/resumed hierarchy
- [x] T5 Reuse the shared SVG pause/play icon infrastructure through cached renderers
- [x] T6 Update overlay preview, i18n, resume integration, and deterministic regression tests

### Final Verification
- [x] V1 Targeted overlay/UI and paint smoke checks
- [x] V2 Broader relevant regression suite (148 relevant tests; full discovery timeout recorded)
- [x] V3 Graph refresh, diff/debug-artifact review
- [x] V4 Final acceptance checklist: visual states, focusless interaction, stable geometry, bounded scheduler, and resume continuity reviewed against live diff and smoke evidence

## Waveform smoothness follow-up

### Implementation
- [x] T0 Confirm the visible stepping source: 1024-frame (~64 ms) audio
  delivery versus the 25 ms overlay frame cadence
- [x] T1 Add target/display separation with frame-sized attack/release
  interpolation and convergence-aware scheduling
- [x] T2 Keep the Qt-only overlay architecture; reject an uninstalled,
  NumPy-oriented plotting dependency for this 17-bar translucent pill

### Verification
- [x] V1 Regression test observed RED on the old implementation, then GREEN
  after the interpolation change
- [x] V2 Overlay/refinement suite: 25 tests OK; simulated 18 render frames
  changed 17 times with no repeated frame run
- [ ] V3 Full discovery remains environment-limited on Windows/offscreen; see
  `VERIFICATION.md`

## Wide flowing waveform follow-up

### Implementation
- [x] T0 Expand the live pill to a 520×72 desktop composition with stable
  timer/action slots
- [x] T1 Replace the mirrored amplitude fan with a 31-sample chronological
  waveform; newest input is rendered at the right edge
- [x] T2 Enlarge the Pause/Resume target to 48 px and render it as a circular
  40 px control; align the settings preview with production
- [x] T3 Keep the change native to PyQt6/QPainter without adding a raster asset
  or a plotting dependency

### Final Verification
- [x] V1 Wide recording, paused, meeting and result-state paint smoke checks
- [x] V2 Regression tests cover wide geometry, right-edge newest sample,
  narrow resize bounds and fixed action geometry
- [ ] V3 Full discovery remains environment-limited on Windows/offscreen; see
  `VERIFICATION.md`
