"""The provider registry: one place that knows every provider Dikte can run on.

A provider is either built in — local whisper.cpp and llama.cpp, Deepgram, the
Claude Code, Codex and Antigravity CLIs — or created by the user in Settings:
any number of OpenAI-compatible gateways, each holding any number of named API
keys. Feature code (transcription, cleanup, assistant, meeting minutes) asks
this module for a provider's credential, base URL and models instead of
keeping its own list of names.

The hosted OpenAI-compatible services this version retired from the standing
offer are still here as ghosts: a config that references one — a provider
setting naming it, a stored key, the environment holding one — gets a working
entry for it, flagged `retired`, and everything downstream (credential, base
URL, models, the key test) keeps answering through the same tables. A config
that references none never sees them offered. Gateways retired one step
further are not here at all; config.py turns whatever a config still holds of
them into a user entry before this registry is asked.

Model lists are fetched where the provider supports it — `/models`, `agy
models`, `codex debug models`, the user's own Claude settings — and suggested
where it does not (the Claude aliases). The boxes that offer them stay
editable, so a list that lags behind the service never blocks a model ID the
user knows is there.
"""

import collections
import json
import os
import re
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
    "id name kind transport base_url capabilities editable custom retired",
    defaults=(False,))   # retired: only a ghost ever carries True

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
    ("deepgram", "Deepgram", "deepgram",
     "https://api.deepgram.com/v1", (TRANSCRIPTION,)),
    ("claude", "Claude Code", "claude-cli", "", (TEXT,)),
    ("codex", "Codex", "codex-cli", "", (TEXT,)),
    ("antigravity", "Antigravity", "agy-cli", "", (TEXT,)),
]

# The hosted gateways a version of this program used to offer. Retired from
# the standing list, but a config that still references one keeps it working
# end to end, so an update takes nothing away from whoever set one up.
# OpenRouter and LLM API were retired one step further: not ghosts but gone,
# with config.py turning whatever a user still had of them into a plain
# user/* gateway on load.
# (name, kind, base_url, capabilities)
_RETIRED = {
    "openai": ("OpenAI", "openai-compatible",
               "https://api.openai.com/v1", (TRANSCRIPTION, TEXT)),
    "groq": ("Groq", "openai-compatible",
             "https://api.groq.com/openai/v1", (TRANSCRIPTION, TEXT)),
}

# The settings that point a job at a provider. A retired id in any of them is
# a config that still runs on that gateway and must keep being able to.
_PROVIDER_SETTINGS = ("transcribe_provider", "cleanup_provider",
                      "meeting_provider", "assistant_provider")

# The flat settings an HTTP provider's key lives in, and the name the
# key-test and model-fetch functions answer in. Deepgram is the one built-in
# here; the other two are the retired gateways, whose ghost entries keep
# reading their key and base URL through this same table. Local and CLI
# providers need neither. This is the only table that maps a standing or
# retired provider to its legacy storage; everything else goes through here.
_LEGACY = {
    "openai": ("openai_api_key", "openai_base_url"),
    "groq": ("groq_api_key", "groq_base_url"),
    "deepgram": ("deepgram_api_key", "deepgram_base_url"),
}

# Where a CLI provider's executable is. `agy` rather than something longer:
# that is the name the Antigravity installer puts on the PATH.
_EXECUTABLES = {"claude": "claude", "codex": "codex", "antigravity": "agy"}

# Claude Code has no model-list command; these aliases follow the installed
# CLI's own --model help. The box they fill is editable, so a full model id
# typed over an alias works the same way it always did.
CLAUDE_MODELS = ["haiku", "sonnet", "opus", "fable"]

# The four settings.json env keys that re-point a Claude alias at a full model
# id. Nothing else in that file's env is ever read: it holds tokens too.
_CLAUDE_ENV_MODELS = (
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
)

# Codex names its models per account, so its catalog is asked of the CLI
# itself (see codex_models) rather than kept here. An empty model still means
# "whatever Codex itself is set to".


def custom_providers(conf):
    """The user-created gateways, as a list of plain dicts."""
    stored = conf.get("providers") or []
    return [p for p in stored if isinstance(p, dict) and p.get("id")]


def _referenced(conf, pid):
    """Whether the config still points at a retired provider.

    Either a job's provider setting names it, or its key is there to be used —
    stored or in the environment, the way Config.api_key reads one. Anything
    else is a name nobody chose, and a retired gateway nobody chose is one the
    settings window should not be offering.
    """
    if any(conf[setting] == pid for setting in _PROVIDER_SETTINGS):
        return True
    setting = _LEGACY.get(pid, (None,))[0]
    return bool(setting and conf.api_key(setting))


def definitions(conf):
    """Every provider: the built-ins, the referenced ghosts and the user's own.

    A retired gateway joins only when the config references it (see
    _referenced) and arrives flagged `retired`, so a caller can tell a standing
    offer from a leftover that is merely still being honoured.
    """
    table = {}
    for pid, name, kind, base_url, caps in _BUILT_INS:
        table[pid] = Provider(pid, name, kind, "http" if base_url else
                              ("local" if kind.startswith("local") else "cli"),
                              base_url, caps, False, False, False)
    for pid, (name, kind, base_url, caps) in _RETIRED.items():
        if _referenced(conf, pid):
            table[pid] = Provider(pid, name, kind, "http", base_url, caps,
                                  False, False, True)
    for entry in custom_providers(conf):
        pid = f"user/{entry['id']}"
        table[pid] = Provider(pid, entry.get("name") or pid,
                              "openai-compatible", "http",
                              entry.get("base_url") or "",
                              (TRANSCRIPTION, TEXT), True, True, False)
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
        # Every OpenAI-compatible provider — the ghost gateways and the user's
        # own entries alike — answers the same /models with the same shapes.
        return api.openai_models(key, base_url(conf, pid), who.name,
                                 audio=(capability == TRANSCRIPTION))
    if who.kind == "deepgram":
        return api.deepgram_models()
    if who.kind == "agy-cli":
        return agy_models(timeout=timeout)
    if who.kind == "claude-cli":
        # settings.json knows the full ids this machine actually runs; the
        # aliases lead anyway, because they are the short names the CLI itself
        # resolves — and they are all there is when the file says nothing.
        discovered = claude_models()
        return list(CLAUDE_MODELS) + [m for m in discovered
                                      if m not in CLAUDE_MODELS]
    if who.kind == "codex-cli":
        return codex_models()
    if who.kind == "local-whisper":
        return sorted(api.ggml.installed_whisper_models())
    if who.kind == "local-llama":
        return sorted(api.ggml.installed_llm_models())
    raise api.ApiError(t("This provider does not list models."))


def _deduped(items):
    """The list without repeats, order kept — a settings file repeats itself."""
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _strings(entry, keyed=False):
    """The string model names inside a dict (its keys or values) or a list.

    Anything else — numbers, nested objects — is dropped rather than coerced:
    a model box holds model ids, and only those.
    """
    if isinstance(entry, dict):
        entry = entry.keys() if keyed else entry.values()
    elif not isinstance(entry, (list, tuple)):
        return []
    return [item for item in entry if isinstance(item, str)]


def claude_models():
    """The models the user's own Claude Code settings name, aliases included.

    ~/.claude/settings.json holds no catalog; it holds what this machine
    runs: the top-level `model` alias, the ANTHROPIC_DEFAULT_*_MODEL values
    that re-point the aliases at full ids, and whatever modelOverrides and
    availableModels add. Those fields are the whole reading list — the rest
    of the file (tokens, base URLs, other env) stays unread, because a model
    box has no business with it. A missing or unparseable file answers [],
    never a raise; the caller falls back to the aliases alone.

    The aliases the settings reference lead — or all four when none does, so
    the short names the CLI resolves are always on offer — followed by the
    full ids in the order the file gave them.
    """
    try:
        with open(os.path.join(_home(), ".claude", "settings.json"),
                  encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(settings, dict):
        return []

    env = settings.get("env")
    env = env if isinstance(env, dict) else {}
    model = settings.get("model")
    found = [model] if isinstance(model, str) else []
    found += _strings([env.get(key) for key in _CLAUDE_ENV_MODELS])
    found += _strings(settings.get("modelOverrides"))
    found += _strings(settings.get("availableModels"), keyed=True)
    found = [name.strip() for name in found]

    aliases = [alias for alias in CLAUDE_MODELS if alias in found]
    full_ids = _deduped(name for name in found
                        if name and name not in CLAUDE_MODELS)
    if not aliases and not full_ids:
        return []
    return (aliases or list(CLAUDE_MODELS)) + full_ids


# The models every Codex offers, whatever its catalog says this week. They
# seed the boxes before anything is fetched and stay in the list after it,
# so the current family is always one click away. The live catalog only
# adds to them.
CODEX_FIXED_MODELS = ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"]


def codex_models(timeout=30):
    """The models the installed Codex CLI lists, the current one first.

    `codex debug models` prints the catalog this account may run: one JSON
    object whose models each carry a slug, a visibility and a priority. The
    slugs with visibility "list" are the ones the CLI itself offers, so those
    are the ones offered here, ordered by the CLI's own priority. What
    ~/.codex/config.toml says the user runs leads — that is the answer the box
    is really for. CODEX_FIXED_MODELS ride along whatever the CLI answers,
    and are the whole answer when it answers nothing. Never raises.
    """
    current = _codex_current_model(_codex_config_text())
    exe = executable("codex")
    if not exe:
        return _deduped([current] + CODEX_FIXED_MODELS if current
                        else list(CODEX_FIXED_MODELS))
    try:
        out = subprocess.run([exe, "debug", "models"], capture_output=True,
                             text=True, timeout=timeout, cwd=_home(),
                             creationflags=_no_window())
    except (OSError, subprocess.SubprocessError):
        out = None
    listed = []
    if out is not None and out.returncode == 0:
        try:
            catalog = json.loads(out.stdout)
        except ValueError:
            catalog = None
        models = catalog.get("models") if isinstance(catalog, dict) else None
        listed = [m for m in (models if isinstance(models, list) else [])
                  if isinstance(m, dict) and m.get("visibility") == "list"]
    # Ascending by the priority the CLI assigns; one that carries none keeps
    # its place after the ones that do, in catalog order.
    listed.sort(key=lambda m: m.get("priority")
                if isinstance(m.get("priority"), (int, float))
                else float("inf"))
    slugs = [m["slug"].strip() for m in listed
             if isinstance(m.get("slug"), str) and m["slug"].strip()]
    head = ([current] if current else []) + list(CODEX_FIXED_MODELS)
    return _deduped(head + slugs)


def _codex_config_text():
    """The raw text of ~/.codex/config.toml, or "" when there is none."""
    try:
        with open(os.path.join(_home(), ".codex", "config.toml"),
                  encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _codex_current_model(text):
    """The top-level `model = "..."` of a config.toml, or "".

    tomllib is the honest read; the regex catches a file the parser refuses
    — one that holds more than Codex promises — rather than losing the model
    line with it. Only that line is ever matched, so nothing else in the
    file, keys included, can end up in a model box.
    """
    try:
        import tomllib
        try:
            data = tomllib.loads(text)
        except ValueError:          # TOMLDecodeError: not TOML after all
            data = None
        if data is not None:
            model = data.get("model")
            return model.strip() if isinstance(model, str) else ""
    except ImportError:             # Python older than the honest read
        pass
    match = re.search(r'^\s*model\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1).strip() if match else ""


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
