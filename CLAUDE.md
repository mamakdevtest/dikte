@AGENTS.md

Claude Code specifics (everything else lives in `AGENTS.md` and `ai/`):

- Project skills are generated into `.claude/skills/` by
  `python tools/ai_sync.py`; edit `ai/skills/` instead.
- Project-scope MCP servers, if ever enabled, come from `.mcp.json`
  derived from `ai/mcp-registry.json`.
