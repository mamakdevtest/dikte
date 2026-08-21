You are the **Lead Orchestrator** for a production-quality stabilization task on the Dikte repository.

A fresh `repomix-output.xml` for this active task has already been supplied. **Do not ask for another RepoMix.** Treat RepoMix as the initial repository map only. Live git state, live files, current Graphify data, tests, and runtime evidence are execution truth.

## User mission

Implement and verify the following in this priority order:

1. **Fix the critical Settings → Save crash first.**

   * The user reports that pressing **Save** in Settings can cause the running application/project to crash or terminate.
   * Find the actual root cause.
   * Add deterministic regression coverage for the reproduced failure.
   * Do not proceed as though this is solved merely because config-file writing is wrapped in an exception handler.

2. **Open Settings automatically when the application starts.**

   * When a normal GUI instance of Dikte is launched, the Settings window should appear automatically at startup.
   * Preserve explicit CLI/headless behavior. Do not cause commands intended for terminal/headless use to unexpectedly display Settings.
   * Existing IPC commands such as explicit `settings`, `toggle`, `ask`, or meeting behavior must retain their intended semantics.

3. **Make the Settings popup feel fast.**

   * The user reports that opening Settings is noticeably slow.
   * Measure/profile the path before changing it.
   * Identify work performed before the first visible paint.
   * Optimize actual bottlenecks rather than guessing.
   * Prefer showing a usable Settings shell immediately and deferring nonessential expensive initialization until after first paint where architecturally safe.
   * Do not introduce races or stale-widget updates.

4. **Fix the Windows application/window icon.**

   * The icon visible in the Windows title bar/taskbar/window chrome is currently wrong/blank/generic.
   * The repository already contains `icons/dikte.ico` and `icons/dikte.png`.
   * Tray icon handling and application/window icon handling are separate concerns.
   * Establish a reliable application-level/window-level icon policy using the shipped assets.
   * Verify title-bar/taskbar behavior as far as the current environment permits.
   * Preserve Linux behavior.

5. **Perform a focused general stability audit for actively used Windows and Linux paths.**

   * Find genuine defects related to this task and fix them.
   * Prioritize crashes, uncaught GUI-slot exceptions, process lifecycle problems, UI-thread blocking, resource leaks, Windows/Linux path/process differences, and user-visible reliability problems.
   * Do not perform unrelated refactors or speculative rewrites.

The project is intended for active daily use, so correctness and repeatability matter more than superficial patches.

---

# Mandatory startup sequence

## 1. Securely inspect live Git and Claude configuration

Before implementation:

* run `git status --short`;
* inspect current branch and HEAD;
* inspect remotes and upstream without changing them;
* inspect staged and unstaged changes;
* identify pre-existing user modifications and preserve them;
* inspect recent relevant commits if useful;
* inspect installed Claude Code version;
* inspect effective project/user/local Claude settings and relevant environment securely.

Never print, log, cache, or persist secrets such as:

* `ANTHROPIC_API_KEY`;
* `ANTHROPIC_AUTH_TOKEN`;
* provider keys;
* Authorization headers.

Do not reset, stash, discard, overwrite, or amend unrelated user work.

This task does **not** authorize a push by itself. Do not push unless a separate explicit user instruction requires it.

Record the starting Git state in task evidence.

---

# 2. Model Capability Bootstrap — before planning or subagents

Discover and deduplicate effective gateway/model IDs from non-secret configuration, including where present:

* every `ANTHROPIC_DEFAULT_*_MODEL`;
* `ANTHROPIC_MODEL`;
* `CLAUDE_CODE_SUBAGENT_MODEL`;
* `ANTHROPIC_CUSTOM_MODEL_OPTION`;
* effective Claude `model`;
* `availableModels`;
* `modelOverrides`;
* relevant role/model settings.

Use:

`~/.claude/cache/mamak-model-capabilities.json`

Fingerprint from:

* installed Claude Code version;
* normalized non-secret base URL/gateway identity;
* alias → model mappings;
* candidate model IDs;
* relevant non-secret model settings.

Default TTL: 7 days.

If a valid matching cache exists, reuse it.

If missing/stale:

1. verify the installed CLI actually supports the flags you intend to use;
2. probe every unique model concurrently at:

   * `high`
   * `xhigh`
   * `max`
3. use minimal one-turn bare/headless Claude CLI probes with no tools, MCP, repo context, hooks, or persistent session;
4. only models with zero PASS in the primary wave get a single concurrent fallback wave at:

   * `medium`
   * `low`.

Never spawn a worker with a known FAIL model/effort tuple.

Do not classify an auth/global transport failure as a model capability failure.

A runtime capability error invalidates only that tuple. Preserve worker handoff state and use the next verified fallback.

Selection policy:

* normal implementation: prefer a verified `high`;
* difficult root-cause analysis / architecture / fresh verification: use verified `xhigh` or `max` only when beneficial;
* do not choose `max` simply because it passes.

Do not expose probe response bodies or credentials.

---

# 3. Calibrate the context window

For a custom gateway, do not assume Claude Code's inferred context size is correct.

If the actual active main-model window is reliably known from configuration, use/advice the installed-version equivalent of:

`CLAUDE_CODE_AUTO_COMPACT_WINDOW=<actual-token-window>`

Use `500000` only if the active route is actually known to provide 500K.

Do not guess.

Do not disable automatic compaction globally.

---

# 4. Create/recover the Context Ledger

Create or recover:

`.claude/mamak-context/YYYY-MM-DD/HHmm-dikte-settings-stability/`

and maintain:

`.claude/mamak-context/ACTIVE.json`

Required files:

* `<date-time>-dikte-settings-stability-plan.md`
* `NOW.md`
* `DECISIONS.md`
* `WORKLOG.md`
* `AGENTS.md`
* `EVIDENCE.md`
* `COMPACTIONS.md`
* `HANDOFF.md`

Rules:

* no secrets;
* no full chat transcript;
* keep `NOW.md` authoritative and small, target <=150 lines / ~8KB;
* overwrite stale NOW state rather than endlessly appending;
* update the ledger after planning, root-cause discovery, important decisions, agent handoffs, failures/fallbacks, implementation milestones, verification, and before deliberate compaction;
* keep the ledger local/gitignored by default;
* on resume read:
  `ACTIVE.json → NOW.md → plan/DECISIONS/HANDOFF`
  before rediscovering the repository.

If current Claude Code supports it and the project does not already have equivalent hooks, verify the current hook schema before adding/reusing:

* `PostCompact`: append timestamp/trigger/`compact_summary` to active `COMPACTIONS.md`;
* `SessionStart` for `compact`/`resume`: inject a bounded recovery packet from active NOW/plan/decisions/handoff;
* optional `SessionEnd`: record last state/time.

Do not block auto-compaction merely to save state.

Keep Context Ledger/cache paths out of Graphify indexing.

---

# 5. Bootstrap/reuse Graphify

After model bootstrap and ledger setup:

* inspect `graphify --version`;
* inspect `.claude/skills/graphify/SKILL.md` if present;
* inspect `graphify-out/graph.json`;
* inspect `graphify-out/GRAPH_REPORT.md`;
* inspect relevant wiki output if present.

If Graphify CLI is genuinely absent, prefer the current supported equivalent of:

`uv tool install graphifyy`

If the project skill is absent, verify installed CLI help/current syntax before project-scoped strict installation.

Do not blindly reinstall or rebuild a valid graph.

Use Graphify **before broad raw-file reads** to narrow the relevant relationships around:

* `settings_ui.py`;
* `config.py`;
* `dikte.py`;
* `ggml.py`;
* `hotkey.py`;
* `overlay.py`;
* startup/CLI/IPC paths;
* Windows icon/launcher paths;
* relevant tests;
* process lifecycle code affected by Settings application.

Then inspect the targeted live files.

Reconcile in this order:

1. supplied RepoMix;
2. current graph;
3. targeted live files;
4. live tests/runtime.

Live source always wins.

---

# Important RepoMix investigation leads

These are leads, **not conclusions**. Verify each against live code.

## Save lifecycle

RepoMix shows `Config.save()` already uses a temporary file plus replace semantics.

The Settings UI also appears to already catch an `OSError` from `conf.save()` and has a regression test asserting that a failed settings-file write warns instead of killing the application.

Therefore do **not** stop at the JSON-writing boundary.

Trace the full path:

`SettingsWindow._save()`
→ gather/update config values
→ `conf.save()`
→ history trim/reload
→ `applied.emit()`
→ Dikte `_apply_settings()`
→ overlay state
→ local-runtime application
→ whisper/LLM stop/start/preload behavior
→ tray rebuild/refresh
→ hotkey listener stop/start/reconfiguration
→ any Qt signal/slot lifecycle
→ any spawned/background process.

`applied.emit()` is especially important because Qt direct signal delivery can synchronously enter the connected slot on the GUI thread.

Construct a deterministic test for an apply-stage failure, not merely a config-write failure.

Investigate whether operational exceptions from:

* local server reconfiguration;
* model/server stop/start;
* hotkey start/stop;
* tray rebuild;
* invalid settings combination;
* disposed Qt object;
* Windows-specific process behavior

can escape the slot/event-loop boundary or leave application state inconsistent.

Requirements for the fix:

* Save must never terminate the application because applying a setting encountered an operational error;
* the true root cause must be fixed at the correct lifecycle boundary;
* do not solve this by wrapping all of `_save()` in a broad catch and pretending success;
* persistence and runtime application should have intentional, distinguishable failure semantics;
* the user must be told when settings were saved but could not be fully applied, if that is the actual outcome;
* never display “Saved successfully” after an apply failure unless the UX explicitly distinguishes persisted vs applied state;
* repeated Save must be safe;
* unchanged Save must be idempotent;
* no leaked/zombie local servers;
* no double-started hotkey listener;
* no partially rebuilt tray state;
* expensive model warmup must not block the GUI thread;
* an apply failure must leave Dikte usable or clearly recoverable.

Consider whether `_apply_settings()` should return/report a structured result or otherwise provide an explicit error boundary rather than relying on an unguarded Qt slot.

Preserve atomic config persistence.

---

# Startup Settings behavior

The application should automatically show Settings for a **normal new GUI application startup**.

Determine the exact live startup path first:

* CLI launcher;
* `--gui`;
* application object construction;
* IPC behavior;
* startup command/verb distinctions.

Do not make every IPC-triggered invocation show Settings.

Desired behavior:

* user starts normal GUI Dikte → Settings appears automatically;
* Settings is fully foregrounded/raised when the desktop permits it;
* explicit `dikte settings` still opens Settings;
* a fresh-login hotkey path that starts Dikte specifically to perform `toggle`, `ask`, or `meeting` should preserve the requested action and must not have its workflow broken by an unwanted modal interaction;
* CLI/headless commands remain headless.

The Settings window should remain a normal non-blocking application window/dialog unless live architecture proves otherwise.

Add regression tests for the startup decision logic instead of relying only on manual observation.

---

# Settings opening performance

Do not assume network access is the main bottleneck.

RepoMix indicates model-list network calls such as cleanup/transcription catalog loading already use background threads in at least some paths.

Inspect everything executed inside `SettingsWindow.__init__` and before the first paint:

* construction of all tabs;
* filesystem/model discovery;
* executable/tool discovery;
* shortcut-status queries;
* local model scans;
* audio-device enumeration;
* history/meeting reads;
* icon/image work;
* subprocess calls;
* network initiation;
* expensive widget population;
* anything that can block Qt's GUI thread.

Measure wall-clock milestones where useful:

* request to open Settings;
* constructor start/end;
* `show()`;
* first `showEvent`/first event-loop opportunity;
* completion of deferred initialization.

Optimization goal:

**The window frame and immediately useful controls should appear quickly; nonessential expensive data may populate after first paint.**

Potential patterns, only if live evidence supports them:

* build critical shell first;
* defer expensive tab-specific initialization with `QTimer.singleShot(0, ...)`;
* lazy-initialize expensive tabs on first selection;
* keep network and subprocess calls off the GUI thread;
* cache stable local discovery for the window lifetime;
* avoid repeated work every time `open_settings()` only raises an already-open window.

Do not move Qt widget mutation onto arbitrary Python worker threads.

Make thread → Qt signal delivery safe if deferred workers can outlive/close the Settings window.

Add performance-oriented contract tests where practical; avoid fragile absolute timing tests in CI. Prefer verifying that expensive functions are deferred rather than executed synchronously in the constructor.

---

# Windows icon investigation

The repository ships:

* `icons/dikte.ico`
* `icons/dikte.png`

RepoMix indicates the tray icon already has a fallback using these files.

That does not guarantee the **application/window/taskbar/title-bar icon** is set.

Inspect:

* `QApplication` initialization;
* `QApplication.setWindowIcon(...)`;
* `SettingsWindow.setWindowIcon(...)`;
* other top-level windows;
* Windows launcher/shortcut icon metadata;
* resource path resolution when source checkout paths contain spaces or when started from a shortcut;
* whether `pythonw.exe` / launcher process identity affects taskbar presentation;
* Windows AppUserModelID only if actually necessary and appropriate—do not add it speculatively.

Prefer one centralized icon-path/icon helper if it reduces duplication and is genuinely useful.

Requirements:

* shipped Dikte icon appears on Settings/top-level Dikte window;
* application-level icon is set early enough for Windows;
* tray behavior remains correct;
* missing/corrupt asset fails gracefully;
* Linux remains functional.

Add tests that at least validate icon resolution/application in Qt offscreen mode where reliable.

Do not regenerate the icon merely because Windows currently displays the wrong icon unless the existing `.ico` is proven invalid.

---

# Cross-platform stability audit

Once the critical Save fix and requested UI behavior are implemented, perform a focused audit.

Prioritize:

## GUI exception boundaries

* Qt signal/slot callbacks that can throw;
* worker completion signals after owning dialogs are destroyed;
* shutdown/restart races;
* Settings close while async work is still running.

## Process lifecycle

* whisper/llama servers;
* ffmpeg/local helpers;
* assistant subprocesses if Settings can affect them;
* Windows `CREATE_NO_WINDOW` / detached process behavior where relevant;
* explicit terminal CLI output must remain visible;
* stop/start transitions must not leak child processes.

## Hotkeys

* repeated reconfiguration;
* start/stop idempotency;
* Windows vs Linux implementations;
* application startup Settings must not steal/break normal shortcut behavior.

## Filesystem/platform behavior

* Windows path/locking differences;
* Linux XDG paths;
* temporary settings replacement;
* local model paths;
* icon paths;
* source directory containing spaces.

Fix only defects supported by live evidence or strong deterministic tests.

Do not turn this task into an installer/uninstaller rewrite unless a directly related bug blocks the requested behavior.

---

# Agent topology

Use the smallest reliable parallel topology.

The Lead should perform Graphify narrowing centrally and provide workers with focused context rather than making every worker reread RepoMix.

## Worker A — Save / Runtime Apply Root Cause

Primary ownership candidates:

* `settings_ui.py`
* `config.py`
* `dikte.py`
* `ggml.py`
* directly relevant tests

Responsibilities:

* reproduce Save crash;
* find root cause;
* establish save-vs-apply error contract;
* fix local/runtime lifecycle;
* add deterministic regression tests.

This is priority #1.

## Worker B — Startup / Settings Performance / Icon

Primary ownership candidates:

* `dikte.py`
* `settings_ui.py`
* startup/CLI files selected by Graphify;
* icon helper if justified;
* relevant tests

Responsibilities:

* automatic Settings-on-normal-startup behavior;
* preserve verb/headless semantics;
* measure and reduce first-open latency;
* application/window icon handling;
* targeted UI tests.

If Worker A and B would both need to write the same file simultaneously, the Lead must partition exact sections/contracts or serialize the writes. Never allow uncontrolled concurrent edits to the same file.

## Worker C — Cross-platform Stability Audit

Prefer read-only until A/B contracts stabilize.

Investigate Windows/Linux defects in:

* process lifecycle;
* Qt callbacks;
* hotkey reconfiguration;
* Settings close/startup races;
* platform path behavior.

Return a short evidence-backed handoff. Implement only approved findings with clear ownership.

## Worker D — Fresh Verifier

Must not be the author of the subsystem under review.

After implementation:

* inspect complete diff;
* inspect Save root cause/failure boundary;
* inspect startup behavior;
* inspect performance change for races;
* inspect Windows icon handling;
* inspect Windows/Linux regressions;
* run targeted verification;
* identify missing tests or unjustified claims.

Lead fixes valid findings and reruns tests.

Ordinary workers must not recursively spawn workers.

Store concise worker handoffs in `AGENTS.md`; do not dump full worker transcripts into main context.

---

# Testing requirements

First establish a clean baseline from the live checkout.

RepoMix contains a prior baseline mentioning:

`python -m unittest discover`

but verify the live project/CI before assuming that is still the required command.

Inspect `.github/workflows/tests.yml`.

Run all tooling that the repository actually configures. Do not invent formatters, linters, or type checkers.

At minimum, when applicable:

* targeted Settings/UI tests;
* targeted config tests;
* targeted Dikte application lifecycle tests;
* local server lifecycle tests;
* hotkey tests;
* IPC/CLI startup tests;
* full unit test suite;
* `git diff --check`.

Add tests for:

1. apply-stage operational failure cannot terminate Save/application flow;
2. persisted-vs-applied failure UX contract;
3. repeated Save;
4. unchanged Save;
5. startup Settings decision logic;
6. explicit CLI/headless commands do not unexpectedly show Settings;
7. hotkey-start GUI verbs preserve their intended action;
8. application/window icon path/application;
9. performance change's deferral/lazy-init contract;
10. any cross-platform bug actually fixed.

Where PyQt permits, use the existing offscreen test architecture.

Do not create brittle tests that depend on pixel-perfect rendering.

---

# Runtime verification

Perform what the current host actually supports.

## If on Windows

Manually/runtime verify as safely as possible:

* normal GUI launch → Settings appears;
* Settings appears promptly;
* title bar/taskbar icon is Dikte;
* Save repeatedly with unchanged settings;
* Save after changing harmless settings;
* Save around local provider/preload changes relevant to the reproduced crash;
* close/reopen Settings repeatedly;
* app stays alive;
* tray remains responsive;
* hotkeys can be reconfigured without duplicated listeners;
* no orphan local model server processes;
* shutdown/restart remains coherent.

Use temporary/test configuration where practical. Do not damage the user's actual Dikte configuration.

## If on Linux

Runtime verify:

* startup Settings;
* opening performance;
* repeated Save;
* tray/hotkeys;
* local provider lifecycle where available;
* Linux behavior is not regressed.

## If a required platform is unavailable

Do not claim runtime success on that platform.

Strengthen deterministic tests and CI-compatible coverage and report exactly what remains platform-runtime-only.

---

# Implementation quality rules

* Prefer minimal coherent changes.
* No unrelated refactors.
* Do not suppress exceptions without understanding them.
* Do not declare a crash fixed merely because an outer `except Exception` was added.
* Do not perform expensive server startup synchronously on the Qt GUI thread.
* Keep Qt widget access on the GUI thread.
* Preserve explicit terminal CLI behavior.
* Preserve Linux semantics while fixing Windows behavior.
* Avoid duplicated platform conditionals when a small tested helper expresses the policy more safely.
* Never expose secrets.
* Never claim a test/runtime check succeeded without direct evidence.

---

# Context Ledger checkpoints

Update ledger after:

* initial git/model/graph state;
* task plan;
* Save crash reproduction;
* Save root cause discovery;
* save/apply contract decision;
* startup behavior decision;
* performance measurement/bottleneck discovery;
* icon architecture decision;
* every agent handoff;
* model/effort fallback;
* meaningful implementation milestone;
* failed verification/fix cycle;
* before deliberate compaction;
* fresh verifier result;
* final verification.

Keep `NOW.md` current and concise.

---

# Graphify completion gate

After source changes, use the installed/current equivalent of:

`graphify update .`

If the installed version has a separate semantic incremental update and relevant semantic inputs changed, run that as appropriate.

Verify:

* graph update succeeds;
* report/graph remains readable;
* ledger/cache/generated orchestration data is not polluting the graph;
* no known stale marker remains unexplained.

Graph freshness is part of task completion.

---

# Final completion criteria

Do not call the task complete until evidence supports all applicable items:

* actual Settings Save crash root cause was identified;
* deterministic regression test covers the failure path;
* Save no longer terminates the application under that path;
* config persistence remains atomic;
* runtime-apply failures have an intentional error boundary and honest user feedback;
* repeated and unchanged Save are safe;
* no local server/process leakage introduced;
* normal GUI startup automatically opens Settings;
* explicit CLI/headless/hotkey-start semantics remain coherent;
* Settings first-open latency is improved based on measured evidence;
* expensive nonessential initialization no longer unnecessarily blocks first paint;
* Windows application/window icon uses the shipped Dikte icon correctly;
* tray icon behavior remains correct;
* Windows-specific and Linux-specific relevant paths were audited;
* genuine discovered defects in scope were fixed;
* full relevant tests pass;
* fresh verifier findings were fixed or explicitly justified;
* Graphify is refreshed;
* Context Ledger/HANDOFF/EVIDENCE are finalized;
* no secrets/generated orchestration files/unrelated user changes are included.

Do not commit or push merely because an older repository prompt requested it. Follow the **current user's request** and current live Git state. If no explicit commit/push instruction exists for this task, leave the verified working-tree changes ready for review.

---

# Final report

Return a concise evidence-backed report containing:

* Save crash root cause;
* why the old behavior could terminate/crash the app;
* exact fix and runtime failure contract;
* files changed;
* startup Settings implementation;
* Settings performance bottleneck and before/after evidence where measurable;
* Windows icon root cause and fix;
* additional real defects found/fixed;
* tests added/changed;
* exact verification commands and results;
* Windows runtime checks actually performed;
* Linux runtime checks actually performed;
* platform checks that could not be executed;
* model capability cache HIT/MISS/REFRESHED state;
* actual agent/model/effort tuples used;
* any runtime tuple fallback;
* Context Ledger status;
* compaction/recovery events, if any;
* Graphify refresh/freshness;
* remaining risks.

Never report success for anything not directly verified.
