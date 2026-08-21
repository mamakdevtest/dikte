"""Who rewrites the transcript once it has been heard.

Normally the local model: llama.cpp on this machine, no key and no bill, and a
dictation left uncleaned when no model is configured — the callers keep the raw
transcript either way. A machine with Claude Code, Codex or Antigravity on it
is already paying for a model though, and the subscription that answers "put
that in my calendar on Thursday" can just as well take the "eee"s out of a
sentence. A hosted gateway set up in its day still answers too. The CLIs cost
seconds rather than one, because one opens a whole session to do it, which is
the trade.

Whoever does it, the job is the same one: no tools, no files, no memory of the
last dictation. There is nothing here to look up and nothing to carry over, and
a transcript is text from a microphone rather than an instruction, so the less
the agent can reach while it reads one, the better.
"""

import os
import shutil
import subprocess
import tempfile

import api
import assistant
import ggml
import providers
from i18n import t

# The retired hosted gateways stay dispatchable: a config still set to one is
# a user who set it up, and the run must keep reaching it.
PROVIDERS = ("local", "claude", "codex", "antigravity",
             "openrouter", "llmapi")


def _subprocess_kwargs():
    """Keep Windows from flashing a console for a wrapped subprocess."""
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


class CleanupError(api.ApiError):
    """What a CLI could not do.

    An ApiError because to the chain a cleanup that failed is a cleanup that
    failed, whichever way it was run, and every caller already catches one and
    keeps the raw transcript.
    """


def provider(conf):
    chosen = conf["cleanup_provider"]
    # A user/* gateway is a real choice, not an unknown name: it must not be
    # quietly traded for the local model.
    if chosen.startswith("user/"):
        return chosen
    return chosen if chosen in PROVIDERS else "local"


def executable(name):
    """The CLI a provider runs, or "" when it needs none."""
    return {"claude": "claude", "codex": "codex", "antigravity": "agy"}.get(
        name, "")


def model(conf):
    """Which model does the cleaning, for the history and the settings window."""
    name = provider(conf)
    if name == "local":
        return conf["local_llm_model"]
    if name == "llmapi":
        return conf["cleanup_llmapi_model"]
    if name == "claude":
        return conf["cleanup_claude_model"].strip() or "haiku"
    if name == "codex":
        # Codex is left on whatever it is set to unless a model is typed in, so
        # here there is only the name of the thing that did it.
        return conf["cleanup_codex_model"].strip() or "codex"
    if name == "antigravity":
        # A slug, and the suggestion rather than nothing: an Antigravity with
        # no model named would pick its own default, which the history could
        # not then say.
        return conf["cleanup_agy_model"].strip() or "gemini-3.6-flash-medium"
    if name.startswith("user/"):
        # The gateway's own entry holds its model; an empty one rides to the
        # request and is refused there rather than borrowing another
        # provider's choice.
        return providers.custom_model(conf, name, providers.TEXT)
    return conf["cleanup_model"]


def run(text, conf, system_prompt, timeout=180, aborter=None):
    """Hand the transcript to whoever is set to clean it up.

    `aborter` is only of use to the two that answer over HTTP; a CLI is stopped
    between blocks instead, which is close enough when a block is seconds.
    """
    return _dispatch(provider(conf), text, conf, system_prompt, timeout,
                     aborter)


# What the settings window's model test sends: a sentence nobody would miss
# and an instruction with one right answer. Neither the user's cleanup prompt
# nor any key rides with them.
_TEST_TEXT = "This is a test."
_TEST_PROMPT = "Reply with exactly: OK"


def test_model(conf, timeout=None):
    """One minimal run through the cleanup provider and model set right now.

    It answers with the model's reply, or raises what run() would raise: the
    point is to prove the whole road — key, address, model id, CLI — rather
    than to clean anything. The wait is run()'s, floors included: a live agy
    run takes minutes whatever the text is.
    """
    return _dispatch(provider(conf), _TEST_TEXT, conf, _TEST_PROMPT,
                     timeout if timeout is not None else 180)


def _dispatch(name, text, conf, system_prompt, timeout, aborter=None):
    """One cleanup request, routed to the provider named.

    Both a dictation and the settings window's model test go through here, so
    the road a test proves is the road the next real cleanup takes.
    """
    if name.startswith("user/"):
        # A gateway out of Settings: the same OpenAI-shaped request as the
        # hosted ones, with the key and the address off its registry entry.
        who = providers.provider(conf, name)
        return api.cleanup(
            text, providers.credential(conf, name), model(conf), system_prompt,
            reasoning=conf["cleanup_reasoning"],
            base_url=providers.base_url(conf, name),
            service=who.name if who else name, timeout=timeout,
            aborter=aborter,
        )
    if name == "openrouter":
        return api.cleanup(
            text, conf.openrouter_key(), conf["cleanup_model"], system_prompt,
            reasoning=conf["cleanup_reasoning"],
            base_url=conf["openrouter_base_url"], timeout=timeout,
            aborter=aborter,
        )
    if name == "llmapi":
        # The same OpenAI-shaped request, one base URL over. LLM API's catalog
        # reports its own effort levels, so the thinking setting rides along.
        return api.cleanup(
            text, conf.llmapi_key(), conf["cleanup_llmapi_model"], system_prompt,
            reasoning=conf["cleanup_reasoning"],
            base_url=conf["llmapi_base_url"], timeout=timeout,
            provider="llmapi", service="LLM API", aborter=aborter,
        )
    if name == "local":
        return _local(text, conf, system_prompt, timeout, aborter)
    if name == "antigravity":
        # A live agy run takes minutes; the shared 180-second default would
        # kill it, so the floor is 300 unless the caller already waits longer.
        return _agy(text, conf, system_prompt, max(timeout, 300))
    runner = _claude if name == "claude" else _codex
    return runner(text, conf, system_prompt, timeout)


def _local(text, conf, system_prompt, timeout, aborter=None):
    """llama.cpp, on this machine, answering the request OpenRouter answers.

    No key and no bill, and the address does not exist until the server is up,
    which is what starting it here is for. The timeout is the hosted one raised:
    the only thing being spent is time.
    """
    service = t("Local model")
    try:
        return api.cleanup(
            text, "", conf["local_llm_model"], system_prompt,
            reasoning=conf["local_llm_reasoning"],
            base_url=api.serving(ggml.llm),
            timeout=max(timeout, api.LOCAL_TIMEOUT),
            provider="local-llm", service=service, aborter=aborter,
        )
    except api.ApiError as exc:
        # A server that died mid-request would otherwise report only that the
        # connection dropped, when the reason is in its own output.
        raise api.local_failure(service, ggml.llm, exc) from None


def _wrap(text):
    """The same fence the OpenRouter call puts around it: this is the material,
    not the instruction, however much of it reads like one."""
    return f"<transcript>\n{text}\n</transcript>"


# --- Claude Code ----------------------------------------------------------

def _claude(text, conf, system_prompt, timeout):
    cmd = [
        "claude", "-p", _wrap(text),
        # --system-prompt rather than --append-system-prompt: the cleanup rules
        # are the whole job, and Claude Code's own instructions are about
        # working on a codebase.
        "--system-prompt", system_prompt,
        "--model", model(conf),
        "--output-format", "text",
        "--tools", "",                                    # nothing to run
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--no-session-persistence",                       # nothing to resume
    ]
    effort = assistant.CLAUDE_EFFORT.get(conf["cleanup_reasoning"], "")
    if effort:
        cmd += ["--effort", effort]

    answer = _output(cmd, timeout, "Claude")
    if not answer:
        raise CleanupError(t("{service} answered with nothing.", service="Claude"))
    return answer


# --- Codex ----------------------------------------------------------------

def _codex(text, conf, system_prompt, timeout):
    # Codex takes no system prompt of its own, so the rules ride in front of the
    # transcript, kept apart from it so the two are not read as one.
    body = f"{system_prompt}\n\n---\n\n{_wrap(text)}"
    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",          # it has no reason to touch the disk
        "--skip-git-repo-check",
        "--ephemeral",                     # nothing to resume
        "--color", "never",
        "-c", 'approval_policy="never"',   # there is nobody here to approve
    ]
    if conf["cleanup_codex_model"].strip():
        cmd += ["-m", conf["cleanup_codex_model"].strip()]
    effort = assistant.CODEX_EFFORT.get(conf["cleanup_reasoning"], "")
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']

    # `codex exec` prints a header, its thinking and a token count around the
    # answer; the file it writes on the way out is the answer on its own.
    handle, last_message = tempfile.mkstemp(prefix="dikte-cleanup-", suffix=".txt")
    os.close(handle)
    cmd += ["-o", last_message, body]
    try:
        _output(cmd, timeout, "Codex")
        answer = _read(last_message)
    finally:
        try:
            os.unlink(last_message)
        except OSError:
            pass

    if not answer:
        raise CleanupError(t("{service} answered with nothing.", service="Codex"))
    return answer


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


# --- Antigravity ----------------------------------------------------------

def _agy(text, conf, system_prompt, timeout):
    # `agy --print` takes no system prompt, so the rules ride in front of the
    # transcript the way Codex's do. The model slug carries its own effort
    # (…-medium, …-high) and no --effort is ever passed: a second word would
    # fight the one in the model name. A model typed in goes through exactly
    # as typed — agy refuses a slug it does not know, which is the loud
    # failure wanted here.
    body = f"{system_prompt}\n\n---\n\n{_wrap(text)}"
    cmd = [
        "agy", "--print", body,
        "--model", model(conf),
        "--output-format", "text",
    ]

    answer = _output(cmd, timeout, "Antigravity")
    if not answer:
        raise CleanupError(t("{service} answered with nothing.",
                             service="Antigravity"))
    return answer


# --- running a CLI --------------------------------------------------------

def _output(cmd, timeout, service):
    """Run cmd to the end and return what it printed.

    It runs in the home directory rather than wherever the agent is pointed: a
    project's instructions have opinions about how text should be written, and
    none of them are about this transcript.
    """
    binary = cmd[0]
    if not shutil.which(binary):
        raise CleanupError(t(
            "{binary} not found. Install it, or have OpenRouter clean up "
            "instead, under Settings → API and models.", binary=binary,
        ))
    try:
        done = subprocess.run(
            cmd, cwd=os.path.expanduser("~"), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, **_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired:
        raise CleanupError(t("{service} did not finish within {seconds} seconds.",
                             service=service, seconds=timeout)) from None
    except OSError as exc:
        raise CleanupError(t("Could not run {binary}: {error}",
                             binary=binary, error=exc)) from exc
    if done.returncode != 0:
        raise CleanupError(assistant.last_line(done.stderr) or t(
            "{service} exited with code {code}.",
            service=service, code=done.returncode))
    return (done.stdout or "").strip()
