# Dikte Workflows & Task Conventions (canonical)

Vendor-neutral conventions every agent follows. Client adapters may add
slash-command sugar but must not change semantics.

## Execution truth hierarchy

1. Live git state, live files, tests, runtime evidence — always win.
2. Graphify graph (`graphify-out/`) — persistent structural memory; use it
   to narrow reading before broad file reads; refresh after source changes.
3. RepoMix snapshot (`repomix-output.xml`) — initial map only; stale by
   definition once work starts.
4. This canonical AI layer (`ai/`, `AGENTS.md`) — durable rules.
5. Context Ledger (`.zcode/mamak-context/`) — current task/session state.

## Quality rules (non-negotiable)

- Never claim success without direct evidence of the verifying command.
- Do not suppress exceptions without understanding them; adding a broad
  `except Exception` does not fix a crash.
- Expensive initialization must not block the Qt GUI thread; widget access
  stays on the GUI thread.
- Persistence failures and runtime-apply failures are distinct outcomes and
  must be reported honestly to the user ("saved but could not apply" is a
  real state).
- No unrelated refactors inside a focused task.
- Secrets never appear in logs, ledgers, commits, or probe output.

## Test & verification contract

- Command: `python -m unittest discover --verbose` (see `.github/workflows/tests.yml`).
- Before starting: establish a clean baseline run and record it in EVIDENCE.md.
- After changes: targeted module tests first, then the full suite,
  then `git diff --check`.
- Use the existing offscreen Qt fixtures (tests/support.py); do not invent
  parallel test infrastructure.

## Context Ledger contract

Root: `.zcode/mamak-context/` (legacy `.claude/mamak-context/` readable,
never written). Pointer: `.zcode/mamak-context/ACTIVE.json` →
`YYYY-MM-DD/HHmm-<task-name>/`.

Required files per task: `NOW.md` (authoritative state, overwrite-not-append,
≤150 lines), `DECISIONS.md`, `WORKLOG.md`, `AGENTS.md` (worker handoffs),
`EVIDENCE.md`, `COMPACTIONS.md`, `HANDOFF.md`.

Rules:

- No secrets, no chat transcripts — distilled state only.
- The ledger stays local (gitignored); it is never committed.
- Update checkpoints: planning, root-cause discovery, decisions, agent
  handoffs, model/effort fallbacks, milestones, failed verifications,
  before compaction, final verification.
- Resume order: `ACTIVE.json` → `NOW.md` → plan/DECISIONS/HANDOFF — but
  re-verify against the live repo before trusting any of it.
- "Summary-only" mode (no writes) exists for quick status checks; only the
  persistent mode writes ledger files.

## Git discipline

- Commit/push only on explicit user instruction; leave verified changes in
  the working tree otherwise.
- Preserve user's pre-existing modifications; never reset/stash/discard them.
- Prefer feature work in a worktree when isolation matters
  (skill: using-git-worktrees).

## Graphify completion gate

After source changes: refresh the graph with the installed equivalent of
`graphify update .`, confirm it succeeds, and confirm ledger/cache/generated
state did not pollute the index. Graph freshness is part of task completion.

## Model/effort selection (when orchestrating subagents)

Resolve intent classes (`worker`, `hard`) against the verified capability
cache; if the cache fingerprint (gateway + alias map) no longer matches the
live configuration, re-probe per the Mamak spec before spawning workers.
Never spawn with a known-FAIL tuple; on tuple failure invalidate only that
tuple, keep handoff state, move to next verified fallback.
