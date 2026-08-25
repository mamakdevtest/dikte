# Dikte AI Control Plane

One canonical source of project truth (`AGENTS.md` + this `ai/` directory);
every coding agent adapts to it through a thin per-client shim.

## Layout

| Path | Role |
|---|---|
| `../AGENTS.md` | Universal entry point (vendor-neutral). Keep ≤ 32 KiB — Codex truncates beyond that and no client expands imports except Claude. |
| `architecture.md` | Canonical architecture facts (module map, tests, platforms, providers, security). |
| `workflows.md` | Task conventions: truth hierarchy, quality rules, test contract, ledger contract, git discipline. |
| `agent-taxonomy.md` | Agent/subagent taxonomy with ownership, tools, verification duties. Named to avoid collision with recursive AGENTS.md discovery (Codex merges every AGENTS.md from root to CWD). |
| `skills/` | Agent Skills (SKILL.md format, agentskills.io): `dikte-*` are project-authored; `vendor/` holds pinned external skills. |
| `mcp-registry.json` | Desired MCP servers described once; client configs derive from it. |
| `../tools/ai_sync.py` | Deterministic generator: materializes skills into client dirs, validates the layer. Run after editing anything here. |

## Client adapter matrix (verified 2026-08-25)

| Client | Instruction discovery | Adapter in this repo |
|---|---|---|
| Claude Code | `CLAUDE.md` (+ `@import`, depth 4); project skills `.claude/skills/<name>/SKILL.md`; project MCP `.mcp.json` | Thin `CLAUDE.md` importing `@AGENTS.md`; generated `.claude/skills/` |
| Codex CLI | `AGENTS.md` natively, root→CWD merge, 32 KiB cap | None (reads canonical directly) |
| OpenCode | `AGENTS.md` natively (beats CLAUDE.md fallback) | None |
| Gemini CLI | `GEMINI.md` default; extra names via settings `context.fileName` | Project `.gemini/settings.json` listing `AGENTS.md` |
| Antigravity | Workspace rules `.agents/rules/` (v2.x; `.agent/rules` legacy); AGENTS.md support community-reported | Thin always-on rule `.agents/rules/dikte.md` |
| ZCode / GLM | Workspace-root `AGENTS.md` natively; no nested merge, no imports | None (root file is the contract) |
| Generic / ChatGPT-class | `AGENTS.md` de-facto standard | None |

Adapters contain no project knowledge — only pointers. Never grow an
adapter past a few lines; put content in the canonical files instead.

## Editing rules

1. Change knowledge in exactly one place: `ai/**` or `AGENTS.md`.
2. After edits run `python tools/ai_sync.py --check` (or without `--check`
   to regenerate `.claude/skills/`).
3. External vendor skills are refreshed by bumping the pinned commit in
   `skills/vendor/manifest.json` and re-running the sync tool's
   `--refresh-vendor` step documented inside it; inspect diffs before committing.
4. The Context Ledger is session state and never enters this layer.
