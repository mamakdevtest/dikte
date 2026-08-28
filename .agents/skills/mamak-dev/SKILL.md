---
name: mamak-dev
description: Orchestrator for /mamak-dev — analyze any prompt, map to the minimal set of Mamak One skills via ROUTING.md, and delegate to parallel subagents for fast implementation.
---

# Mamak Dev Orchestrator

Use when the prompt starts with `/mamak-dev` or when the user wants the full Mamak One skill system to be applied automatically without manually picking skills.

This skill does not replace domain skills. It **routes**. Every rule from `mamak-one-architecture` and `AGENTS.md` still applies.

## Trigger

```
/mamak-dev <task in natural language>
```

Examples:
```
/mamak-dev frontend tarafindaki ui ux guncelle ana menudeki hatalari analiz edip fixle
/mamak-dev Electron IPC'ye yeni kanal ekle ve vault entegrasyonunu kontrol et
/mamak-dev SQLite settings tablosu ekle migration ile
```

## Workflow (must follow exactly)

### 1. Analyze prompt (no code yet)
- Extract intent, domains, trust boundaries, platforms (Windows/macOS/Linux).
- Read `Master-Architecture.md` relevant sections + existing ADRs/contracts.
- State what is known vs. what is missing (do not invent stack).

### 2. Map to skills via ROUTING.md
Inspect `.agents/skills/INDEX.md` and `ROUTING.md`, then select the **minimum sufficient set**.

Common mappings (from `ROUTING.md:13`):
- Architecture/boundary → `mamak-one-architecture` (+ `architecture-decision-records` if new contract)
- Theia extension/widget → `theia-development` + `current-docs-research`
- React/UI → `theia-development` + `react-best-practices` + `composition-patterns`
- Electron/IPC/preload/window → `electron-security` + `current-docs-research`
- Process/lifecycle/health → `electron-security`
- Git/GitHub PKCE/vault → `github-oauth-pkce` + `electron-security`
- SQLite/migration → `sqlite-persistence`
- MCP/agent tool → `mcp-development`
- Bug/failure → `systematic-debugging`
- Test/regression → `desktop-testing`
- Version-sensitive API → `current-docs-research`
- Missing expertise → `find-skills` (hardened, project-local only)

Do not load unrelated skills. If prompt covers multiple domains, union the sets and deduplicate.

### 3. Load selected SKILL.md files
Read each selected `SKILL.md` completely before planning. Apply their constraints (e.g., `shell=false`, vault rules, `safeStorage` provider check, permission diff).

### 4. Plan and delegate with subagents
Create a short plan with 3-7 steps, then delegate in parallel when the agent supports subagents.

**Delegation model:**

| Subagent | Owns | Loads |
|---|---|---|
| `explore` | Repo scan, file map, existing contract/ADR read | `mamak-one-architecture` + domain skill |
| `frontend` | Theia widget / React component / UI fix | `theia-development`, `react-best-practices`, `composition-patterns` |
| `backend` | Service, JSON-RPC, process, manifest, SQLite | `sqlite-persistence` or `electron-security` as needed |
| `security` | Trust boundary, IPC, vault, OAuth, MCP | `electron-security`, `github-oauth-pkce`, `security-threat-model` |
| `debug` | Root-cause before fix | `systematic-debugging` |
| `test` | Contract/widget/Electron test selection | `desktop-testing` |

Rules:
- One subagent = one domain slice, no overlapping file ownership.
- Each subagent reads only its required `SKILL.md` files.
- If subagents are unavailable (Cursor/Codex without teams), run the same slices sequentially and keep the slice isolation.
- Spawn subagents in parallel where independent (explore + debug can run together; frontend/backend after explore).

### 5. Implement smallest complete change
- Keep Application vs Workspace separation.
- No raw shell strings from renderer/repo/manifest. Use typed service + `shell=false`.
- Never expose secrets, never destructive `git reset --hard`, preserve dirty workspaces.
- New trust boundary / contract / persistence / updater / dependency → write ADR first (`architecture-decision-records`).

### 6. Verify proportionally then hand off
- Run only `skill paths valid / SKILL.md exists / frontmatter / routing / bootstrap` structural checks by default. Do not run full build/E2E unless task explicitly asks.
- Before claiming success, run `verification-before-completion` evidence gate.
- Report: domains detected → skills used → subagents spawned → files changed → checks passed.

## Example: `/mamak-dev frontend tarafindaki ui ux guncelle ana menudeki hatalari analiz edip fixle`

1. Analyze → domains: `frontend/React`, `Theia widget`, `desktop UI`, `bug fix` → boundaries: `renderer` (no vault/IPC).
2. Select → `mamak-one-architecture`, `theia-development`, `react-best-practices`, `composition-patterns`, `systematic-debugging`, `desktop-testing`, `verification-before-completion` (+ `current-docs-research` only if API version touched).
3. Plan → `1) debug: systematic-debugging ile ana menu hatalari root-cause 2) frontend: composition-patterns ile menu component API duzelt 3) theia: widget lifecycle fix 4) test: desktop-testing ile widget contract test`
4. Delegate → spawn `debug` + `explore` in parallel, then `frontend` subagent, then `test` check.
5. Verify → structural checks + `verification-before-completion`.

## Constraints (never bypass)

- `.agents/skills/` is the only maintained skill source. Never copy skills into `.claude/skills` manually; use `scripts/ai/bootstrap-agents.*`.
- External examples never override `Master-Architecture.md`, Electron security, or ADR requirements.
- Version-sensitive work must run `current-docs-research` (installed version → official docs → current API).
- Keep edits minimal; no unrelated refactors, no 50-skill bulk load.
