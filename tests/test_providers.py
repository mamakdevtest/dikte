"""The provider registry: definitions, credentials, models and verdicts.

Everything here is offline. HTTP goes through support.fake_urlopen, every CLI
call through a patched providers.executable / subprocess.run, and the local
branches through a patched ggml. What is checked is the shape of the registry
and the dispatch of the calls, not what any service says today.
"""

import json
import unittest
from unittest import mock

import api
import cleanup
import config
import ggml
import providers
from tests.support import DikteTest, FakeCompleted, fake_urlopen


def gateway(conf, name="Gateway", base_url="https://gw.example/v1", keys=()):
    """A custom provider entry, with keys as (id, label, secret, active-ish)."""
    entry = {"id": "abc123", "name": name, "base_url": base_url,
             "enabled": True, "active": "", "keys": []}
    for kid, label, secret in keys:
        entry["keys"].append({"id": kid, "label": label, "secret": secret,
                              "enabled": True})
    entry["active"] = entry["keys"][0]["id"] if entry["keys"] else ""
    return entry


class Definitions(DikteTest):
    def test_every_built_in_is_present_with_its_capabilities(self):
        table = providers.definitions(self.config())
        for pid in ("local", "local-llm", "openai", "groq", "openrouter",
                    "llmapi", "deepgram", "claude", "codex", "antigravity"):
            self.assertIn(pid, table)
        self.assertEqual(table["deepgram"].capabilities,
                         (providers.TRANSCRIPTION,))
        self.assertEqual(table["antigravity"].capabilities, (providers.TEXT,))
        self.assertEqual(table["claude"].capabilities, (providers.TEXT,))
        self.assertEqual(table["local"].capabilities, (providers.TRANSCRIPTION,))
        self.assertEqual(table["local-llm"].capabilities, (providers.TEXT,))
        self.assertEqual(table["openai"].capabilities,
                         (providers.TRANSCRIPTION, providers.TEXT))

    def test_transports(self):
        table = providers.definitions(self.config())
        self.assertEqual(table["local"].transport, "local")
        self.assertEqual(table["local-llm"].transport, "local")
        self.assertEqual(table["claude"].transport, "cli")
        self.assertEqual(table["antigravity"].transport, "cli")
        self.assertEqual(table["openai"].transport, "http")

    def test_custom_providers_appear_with_user_ids(self):
        conf = self.config(providers=[gateway(conf=None, name="My gate")])
        table = providers.definitions(conf)
        self.assertIn("user/abc123", table)
        who = table["user/abc123"]
        self.assertEqual(who.name, "My gate")
        self.assertEqual(who.base_url, "https://gw.example/v1")
        self.assertTrue(who.custom)
        self.assertTrue(who.editable)
        self.assertFalse(table["openai"].custom)

    def test_broken_entries_are_dropped(self):
        conf = self.config(providers=[{"no": "id"}, "junk", gateway(None)])
        self.assertEqual(len(providers.custom_providers(conf)), 1)

    def test_supports_filters_by_capability(self):
        conf = self.config()
        self.assertTrue(providers.supports(conf, "openai", providers.TEXT))
        self.assertTrue(providers.supports(conf, "deepgram",
                                           providers.TRANSCRIPTION))
        self.assertFalse(providers.supports(conf, "deepgram", providers.TEXT))
        self.assertFalse(providers.supports(conf, "antigravity",
                                            providers.TRANSCRIPTION))
        self.assertFalse(providers.supports(conf, "nope", providers.TEXT))

    def test_http_providers_filtered_by_capability(self):
        conf = self.config(providers=[gateway(None)])
        text = providers.http_providers(conf, providers.TEXT)
        self.assertNotIn("deepgram", text)
        self.assertNotIn("local", text)
        self.assertIn("user/abc123", text)
        everything = providers.http_providers(conf)
        self.assertIn("deepgram", everything)


class CredentialResolution(DikteTest):
    def test_built_in_reads_the_flat_setting(self):
        conf = self.config(openai_api_key="sk-flat")
        self.assertEqual(providers.credential(conf, "openai"), "sk-flat")

    def test_built_in_falls_back_to_the_environment(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}):
            conf = self.config()
            self.assertEqual(providers.credential(conf, "openai"), "sk-env")

    def test_keyless_built_ins_answer_empty(self):
        conf = self.config()
        self.assertEqual(providers.credential(conf, "claude"), "")
        self.assertEqual(providers.credential(conf, "local"), "")

    def test_custom_active_credential(self):
        entry = gateway(None, keys=[("k1", "One", "s1"),
                                    ("k2", "Two", "s2")])
        entry["active"] = "k2"
        conf = self.config(providers=[entry])
        self.assertEqual(providers.credential(conf, "user/abc123"), "s2")

    def test_custom_explicit_credential_id(self):
        entry = gateway(None, keys=[("k1", "One", "s1"), ("k2", "Two", "s2")])
        conf = self.config(providers=[entry])
        self.assertEqual(
            providers.credential(conf, "user/abc123", "k2"), "s2")

    def test_missing_active_falls_back_to_the_first_key(self):
        entry = gateway(None, keys=[("k1", "One", "s1"), ("k2", "Two", "s2")])
        entry["active"] = "gone"
        conf = self.config(providers=[entry])
        self.assertEqual(providers.credential(conf, "user/abc123"), "s1")

    def test_switching_the_active_credential(self):
        entry = gateway(None, keys=[("k1", "One", "s1"), ("k2", "Two", "s2")])
        conf = self.config(providers=[entry])
        providers.set_active_credential(conf, "user/abc123", "k2")
        self.assertEqual(providers.active_credential(conf, "user/abc123"),
                         "k2")
        self.assertEqual(providers.credential(conf, "user/abc123"), "s2")
        # An id the entry does not hold changes nothing.
        providers.set_active_credential(conf, "user/abc123", "nope")
        self.assertEqual(providers.active_credential(conf, "user/abc123"),
                         "k2")

    def test_removing_the_active_credential_moves_it(self):
        entry = gateway(None, keys=[("k1", "One", "s1"), ("k2", "Two", "s2")])
        conf = self.config(providers=[entry])
        providers.remove_credential(conf, "user/abc123", "k1")
        self.assertEqual(providers.active_credential(conf, "user/abc123"),
                         "k2")
        self.assertEqual(providers.credential(conf, "user/abc123"), "s2")
        providers.remove_credential(conf, "user/abc123", "k2")
        self.assertEqual(providers.credential(conf, "user/abc123"), "")
        self.assertEqual(providers.active_credential(conf, "user/abc123"), "")

    def test_base_url_trails_no_slash(self):
        conf = self.config(openai_base_url="https://api.openai.com/v1/")
        self.assertEqual(providers.base_url(conf, "openai"),
                         "https://api.openai.com/v1")


class Management(DikteTest):
    def test_add_provider_makes_unique_ids(self):
        conf = self.config()
        first = providers.add_provider(conf, "One", "https://a.example/v1")
        second = providers.add_provider(conf, "Two", "")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("user/"))
        self.assertEqual(len(providers.custom_providers(conf)), 2)
        # A blank name still gets a usable one; a blank URL stays blank.
        third = providers.add_provider(conf, "  ", None)
        entry = providers._custom(conf, third)
        self.assertEqual(entry["name"], "Gateway")
        self.assertEqual(entry["base_url"], "")

    def test_remove_provider(self):
        entry = gateway(None)
        conf = self.config(providers=[entry])
        providers.remove_provider(conf, "user/abc123")
        self.assertEqual(providers.custom_providers(conf), [])
        self.assertIsNone(providers.provider(conf, "user/abc123"))

    def test_rename_and_rebase_provider(self):
        conf = self.config(providers=[gateway(None)])
        providers.rename_provider(conf, "user/abc123", "Renamed")
        providers.set_base_url(conf, "user/abc123", "https://n.example/v1/")
        who = providers.provider(conf, "user/abc123")
        self.assertEqual(who.name, "Renamed")
        self.assertEqual(providers.base_url(conf, "user/abc123"),
                         "https://n.example/v1")

    def test_add_credential_requires_a_secret(self):
        conf = self.config(providers=[gateway(None)])
        self.assertIsNone(providers.add_credential(conf, "user/abc123",
                                                   "Bad", "  "))
        self.assertIsNone(providers.add_credential(conf, "openai", "Bad",
                                                   "nope"))
        kid = providers.add_credential(conf, "user/abc123", "Mine", " sec ")
        self.assertTrue(kid)
        entry = providers._custom(conf, "user/abc123")
        self.assertEqual(entry["keys"][0]["secret"], "sec")
        self.assertEqual(entry["active"], kid)

    def test_rename_and_replace_credential(self):
        conf = self.config(providers=[gateway(
            None, keys=[("k1", "One", "s1")])])
        providers.rename_credential(conf, "user/abc123", "k1", "Renamed")
        providers.replace_credential(conf, "user/abc123", "k1", "s9")
        self.assertEqual(providers.credential(conf, "user/abc123"), "s9")
        entry = providers._custom(conf, "user/abc123")
        self.assertEqual(entry["keys"][0]["label"], "Renamed")

    def test_credentials_listing_has_no_secrets(self):
        entry = gateway(None, keys=[("k1", "One", "super-secret-one"),
                                    ("k2", "", "super-secret-two")])
        entry["keys"][1]["enabled"] = False
        conf = self.config(providers=[entry])
        listing = providers.credentials(conf, "user/abc123")
        self.assertEqual([k["id"] for k in listing], ["k1", "k2"])
        self.assertEqual([k["label"] for k in listing], ["One", "k2"])
        self.assertEqual([k["enabled"] for k in listing], [True, False])
        for key in listing:
            self.assertNotIn("secret", key)
        # And the stored JSON that gets written out keeps them only there.
        built_in = providers.credentials(conf, "openai")
        self.assertEqual(built_in, [{"id": "default", "label": "Default",
                                     "enabled": True}])

    def test_mask(self):
        self.assertEqual(providers.mask(""), "")
        self.assertEqual(providers.mask("short"), "•" * 8)
        self.assertEqual(providers.mask("123456789"), "•" * 9 + "6789")
        self.assertEqual(providers.mask("sk-1234567890abcd"),
                         "•" * 17 + "abcd")
        self.assertEqual(providers.mask("x" * 40), "•" * 24 + "xxxx")


class FetchModels(DikteTest):
    def test_openrouter_dispatches_to_the_openrouter_catalog(self):
        with fake_urlopen({"data": [
                {"id": "openai/gpt-4o"},
                {"id": "a/whisper-large", "architecture": {"output_modalities":
                                                    ["transcription"]}}]}) as calls:
            ids = providers.fetch_models(self.config(openrouter_api_key="k"),
                                         "openrouter")
        self.assertEqual(ids, ["a/whisper-large", "openai/gpt-4o"])
        self.assertTrue(calls[0].full_url.startswith(
            "https://openrouter.ai/api/v1/models"))

    def test_openrouter_transcription_narrows_the_query(self):
        with fake_urlopen({"data": []}) as calls:
            providers.fetch_models(self.config(), "openrouter",
                                   capability=providers.TRANSCRIPTION)
        self.assertIn("output_modalities", calls[0].full_url)

    def test_llmapi_dispatch(self):
        with fake_urlopen({"data": [
                {"id": "m-text", "architecture": {"input_modalities": ["text"],
                                                  "output_modalities":
                                                      ["text"]}},
                {"id": "m-image", "architecture": {"input_modalities":
                                                   ["image"],
                                                   "output_modalities":
                                                       ["image"]}}]}):
            ids = providers.fetch_models(self.config(), "llmapi")
        self.assertEqual(ids, ["m-text"])

    def test_openai_dispatch_and_empty_key(self):
        conf = self.config()
        with self.assertRaises(api.ApiError):
            providers.fetch_models(conf, "openai")
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            with fake_urlopen({"data": [{"id": "whisper-1"},
                                        {"id": "gpt-x"}]}):
                ids = providers.fetch_models(
                    self.config(openai_api_key="sk-k"), "openai",
                    capability=providers.TRANSCRIPTION)
        self.assertEqual(ids, ["whisper-1"])

    def test_a_custom_gateway_s_text_fetch_gets_the_whole_catalog(self):
        """The bug this pins: a cleanup fetch on a user gateway used to hand
        back the audio models, because the one /models reader always preferred
        them. For text, the gateway's full catalog is the answer."""
        entry = gateway(None, keys=[("k1", "One", "sk-gw")])
        conf = self.config(providers=[entry])
        with fake_urlopen({"data": [{"id": "whisper-1"},
                                    {"id": "glm-5"},
                                    {"id": "gpt-5.x"},
                                    {"id": "gemini-3-flash"}]}) as calls:
            ids = providers.fetch_models(conf, "user/abc123",
                                         capability=providers.TEXT)
        self.assertEqual(ids, ["gemini-3-flash", "glm-5", "gpt-5.x",
                               "whisper-1"])
        self.assertEqual(calls[0].full_url, "https://gw.example/v1/models")

    def test_a_custom_gateway_s_transcription_fetch_keeps_the_audio_models(self):
        entry = gateway(None, keys=[("k1", "One", "sk-gw")])
        conf = self.config(providers=[entry])
        with fake_urlopen({"data": [{"id": "whisper-1"},
                                    {"id": "gpt-4o-transcribe"},
                                    {"id": "gpt-5.x"}]}):
            ids = providers.fetch_models(conf, "user/abc123",
                                         capability=providers.TRANSCRIPTION)
        self.assertEqual(ids, ["gpt-4o-transcribe", "whisper-1"])

    def test_deepgram_is_a_static_catalog(self):
        self.assertEqual(providers.fetch_models(self.config(), "deepgram"),
                         ["nova-3", "nova-2", "base", "enhanced"])

    def test_claude_aliases_and_codex_suggestions_without_settings(self):
        """No Claude or Codex settings to read: the aliases stand on their
        own, and Codex offers its three suggestions. The home is patched to
        an empty one, so the machine these run on changes nothing."""
        home = self.path("empty-home")
        home.mkdir()
        with mock.patch.object(providers.os.path, "expanduser",
                               lambda p, h=str(home): p.replace("~", h, 1)):
            self.assertEqual(providers.fetch_models(self.config(), "claude"),
                             providers.CLAUDE_MODELS)
            self.assertEqual(providers.fetch_models(self.config(), "codex"),
                             providers.CODEX_MODELS)

    def test_antigravity_parses_slugs(self):
        self.patch_attr(providers, "executable",
                        mock.Mock(return_value="/usr/bin/agy"))
        done = FakeCompleted(
            stdout="slug\tName\nanother\tLong Name\nslug\tDup\n"
                   "bad slug\tSkipped\n\n",
            stderr="Fetching available models...")
        with mock.patch.object(providers.subprocess, "run",
                               return_value=done) as run:
            slugs = providers.fetch_models(self.config(), "antigravity")
        self.assertEqual(slugs, ["slug", "another"])
        self.assertEqual(run.call_args.args[0], ["/usr/bin/agy", "models"])

    def test_antigravity_not_installed(self):
        self.patch_attr(providers, "executable",
                        mock.Mock(return_value=None))
        with self.assertRaises(api.ApiError):
            providers.fetch_models(self.config(), "antigravity")

    def test_antigravity_failure_reported(self):
        self.patch_attr(providers, "executable",
                        mock.Mock(return_value="/usr/bin/agy"))
        with mock.patch.object(providers.subprocess, "run", return_value=FakeCompleted(returncode=1, stderr="boom")):
            with self.assertRaises(api.ApiError):
                providers.fetch_models(self.config(), "antigravity")

    def test_unknown_provider(self):
        with self.assertRaises(api.ApiError):
            providers.fetch_models(self.config(), "nope")


class ThrowawayHome(DikteTest):
    """A home the test owns, so the Claude and Codex readers are judged on
    what was written here, never on what the machine happens to have."""

    def home_only(self, *files):
        """Point expanduser at an empty home, then write {relative: text}."""
        home = self.path("home")
        home.mkdir(exist_ok=True)
        self.patch_attr(providers.os.path, "expanduser",
                        lambda p, h=str(home): p.replace("~", h, 1))
        for relative, text in files:
            path = home.joinpath(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return home


class ClaudeModels(ThrowawayHome):
    def settings(self, payload):
        self.home_only((".claude/settings.json", json.dumps(payload)))

    def test_the_referenced_alias_leads_the_resolved_ids(self):
        self.settings({
            "model": "fable",
            "env": {"ANTHROPIC_DEFAULT_OPUS_MODEL": "llm-api/qwen3.8-max",
                    "ANTHROPIC_DEFAULT_SONNET_MODEL": "llm-api/qwen3.8-max",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "vendor/haiku-4.5",
                    "ANTHROPIC_DEFAULT_FABLE_MODEL": "llm-api/qwen3.8-max",
                    "ANTHROPIC_API_KEY": "sk-never-in-a-model-box"},
            "apiKeyHelper": "/usr/bin/op-read",
        })
        self.assertEqual(providers.claude_models(),
                         ["fable", "llm-api/qwen3.8-max", "vendor/haiku-4.5"])

    def test_nothing_but_model_names_leaves_the_file(self):
        """The one env key that is not a model name, and any other field,
        stay unread: a model box has no business with tokens or helpers."""
        self.settings({"model": "opus",
                       "env": {"ANTHROPIC_DEFAULT_HAIKU_MODEL": "vendor/h",
                               "ANTHROPIC_API_KEY": "sk-never-appears",
                               "ANTHROPIC_BASE_URL": "https://no.pe"},
                       "primaryApiKey": "sk-also-never",
                       "apiKeyHelper": "/usr/bin/op-read"})
        models = providers.claude_models()
        for not_a_model in ("sk-never-appears", "sk-also-never",
                            "https://no.pe", "/usr/bin/op-read"):
            self.assertNotIn(not_a_model, models)
        self.assertEqual(models, ["opus", "vendor/h"])

    def test_no_alias_referenced_all_four_lead(self):
        self.settings({"env": {"ANTHROPIC_DEFAULT_FABLE_MODEL":
                               "vendor/fable-2"}})
        self.assertEqual(providers.claude_models(),
                         ["haiku", "sonnet", "opus", "fable",
                          "vendor/fable-2"])

    def test_overrides_and_available_models_in_either_shape(self):
        """modelOverrides names full ids in its values, availableModels in
        its keys — and a list shape is taken at face value either way."""
        self.settings({"modelOverrides": {"opus": "vendor/opus-max"},
                       "availableModels": {"vendor/one": {"label": "One"},
                                           "vendor/two": 2}})
        self.assertEqual(providers.claude_models(),
                         ["haiku", "sonnet", "opus", "fable",
                          "vendor/opus-max", "vendor/one", "vendor/two"])
        self.settings({"availableModels": ["vendor/one", 7, "vendor/one"]})
        self.assertEqual(providers.claude_models(),
                         ["haiku", "sonnet", "opus", "fable", "vendor/one"])

    def test_a_missing_or_silent_file_answers_nothing(self):
        self.home_only()
        self.assertEqual(providers.claude_models(), [])
        self.home_only((".claude/settings.json", "{not json"))
        self.assertEqual(providers.claude_models(), [])
        # JSON that is not an object, and an object with nothing model-shaped.
        self.home_only((".claude/settings.json", "[1, 2]"))
        self.assertEqual(providers.claude_models(), [])
        self.home_only((".claude/settings.json", "{}"))
        self.assertEqual(providers.claude_models(), [])

    def test_fetch_models_appends_the_discovered_ids_to_the_aliases(self):
        self.settings({"model": "sonnet",
                       "env": {"ANTHROPIC_DEFAULT_OPUS_MODEL":
                               "llm-api/qwen3.8-max"}})
        self.assertEqual(providers.fetch_models(self.config(), "claude"),
                         ["haiku", "sonnet", "opus", "fable",
                          "llm-api/qwen3.8-max"])


class CodexModels(ThrowawayHome):
    def config_toml(self, text):
        self.home_only((".codex/config.toml", text))

    def test_the_model_codex_runs_leads_the_suggestions(self):
        self.config_toml('model = "gpt-5.5-codex"\nmodel_provider = "openai"\n')
        self.assertEqual(providers.codex_models(),
                         ["gpt-5.5-codex"] + providers.CODEX_MODELS)
        self.assertEqual(providers.fetch_models(self.config(), "codex"),
                         ["gpt-5.5-codex"] + providers.CODEX_MODELS)

    def test_a_suggestion_set_as_current_leads_once(self):
        self.config_toml('model = "gpt-5.6-sol"\n')
        self.assertEqual(providers.codex_models(),
                         ["gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.6-terra"])

    def test_a_missing_file_leaves_the_suggestions(self):
        self.home_only()
        self.assertEqual(providers.codex_models(), providers.CODEX_MODELS)
        self.assertEqual(providers.fetch_models(self.config(), "codex"),
                         providers.CODEX_MODELS)

    def test_secrets_stay_out_of_the_model_box(self):
        """Only the top-level model line is read; keys and tokens elsewhere
        in the file, whatever they are named, never reach the list."""
        self.config_toml('model = "gpt-5.5-codex"\n'
                         'api_key = "sk-live-secret-123"\n'
                         '[env]\nOPENAI_API_KEY = "sk-env-also-secret"\n')
        models = providers.codex_models()
        self.assertEqual(models[0], "gpt-5.5-codex")
        for secret in ("sk-live-secret-123", "sk-env-also-secret"):
            self.assertNotIn(secret, models)

    def test_a_file_the_parser_refuses_still_yields_the_model(self):
        self.config_toml('model = "gpt-5.5-codex"\nnot <<< toml\n')
        self.assertEqual(providers.codex_models()[0], "gpt-5.5-codex")

    def test_an_empty_model_line_is_dropped(self):
        self.config_toml('model = ""\n')
        self.assertEqual(providers.codex_models(), providers.CODEX_MODELS)


class TestProvider(DikteTest):
    def test_openai_with_no_key(self):
        with self.assertRaises(api.ApiError):
            providers.test_provider(self.config(), "openai")

    def test_openai_with_a_key(self):
        with fake_urlopen({"data": [{"id": "whisper-1"}]}):
            verdict = providers.test_provider(
                self.config(openai_api_key="sk-k"), "openai")
        self.assertEqual(verdict, "Key works.")

    def test_openrouter_verdict(self):
        with fake_urlopen({"data": {"limit": 5, "usage": 1}}) as calls:
            verdict = providers.test_provider(
                self.config(openrouter_api_key="sk-or"), "openrouter")
        self.assertIn("Key works", verdict)
        self.assertTrue(calls[0].full_url.endswith("/key"))

    def test_llmapi_verdict(self):
        with fake_urlopen({"data": [{"id": "a"}, {"id": "b"}]}):
            verdict = providers.test_provider(
                self.config(llmapi_api_key="sk-l"), "llmapi")
        self.assertIn("2", verdict)

    def test_deepgram_verdict(self):
        with fake_urlopen({}) as calls:
            verdict = providers.test_provider(
                self.config(deepgram_api_key="dg"), "deepgram")
        self.assertEqual(verdict, "Key works.")
        self.assertIn("/listen", calls[0].full_url)

    def test_cli_providers_report_the_version(self):
        for pid in ("claude", "codex", "antigravity"):
            with self.subTest(pid=pid):
                self.patch_attr(providers, "executable",
                                mock.Mock(return_value=f"/usr/bin/{pid}"))
                done = FakeCompleted(stdout=f"{pid} 1.2.3\nsecond line")
                with mock.patch.object(providers.subprocess, "run",
                                       return_value=done):
                    verdict = providers.test_provider(self.config(), pid)
                self.assertIn("1.2.3", verdict)
                self.assertNotIn("second", verdict)

    def test_cli_provider_not_installed(self):
        self.patch_attr(providers, "executable", mock.Mock(return_value=None))
        for pid in ("claude", "codex", "antigravity"):
            with self.subTest(pid=pid):
                with self.assertRaises(api.ApiError):
                    providers.test_provider(self.config(), pid)

    def test_local_whisper(self):
        conf = self.config(local_model="ggml-base.bin")
        with mock.patch.object(conf, "local_whisper_ready",
                               return_value=False):
            self.assertEqual(providers.test_provider(conf, "local"),
                             "Not configured")
        with mock.patch.object(conf, "local_whisper_ready", return_value=True):
            self.assertIn("ggml-base.bin",
                          providers.test_provider(conf, "local"))

    def test_local_llama(self):
        conf = self.config(local_llm_model="qwen.gguf")
        with mock.patch.object(api.ggml, "program_path",
                               return_value="") as path:
            self.assertEqual(providers.test_provider(conf, "local-llm"),
                             "Not configured")
        with mock.patch.object(api.ggml, "program_path",
                               return_value="/bin/llama-server"):
            self.assertIn("qwen.gguf",
                          providers.test_provider(conf, "local-llm"))
        conf["local_llm_model"] = ""
        with mock.patch.object(api.ggml, "program_path",
                               return_value="/bin/llama-server"):
            self.assertEqual(providers.test_provider(conf, "local-llm"),
                             "Not configured")

    def test_unknown_provider_cannot_be_tested(self):
        with self.assertRaises(api.ApiError):
            providers.test_provider(self.config(), "nope")


class CustomGatewayFlow(DikteTest):
    def test_custom_provider_end_to_end(self):
        conf = self.config()
        pid = providers.add_provider(conf, "My gate", "https://g.example/v1")
        kid = providers.add_credential(conf, pid, "Home", "sk-gw")
        self.assertEqual(providers.credential(conf, pid), "sk-gw")
        with fake_urlopen({"data": [{"id": "whisper-2"}]}) as calls:
            ids = providers.fetch_models(conf, pid)
            verdict = providers.test_provider(conf, pid)
        self.assertEqual(ids, ["whisper-2"])
        self.assertEqual(verdict, "Key works.")
        self.assertTrue(calls[0].full_url.startswith("https://g.example/v1"))
        self.assertTrue(kid)

    def test_custom_provider_with_no_key(self):
        conf = self.config()
        pid = providers.add_provider(conf, "Empty", "https://g.example/v1")
        with self.assertRaises(api.ApiError):
            providers.test_provider(conf, pid)


class ConfigRoundTrip(DikteTest):
    def test_custom_providers_survive_a_save_and_reload(self):
        conf = self.config()
        pid = providers.add_provider(conf, "Kept", "https://k.example/v1")
        providers.add_credential(conf, pid, "Home", "sk-keep")
        conf.save()

        # A fresh Config over the same file, the way the next launch reads it.
        import config as cfg
        reloaded = cfg.Config()
        self.assertEqual(providers.custom_providers(reloaded),
                         providers.custom_providers(conf))
        self.assertEqual(providers.credential(reloaded, pid), "sk-keep")

    def test_defaults_contain_an_empty_provider_list(self):
        import config as cfg
        self.assertIn("providers", cfg.DEFAULTS)
        self.assertEqual(cfg.DEFAULTS["providers"], [])


if __name__ == "__main__":
    unittest.main()


class UserGatewayRuntimeTest(DikteTest):
    """A user/* gateway must reach its own key, URL and model at runtime —
    never another provider's. The UI offering it is not the contract; the
    request is."""

    def _gateway(self, model="my-whisper"):
        self.conf = self.config()
        pid = providers.add_provider(self.conf, "My GW", "https://gw.example/v1")
        providers.add_credential(self.conf, pid, "Work", "sk-gw-key-123456")
        providers.set_custom_model(self.conf, pid, "transcription", model)
        providers.set_custom_model(self.conf, pid, "text", "gw-cleaner")
        return pid

    def test_transcribe_target_uses_the_gateway_not_openai(self):
        pid = self._gateway()
        self.conf["transcribe_provider"] = pid
        self.conf["openai_api_key"] = "sk-openai-should-not-appear"
        target = self.conf.transcribe_target()
        self.assertEqual(target.provider, pid)
        self.assertEqual(target.api_key, "sk-gw-key-123456")
        self.assertEqual(target.base_url, "https://gw.example/v1")
        self.assertEqual(target.model, "my-whisper")

    def test_transcribe_target_of_a_deleted_gateway_is_a_dead_end(self):
        self.conf = self.config()
        self.conf["transcribe_provider"] = "user/gone"
        target = self.conf.transcribe_target()
        self.assertEqual(target.provider, "user/gone")
        self.assertEqual(target.api_key, "")
        self.assertEqual(target.base_url, "")

    def test_cleanup_run_sends_the_gateway_key_and_url(self):
        pid = self._gateway()
        self.conf["cleanup_provider"] = pid
        self.conf["openrouter_api_key"] = "sk-or-should-not-appear"
        sent = {}

        def fake_cleanup(text, key, model, prompt, **kw):
            sent.update(key=key, model=model, base_url=kw.get("base_url"))
            return "clean"

        with mock.patch.object(api, "cleanup", fake_cleanup):
            self.assertEqual(cleanup.run("hi", self.conf, "sys"), "clean")
        self.assertEqual(sent["key"], "sk-gw-key-123456")
        self.assertEqual(sent["base_url"], "https://gw.example/v1")
        self.assertEqual(sent["model"], "gw-cleaner")

    def test_cleanup_provider_stays_the_gateway(self):
        self.conf["cleanup_provider"] = self._gateway()
        self.assertEqual(cleanup.provider(self.conf),
                         self.conf["cleanup_provider"])

    def test_custom_models_round_trip_through_the_config(self):
        self._gateway("stt-x")
        pid = self.conf["providers"][0]["id"]
        pid = f"user/{pid}"
        self.conf.save()
        reloaded = config.Config()
        self.assertEqual(providers.custom_model(reloaded, pid, "transcription"),
                         "stt-x")
        self.assertEqual(providers.custom_model(reloaded, pid, "text"),
                         "gw-cleaner")
