# Dikte — Modernization Roadmap

> Status: **proposal, not yet executed.** Nothing in this document has been
> implemented. Every finding below was produced by a read-only pass on
> `master @ ffe8a5c` on 2026-09-12 (Linux, KDE/Wayland, Python 3.14.7).
> Live source wins over this file.
>
> Turkish twin: [`ROADMAP-tr.md`](ROADMAP-tr.md)

## 0. How to read this

- **§1–§2** are findings: what is actually wrong, with the command or file that
  proves it. Nothing here is inferred from a design doc.
- **§3** answers the technology question (Python vs C++ vs something else).
- **§4** explains the single root cause behind "the interface doesn't look right".
- **§5** is the phased plan. Each phase has tasks, files, verification and a
  definition of done. Phases are ordered by *dependency*, not by appeal.
- **§7** lists the decisions only the product owner can make. They block Phase 2.

## 1. Verified baseline

Commands run, real results:

| Check | Command | Result |
|---|---|---|
| Test suite | `python3.14 -m unittest discover` | **Ran 1473 tests in 102.7 s — OK** (0 failures, 0 errors) |
| CLI smoke | `python3.14 dikte.py --help` | exit 0, 25 verbs listed |
| Runtime health | `python3.14 dikte.py doctor` | all tools found (`pw-record`, `wl-copy`, `ydotool`, `ffmpeg`, `pactl`, `kwriteconfig6`, `claude`, `codex`); Deepgram key present; codex cleanup configured; application running |
| UI capture | `python3.14 tools/shoot_ui.py --out /tmp/dikte-shots --themes blue --langs tr,en` | **60 PNGs written** — 11 pages × 2 languages + overlay/result/live/thinking/dialog states |
| Graph freshness | `graphify-out/GRAPH_REPORT.md` | built from `e240740`; **HEAD is `ffe8a5c` → stale** |
| Code size | `wc -l` | 22,792 LOC across 26 root modules + 6,383 LOC in `ui/` ≈ **29k LOC**. Monoliths: `settings_ui.py` 3,239 · `overlay.py` 2,086 · `dikte.py` 2,053 · `config.py` 1,786 |
| Silent-failure surface | `grep -c 'except Exception'` (non-test) | **313 sites** |

The suite is green. **That is the important finding**: every defect in §2 survives
a fully green 1,473-test suite, so the suite is not currently the safety net the
conventions assume it is.

## 2. Findings register

Severity: **S1** blocks a daily driver · **S2** visible degradation · **S3** polish.

### 2.1 Functional & reliability (F)

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F1 | S1 | **The current reliability pass is unfinished.** R1 (dynamic activity registry), R2 (independent meeting/dictation/agent/result overlay views), R3 (safe concurrent-capture policy), R4 (audio-before-classification), R6 (recovery UX), R7 (editing-level parity), R8 (regression coverage) and verification V4 are all unchecked. The task file itself records the reason: *"the prior static coordinator and shared meeting/dictation overlay do not provide independent simultaneous activities."* | `docs/ai/TASKS.md:13-21` |
| F2 | S1 | **313 `except Exception` sites.** AGENTS.md rules 3 and 4 require "evidence before claims" and distinguishing persisted-vs-applied failures. At this density that is not enforceable by review, and it is the mechanism by which a failed model download, a failed paste or a failed save can leave the indicator looking normal. | `grep -rn 'except Exception' --include=*.py` |
| F3 | S2 | **Three gaps recorded but not closed**: `OverlayCoordinator.update` is not triggered per `show_*`/`dismiss` (occasional position drift); `Config.data` has a partially-locked in-process read race; there is no cross-process file locking. | `docs/ai/VERIFICATION.md` "Gaps / notes" |
| F4 | S2 | **Packaging metadata contradicts itself and the product.** `pyproject.toml` declares `license = { text = "MIT" }` while `README.md` and `LICENSE` are GPL-3.0 — and PyQt6 is GPL-3.0-or-commercial, so the MIT claim is not just a typo, it is a licence conflict. `requires-python = ">=3.11,<3.14"` excludes 3.14, on which the entire suite passes locally. | `pyproject.toml:11,10` |

### 2.2 Localization (L)

| # | Sev | Finding | Evidence |
|---|---|---|---|
| L1 | S1 | **104 distinct user-facing strings reach `t()` with no Turkish entry**, so they render in English inside a Turkish UI. Measured with `tools/i18n_gaps.py`, which walks every `t()`/`_t()` literal in product code. Worst: `ui/local_models.py` (26), `ui/pages/general.py` (15), `ui/pages/meeting.py` (8), `ui/pages/providers.py` (6), `ui/pages/agent.py` (6). | `python tools/i18n_gaps.py` |
| L2 | S1 | `"Overlay/Indicator"` is a **hardcoded English literal** used as both the nav label and the page title. | `settings_ui.py:507`, `ui/pages/overlay.py:59` |
| L3 | S2 | The sidebar footer hardcodes `"Local"` and `"Ready"`. Only `"Ready: {model}"` exists in the table. | `i18n.t("Ready") == "Ready"`, `i18n.t("Local") == "Local"` |
| L4 | S2 | Untranslated strings include **runtime states and destructive confirmations**: `Checking…`, `Downloading…`, `Download stopped.`, `Fetching the model list…`, `Delete model`, `Delete {name} from this machine?`. These are exactly the strings a user must understand before losing data. | probe output |
| L5 | S2 | **Existing Turkish entries read badly.** `"Runs on" → "Şunun üstünde çalışır"` was a sentence fragment used as a form label in three pages (Agent, Meeting, API); now `"Çalıştığı yer"`. The `"Local"` chip was untranslated next to `"Local dictation" → "Yerel dikte"`; now `"Yerel"`. **Correction:** the survey also claimed a `Promtlar`/`Promptlar` spelling split — `Promtlar` appears nowhere in the repository, it was a misreading of a screenshot. The table has always said `Promptlar`. | `i18n.py:531,993`; corrected 2026-09-12 |
| L6 | S1 | **The i18n guard was a count, not a set.** `test_user_visible_strings_reach_t` asserted `len(missing) <= 104` over a scan that measured 102 — two units of slack, no way to tell a new gap from an old one (swapping one untranslated string for another keeps the number), no tightening when a gap closed, and no coverage of the `_t` alias, which is how `Local` and `Ready` — shown in the sidebar of every page — stayed invisible. Replaced in Phase 0 with an exact-set record. | `tests/test_i18n.py`, `tests/i18n_untranslated.json` |
| L7 | S3 | No locale-aware number or date formatting: durations rendered `3.2s` / `2.0 sn` (dot decimal) in Turkish, history rows showed ISO `2026-08-21 12:05:00`. **Fixed in Phase 1** by `ui/format.py`. | `blue_tr_page00.png`, `blue_tr_page09.png` |
| L8 | S2 | **The translation table carries entries nothing asks for.** Two static measurements disagree because a key often travels through a variable: scanning call sites says 131 keys have no `t("literal")` caller, scanning every string literal in product code says 69. Five were confirmed dead by supersession and deleted in Phase 1 (`"No KDE shortcut installed."` ×3, `"Registered in KDE: {shortcut}"`, the pre-`{retry}` minutes message). The rest need runtime coverage — a static scan cannot answer this, and both numbers over-report. | Phase 1 deletion; instrument proposed in Phase 6 |
| L9 | S2 | **One source string was written in Turkish, not English.** `ui/pages/dashboard.py` passed `t("Genel bakış — son dikte ve toplantılarınız")`, and the table carried a matching entry that mapped the Turkish string to itself — so the *English* window showed Turkish while the Turkish window looked correct, and the gap guard could not see it (it asks whether an entry exists, and one did). Fixed at the call site, and the new guard then immediately found a **second, pre-existing instance** of the same entry that the fix had missed. | `tests/test_i18n.py::test_no_source_string_is_already_turkish` |

### 2.3 UI & visual (U)

Findings below are from the 60 captured frames, reviewed surface by surface.

| # | Sev | Finding | Evidence |
|---|---|---|---|
| U1 | S1 | **Two dead icon keys break the sidebar.** `shell.NAV` requests `"history"` and `settings_ui.py:507` requests `"pip"`; neither exists in `ui/icons.py` (56 icons). Both nav rows render with no glyph, breaking the icon column for two of eleven items. | icon probe: `'history' present: False`, `'pip' present: False` |
| U2 | S1 | **No primary/secondary button hierarchy.** `Kaydet` and `Promptlar` sit in the same footer with equal weight on every page; Save — which is the action that persists everything the page changed — is neither dominant nor positioned where the platform expects it. | all `blue_tr_page*.png` |
| U3 | S2 | **Contrast and state legibility.** The muted text tier and every disabled control read as too faint across 8 of 11 pages; disabled and enabled buttons are hard to distinguish. | overlay, history, minutes, audio-file, dashboard |
| U4 | S2 | **Oversized, mis-centred empty states.** The History "recoverable" card is a large empty box; the dashboard's empty chart card holds a full card's height; the Overlay page never centres its empty state. | `blue_tr_page09/00/10.png` |
| U5 | S2 | **Form-column alignment drifts.** Controls do not share one left/right edge within a card, and the shortcut row (combo + Install/Remove + a second line of links) overflows into the label column. | `blue_tr_page04.png` |
| U6 | S2 | **`LivePopup` does not size to its content** — a fixed ~500×520 panel with three lines of text leaves two thirds dead space, and has no empty state. | `blue_tr_live_expanded.png` |
| U7 | S3 | The `Local` chip looks interactive but is not; the `1.0` version label is unlabelled. | sidebar in every frame |
| U8 | S2 | **Dependent content is not disabled when its toggle is off.** "Custom prompt" off, while the whole cleanup-prompt section below stays fully enabled and editable. | `blue_tr_page03.png` |
| U9 | S2 | The 5-way "Editing level" segmented control is cramped, with click targets below comfortable size. | `blue_tr_page03.png` |
| U10 | S2 | **The recording pill**: the centre glyph is unlabelled and low-contrast, the timer `0:03` carries no "recording" context, Pause/Stop are cramped with insufficient separation, and there is no drag affordance. | `blue_tr_overlay_rec.png` |
| U11 | S2 | The busy pill and the "thinking" panel do not look like they come from the same product — different radii, font sizes, and the secondary panel has no activity indicator while its text says "Cleaning up…". | `blue_tr_overlay_busy.png` |
| U12 | S3 | The tray menu carries no icons, no group separators, and no on/off state for the toggle-style items. | `blue_tr_hintmenu.png` |

### 2.4 Cross-platform & distribution (X)

| # | Sev | Finding | Evidence |
|---|---|---|---|
| X1 | S1 | **There is no distributable build for any platform.** Install is a source checkout plus a developer Python: `install.sh` writes shortcuts and expects `dikte` on `PATH`; `install.ps1` registers a Start-menu entry but still runs `pythonw dikte.py`. No `.exe`, `.dmg`/`.app`, AppImage or Flatpak. For a daily-driver utility this is the largest adoption blocker. | `install.sh`, `install.ps1`, no packaging config |
| X2 | S1 | **The Linux overlay depends on XWayland.** `dikte.py:41` sets `QT_QPA_PLATFORM=xcb` so the indicator can be placed in a screen corner. On a Wayland-only session without XWayland the indicator cannot appear at all, and fractional scaling is unreliable through that path. | `dikte.py:41`, `README.md:236` |
| X3 | S3 | **Corrected on 2026-09-12: this was largely wrong.** The shortcut field already picks its suggestion list per platform (`SHORTCUTS` / `WIN_SHORTCUTS` / `MAC_SHORTCUTS`, chosen by `hotkey.desktop_name()`), both shortcut defaults are empty so a fresh install shows no hint at all, and the KDE-only explanation is gated on `hotkey.shortcut_needs_restart()` with a separate macOS branch. The `Meta+A` the survey objected to came from `tools/shoot_ui.py`'s own fixture data, not from the product — **a screenshot harness manufactured a finding about the product.** What survives is L8: three superseded KDE-specific keys nothing asked for. | `settings_ui.py:127-141`, `hotkey.py:desktop_name`, `tools/shoot_ui.py:CHANGED` |
| X4 | S2 | **Nothing builds or launches a frozen artifact on any OS.** CI runs the test suite on Linux, Windows **and macOS** (3.11–3.13; 3.14 added in Phase 0), so the macOS code paths are exercised — what no job does is produce or start a distributable build, which is why X1 stays open. | `.github/workflows/tests.yml` |
| X5 | S2 | The suite's Windows-only code path has a history of being exercised on Linux (`ctypes.windll`); it is currently mocked away rather than run on Windows in CI. | `docs/ai/VERIFICATION.md` |

### 2.5 Engineering hygiene (H)

| # | Sev | Finding | Evidence |
|---|---|---|---|
| H1 | S2 | The graphify graph is stale. AGENTS.md makes freshness part of completion. | §1 |
| H2 | S3 | Zero `TODO`/`FIXME` markers in the tree — good discipline, but it means known issues live only in prose docs, where a new contributor will not find them. | `grep -rn 'TODO\|FIXME'` → 0 |
| H3 | S3 | `settings_ui.py` (3,239 lines) and `overlay.py` (2,086 lines) are at the size where every change carries collateral risk. | `wc -l` |
| H4 | S2 | **One third of the swallowed failures sit in one file.** `settings_ui.py` holds **102 of the 313** broad handlers; `dikte.py` holds 41. The two monoliths are where the "honest failure UX" rule (§F2) is least enforceable, and they are also the two files every interface change has to touch. | `python tools/except_audit.py` |
| H5 | S2 | **The dashboard page bypasses the shell's own page API.** `DashboardWindow.__init__` inserts its tab straight into the `QTabWidget` and then hand-builds the navigation button, reaching into `shell._nav_layout`, `shell._nav` and `shell._nav_titles` and rewiring every existing button's `clicked` signal. It duplicates `AppShell.add_page()` instead of calling it, which is why the page count cannot be derived from `add_page` calls alone and why the icon contract (T0.4) does not cover it. | `ui/app_window.py:23-53` |

## 3. Technology decision

### 3.1 Verdict: stay on Python 3.11+ / PyQt6

Not because it is convenient, but because **the language is not where any of the
problems in §2 live.**

- Every performance-critical step already runs outside Python: audio capture
  (`pw-record` / `ffmpeg` / WinMM / AVFoundation), VAD maths, inference
  (`whisper.cpp`, `llama.cpp`), and file IO. Python orchestrates processes and
  paints a settings window. Rewriting the orchestrator buys milliseconds.
- The genuinely hard, platform-specific work — global hotkeys (evdev /
  `RegisterHotKey` / Carbon), synthetic paste (`ydotool` / `SendInput` /
  CoreGraphics), device enumeration (`pactl` / WASAPI / AVFoundation) — is
  already written natively through ctypes and the platform APIs. **This is the
  part a rewrite would cost the most to reproduce and gain the least.**
- The assets that would be destroyed: 29k LOC, 1,473 green tests, a documented
  design contract, and a working `install.sh`/`install.ps1` pair. A rewrite
  resets all four to zero and re-earns them with no user-visible benefit.
- PyQt6 already brings the native toolkit. If fluid animation is ever needed,
  Qt Quick/QML ships inside PyQt6 — that is a rendering change, not a language
  change.

**The honest exception:** if the product must ship a <100 MB installer or a
sub-100 ms cold start as a *hard* requirement, a compiled shell becomes
justifiable. Nothing in the repo states such a requirement, and X1 (there is no
build at all) is a packaging problem, solvable in Python.

### 3.2 Why not C++/Qt

Would reach parity in 6–12 months, and would re-derive the entire platform
layer from scratch. It fixes none of §2.1, §2.2 or §2.3, which are the findings
users actually feel.

### 3.3 Other stacks, and why they lose here

| Option | Verdict |
|---|---|
| **Rust + Tauri** | Adds a webview, which `docs/ai/GOAL.md` explicitly lists as out of scope ("Embedding HTML/webview/Electron/QtWebEngine to fake fidelity"). Turns a one-language project into Python-backend + Rust-shell + web-frontend, and each OS's hotkey/paste/audio integration still has to be written again in Rust. |
| **Electron** | Contradicts the product identity (local-first, no account, small utility), 150 MB+ baseline, worse cold start. |
| **Rust + egui / Slint** | Reasonable for a *new* app. For this one it is the C++/Qt problem with a smaller ecosystem. |
| **Qt Quick / QML inside PyQt6** | The only rendering-level change worth keeping on the table. Not needed for §2.3 — those are design decisions, not rendering limits. Consider only if the overlay work in Phase 3 hits a real QPainter ceiling. |

### 3.4 In-stack upgrades worth making

Grounded in live repository data (GitHub API / PyPI, fetched 2026-09-12):

| Component | Now | Assessment |
|---|---|---|
| `whisper.cpp` | used | ★53.6k, last push **2026-09-11**, MIT, GPU via CUDA/ROCm/Vulkan. **Keep.** |
| `llama.cpp` | used | ★128k, last push 2026-09-12, MIT. **Keep.** |
| **`sherpa-onnx`** | not used | ★14.7k, last push **2026-09-11**, Apache-2.0, **1.13.8 released 2026-09-10**, prebuilt binaries per platform, ONNX-only. Worth evaluating as an **optional second local engine**: its streaming Zipformer transducer models give true partials without a torch dependency. Additive, not a replacement. |
| `faster-whisper` | not used | ★25.4k but last push **2025-11-19** (~10 months stale) and it pulls CTranslate2 + cuDNN. **Do not adopt**, despite being the popular answer. |
| `whisperX` | not used | Active, but needs torch + pyannote — a heavy dependency tree for speaker labels the app already derives from the audio channel. **Reject.** |
| VAD | hand-rolled dB gate | Works, dependency-free, and the current `silence_db` / `margin` UX is built on it. `silero-vad` (MIT, active) exists, but adopting it means a new runtime dependency for an unmeasured gain. **Measure first; do not rewrite blind.** |
| Packaging | none | `pyinstaller` 6.22.2 (active, bootloader exception) for the app; `nuitka` 4.2.1 is active but AGPL tooling with long builds. **PyInstaller.** |

### 3.5 PyQt6 vs PySide6 — a decision, not a default

| | PyQt6 | PySide6 |
|---|---|---|
| Latest | 6.11.0 (2026-03-30) | 6.11.2 (2026-08-18) |
| Licence | GPL-3.0 **or commercial** | LGPL-3.0 / GPL-2.0 / GPL-3.0 |
| Consequence | Shipping binaries obliges you to GPL-3.0 the whole app | Shipping binaries carries no copyleft obligation on your code |

Today the project declares GPL-3.0, so **PyQt6 is legal and there is no
technical reason to move** — the API is near-identical and the port is mostly
import renaming (`pyqtSignal`→`Signal`, `pyqtSlot`→`Slot`, `exec()`→`exec()`).
But `pyproject.toml` says MIT, which is incompatible with PyQt6. **Pick one:**
either correct the metadata to GPL-3.0 and stay, or move to PySide6 and keep the
option of a non-GPL build. This is question **Q1** in §7.

## 4. The visual direction problem — root cause of "the UI doesn't look right"

There is not one design; there are three, all still present in the repo:

1. **`docs/design-reference.md` (2026-08-21)** — "Warm Technical Minimalism":
   warm stone `#F4F1EA` canvas, sand `#EEE9DE` sidebar, ivory `#FBFAF6` surfaces,
   ink `#242628` text, terracotta `#E4573D` as the *only* accent. Explicit
   negatives: no purple, no neon, no glass, no big radii. **Not implemented.**
2. **`docs/settings-*.webp`, still embedded in the README** — a flat dark window
   with a title bar, **nine horizontal tabs** with a blue underline, a checkbox
   form, a blue Save button bottom-right, **no sidebar**. This is a *previous UI
   generation*. The current build has a 226 px sidebar and eleven pages. **The
   README advertises a product that no longer exists.**
3. **`ui/tokens.py`, what actually ships** — six *dark-only* colour rooms
   (`blue`, `green`, `violet`, `orange`, `pink`, `teal`), each a charcoal base
   mixed with a saturated accent, plus a real `LIGHT` palette that is unreachable.

That last point is a concrete bug, not a preference:

```
normalize('light') -> 'blue'
```

Every theme name outside the six is coerced to `blue`, so `ui_theme: "light"`
silently becomes a dark room, and the `LIGHT` token dict (§`ui/tokens.py:74-98`)
is dead code kept alive only as an alias. **There is no reachable light theme
any more, and the documented design brief is not the shipped design.**

Consequence for the plan: **fixing §2.3 before §7/Q2 is answered would produce a
fourth generation.** The direction must be locked first.

## 5. Phased roadmap

Effort is in developer-days for one focused engineer, and excludes the
unverifiable macOS/Windows passes.

### Phase 0 — Guardrails — **EXECUTED 2026-09-12**

The point of this phase is that the next five phases cannot regress silently.
Nothing here is user-visible. Evidence for every row is in §9.

| Task | Delivered | How it was shown to work |
|---|---|---|
| T0.1 | Licence contradiction **documented, not resolved** — Q1 is still open. A comment in `pyproject.toml` states the conflict and points at Q1. | `pyproject.toml:10-15` |
| T0.2 | `requires-python` widened to `>=3.11,<3.15`; `"3.14"` added to all three CI matrices. The old bound excluded a configuration the suite already passed on, so it described packaging policy rather than the code. | 1477 tests pass on 3.14.7 locally; Windows/macOS 3.14 explicitly marked unverified in the workflow |
| T0.3 | The count ratchet replaced by an **exact-set record** — `tests/i18n_untranslated.json`, 104 entries each with call sites — plus `tools/i18n_gaps.py` as the generator. The scan now follows the `_t` alias. Both directions fail. | proven red twice: dropping `Ask` → `['Ask']`; inventing `Nobody translated this` → `['Nobody translated this']` |
| T0.4 | New `tests/test_icon_contracts.py`, and the two dead keys it found are fixed: `settings_ui.py:507` asks for `monitor`, and `ui/icons.py` gains a `history` glyph. | proven red first, naming both defects: `settings_ui.py:503 add_page('history')`, `settings_ui.py:507 add_page('pip')`, `ui.shell.NAV → ['history']` |
| T0.5 | `tools/shoot_ui.py` grows a surface manifest, a page-count cross-check against the source, and `--check`; wired into the Linux CI job so it runs without being remembered. | proven red in both branches: `missing: blue_en_overlay_somehow_missing.png` and `blank: blue_tr_overlay_rec.png`; green run reports `30 surfaces x 2 theme-and-language runs, all drawn` |
| T0.6 | New `tools/except_audit.py`. | first census: **313 handlers in 36 modules**, 102 of them in `settings_ui.py` → finding H4 |
| T0.7 | Graph refreshed. | `5372 nodes, 9509 edges, 311 communities`; `Built from commit: ffe8a5c7` (= HEAD) |
| — | Full suite after the phase | `Ran 1477 tests in 101.1s — OK` (was 1473). `git diff --check` clean. |

**Verification contract, honoured:** every guard was run against the tree it is
meant to fail on *before* the fix, and the failure output is quoted above. A
guard that has never gone red is not evidence that it tests anything.

**Two findings surfaced by doing this**, not predicted by the survey: H4 (a third
of the swallowed failures live in one file) and H5 (the dashboard page bypasses
`AppShell.add_page()` entirely, which is why the page count had to be derived
from two call shapes rather than one).

### Phase 1 — Localization closure — **EXECUTED 2026-09-12**

| Task | Delivered | How it was shown to work |
|---|---|---|
| T1.1 | All 104 strings translated, in a dated block at the end of the table, grouped by source module. The block says where new strings should go instead (the topical sections above). | `python tools/i18n_gaps.py` → **`0 strings reach t() with no Turkish entry`**; the record is empty and the guard fails if it refills |
| T1.2 | The English source is now `"Indicator"` rather than the slash-joined `"Overlay/Indicator"`, in both the nav label and the page title; Turkish `"Gösterge"`. | `settings_ui.py:507`, `ui/pages/overlay.py:59`; confirmed in the re-shot frame |
| T1.3 | `"Local"` → `"Yerel"`, `"Ready"` → `"Hazır"`, and the unlabelled `1.0` now carries a `"Sürüm"` tooltip. | re-shot frame: the sidebar footer reads `whisper-1 · Yerel · ● Hazır · 1.0` |
| T1.4 | `"Runs on" → "Çalıştığı yer"` (it is a form label in three pages, not a sentence). The *prompt* sub-item turned out to be a false premise — see §9. | `i18n.py:531` |
| T1.5 | New `ui/format.py` (`decimal_separator`, `number`, `seconds`, `when`) plus `meeting.format_when` extended to read stamps that carry seconds, so month names are not duplicated. Applied to the history list, the history details dialog and the dashboard. | re-shot frames read `21 Ağu 2026 12:05 (2,0 sn)`, `3,2 sn`, `10 dk` — was `2026-08-21 12:05:00`, `3.2s` |
| T1.6 | **Nothing to do** — the finding was wrong. See the corrected X3. | `settings_ui.py:127-141` |
| — | Two defects found while doing the work: **L8** (dead entries) and **L9** (a Turkish string used as the English source). L9 gained a permanent guard. | `tests/test_i18n.py::test_no_source_string_is_already_turkish`, proven red before the fix landed |

**Verification:** gap record empty; the tour re-shot in `tr` and `en` and read
frame by frame — every remaining English string in those frames is data (a model
id, a provider id, a fixture's meeting title), not interface text.

### Phase 2 — Design system (4–6 d) — *blocked on Q2*

| Task | What | Files |
|---|---|---|
| T2.1 | **Lock one visual direction** and write it into a single source of truth (see Q2) | `ui/tokens.py`, `docs/design-reference.md` |
| T2.2 | **Restore a reachable light theme.** Fix `normalize()` so `light`/`dark` map to themselves, or retire them honestly and delete `LIGHT`. A config value must not silently become a different theme. | `ui/tokens.py` |
| T2.3 | Rebuild the contrast scale: `fg2`/`fg3` to a verified contrast ratio, and distinct enabled / hover / focus / **disabled** states | `ui/tokens.py`, `ui/qss.py` |
| T2.4 | Define the control-height and spacing rhythm once; make every page inherit it (fixes U5) | `ui/tokens.py`, `ui/qss.py`, `ui/widgets.py` |
| T2.5 | Button hierarchy: exactly one primary per page, positioned per platform convention; destructive actions visually separated (U2) | `ui/widgets.py`, `ui/shell.py`, all pages |
| T2.6 | State-coupling rule: a control whose master toggle is off is disabled, not merely described as inactive (U8) | page modules |

**Verification:** contrast ratios measured and recorded; the tour captured in
both themes; a written token table in the repo; `tests/test_theme.py` extended.

### Phase 3 — Surface-by-surface rebuild (10–14 d)

Rebuild in this order — most-visible first, and each surface has its own
verification frame from T0.5.

| Order | Surface | Fixes |
|---|---|---|
| 1 | Recording pill + paused/busy/warning/error states | U10, U11 |
| 2 | Result overlay + live popup (content-sizing, empty state) | U6 |
| 3 | Thinking panel — same visual family as the pill | U11 |
| 4 | Tray menu — icons, separators, toggle state | U12 |
| 5 | Dashboard (stat semantics, empty states) | U4 |
| 6 | The nine settings pages | U2–U5, U9 |
| 7 | Native Wayland indicator path, or a documented, tested fallback (X2) | X2 |

**Verification:** every captured frame reviewed against the locked direction;
the golden-image manifest updated deliberately in each commit, never blindly.

### Phase 4 — Reliability closure (7–10 d)

Close the pass that is already open, in its own dependency order:

| Task | Source | What |
|---|---|---|
| T4.1 | F1/R1 | Dynamic activity-session registry; coordinator-owned geometry |
| T4.2 | F1/R2 | Independent meeting/dictation/agent/result views; bounded detail surface |
| T4.3 | F1/R3 | Safe concurrent-capture policy; non-destructive "this device is busy" UX |
| T4.4 | F1/R4 | Audio persisted before any classification; crash-discoverable capture |
| T4.5 | F1/R6 | History/Minutes recovery details, explicit deletion, retry UX |
| T4.6 | F1/R7 | Editing-level migration completion + EN/TR parity |
| T4.7 | F1/R8 | Deterministic regression coverage for every defect above |
| T4.8 | F2 | Burn down the `except Exception` allowlist: each remaining site either reports its failure or is explicitly listed with a reason |
| T4.9 | F3 | `OverlayCoordinator.update` trigger; close the `Config.data` read race; decide on cross-process locking |

**Verification:** `docs/ai/TASKS.md` R1–R8 all `[x]`; a fresh reviewer on the
final diff (V4); full suite green with the new regression tests named in
`docs/ai/VERIFICATION.md`.

### Phase 5 — Distribution & cross-platform (15–20 d)

| Task | What |
|---|---|
| T5.1 | PyInstaller spec per OS; the frozen app must not require a developer Python |
| T5.2 | Per-OS CI build jobs that **launch the frozen artifact** and assert it starts — the current CI only runs tests (X4) |
| T5.3 | Linux: AppImage + Flatpak (+ `.desktop`, icons, PipeWire/portal permissions) |
| T5.4 | Windows: ship the frozen app through the existing `install.ps1`; optional portable zip |
| T5.5 | macOS: `.app`/`.dmg`, signing + notarisation, `NSMicrophoneUsageDescription`, and an explicit Accessibility-permission flow — the hotkey path needs it and nothing documents it today |
| T5.6 | A written, per-OS manual verification protocol (checklist) so a macOS/Windows claim has evidence behind it, not hope |
| T5.7 | Add a macOS CI runner so the macOS code paths are executed at all |

**Verification:** a downloaded artifact from each OS starts, records, transcribes,
pastes and quits; each run recorded in `docs/ai/VERIFICATION.md` with the OS and
version it was observed on.

### Phase 6 — Product depth (optional, ranked)

Only after Phase 5. Ranked by value against effort:

1. First-run experience: a working three-step wizard (mic → model → test), because
   the local-model download is currently the highest-friction moment.
2. `sherpa-onnx` streaming partials as an optional second local engine (§3.4).
3. A diagnostics bundle from `dikte doctor --json` — already 80% built — for
   bug reports without telemetry.
4. Diarisation quality for meetings beyond channel-splitting.

## 6. Verification contract

Non-negotiable for every phase, inherited from `ai/workflows.md`:

- The new guard is proven to **fail** before the fix and **pass** after. A guard
  that has never gone red is not evidence.
- Targeted modules → full suite → `git diff --check`.
- Every phase records its real command output in `docs/ai/VERIFICATION.md`.
  No predicted PASS.
- The screenshot tour is re-captured and reviewed, not assumed.
- Graph refreshed before the phase is called complete.
- No new third-party dependency without an explicit decision (§7/Q3).

## 7. Decisions

Recorded 2026-09-12. Anything still open blocks the phase that depends on it.

| # | Question | Answer |
|---|---|---|
| **Q1** | **Licence intent**: stay GPL-3.0 (keep PyQt6) or keep the option of a non-GPL build (move to PySide6)? | **Deferred.** Phase 0 documents the contradiction in `pyproject.toml` and leaves the metadata as it is. **Still blocking T5.5** — signed closed-source binaries are not possible until this is answered, and the current state is unshippable under either reading. |
| **Q2** | **Visual direction** | **Answered: return to the documented "Warm Technical Minimalism"** — warm stone `#F4F1EA` canvas, sand `#EEE9DE` sidebar, ivory `#FBFAF6` surfaces, ink `#242628` text, terracotta `#E4573D` as the single accent, with a **real light and a real dark theme**. This makes `docs/design-reference.md` the binding contract again and retires the six derived dark colour rooms as the product surface. |
| **Q3** | **Dependency policy** | **Answered: the stdlib + PyQt6 rule stands.** Packaging tooling is a **build-time-only** exception, so PyInstaller is allowed in Phase 5 and nothing new enters the runtime. `ui/format.py` (T1.5) is therefore hand-written, and `sherpa-onnx` (§3.4) is **not** adopted. |
| **Q4** | **Distribution**: which installers must exist? | **Still open.** Sizes Phase 5; not needed to start Phase 1 or 2. |
| **Q5** | **Hardware access** | **Answered: a Windows machine is available.** So Phase 5 can be manually verified on Windows, and T5.6's protocol must cover it. **macOS remains unverified** — anything claimed there is CI-only and must be labelled that way. |

### Consequences of Q2 that the plan has to absorb

Locking the warm direction is not a palette swap; it retires the current product
surface. Concretely, Phase 2 has to:

- rewrite `ui/tokens.py` so the canonical themes are `light` and `dark` in the
  warm palette, and the six colour rooms become either removed or an optional
  secondary set — a decision inside Phase 2, not before it;
- make `LIGHT` reachable (T2.2) instead of an alias that `normalize()` throws away;
- **re-shoot `docs/settings-*.webp`**, which currently advertise a previous
  interface generation with horizontal tabs and no sidebar, and cut the README's
  screenshot table down to the pages that still exist;
- re-derive the accent usage: terracotta is a *recording* signal, not a button
  colour, which changes every `accent`-filled control in `ui/qss.py`.


## 8. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| The UI is rebuilt before the direction is locked | A fourth design generation; the work is thrown away | Q2 answered before T2.1 starts |
| Phase 4 touches the state machine while Phase 3 touches the same overlay | Merge conflicts and double regressions | Phase 4 after Phase 3, on separate branches |
| Translating 103 strings degrades the Turkish copy | The UI gets worse in the language most users see | T1.4 is a review task with a native-speaker pass, not a fill-in |
| Phase 5 growth (three OSes × signing × notarisation) consumes the whole budget | Feature work stops | Phase 5 is last and can be split; T5.1–T5.2 alone already remove the biggest blocker |
| 313 `except Exception` sites hide a real failure during the rebuild | A user-visible defect ships looking like a success | T0.6 makes it measurable; T4.8 makes each site either honest or documented |
| The macOS/Windows paths ship unverified | Credibility loss on first real use | Q5; and T5.6's protocol, with per-OS evidence in `VERIFICATION.md` |

## 9. Change log and evidence

### 2026-09-12 — Phase 0 executed

Files touched (6 modified, 6 added):

| File | Change |
|---|---|
| `pyproject.toml` | `requires-python` → `>=3.11,<3.15`; the licence conflict documented in place, pointing at Q1 |
| `.github/workflows/tests.yml` | `"3.14"` added to all three matrices with the unverified-platforms caveat; a new Linux step runs `tools/shoot_ui.py --check` |
| `tests/test_i18n.py` | the count ratchet replaced by an exact-set ratchet; `untranslated_strings()` and `recorded_gaps()` are module-level so the generator can share them |
| `tests/i18n_untranslated.json` | new — the recorded gap set, 104 entries with call sites |
| `tests/test_icon_contracts.py` | new — icon-key integrity over `shell.NAV` and every literal passed to an icon API |
| `tools/i18n_gaps.py` | new — the generator/reader for the gap record |
| `tools/except_audit.py` | new — the broad-handler census |
| `tools/shoot_ui.py` | surface manifest, source-derived page count, `--check`, `--check` wired into CI |
| `ui/icons.py` | a `history` glyph added (`"history"` was requested by `shell.NAV` and rendered blank) |
| `settings_ui.py` | the overlay page asked for a `"pip"` icon that never existed; it now asks for `monitor` |

Raw results:

```
$ python3.14 -m unittest discover
Ran 1477 tests in 101.148s
OK

$ python3.14 tools/shoot_ui.py --out /tmp/dikte-check --themes blue --langs tr,en --check
wrote 60 PNGs to /tmp/dikte-check
surface check OK: 30 surfaces x 2 theme-and-language runs, all drawn

$ python3.14 tools/except_audit.py
313 broad handlers in 36 modules. `--list` shows them, `--allowlist` prints the skeleton.

$ git diff --check      # clean
```

Red proofs, run before each fix landed:

```
icon guard, pre-fix:    settings_ui.py:503 add_page('history')
                        settings_ui.py:507 add_page('pip')
                        ui.shell.NAV requests unknown icon keys: ['history']
i18n guard, drop:       AssertionError: Lists differ: [] != ['Ask']
i18n guard, invent:     AssertionError: Lists differ: [] != ['Nobody translated this']
surface check, missing: ['missing: blue_en_overlay_somehow_missing.png']
surface check, blank:   ['blank: blue_tr_overlay_rec.png']
```

Graph: `5372 nodes, 9509 edges, 311 communities`, `Built from commit: ffe8a5c7`.

### 2026-09-12 — Phase 1 executed

Files touched (9 modified, 1 added):

| File | Change |
|---|---|
| `i18n.py` | 105 entries added in a dated block; `"Runs on"` relabelled; five dead entries deleted |
| `ui/format.py` | new — `decimal_separator`, `number`, `seconds`, `when` |
| `meeting.py` | `format_when` now reads stamps that carry seconds, so history rows and meeting rows share one implementation |
| `settings_ui.py` | the history list and the history details dialog go through `ui/format`; the indicator page is named `"Indicator"` |
| `ui/pages/dashboard.py` | the subtitle is English again (see L9); durations and stamps formatted; `t("—")` unwrapped |
| `ui/pages/overlay.py` | page title renamed to `"Indicator"` |
| `ui/shell.py` | the version number carries a `"Sürüm"` tooltip |
| `tests/test_i18n.py` | new guard: a source string may not contain a Turkish letter |
| `tests/i18n_untranslated.json` | the record is now empty |

Raw results:

```
$ python3.14 tools/i18n_gaps.py
0 strings reach t() with no Turkish entry:

$ python3.14 tools/shoot_ui.py --out /tmp/dikte-p1 --themes blue --langs tr,en --check
wrote 60 PNGs to /tmp/dikte-p1
surface check OK: 30 surfaces x 2 theme-and-language runs, all drawn
```

Red proof, before the fix landed:

```
$ python3.14 -m unittest tests.test_i18n.Table.test_no_source_string_is_already_turkish
AssertionError: Lists differ: [] != ['Genel bakış — son dikte ve toplantılarınız']
```

And the guard earned its keep on its first full run: the suite came back
`1478 tests, FAILED (failures=1)` because the table carried a *second* copy of
that Turkish key — one that mapped the Turkish string to itself and had been
there long before the survey. The call-site fix alone would have left it. That is
the whole argument for a guard rather than a one-off cleanup.

Full suite after the phase: `Ran 1478 tests in 90.237s — OK` (was 1473).

Read off the re-shot Turkish frames, not assumed:

```
history row      21 Ağu 2026 12:05 (2,0 sn)      was  2026-08-21 12:05:00 (2.0 sn)
dashboard card   3,2 sn ort.  ·  10 dk           was  3.2s avg  ·  10 min
sidebar footer   whisper-1 · Yerel · ● Hazır     was  whisper-1 · Local · ● Ready
nav item         Gösterge                        was  Overlay/Indicator
```

Every English string still visible in those frames is data rather than interface
text: `whisper-1` (a model id), `openai` / `ask` (provider ids in the donut
legend), and the fixture's own `Shot meeting` and `What is the capital of
Turkey?`.

### Corrections made to this document while executing it

Recorded because a plan that quietly edits itself is worse than one that shows
where it was wrong:

- **X4 was wrong.** It claimed no macOS CI runner existed. `.github/workflows/tests.yml`
  has run `test-macos` on `macos-latest` all along. The finding survives in a
  weaker form: no job builds or launches a frozen artifact.
- **L1 was low.** 103 → 104, using `tools/i18n_gaps.py` as the single measurement.
- **L6 was wrong in shape.** It claimed the suite did not guard the i18n gap at
  all. It did — as a count ratchet with two units of slack that could not see the
  `_t` alias. The corrected finding is stronger and more specific.
- **T0.5 was over-specified.** The plan asked for a golden-image tour; pixel
  goldens are not deterministic across Qt versions and platforms, which this
  repository forbids. Delivered as a presence-and-non-blankness check instead,
  with the reason written into the tool.

And during Phase 1:

- **X3 was largely wrong**, and wrong because of the survey's own method. It
  claimed the UI offers `Meta+A` on every platform; the shortcut field has always
  picked its list per platform, both defaults are empty, and the KDE-only copy is
  gated. The `Meta+A` came from `tools/shoot_ui.py`'s fixture dictionary, so the
  harness manufactured a product finding. Corrected in the table; the lesson is
  that a screenshot proves what the *fixture* renders, not what a user sees.
- **The `Promtlar` half of L5 was a misreading.** `Promtlar` appears nowhere in
  the repository. The vision pass read `Promptlar` wrong and the survey repeated
  it as a defect. Corrected.
- **T1.4's *prompt* sub-item was a false premise** for the same reason: the table
  has always said `Promptlar`. Nothing was standardised because nothing was
  inconsistent.
- **T1.6 evaporated** on inspection — see X3.
- **The plan's framing of L1 was right and its number was low**: 104, not 103,
  once the `_t` alias was followed.

---

*Begun from a read-only survey of `master @ ffe8a5c` on 2026-09-12; Phases 0 and 1
executed the same day. Turkish twin: [`ROADMAP-tr.md`](ROADMAP-tr.md).*
