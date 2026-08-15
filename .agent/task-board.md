# Task Board — LLM API (llmapi.ai) provider integration into Dikte

Coordinator: team-lead (llm-api/qwen3.8-max, xhigh).
Approved models: `llm-api/qwen3.8-max` (visual/coordinator, start xhigh),
`llm-api/deepseek-v4-flash-0731` (non-visual, start high). No third models.

## Assignments

| ID | Role/Owner | Model | Start effort | Attempts | Fallback chain | Owns (files/modules) | Deps | Status | Notes |
|----|------------|-------|--------------|----------|----------------|----------------------|------|--------|-------|
| A1 | Research — repo wiring (deep) | deepseek-v4-flash-0731 | high | 1 | — | none (read-only) | — | in-progress | settings_ui/cli/i18n/tests deep map |
| A2 | Research — LLM API docs | deepseek-v4-flash-0731 | high | 1 | — | none (read-only, web) | — | in-progress | first-party docs only |
| A3 | Research — STT/TTS audio feasibility | deepseek-v4-flash-0731 | high | 1 | — | none (read-only) | — | in-progress | Dikte STT path + LLMAPI catalog |
| D1 | Docs — README.md / README.tr.md | deepseek-v4-flash-0731 | high | 1 | — | README.md, README.tr.md | A2 | in-progress | text only, no invented capabilities |
| C1 | Impl — api.py + config.py | deepseek-v4-flash-0731 | high | 0 | — | api.py, config.py | swarm | pending |
| C2 | Impl — cleanup.py / assistant.py / meeting.py | deepseek-v4-flash-0731 | high | 0 | — | cleanup.py, assistant.py, meeting.py | C1 | pending |
| C3 | Impl — cli.py | deepseek-v4-flash-0731 | high | 0 | — | cli.py | C1 | pending |
| U1 | Impl — settings_ui.py + i18n.py | deepseek-v4-flash-0731 | high | 0 | — | settings_ui.py, i18n.py | C1 | pending |
| T1 | Tests — unittest coverage | deepseek-v4-flash-0731 | high | 0 | — | tests/ | C2,C3,U1 | pending |
| V1 | Vision QA — settings screenshots | llm-api/qwen3.8-max | xhigh | 0 | effort ladder only | none | U1,T1 | pending |
| R1 | Independent review + regression | llm-api/qwen3.8-max | xhigh | 0 | effort ladder only | whole diff | T1 | pending |

## Discoveries
- ROUTING: harness rejects `deepseek` as an agent model override (allowed: sonnet|opus|haiku|fable only). `llm-api/deepseek-v4-flash-0731` cannot be pinned per agent here. All workers run on the session model `llm-api/qwen3.8-max` (approved). No unapproved third model used. Fallback event logged below.
- LLMAPI first-party live findings (api.llmapi.ai, 2026-08-14):
  - `GET /v1/models` → HTTP 200, no auth required. `{"data":[…]}`, 389 models. Entry fields: id, name, description, family, created, free, pricing, context_length, architecture{tokenizer, input_modalities, output_modalities}, providers[] (providerId, reasoningLevels, defaultReasoningLevel, contextSize, streaming, vision, tools, reasoning…), supported_parameters[], top_provider, web_search. Schema mirrors OpenRouter.
  - Error shape: `{"error":{"message","type":"invalid_request_error","param","code"}}` (OpenAI-style; existing api._extract_error handles it). Codes seen: missing_authorization, invalid_api_key, missing_content_type, missing_request_body.
  - Reasoning vocabulary in metadata: low/medium/high/xhigh/max — matches Dikte REASONING_LEVELS; `reasoning` in supported_parameters of text models.
  - Audio catalog: 47 models audio→text (whisper-1, gpt-4o-transcribe, nova-3, scribe_v2, ink-whisper…; params language/timestamps/sample_rate/seconds), 15 models text→audio (gpt-4o-mini-tts, sonic-3, aura-2, eleven_v3…; params voice/speed/encoding).
  - STT GATE VERDICT: **NOT VERIFIED** — no first-party doc of an audio invocation protocol; gateway applies global middleware (content-type/body/auth) identically on fake and real routes, so HTTP probes cannot prove route existence; no credentials for live test. Decision: LLM API will be text-only (cleanup, assistant, minutes). NOT added to TRANSCRIBERS. No TTS/realtime.

## Blockers
- none yet

## Fallback events
- none yet

## Validation evidence
- Baseline: `python -m unittest discover` → 960 tests OK (6.4s), branch master @ 77b26e7.

## Handoff/sync log
- 14:58 board created; swarm launched (A1/A2/A3/D1).
