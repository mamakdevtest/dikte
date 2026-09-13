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
| H6 | S3 | **`ui/components.py` is dead code that shadows the live one.** It defines a `Button` and a `Dropdown` duplicating `ui/widgets.py`, and no source file, test or document imports it. Its `Button` was a copy of `btn()`'s height logic rather than a call to it, so it would have drifted from the rhythm unnoticed. Recorded rather than deleted: removing a module is its own reviewable change. | `grep -rn "components" --include=*.py .` finds nothing outside the file |
| H7 | S3 | **Long copy is duplicated across five page modules.** The same help string appears twice each in `audiofile.py` (×3), `cleanup.py`, `general.py` and `history.py`. Most are almost certainly the two branches of an if/else rather than two live elements — but the `cleanup.py` one was rendering together, confirmed on a frame, and is fixed. The rest need judging against what actually renders, which is the surface pass. | a scan over `t("…")` literals longer than 40 chars per page module |

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
| T0.5 | `tools/shoot_ui.py` grows a surface manifest, a page-count cross-check against the source, and `--check`; wired into the Linux CI job so it runs without being remembered. | proven red in both branches: `missing: blue_en_overlay_somehow_missing.png` and `blank: blue_tr_overlay_rec.png` (the tour's themes were `blue,orange` then; it runs `light,dark` now); green run reports `30 surfaces x 2 theme-and-language runs, all drawn` |
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

### Phase 2 — Design system — **done 2026-09-12**

| Task | State | What landed, and what proves it |
|---|---|---|
| T2.1 | **done** | The documented warm direction is now the only one. `ui/tokens.py` carries a warm-stone `LIGHT` and a warm-charcoal `DARK` and nothing else. **The six saturated colour rooms are retired.** They were a charcoal base mixed with one accent each — which is why all six read as the same dark interface with a differently coloured button, and why the app never looked like the design it claimed to follow. `RETIRED_THEMES` keeps the names so `normalize()` can be explicit about what replaced them instead of pretending they are still themes. |
| T2.2 | **done** | `light` and `dark` map to themselves; the light theme is reachable for the first time. The default moves from `blue` to `dark` (`config.py`, `settings_ui.py`, `dikte.py`, `ui/shell.py`). The picker offers the two themes and its swatches carry a selection ring in palette ink, so a light swatch on a light sidebar no longer dissolves. |
| T2.3 | **done** | Every text pairing measured against the background it is drawn on: `fg` 12.2–12.7:1, `fg2` 7.5:1, `fg3` 5.5–5.6:1 at worst, status colours 4.6–6.5:1 as chip labels on their own tint, filled button 14.5–17.0:1, and lines visible at 1.31–1.90:1. `tests/test_theme.py` pins all of it. The state review found the real defect: `ghost` and `danger` declared `border-color: transparent` *below* the focus rule, so QSS's document-order tie-break gave them no focus ring at all — fixed by putting one focus rule after every variant, guarded per variant. **Not verified:** that the ring paints, because focus does not resolve in an unfocused offscreen window. |
| T2.4 | **done** | The rhythm is declared once in `ui/tokens.py` (`CONTROL`, `ROW_HEIGHT`, `CELL`, `INDICATOR`) and nothing else picks its own height. Fields, combos, buttons, the segmented control and the sidebar rows all move to `CONTROL["md"]`, so a control and its neighbour line up by construction rather than by luck. Guarded: no literal `min-height` above 1px or `height` above 14px in the sheet, no `setFixedHeight` above 14 in code. |
| T2.5 | **done** | Button levels now mean what the reference says. `Reset to default` on the Agent and Meeting pages was `secondary`, and the reference names Reset as the ghost example — it is ghost now. The `Delete` that removes a downloaded model was `ghost`, i.e. the weight of a bookmark, on a confirmed destructive action — it is danger now. Both action rows put the destructive buttons past the stretch: History had Delete between Copy and the gap, and Minutes had the same shape in the opposite order, so the two pages disagreed with each other as well. Guarded: a danger button added before its row's stretch fails the suite. |
| T2.6 | **done** | Audited every master toggle against its dependents. `auto_paste` and `skip_silent` were wired, and the cleanup page's prompt editors were gated by a hand-rolled copy of `ui.widgets.gate()` wrapped in `except Exception: pass` — a failed connect would have left the prompt editors live while the toggle said their prompts were not in use. It calls the shared helper now. The remaining switches (`result_overlay_enabled`, `live_transcript`, `keep_audio`) have no dependents: the corner picker belongs to the recording indicator, and the info note describes behaviour rather than gating a control. Verified by pixel: the prompt field renders `surface2`, the disabled background, with the toggle off. |

**Verification, as delivered:** `unittest discover` 1500 tests OK in 85 s;
`tools/quick_tests.py` 1361 in 14 s; `shoot_ui.py --check` drawn 60 frames across
2 themes × 1 language with the surface manifest intact; the two themes proven
distinct by pixel, not by filename.

One more thing came out of the button work: the tour could not have checked any of
it. Every settings page lives in a scroll area, and the capture was a fixed
1000×700, so the History page's delete row and the Minutes page's action row had
never appeared in a single frame. Each page is now measured and the window grown
to fit it, and the frames come out between 700 and 2040 px at their own height.
The reorder was then confirmed on the picture: 101 px of danger-red text on the
row, with a measured 250 px gap between it and the last safe action.

Findings that came out of doing this, recorded in "Corrections" below: the tour
had been rendering one palette for every theme name it claimed (N1), terracotta
cannot carry button text at any size the design uses (N2), a style rule that
matches nothing fails silently in two more ways (N3), and the tour was photographing
only the top of every page (N4).

### Phase 3 — Surface-by-surface rebuild (10–14 d) — *in progress: 5 of 7 delivered*

Rebuild in this order — most-visible first, and each surface has its own
verification frame from T0.5. Each finding is re-checked against the code and a
current frame before anything is changed: three of the survey's UI findings have
now turned out to be stale or wrong (X3, the `Promtlar` half of L5, and most of
U10), and all three were written from the old screenshots.

| Order | State | Surface | What it settled |
|---|---|---|---|
| 1 | **done** | Recording pill + paused/busy/warning/error states | U10 re-checked claim by claim: the timer *does* carry recording context (red dot, timer, Pause/Stop read as one control), Pause and Stop are *not* cramped, and the "missing drag affordance" contradicts documented behaviour — `i18n.py:887` tells the user the indicator "sürüklenemez", and Settings places it by corner. The one real defect was that the live-transcript button, Pause and Stop had **no name in any form**: the pill is a single custom-painted widget, only the meeting toggle ever set a tooltip or accessible description. Fixed, and the new region-name contract fails when a `_hover_*` flag is added without one. U11's busy-pill comparison is the next surface's job, since it needs both frames. |
| 2 | **done** | Result overlay + live popup (content-sizing, empty state) | U6's first half held — the card really was a fixed 260 px box with three lines in it — and is fixed: it is now as tall as its text, 124 px for three lines, with the expanded state carrying a 24-line transcript at 460×460. Its second half was stale: the "no empty state" claim predates the placeholder the text area has always had. Sizing the card properly then exposed two defects that were hiding behind the fixed height: the card was a line short of its own text (the application stylesheet's 8 px padding on text areas was invisible to a margins-only count, so the last line scrolled out of sight while the card still had room), and the disabled expand arrow drew in the enabled colour (a palette colour does not reach a QToolButton whose text Qt resolves through QStyleSheetStyle). Both fixed and guarded. |
| 3 | **done** | Thinking panel — same visual family as the pill | U11: first half true and worse than reported (the activity cue was a QLabel with nothing to draw — see N6b), second half unsupportable (the reference is a settings reference and says nothing about the indicator). Reading the file also found that the panel had no i18n at all and that showing it resets the interface language (N7). |
| 4 | **done** | Tray menu — icons, separators, toggle state | U12 re-checked claim by claim: 11 actions all carry an icon and `tests/test_icon_contracts.py` already guards those names; four separators group the menu into dictation / meetings / settings+restart / quit; state shows in the label, an icon accent and the tooltip, with PAUSED deliberately sharing RECORDING's label because pause is the overlay's button. The real defect was unreported: both ask tooltips named a fixed assistant — "recording for Claude", "talking to Claude" — under a `display_name(self.conf)` that already knew better, so Codex and local-model users were told the wrong program had the microphone. Fixed, with the choice moved into a testable `ask_tray_state()`. |
| 5 | **done** | Dashboard (stat semantics, empty states) | U4's three claims: the History recovery card held **and was worse** — it rendered in every state, an empty list box and a dead Retry button in the page's best space (fixed: it hides when nothing is retryable); the Indicator page never centring its empty state held (fixed: it sits between two stretches); the dashboard's empty chart card could **not** be supported — the two chart cards share a row and the right-hand one holds a real donut, and the empty one centres its own "No data yet". The tour now seeds a retryable job, so the card is photographed both ways instead of only as an empty box. |
| 6 | next | The nine settings pages | U2–U5, U9 |
| 7 | | Native Wayland indicator path, or a documented, tested fallback (X2) | X2 |

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

### 2026-09-12 — Phase 2, first delivery (T2.1, T2.2, colour half of T2.3)

| File | Change |
|---|---|
| `ui/tokens.py` | rewritten: warm-stone `LIGHT` and warm-charcoal `DARK`, `THEMES = {light, dark}`, `DEFAULT_THEME`, `RETIRED_THEMES`, and `mix` / `relative_luminance` / `contrast_ratio` so the palette's claims are checkable |
| `ui/qss.py` | the two hardcoded colours are gone (`#FFF8F5` on filled buttons, `#8A6A14` on the tan chip); `mix` now comes from `ui/tokens` |
| `ui/theme.py` | the six room exports removed; `toggle()` swaps two themes |
| `ui/pages/general.py` | picker offers light and dark; swatch edge and selection ring come from palette ink |
| `config.py`, `settings_ui.py`, `dikte.py`, `ui/shell.py` | default theme `blue` → `dark` so the locked direction is what a new install gets |
| `settings_ui.py` | the Save button is a `primary`: it was unstyled, so no page had a primary action at all |
| `tools/shoot_ui.py`, `.github/workflows/tests.yml` | the tour runs `light,dark`, and tells the config which theme it is presenting |
| `tests/test_theme.py` | extended into a contract: reachability, tier ordering, every text pairing, no bare colour in the engine, the filled button is ink |

Raw result of the tour, read from the pixels rather than the file names:

```
light_tr_page01.png  sha=4d78bde6b7f4  [('#fbfaf6', 37952), ('#f4f1ea', 20645), ('#eee9de', 14204)]
dark_tr_page01.png   sha=f34094f439e7  [('#232019', 35341), ('#1c1a17', 20645), ('#171512', 14204)]
light_tr_page03.png  sha=b8ce7847213e  [('#f4f1ea', 24996), ('#fbfaf6', 17883), ('#eee9de', 14281)]
dark_tr_page03.png   sha=a22a6b35fb0e  [('#1c1a17', 24996), ('#232019', 16135), ('#171512', 14281)]
```

The canvas and sidebar pixel counts are identical across the two themes
(20645 / 14204) — one layout, two palettes, which is the property the colour
contract promised. The measured palette is now the one the design reference
describes, and the two themes differ by SHA, not just by name.

### 2026-09-12 — Phase 2, second delivery (T2.4, and the palette re-solved)

| File | Change |
|---|---|
| `ui/tokens.py` | the palette deepened so the warmth and the planes read; `CONTROL` / `CONTROL_PAD` / `ROW_HEIGHT` / `ROW_PAD` / `CELL` / `INDICATOR`; `CHIP_TINT` / `NOTE_TINT` / `SAGE_CHIP_TINT` |
| `ui/qss.py` | every control height taken from the rhythm; chip and note tints from the tokens; no bare colour left |
| `ui/widgets.py`, `ui/components.py` | the five hardcoded button heights now read `CONTROL` |
| `ui/shell.py` | the engine card is a `QFrame`, so `QFrame#card` actually styles it |
| `ui/pages/cleanup.py`, `i18n.py` | the page subtitle no longer repeats the tab's help text |
| `tests/test_style_contracts.py` | **new**: objectName/style matching, the exemption lists, and the control rhythm |
| `tests/test_theme.py` | tier targets per tier, surface2 and field in the background set, line visibility, chip and note tints |

Two measurements worth keeping:

```
engine card surface in the sidebar        before: 0 px        after: 19 371 px
the tour, light vs dark, same surface     before: identical sha=4d78bde6b7f4
                                          after:  light 4d78bde6…  dark f34094f4…
```

The card is the clearest one. "The status line is too faint" had been treated as a
contrast problem through two palette revisions, and no palette can fix it, because
there was no card: the widget was built as a `QWidget` while the sheet styles cards
as `QFrame#card`, so Qt matched nothing and drew nothing. The text was not faint,
it was sitting on the bare sidebar.

### 2026-09-12 — Phase 2, third delivery (T2.5, T2.6, and the focus ring)

| File | Change |
|---|---|
| `ui/pages/agent.py`, `ui/pages/meeting.py` | `Reset to default` was secondary; the reference names Reset as the ghost example |
| `ui/local_models.py` | the `Delete` that removes a downloaded model was ghost, the weight of a bookmark, on a confirmed destructive action |
| `ui/pages/history.py`, `ui/pages/minutes.py` | the destructive buttons move past the stretch, and the two pages agree on the order |
| `ui/pages/cleanup.py` | the hand-rolled gate is the shared `ui.widgets.gate()` |
| `ui/qss.py` | one focus rule after every button variant; a disabled tab group dims |
| `tools/shoot_ui.py` | each settings page is photographed whole instead of its top 700 px |
| `tests/test_style_contracts.py` | three more contracts: destructive placement, focus survival, the rhythm (from the earlier delivery) |

Measured, not read:

```
History page, before the tour fix   the delete row was not in any frame at all
after                              101 px of danger-red text, 250 px from the
                                   last safe action on the same row
prompt field, toggle off           background surface2 (#f2ede1) = disabled
                                   (the enabled field colour is #f7f3e9)
```

### 2026-09-12 — Phase 3, surface 1 (the recording pill)

| File | Change |
|---|---|
| `overlay.py` | every interactive region of the pill gets a tooltip and an accessible description, and the widget itself gets a name; naming happens in one place, from whatever the pointer is over |
| `i18n.py` | `"Recording indicator"` → `"Kayıt göstergesi"` — the i18n guard caught the new string before the suite would have, which is what it is for |
| `tests/test_overlay_refinement.py` | a `RegionNames` contract: each region is named, the empty case clears rather than goes stale, Pause says Resume when paused, and a new `_hover_*` flag in the source without a region name fails the suite |

Proven red before green: with naming restored to meeting-only, the contract names
the gap — `the expand region has no name`, `the live region has no name`, `the
meeting region has no name`.

### 2026-09-12 — Phase 3, surface 2 (the live card)

| File | Change |
|---|---|
| `ui/live_popup.py` | the card is as tall as its text, between `MIN_HEIGHT` and the compact cap; the expanded state raises the cap instead of forcing a size; the chrome is measured rather than counted; the arrow takes its disabled colour where Qt will actually read it |
| `tests/test_live_popup.py` | the sizing contract: three lines do not fill a card, the card grows with the text, the compact card caps and scrolls, the arrow is offered only when there is more to reveal, a card below its cap never scrolls, the empty state exists, the disabled arrow is a different colour |
| `tools/shoot_ui.py` | the live popup is shown before it is fed (it sizes itself, and a hidden popup has no viewport to measure); the expanded frame carries a transcript long enough for the state to mean something |

Measured on the frames:

```
live card, three lines      before  460x260, one line visible, the rest dead
                            after   460x124, all three lines, no scrollbar
live card, expanded         before  460x260, the same three lines
                            after   460x460, 24 lines (the fixture now has some)
the disabled expand arrow            #585953 (fg3), was drawn in fg
arrow disabled / enabled    active on three lines (nothing more to reveal)
```

### 2026-09-12 — Phase 3, surface 3 (the thinking panel)

| File | Change |
|---|---|
| `ui/thinking.py` | the activity cue is a widget that paints its own arc from the palette instead of an empty 14×14 QLabel repainted every tick; twelve user-visible strings go through `t()`; the spinner is told when the run is paused |
| `tests/test_thinking.py` | new. The cue (it draws, it turns, a paused one holds still, the panel's own tick turns it) and the language (every label changes with the language, the paused panel is translated, the default stage is translated) |
| `tests/test_style_contracts.py` | `Spinner` joins `SELF_PAINTED` — the sheet has no rule for it because it paints its own arc |
| `tools/shoot_ui.py` | the panel is fed its stage through `t()`, like the pipeline does, so the Turkish frame stops showing English stage text |

U11, claim by claim:

| U11 claim | Verdict |
|---|---|
| "no activity indicator while its text says 'Cleaning up…'" | **True, and worse**: the cue was a bare `QLabel` — 14×14, empty, `update()`d every 33 ms, nothing ever painted |
| "does not look like the same product — different radii, font sizes" | **Unsupportable.** `docs/design-reference.md` is a settings reference and says nothing about the indicator; a 72 px pill and a 380 px panel *should* size type differently. Narrower and defensible: the pill's 24 px corner is not one of the tokens' four radii (4/6/8/12) — the scale simply does not cover it. Recorded, not changed |

Two defects found while checking it, neither of them reported:

- **The panel had no i18n at all.** `ui/thinking.py` never imported `t`, so the English
  interface showed "Dusunuyor…" with "Duraklat / Durdur / Kapat" under it — Turkish,
  ASCII-folded, in every language. Fixed; the correct spelling comes with it.
- **N7 — showing the panel resets the interface language.** `_reposition()` builds a
  `cfg.Config` to read one value, and `Config.__init__` re-applies the stored
  `ui_language` to the whole process. Harmless in the running app, where the two agree,
  and invisible until a test set a language without storing it: the language flipped back
  the moment the panel appeared. Not fixed — removing a side effect from `Config` reaches
  every one of its callers.

The tour also stops handing the panel an English stage literal, so the Turkish frame
shows what a Turkish user sees.

### 2026-09-12 — Phase 3, surface 4 (the tray menu)

| File | Change |
|---|---|
| `dikte.py` | `ask_tray_state(state, agent)` — the (icon, tooltip) choice for the tray while the assistant has the microphone. Both tooltips name the configured assistant instead of a fixed one |
| `i18n.py` | `"Dikte: recording for {name}"` and `"Dikte: talking to {name}"` replace the two entries that had "Claude" baked into the source string |
| `tests/test_tray_menu.py` | the tooltip names whoever is configured (five providers), a paused assistant says paused, a working one wears the working icon, the two states do not share a cue, and the tooltips are translated with the name intact |

The tray menu had no test of its own contents before this — `tests/test_tray_menu.py`
covered the meeting timestamps and the hint painting, not the menu.

U12, claim by claim:

| U12 claim | Verdict |
|---|---|
| icons | 11 actions, each given an icon; `tests/test_icon_contracts.py` already fails on a name the icon set does not have |
| separators | 4, grouping the menu as dictation / meetings / settings+restart / quit |
| toggle state | present and layered: the label ("Start recording" → "Stop and transcribe" → "Working…"), an icon accent (green record dot while capturing, red stop while the agent runs, red discard while a recording stands to be lost) and the tooltip. PAUSED deliberately shares RECORDING's label — `dikte.py` says pause is the overlay's button and the main toggle stays stop — so the menu does not separate them and the tooltip does. Checked, left alone |
| **the defect nobody reported** | both ask tooltips named a **fixed** assistant: "Dikte: recording for Claude", "Dikte: talking to Claude", two lines under an `agent = assistant.display_name(self.conf)` that had already worked out the right one and was being used for the action labels above them. A Codex, Antigravity or local-model user was told the wrong program had their microphone. The Turkish entries had quietly dropped the name — "Dikte: ajan için kaydediyor" — which is the tell |

What could not be verified: the menu as a desktop tray draws it. The tour has no tray and
`QSystemTrayIcon` has nothing to attach to offscreen, so the menu's painting and its
contents are covered separately but never together.

### 2026-09-12 — Phase 3, surface 5 (empty states)

| File | Change |
|---|---|
| `settings_ui.py` | `_load_voice_jobs` hides the recovery card when nothing is retryable — it used to render in every state, an empty list box and a dead Retry button in the best space on the History page |
| `ui/pages/overlay.py` | the Indicator page's empty state sits between two stretches instead of under the title with a void beneath it |
| `tools/shoot_ui.py` | one retryable voice job is seeded, so the recovery card is photographed filled and enabled rather than only as an empty box |
| `tests/test_empty_states.py` | new. The card hides with no jobs, appears with a retryable one, stays hidden for a completed one; the empty state has slack above and below, and the page still says what it says |

U4, claim by claim:

| U4 claim | Verdict |
|---|---|
| "the History 'recoverable' card is a large empty box" | **True, and worse.** The card was not a box that happened to be empty, it was a card that rendered in *every* state, always claiming there was something to recover. Fixed. The tour had no failed job seeded, which is why every frame showed it empty and why the finding was recorded as a size problem |
| "the dashboard's empty chart card holds a full card's height" | **Unsupportable.** The two chart cards share a row and the right-hand one carries a real donut, so the row's height comes from something with content in it; the empty card centres its own "No data yet", which is the treatment U4 asks for elsewhere |
| "the Overlay page never centres its empty state" | **True.** `EmptyState` centres its own contents but nothing centred `EmptyState`; the page added a trailing stretch and pushed it to the top. Fixed, and measured in the frame as centred |

Left alone, deliberately: the job list inside a *filled* card keeps its fixed 110 px cap,
so one job leaves space below it. The rows word-wrap, so content-sizing would need
per-row `sizeHintForRow` and would misjudge itself when built before the first layout
pass — the failure that made the live popup's first sizing attempt scroll.

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
- **N1 — the screenshot tour was lying about the theme it captured.** `theme.apply(thm)`
  in `tools/shoot_ui.py` set the application sheet, but the settings window applies
  the *saved* theme as it opens (`settings_ui.py:558`), so every frame was drawn in
  the config default. It was invisible for as long as the tool's default (`blue,orange`)
  happened to share its first entry with the config default (`blue`): the `orange`
  run was rendering blue, and nothing said so. Found only because the default moved
  to `dark` and the "light" frames came out dark — and then proven, not assumed:
  `light_tr_page01.png` and `dark_tr_page01.png` were byte-identical
  (`sha=4d78bde6b7f4` both), and distinct after the fix. Fixed by giving the tour's
  config the theme it is presenting. **A verification tool that cannot fail loudly is
  not verification**, and this one had been silently passing for its whole life.

- **N2 — terracotta cannot carry button text.** `docs/design-reference.md` says the
  primary action is "ink charcoal, bg #242628, NOT orange" and it turns out to be a
  constraint, not a preference: the button's label measures 3.51:1 on the light
  theme's `accent` and 2.58:1 on the dark one's, both under AA, and `accentDeep`
  only just clears it (4.72 / 4.61) — too close to spend on a filled control. So
  the filled button is ink (14.5 / 16.6:1) and terracotta is what the reference says
  it is: the recording signal. Two consequences worth recording. The QSS carried a
  terracotta `variant="primary"` that **no call site used**, so the styling existed
  and nothing wore it; and the actual Save button was unstyled, which is U2 (no
  button hierarchy) in its concrete form — repaired here by making Save a primary.

- **N3 — a style rule that matches nothing fails silently, in three ways.** The
  plan treated "the sheet has no effect" as one class of bug; doing the work found
  three shapes of it, each of which renders a default-looking widget and raises
  nothing. (1) **Wrong widget class:** the sidebar's engine card was a `QWidget`
  while the sheet styles cards as `QFrame#card`, so the card had no surface and no
  border — 0 px, where the fix produces 19 371. "The status line is too faint" had
  been treated as a contrast problem through two palette revisions; no palette can
  fix a missing card. `tests/test_style_contracts.py` now asks which widget class
  received each objectName and whether any rule reaches it. (2) **Cascade order:**
  `ghost` and `danger` set `border-color: transparent` below `QPushButton:focus`,
  and QSS resolves equal specificity by document order, so those two variants had
  no focus ring at all. Guarded per variant — the obvious version of that test
  passes while they are broken, because `seg:focus` sits below them and answers for
  the family. (3) **A selector Qt does not support:** `QTabBar:disabled::tab` is
  accepted and does nothing, while `QTabBar::tab:disabled` works. Only measuring
  told them apart. The lesson is that a style change needs a measurement attached,
  because "it looks fine" and "the rule never applied" look identical.

- **N4 — the tour was photographing the top of every page.** Every settings page
  lives in a scroll area and the capture was a fixed 1000×700, so the History
  page's delete row and the Minutes page's action row had never appeared in any
  frame of any run. That is not a small blind spot: it is the lower half of four
  pages, and it is why the button-hierarchy work had to be reordered on faith
  before it could be checked at all. `tools/shoot_ui.py` now measures each page and
  grows the window to fit it — 700 to 2040 px, at each page's own height — and the
  reorder was then confirmed on the frame.

- **N5 — U10 was mostly stale, and one of its parts contradicted the product's own
  documentation.** The survey listed four faults in the recording pill, written
  from `blue_tr_overlay_rec.png`, a frame from the generation before the design
  work. Re-checked against the code and a current frame: the timer *does* carry
  recording context (a red dot, a monospaced timer and Pause/Stop read as one
  control); Pause and Stop are *not* cramped, they are separate circles with a
  visible gap; and "there is no drag affordance" asks for behaviour the product
  documents against — `i18n.py:887` tells the user the indicator "sürüklenemez"
  ("cannot be dragged") and Settings places it by corner, so a drag handle would
  contradict shipped copy. The fourth claim, "the centre glyph is unlabelled and
  low-contrast", was half right and the half that mattered was not contrast: the
  glyph is drawn in `fg3` at 5.6:1 and brightens on hover, which is deliberate, but
  it had **no name in any form** — no tooltip, no accessible description, and no
  visible text anywhere in the interface. Pause and Stop were in the same position.
  That is now fixed and guarded. **Third UI finding in a row to be mostly wrong
  about the current product**; the survey's screenshots are from an older
  generation, and this plan should stop trusting any finding that has not been
  re-checked against source.

- **N6 — U6 was half right, and the half that was wrong was wrong for a reason
  worth recording.** "The live card does not size to its content" held: 260 px of
  fixed card with three lines in it. "It has no empty state" did not — the text
  area has carried a placeholder since it was written, and the survey read the
  absence of an empty-*looking* frame as the absence of an empty state, because it
  had no frame of an empty card to look at. That is the same mechanism as N5:
  a claim about what is missing, made from a screenshot of a case that happens to
  be populated. **Four UI findings in a row have now been partly or wholly wrong**,
  and every one of them from a screenshot. Fixing the sizing then found two defects
  *nobody had reported*, both of which had been invisible precisely because the card
  was a fixed height: the card was always one line short of its own text (the sheet's
  8 px text padding is invisible to a count made from the layout margins), and the
  disabled expand arrow drew in the enabled colour (a palette colour never reaches a
  QToolButton whose text Qt resolves through QStyleSheetStyle). The lesson is the
  converse of N4's: a wrong size hides other faults, so correcting one is worth a
  fresh look at everything that renders through it.

- **N7 — reading a config value re-applies the interface language to the whole
  process.** `Config.__init__` ends by calling `i18n.set_language(self.data["ui_language"])`,
  so *constructing* a `Config` is not a read: it is a global side effect. `ThinkingPopup._reposition()`
  builds one to look up `overlay_corner`, which means showing the panel quietly resets the
  language to whatever is stored. Nothing is visibly wrong in the running app — the stored
  language and the applied one are the same by construction — which is exactly why it went
  unnoticed until a test set a language without storing it and watched it revert the moment
  the panel appeared. Left unfixed on purpose: the fix is to move the call to the two places
  that actually change the language, and that touches every caller of `Config` in a codebase
  where `Config` is constructed freely, including on paint paths. Recorded so that the next
  person who writes a language-sensitive test does not spend an hour on it.

- **A static check for "strings that never reach `t()`" cannot work here, and its first
  output was 182 false positives.** The tray tooltips looked like untranslated literals and
  were not: the sink is `self.tray.setToolTip(t(tip))`, so a literal assigned to `tip` is
  translated there. The scan flagged 182 strings that are all *table entries* — navigation
  labels, provider names, corner names — reached through `t(<variable>)`, which a literal
  scan cannot follow. It is worth recording because the temptation was to "fix" 182 strings
  that were never broken, and because the honest alternative already exists and costs little:
  build the surface in two languages and compare what it shows, one label at a time. That is
  what caught the thinking panel's untranslated literals, and it catches table indirection,
  variable assignment, and anything else the static scan cannot see.

  The same scan failed a second way on its next outing, and this one is specific to
  Turkish: looking for ASCII-folded words in the translations, it reported 63 of them —
  every one of them a false positive caused by `re.IGNORECASE`, under which Turkish `ı`
  and `i` fold together, so the pattern for `toplanti` matched the correct `Toplantı`.
  Matching both spellings exactly instead finds **zero**, and the string I started from
  (`"son 30 gun"`, read off a frame) is `"son 30 gün"` in the table. Two lessons: a scan
  over Turkish text must not use case-insensitive matching, and a diacritic read off a
  small rendering is not evidence of a missing diacritic.

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

*Begun from a read-only survey of `master @ ffe8a5c` on 2026-09-12; Phases 0, 1 and
2 executed the same day. Turkish twin: [`ROADMAP-tr.md`](ROADMAP-tr.md).*
