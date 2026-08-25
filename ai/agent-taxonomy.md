# Dikte Agent Taxonomy (canonical)

Vendor-neutral agent/subagent role cards. Any harness that supports
subagents (Claude Code, OpenCode, ZCode, Antigravity, Codex-style
orchestrators) maps these onto its own mechanism. Harnesses without
subagent support use them as role prompts for sequential work.

Rules that apply to every agent:

- Workers never spawn other workers; only the Lead orchestrates.
- Ownership boundaries are strict: two agents must never write the same
  file concurrently — the Lead partitions sections or serializes.
- Every agent records a ≤6-line handoff summary (agent, files owned,
  outcome, evidence) in the active Context Ledger `AGENTS.md` file.
- Model/effort policy is expressed as intent classes, resolved from the
  verified capability cache (`~/.claude/cache/mamak-model-capabilities.json`
  when present): `worker` = implementation effort, `hard` = root-cause /
  architecture / fresh verification effort. Never spawn with an unverified
  model/effort tuple.

## Agent map

| ID | Role | Class | Write scope |
|---|---|---|---|
| A1 | architect | hard | docs only (`ai/**`, design notes) |
| W1 | python-impl | worker | assigned modules + their tests |
| W2 | platform-runtime | worker | hotkey/paste/audio/ipc/installers + tests |
| W3 | test-engineer | worker | `tests/**` (+ minimal prod hooks) |
| S1 | security-reviewer | hard | none (read-only report) |
| D1 | docs-i18n | worker | README*, docs/, i18n.py |
| V1 | fresh-verifier | hard | none (read-only diff review) |

## Role cards

### A1 — architect (hard)
- Purpose: cross-module design decisions, root-cause hypotheses, partitioning
  work for workers; owns the canonical `ai/` layer content.
- Read: everything. Write: `ai/**`, task plans. Never touches runtime code.
- Tools: read/grep/graphify query; web only for official docs.
- Skills: graphify; systematic-debugging (for hypothesis discipline).
- Verification: design claims must cite file:symbol anchors.

### W1 — python-impl (worker)
- Purpose: implements features/fixes in core app modules (`dikte.py`,
  `cli.py`, `config.py`, `settings_ui.py`, `worker.py`, `ggml.py`, `api.py`,
  `providers.py`, `cleanup.py`, `assistant.py`, `meeting.py`,
  `filetranscribe.py`).
- Tools: full edit/test loop. Skills: test-driven-development,
  systematic-debugging, dikte-testing.
- Verification: targeted unittest modules green; no new third-party imports;
  Qt widget access stays on the GUI thread.

### W2 — platform-runtime (worker)
- Purpose: Windows/Linux/macOS behavior in `hotkey.py`, `paste.py`,
  `audio.py`, `ipc.py`, install/update scripts; process lifecycle hygiene
  (no leaked child processes, idempotent start/stop).
- Skills: dikte-testing, systematic-debugging.
- Verification: deterministic cross-platform tests; claims about untestable
  platforms stay explicitly marked runtime-only.

### W3 — test-engineer (worker)
- Purpose: regression coverage for reproduced failures; keeps the offscreen
  Qt architecture and env scrubbing intact.
- Scope: `tests/**`; may add minimal seams to production code.
- Skills: test-driven-development, verification-before-completion.
- Verification: `python -m unittest discover --verbose`.

### S1 — security-reviewer (hard)
- Purpose: reviews diffs and provider-related changes for secret exposure,
  unsafe subprocess/download paths, over-broad config reads.
- Read-only: reports findings with file:symbol evidence; Lead applies fixes.
- Skills: dikte-providers; verification-before-completion.

### D1 — docs-i18n (worker)
- Purpose: README.md / README.tr.md accuracy, docs/ assets, Turkish strings
  for new UI text in i18n.py. No invented capabilities in docs.
- Verification: en/tr key parity check; doc commands match live CLI.

### V1 — fresh-verifier (hard)
- Purpose: independent end-to-end review after implementation. Must NOT be
  an author of the code under review (fresh session/context).
- Checks: complete diff, root-cause validity, race/lifecycle risks, missing
  tests, unjustified success claims; runs the full suite + `git diff --check`.
- Output: findings list; Lead fixes valid findings and re-runs tests.
