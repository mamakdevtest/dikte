"""The provider registry: definitions, credentials, models and verdicts.

Everything here is offline. HTTP goes through support.fake_urlopen, every CLI
call through a patched providers.executable / subprocess.run, and the local
branches through a patched ggml. What is checked is the shape of the registry
and the dispatch of the calls, not what any service says today.
"""

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
                    self.config(openai_api_key="sk-k"), "openai")
        self.assertEqual(ids, ["whisper-1"])

    def test_deepgram_is_a_static_catalog(self):
        self.assertEqual(providers.fetch_models(self.config(), "deepgram"),
                         ["nova-3", "nova-2", "base", "enhanced"])

    def test_claude_lists_aliases_and_codex_nothing(self):
        conf = self.config()
        self.assertEqual(providers.fetch_models(conf, "claude"),
                         providers.CLAUDE_MODELS)
        self.assertEqual(providers.fetch_models(conf, "codex"), [])

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
