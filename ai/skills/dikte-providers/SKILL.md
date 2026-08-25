---
name: dikte-providers
description: Dikte provider/gateway registry rules - credentials, dispatch, legacy migration, secret handling. Use when touching providers.py, api.py, config.py credential paths, or any API-key surface.
---

# Dikte Providers & Secrets

## Registry shape (providers.py)

- Capabilities: TRANSCRIPTION, TEXT.
- Built-ins: local, local-llm, deepgram, claude, codex, antigravity.
  Retired built-ins ("ghosts", e.g. openai/groq) exist only so old configs
  keep working; they resurface solely when referenced by stored config.
- User-defined OpenAI-compatible gateways persist as `user/<uuid>` entries
  under config key `providers`, with structured credentials:
  `{keys: [{id, label, secret, enabled}], active}`.
- `_LEGACY` mapping is the only bridge between flat legacy fields
  (`*_api_key`) and registry entries; Config.load runs an idempotent
  migration. Never bypass it with ad-hoc renames.

## Dispatch paths

- Transcription: `Config.transcribe_target` (unknown target falls back to
  openai ghost for backward compat).
- Cleanup: `cleanup._dispatch` → local llama.cpp / CLI agent / user gateway.
- Assistant: `assistant.ask` → claude/codex/antigravity/plain-HTTP gateway.
- Model catalogs: `providers.fetch_models`; display-only masking via
  `providers.mask`.

## Secret handling (absolute)

1. Never print, log, or commit any `secret`/`*_api_key` value or its env var.
2. Masked display (bullets + last 4) is the only sanctioned form.
3. Env fallback reads use uppercase same-name variables; keep the scrub list
   in `tests/__init__.py` in sync when adding providers.
4. Third-party config reads stay narrow by design: Claude settings.json only
   for model fields (it also holds tokens), Codex config.toml only top-level
   `model=`. Do not widen them.
5. Downloaded model/server binaries are sha256-verified against hub.py
   metadata before execution — never relax this.

## Migration safety

- Migrations must be idempotent and lossless: raw stored keys that no longer
  map to DEFAULTS must survive inside `self.data`, not vanish on save.
- Changing provider semantics requires updating: providers.py, config.py
  migration, settings_ui boxes, i18n strings (en+tr), and targeted tests.
