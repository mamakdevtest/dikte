"""The provider registry: one place that knows every provider Dikte can run on.

A provider is either built in — local whisper.cpp and llama.cpp, Deepgram, the
OpenAI-compatible services, the Claude Code, Codex and Antigravity CLIs — or
created by the user in Settings: any number of OpenAI-compatible gateways,
each holding any number of named API keys. Feature code (transcription,
cleanup, assistant, meeting minutes) asks this module for a provider's
credential, base URL and models instead of keeping its own list of names.

Model lists are fetched where the provider supports it (`/models`, `agy
models`) and suggested where it does not (Claude and Codex aliases). The
boxes that offer them stay editable, so a list that lags behind the service
never blocks a model ID the user knows is there.
"""

import collections
import shutil
import subprocess
import uuid

import api

from i18n import t

# What a provider can do. Cleanup, assistant and meeting minutes are all text
# generation, so one capability covers them; speech to text is the other.
TRANSCRIPTION = "transcription"
TEXT = "text"

Provider = collections.namedtuple(
    "Provider",
    "id name kind transport base_url capabilities editable custom")

# kind              transport   credential
# openai-compatible http        API key, Authorization: Bearer
# deepgram          http        API key, Token
# local-whisper     local       none
# local-llama       local       none
# claude-cli        CLI         account/session
# codex-cli         CLI         account/session
# agy-cli           CLI         account/session

_BUILT_INS = [
    ("local", t("Local whisper"), "local-whisper", "", (TRANSCRIPTION,)),
    ("local-llm", t("Local llama"), "local-llama", "", (TEXT,)),
    ("openai", "OpenAI", "openai-compatible",
     "https://api.openai.com/v1", (TRANSCRIPTION, TEXT)),
    ("groq", "Groq", "openai-compatible",
     "https://api.groq.com/openai/v1", (TRANSCRIPTION, TEXT)),
    ("openrouter", "OpenRouter", "openai-compatible",
     "https://openrouter.ai/api/v1", (TRANSCRIPTION, TEXT)),
    ("llmapi", "LLM API", "openai-compatible",
     "https://api.llmapi.ai/v1", (TRANSCRIPTION, TEXT)),
    ("deepgram", "Deepgram", "deepgram",
     "https://api.deepgram.com/v1", (TRANSCRIPTION,)),
    ("claude", "Claude Code", "claude-cli", "", (TEXT,)),
    ("codex", "Codex", "codex-cli", "", (TEXT,)),
    ("antigravity", "Antigravity", "agy-cli", "", (TEXT,)),
]

# The flat settings a built-in HTTP provider's key lives in, and the name the
# key-test and model-fetch functions answer in. Local and CLI providers need
# neither. This is the only table that maps a built-in to its legacy storage;
# everything else goes through here.
_LEGACY = {
    "openai": ("openai_api_key", "openai_base_url"),
    "groq": ("groq_api_key", "groq_base_url"),
    "openrouter": ("openrouter_api_key", "openrouter_base_url"),
    "llmapi": ("llmapi_api_key", "llmapi_base_url"),
    "deepgram": ("deepgram_api_key", "deepgram_base_url"),
}

# Where a CLI provider's executable is. `agy` rather than something longer:
# that is the name the Antigravity installer puts on the PATH.
_EXECUTABLES = {"claude": "claude", "codex": "codex", "antigravity": "agy"}

# Claude Code has no model-list command; these aliases follow the installed
# CLI's own --model help. The box they fill is editable, so a full model id
# typed over an alias works the same way it always did.
CLAUDE_MODELS = ["haiku", "sonnet", "opus", "fable"]

# Codex names its models per account; there is nothing to list locally, so
# the box starts empty and stays editable — an empty model means "whatever
# Codex itself is set to".
CODEX_MODELS = []


def custom_providers(conf):
    """The user-created gateways, as a list of plain dicts."""
    stored = conf.get("providers") or []
    return [p for p in stored if isinstance(p, dict) and p.get("id")]


def definitions(conf):
    """Every provider: the built-ins plus the user's own, id → Provider."""
    table = {}
    for pid, name, kind, base_url, caps in _BUILT_INS:
        table[pid] = Provider(pid, name, kind, "http" if base_url else
                              ("local" if kind.startswith("local") else "cli"),
                              base_url, caps, False, False)
    for entry in custom_providers(conf):
        pid = f"user/{entry['id']}"
        table[pid] = Provider(pid, entry.get("name") or pid,
                              "openai-compatible", "http",
                              entry.get("base_url") or "",
                              (TRANSCRIPTION, TEXT), True, True)
    return table


def provider(conf, pid):
    """One provider, or None. `pid` is a registry id: `openai`, `user/...`."""
    return definitions(conf).get(pid)


def supports(conf, pid, capability):
    who = provider(conf, pid)
    return bool(who) and capability in who.capabilities


def http_providers(conf, capability=None):
    """The id → Provider table a credential-backed selector offers."""
    table = definitions(conf)
    return {pid: who for pid, who in table.items()
            if who.transport == "http"
            and (capability is None or capability in who.capabilities)}


def cli_providers():
    """The id → executable-name table of the CLI-backed providers."""
    return dict(_EXECUTABLES)


def executable(pid):
    """The installed path of a CLI provider's executable, or None."""
    name = _EXECUTABLES.get(pid)
    return shutil.which(name) if name else None


def executable_version(pid):
    """The first line of `--version`, or None when not installed."""
    path = executable(pid)
    if not path:
        return None
    try:
        out = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=15, cwd=_home(),
                             creationflags=_no_window())
        return (out.stdout or out.stderr).strip().splitlines()[0][:120]
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def _home():
    import os
    return os.path.expanduser("~")


def _no_window():
    # The same flag cleanup.py uses: a console the user did not ask for is
    # not part of any provider's interface.
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess,
                                                  "CREATE_NO_WINDOW") else 0


def base_url(conf, pid):
    """The endpoint an HTTP provider is called at."""
    if pid in _LEGACY:
        return conf[_LEGACY[pid][1]].rstrip("/")
    who = provider(conf, pid)
    return (who.base_url if who else "").rstrip("/")


# --- credentials ---------------------------------------------------------

def _custom(conf, pid):
    entry_id = pid.split("/", 1)[1] if pid.startswith("user/") else pid
    for entry in custom_providers(conf):
        if entry["id"] == entry_id:
            return entry
    return None


def credentials(conf, pid):
    """The named keys of a provider: [{id, label, enabled}], secret-free."""
    entry = _custom(conf, pid)
    if entry is None:
        # A built-in's first key is the flat setting it always was; extra
        # named keys would have nowhere legacy code looks, so one it is.
        setting = _LEGACY.get(pid, (None,))[0]
        return ([{"id": "default", "label": t("Default"), "enabled": True}]
                if setting else [])
    return [{"id": k.get("id"), "label": k.get("label") or k.get("id"),
             "enabled": k.get("enabled", True)}
            for k in entry.get("keys", [])]


def credential(conf, pid, credential_id=None):
    """The active secret of a provider, or "".

    Built-ins fall back to the environment variable named after their
    setting, the way Config.api_key always has; a custom provider's active
    key is the one its entry names.
    """
    entry = _custom(conf, pid)
    if entry is None:
        if pid not in _LEGACY:
            return ""
        return conf.api_key(_LEGACY[pid][0])
    wanted = credential_id or entry.get("active")
    keys = entry.get("keys", [])
    chosen = next((k for k in keys if k.get("id") == wanted), None)
    if chosen is None and keys:
        chosen = keys[0]
    return (chosen.get("secret") or "").strip() if chosen else ""


def active_credential(conf, pid):
    entry = _custom(conf, pid)
    return entry.get("active") if entry else "default"


def mask(secret):
    """A bullet run with the last four characters, never the key itself."""
    if not secret:
        return ""
    tail = secret[-4:] if len(secret) > 8 else ""
    return "•" * min(24, max(8, len(secret))) + tail


# --- provider and credential management ---------------------------------

def _persist(conf):
    conf["providers"] = custom_providers(conf)


def add_provider(conf, name, base_url):
    """A new OpenAI-compatible gateway. Returns its registry id."""
    entry = {"id": uuid.uuid4().hex[:10], "name": name.strip() or "Gateway",
             "base_url": (base_url or "").strip(), "enabled": True,
             "keys": [], "active": ""}
    conf["providers"] = custom_providers(conf) + [entry]
    return f"user/{entry['id']}"


def remove_provider(conf, pid):
    entry_id = pid.split("/", 1)[-1]
    conf["providers"] = [p for p in custom_providers(conf)
                         if p["id"] != entry_id]


def set_base_url(conf, pid, base_url):
    entry = _custom(conf, pid)
    if entry is not None:
        entry["base_url"] = (base_url or "").strip()
        _persist(conf)


def rename_provider(conf, pid, name):
    entry = _custom(conf, pid)
    if entry is not None:
        entry["name"] = name.strip() or entry["name"]
        _persist(conf)


def add_credential(conf, pid, label, secret):
    entry = _custom(conf, pid)
    if entry is None or not (secret or "").strip():
        return None
    key = {"id": uuid.uuid4().hex[:10], "label": (label or "").strip(),
           "secret": secret.strip(), "enabled": True}
    entry.setdefault("keys", []).append(key)
    if not entry.get("active"):
        entry["active"] = key["id"]
    _persist(conf)
    return key["id"]


def rename_credential(conf, pid, credential_id, label):
    entry = _custom(conf, pid)
    for key in entry.get("keys", []) if entry else []:
        if key["id"] == credential_id:
            key["label"] = (label or "").strip() or key["label"]
            _persist(conf)


def replace_credential(conf, pid, credential_id, secret):
    entry = _custom(conf, pid)
    for key in entry.get("keys", []) if entry else []:
        if key["id"] == credential_id:
            key["secret"] = (secret or "").strip()
            _persist(conf)


def remove_credential(conf, pid, credential_id):
    entry = _custom(conf, pid)
    if not entry:
        return
    entry["keys"] = [k for k in entry.get("keys", [])
                     if k["id"] != credential_id]
    if entry.get("active") == credential_id:
        entry["active"] = entry["keys"][0]["id"] if entry["keys"] else ""
    _persist(conf)


def set_active_credential(conf, pid, credential_id):
    entry = _custom(conf, pid)
    if entry is not None and any(k["id"] == credential_id
                                 for k in entry.get("keys", [])):
        entry["active"] = credential_id
        _persist(conf)


def custom_model(conf, pid, capability):
    """The model a custom gateway runs with for a capability, or ""."""
    entry = _custom(conf, pid)
    if entry is None:
        return ""
    return (entry.get("models") or {}).get(capability, "")


def set_custom_model(conf, pid, capability, model):
    """Remember which model a custom gateway runs with, per job.

    A gateway's cleanup model and its transcription model are two different
    answers, so the entry holds them apart rather than one flat setting.
    """
    entry = _custom(conf, pid)
    if entry is not None:
        entry.setdefault("models", {})[capability] = (model or "").strip()
        _persist(conf)


# --- model discovery ------------------------------------------------------

def fetch_models(conf, pid, capability=TEXT, timeout=20):
    """The models a provider offers for a capability, or raises ApiError.

    Called from a worker thread; nothing here touches Qt or the config file.
    """
    who = provider(conf, pid)
    if who is None:
        raise api.ApiError(t("Unknown provider."))
    key = credential(conf, pid)
    if who.kind == "openai-compatible":
        url = base_url(conf, pid)
        if pid == "openrouter":
            return api.openrouter_models(key, transcription=(
                capability == TRANSCRIPTION))
        if pid == "llmapi":
            return api.llmapi_models(key, url, transcription=(
                capability == TRANSCRIPTION))
        return api.openai_models(key, url, who.name)
    if who.kind == "deepgram":
        return api.deepgram_models()
    if who.kind == "agy-cli":
        return agy_models(timeout=timeout)
    if who.kind == "claude-cli":
        return list(CLAUDE_MODELS)
    if who.kind == "codex-cli":
        return list(CODEX_MODELS)
    if who.kind == "local-whisper":
        return sorted(api.ggml.installed_whisper_models())
    if who.kind == "local-llama":
        return sorted(api.ggml.installed_llm_models())
    raise api.ApiError(t("This provider does not list models."))


def agy_models(timeout=20):
    """The model slugs `agy models` prints, one per line.

    Antigravity is the one CLI that lists its own catalog; the call is a
    local account query, no prompt is run.
    """
    path = executable("antigravity")
    if not path:
        raise api.ApiError(t("{service} is not installed.",
                             service="Antigravity"))
    try:
        out = subprocess.run([path, "models"], capture_output=True,
                             text=True, timeout=timeout, cwd=_home(),
                             creationflags=_no_window())
    except (OSError, subprocess.SubprocessError) as exc:
        raise api.ApiError(t("Could not run {service}: {error}",
                             service="Antigravity", error=exc)) from exc
    if out.returncode != 0:
        raise api.ApiError(t("Could not run {service}: {error}",
                             service="Antigravity",
                             error=(out.stderr or "").strip()[:200]))
    # A line is `slug<TAB>Display name`; the slug is the part --model wants.
    slugs = []
    for line in out.stdout.splitlines():
        slug = line.split("\t")[0].strip()
        if slug and " " not in slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def test_provider(conf, pid, timeout=30):
    """One provider's connection verdict, as a line of text or an error."""
    who = provider(conf, pid)
    if who is None:
        raise api.ApiError(t("Unknown provider."))
    if who.kind == "deepgram":
        return api.deepgram_key_status(credential(conf, pid),
                                       base_url(conf, pid))
    if who.kind == "openai-compatible":
        key = credential(conf, pid)
        if pid == "openrouter":
            return api.openrouter_key_status(key)
        if pid == "llmapi":
            return api.llmapi_key_status(key, base_url(conf, pid))
        if not key:
            raise api.ApiError(t("{service} API key is empty. Add it in "
                                 "Settings.", service=who.name))
        api.openai_models(key, base_url(conf, pid), who.name)
        return t("Key works.")
    if who.kind in ("claude-cli", "codex-cli", "agy-cli"):
        if not executable(who.id):
            raise api.ApiError(t("{service} is not installed.",
                                 service=who.name))
        version = executable_version(who.id)
        return t("{service} found: {version}", service=who.name,
                 version=version or "?")
    if who.kind == "local-whisper":
        return (t("Ready: {model}", model=conf["local_model"])
                if conf.local_whisper_ready() else
                t("Not configured"))
    if who.kind == "local-llama":
        return (t("Ready: {model}", model=conf["local_llm_model"])
                if api.ggml.program_path(api.ggml.LLAMA,
                                         conf["local_llm_binary"])
                and conf["local_llm_model"] else t("Not configured"))
    raise api.ApiError(t("This provider cannot be tested."))
