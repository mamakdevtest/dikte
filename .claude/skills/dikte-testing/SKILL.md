---
name: dikte-testing
description: How to write and run tests for the Dikte PyQt6 app - offscreen Qt architecture, sandbox fixtures, deterministic regression rules. Use when adding or changing any test.
---

# Dikte Testing

## Run

```sh
python -m unittest discover --verbose   # the contract command, ~82s
python tools/quick_tests.py             # iteration: the same minus test_ui, ~14s
python tools/quick_tests.py tests.test_worker   # or just what you touched
```

Same command CI uses (`.github/workflows/tests.yml`: Linux + Windows,
Python 3.11–3.13). Only dependency: PyQt6. No network, no audio device.
`tests.test_ui` is 68 of the full suite's 82 seconds — 131 tests that each
build the whole settings window — so it is the last thing to run, not the
first. The full command is still what "done" means.

## Architecture (do not fight it)

- `tests/__init__.py` pins `QT_QPA_PLATFORM=offscreen` **before** any Qt
  import; redirects XDG_CONFIG_HOME/XDG_DATA_HOME/HOME into a temp dir;
  scrubs provider-key env vars (`OPENAI/GROQ/DEEPGRAM/..._API_KEY`) and
  locale vars at import time.
- `tests/support.py` provides `DikteTest`: per-test tmp root, patches for
  CONFIG_FILE/DATA_DIR/HISTORY/RECORDINGS/MEETINGS, blocks `os.execv` and
  network, plus fakes: `fake_urlopen` (canned HTTP replay), `FakeCompleted`
  (subprocess results), `only_these_tools` (tool-call restriction).

## Rules for new tests

1. Deterministic only: no pixel rendering, real network, audio devices, or
   wall-clock timing margins.
2. Reproduce a bug at the layer where it lives before fixing it; the
   regression test must fail on old code.
3. For Qt behavior use the existing offscreen fixtures; widget access stays
   on the GUI thread even in tests.
4. When adding a provider, extend the env-var scrub list in
   `tests/__init__.py`.
5. Prefer asserting contracts (deferred init, signal emission, file state)
   over implementation details.

## Failure triage order

1. Does it fail in isolation (`python -m unittest tests.test_x`)? → test bug.
2. Does it fail only after your change? → your change; fix forward.
3. Does it fail on master too? → record baseline in ledger EVIDENCE.md,
   don't silently absorb.
