"""Tests for the in-process LLM backends and the model layer around them.

Three groups:

* **llama.cpp** — run against a *real* tiny GGUF built by ``gguf_fixture``, so
  the integration is exercised through actual llama.cpp inference, not mocks.
  Skipped (not failed) when llama-cpp-python isn't installed.
* **transformers** — the client is verified for configuration, probing and the
  precise reason it is unavailable; without PyTorch installed here the weight
  path is skipped, which is exactly what the code promises users.
* **Brain / API** — the transformer is the default brain, MYGPT_ARCH=mlp still
  works, an MLP checkpoint is refused by the transformer instead of crashing,
  and the new endpoints answer.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mygpt.hf_backend import HFClient                      # noqa: E402
from mygpt.llamacpp_backend import LlamaCppClient          # noqa: E402

try:
    import llama_cpp                                        # noqa: F401
    HAVE_LLAMACPP = True
except Exception:
    HAVE_LLAMACPP = False
try:
    import torch                                            # noqa: F401
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False


def _clean_env(**overrides):
    """Environment with every backend knob cleared, then overridden."""
    keys = [k for k in os.environ
            if k.startswith("MYGPT_") or k in ("OLLAMA_HOST",)]
    saved = {k: os.environ.pop(k) for k in keys}
    os.environ.update({k: str(v) for k, v in overrides.items()})
    return saved


def _restore(saved):
    for k in list(os.environ):
        if k.startswith("MYGPT_") or k == "OLLAMA_HOST":
            os.environ.pop(k)
    os.environ.update(saved)


class LlamaCppClientTests(unittest.TestCase):
    """Real llama.cpp inference on a synthesised GGUF."""

    @classmethod
    def setUpClass(cls):
        if not HAVE_LLAMACPP:
            raise unittest.SkipTest("llama-cpp-python is not installed")
        from gguf_fixture import tiny_gguf
        cls.gguf = tiny_gguf()

    def setUp(self):
        self.saved = _clean_env(MYGPT_LLAMACPP_MODEL=self.gguf)
        self.tmp = tempfile.mkdtemp()
        self.client = LlamaCppClient(os.path.join(self.tmp, "llamacpp.json"))

    def tearDown(self):
        self.client.unload()
        _restore(self.saved)

    def test_package_is_importable(self):
        self.assertTrue(self.client.package_available())

    def test_available_with_a_real_model_file(self):
        self.assertTrue(self.client.available())

    def test_probe_reports_the_model_and_version(self):
        info = self.client.probe()
        self.assertEqual(info["kind"], "llamacpp")
        self.assertTrue(info["available"])
        self.assertTrue(info["package"])
        self.assertTrue(info["package_version"])
        self.assertEqual(info["model"], os.path.basename(self.gguf))
        self.assertEqual(info["reason"], "")
        self.assertIn("llama.cpp", info["project_url"])

    def test_loads_the_model_with_real_llama_cpp(self):
        llm = self.client.load()
        self.assertIsNotNone(llm)
        self.assertEqual(self.client.loaded_model, self.gguf)
        self.assertGreater(llm.n_vocab(), 200)          # byte vocab + specials
        self.assertIsNotNone(self.client.load_seconds)
        # a second call must reuse the loaded instance, not reload
        self.assertIs(self.client.load(), llm)

    def test_generate_runs_real_inference(self):
        text = self.client.generate("hello world", max_tokens=8,
                                    temperature=0.8)
        self.assertIsNotNone(text)
        self.assertIsInstance(text, str)
        self.assertLessEqual(len(text), 400)

    def test_chat_returns_text(self):
        answer = self.client.chat("say something", history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        self.assertIsNotNone(answer)
        self.assertIsInstance(answer, str)

    def test_history_is_trimmed_and_roles_filtered(self):
        history = [{"role": "tool", "content": "ignore me"}]
        history += [{"role": "user", "content": f"turn {i}"} for i in range(20)]
        messages = self.client._messages("last", history)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["content"], "last")
        # system + at most MAX_HISTORY_TURNS turns + the new message
        self.assertLessEqual(len(messages), 1 + 6 + 1)
        self.assertNotIn("tool", {m["role"] for m in messages})

    def test_context_is_clamped_to_the_trained_window(self):
        """Loading 2048 tokens of context on a 512-token model is a bug."""
        self.assertEqual(LlamaCppClient.model_context_length(self.gguf), 512)
        self.client.n_ctx = 2048
        llm = self.client.load()
        self.assertEqual(self.client.effective_n_ctx, 512)
        self.assertEqual(llm.n_ctx(), 512)

    def test_unload_clears_the_model(self):
        self.client.load()
        self.client.unload()
        self.assertIsNone(self.client.loaded_model)

    def test_discovery_finds_a_model_dropped_in_the_models_dir(self):
        models_dir = os.path.join(self.tmp, "models")
        os.makedirs(models_dir, exist_ok=True)
        target = os.path.join(models_dir, "dropped.gguf")
        with open(target, "wb") as handle:
            handle.write(b"GGUF")                       # discovery, not loading
        client = LlamaCppClient(models_dir=models_dir)
        client.model_path = ""
        self.assertIn(os.path.realpath(target),
                      [os.path.realpath(p) for p in client.discover()])
        self.assertEqual(client.resolved_model(), target)

    def test_configure_persists_settings(self):
        path = os.path.join(self.tmp, "cfg.json")
        client = LlamaCppClient(path)
        client.configure(model_path=self.gguf, n_ctx=256, temperature=0.5)
        with open(path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["n_ctx"], 256)
        self.assertAlmostEqual(saved["temperature"], 0.5)
        # a fresh client reads it back
        again = LlamaCppClient(path)
        self.assertEqual(again.n_ctx, 256)

    def test_disabled_client_is_unavailable(self):
        self.client.configure(enabled=False)
        self.assertFalse(self.client.available())
        self.assertEqual(self.client.probe()["reason"], "disabled")
        self.assertIsNone(self.client.chat("hello"))

    def test_no_model_means_unavailable_with_a_helpful_reason(self):
        client = LlamaCppClient()
        client.model_path = os.path.join(self.tmp, "nothing-here.gguf")
        client.models_dir = os.path.join(self.tmp, "empty-models")
        self.assertFalse(client.available())
        reason = client.probe()["reason"]
        self.assertIn(".gguf", reason)
        self.assertIsNone(client.chat("hello"))
        self.assertIsNone(client.generate("hello"))

    def test_load_raises_without_a_model(self):
        client = LlamaCppClient()
        client.model_path = ""
        client.models_dir = None
        for key in ("MYGPT_LLAMACPP_MODEL",):
            os.environ.pop(key, None)
        with self.assertRaises(RuntimeError):
            client.load()

    def test_a_corrupt_gguf_is_reported_not_crashed(self):
        bad = os.path.join(self.tmp, "broken.gguf")
        with open(bad, "wb") as handle:
            handle.write(b"this is not a GGUF file")
        client = LlamaCppClient()
        client.model_path = bad
        self.assertTrue(client.available())        # a file exists...
        self.assertIsNone(client.chat("hello"))    # ...but llama.cpp rejects it
        self.assertTrue(client.last_error, "the real llama.cpp error is kept")
        self.assertIsNone(client.loaded_model)


class HFClientTests(unittest.TestCase):
    """The transformers client: configuration and honest unavailability."""

    def setUp(self):
        self.saved = _clean_env()
        self.tmp = tempfile.mkdtemp()
        self.client = HFClient(os.path.join(self.tmp, "hf.json"))

    def tearDown(self):
        _restore(self.saved)

    def test_probe_explains_what_is_missing(self):
        info = self.client.probe()
        self.assertEqual(info["kind"], "hf")
        self.assertIn("package", info)
        self.assertIn("torch", info)
        if not self.client.available():
            self.assertTrue(info["reason"])
            if not info["torch"]:
                self.assertIn("torch", info["reason"].lower())
            elif not info["package"]:
                self.assertIn("transformers", info["reason"].lower())

    def test_no_model_is_unavailable(self):
        self.assertFalse(self.client.available())
        self.assertIsNone(self.client.chat("hello"))
        self.assertIsNone(self.client.generate("hello"))

    def test_local_directory_needs_config_json(self):
        empty = os.path.join(self.tmp, "not-a-model")
        os.makedirs(empty, exist_ok=True)
        self.client.model = empty
        resolvable, why = self.client.model_resolvable()
        self.assertFalse(resolvable)
        self.assertIn("config.json", why)

    def test_local_directory_with_config_resolves(self):
        model_dir = os.path.join(self.tmp, "tiny-model")
        os.makedirs(model_dir, exist_ok=True)
        with open(os.path.join(model_dir, "config.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"model_type": "gpt2"}, handle)
        self.client.model = model_dir
        resolvable, why = self.client.model_resolvable()
        self.assertTrue(resolvable, why)

    def test_offline_mode_refuses_hub_ids(self):
        self.client.model = "some/model-on-the-hub"
        self.client.offline = True
        resolvable, why = self.client.model_resolvable()
        self.assertFalse(resolvable)
        self.assertIn("offline", why)

    def test_hub_id_resolves_when_online(self):
        self.client.model = "some/model-on-the-hub"
        self.client.offline = False
        resolvable, why = self.client.model_resolvable()
        self.assertTrue(resolvable)
        self.assertIn("hub", why)

    def test_configure_persists(self):
        path = os.path.join(self.tmp, "cfg.json")
        client = HFClient(path)
        client.configure(model="Qwen/Qwen2.5-0.5B-Instruct", device="cpu",
                         max_tokens=64, temperature=0.3)
        again = HFClient(path)
        self.assertEqual(again.model, "Qwen/Qwen2.5-0.5B-Instruct")
        self.assertEqual(again.max_tokens, 64)
        self.assertAlmostEqual(again.temperature, 0.3)

    def test_load_explains_why_it_cannot(self):
        if HAVE_TORCH:
            self.skipTest("torch is present; the failure path differs")
        with self.assertRaises(RuntimeError) as ctx:
            self.client.load()
        self.assertIn("torch", str(ctx.exception).lower())

    def test_prompt_falls_back_to_a_transcript(self):
        text = self.client._prompt("what is a trie", [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        self.assertIn("what is a trie", text)
        self.assertIn("MyGPT", text)


class BrainArchitectureTests(unittest.TestCase):
    """The Brain ships the transformer by default, and stays compatible."""

    def setUp(self):
        self.saved = _clean_env(MYGPT_CHECKPOINTS=tempfile.mkdtemp())
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        _restore(self.saved)

    def _brain(self, **env):
        for key, value in env.items():
            os.environ[key] = str(value)
        from mygpt.brain import Brain
        return Brain(tempfile.mkdtemp(), os.path.join(ROOT, "seed_corpus.json"))

    def test_default_brain_is_a_transformer(self):
        brain = self._brain(MYGPT_BLOCKS=1, MYGPT_DIM=32, MYGPT_HEADS=2)
        self.assertEqual(brain.arch, "transformer")
        self.assertEqual(brain.lm.arch, "transformer")
        self.assertGreater(brain.lm.param_count(), 1000)

    def test_mlp_arch_still_selectable(self):
        brain = self._brain(MYGPT_ARCH="mlp")
        self.assertEqual(brain.arch, "mlp")
        self.assertEqual(getattr(brain.lm, "arch", "mlp"), "mlp")

    def test_model_card_describes_the_brain(self):
        brain = self._brain(MYGPT_BLOCKS=2, MYGPT_DIM=32, MYGPT_HEADS=4,
                            MYGPT_CTX=4)
        card = brain.model_card()
        self.assertEqual(card["arch"], "transformer")
        self.assertEqual(card["blocks"], 2)
        self.assertEqual(card["heads"], 4)
        self.assertEqual(card["dim"], 32)
        self.assertEqual(card["context"], 4)
        self.assertGreater(card["params"], 0)
        self.assertIn("backends", card)
        self.assertIn("brain", card["backends"])

    def test_backend_summary_lists_every_engine(self):
        brain = self._brain(MYGPT_BLOCKS=1, MYGPT_DIM=32, MYGPT_HEADS=2)
        summary = brain.backend_summary()
        for key in ("brain", "cortex", "ollama", "llamacpp", "hf"):
            self.assertIn(key, summary)
            self.assertIn("available", summary[key])
        self.assertTrue(summary["brain"]["available"])

    def test_mlp_checkpoint_is_refused_by_the_transformer(self):
        """Downgrading the architecture must not crash the boot."""
        from mygpt.langmodel import NeuralLM
        data_dir = tempfile.mkdtemp()
        # write an MLP-shaped checkpoint into the data dir
        mlp = NeuralLM()
        mlp.observe("the old brain knew this")
        mlp.rebuild_vocab()
        mlp.save(os.path.join(data_dir, "lm_weights.npz"))
        with open(os.path.join(data_dir, "corpus.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(["the old brain knew this", "and this too"], handle)
        from mygpt.brain import Brain
        brain = Brain(data_dir, None)        # default arch = transformer
        self.assertEqual(brain.arch, "transformer")
        # the corpus was re-tokenised rather than silently dropped
        self.assertIn("old", " ".join(brain.lm.word2idx))

    def test_unknown_architecture_falls_back_to_the_transformer(self):
        brain = self._brain(MYGPT_ARCH="not-a-real-arch", MYGPT_BLOCKS=1,
                            MYGPT_DIM=32, MYGPT_HEADS=2)
        self.assertEqual(brain.arch, "transformer")


class ModelApiTests(unittest.TestCase):
    """The /api/model, /api/generate and /api/engines surface."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        saved = _clean_env(
            MYGPT_DATA=os.path.join(cls.tmp, "data"),
            MYGPT_CHECKPOINTS=os.path.join(cls.tmp, "ckpts"),
            MYGPT_CORTEX_ENABLED="0", MYGPT_OLLAMA_ENABLED="0",
            MYGPT_LLAMACPP_ENABLED="0", MYGPT_HF_ENABLED="0",
            MYGPT_BLOCKS="1", MYGPT_DIM="32", MYGPT_HEADS="2", MYGPT_CTX="4",
        )
        cls.saved = saved
        sys.path.insert(0, ROOT)
        import app as app_module
        cls.app_module = app_module
        app_module.app.config["TESTING"] = True
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        _restore(cls.saved)

    def test_model_endpoint_describes_the_transformer(self):
        body = self.client.get("/api/model").get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["arch"], "transformer")
        self.assertGreater(body["params"], 0)
        self.assertGreater(body["vocab"], 0)
        self.assertIn("vision", body)
        self.assertIn("training", body)

    def test_engines_endpoint_covers_all_five(self):
        body = self.client.get("/api/engines").get_json()
        self.assertTrue(body["ok"])
        for key in ("brain", "cortex", "ollama", "llamacpp", "hf"):
            self.assertIn(key, body["engines"])
        self.assertTrue(body["engines"]["brain"]["available"])

    def test_topnext_returns_ranked_probabilities(self):
        body = self.client.get("/api/model/topnext?q=the cat sat").get_json()
        self.assertTrue(body["ok"])
        preds = body["predictions"]
        self.assertEqual(len(preds), 5)
        probs = [p["probability"] for p in preds]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertLessEqual(sum(probs), 1.0 + 1e-6)

    def test_topnext_validation(self):
        self.assertEqual(self.client.get("/api/model/topnext").status_code, 400)
        long_q = "x" * 500
        self.assertEqual(
            self.client.get(f"/api/model/topnext?q={long_q}").status_code, 400)

    def test_generate_samples_from_the_brain(self):
        body = self.client.post("/api/generate", json={
            "prompt": "the cat", "tokens": 6, "temperature": 0.8}).get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["engine"], "brain")
        self.assertEqual(body["arch"], "transformer")
        self.assertIsInstance(body["text"], str)
        self.assertIn("ms", body)

    def test_generate_clamps_extreme_parameters(self):
        body = self.client.post("/api/generate", json={
            "tokens": 10 ** 6, "temperature": 99, "top_k": -5, "top_p": 42
        }).get_json()
        self.assertIn("ok", body)          # clamped, never a 500

    def test_engine_config_validates_the_engine_name(self):
        r = self.client.post("/api/engine/config", json={"engine": "nope"})
        self.assertEqual(r.status_code, 400)

    def test_engine_config_applies_llamacpp_settings(self):
        r = self.client.post("/api/engine/config", json={
            "engine": "llamacpp", "model_path": "/tmp/does-not-exist.gguf",
            "n_ctx": 1024})
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["applied"]["n_ctx"], 1024)
        self.assertIn("status", body)

    def test_engine_config_applies_hf_settings(self):
        body = self.client.post("/api/engine/config", json={
            "engine": "hf", "model": "some/model", "device": "cpu"}).get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["applied"]["model"], "some/model")


if __name__ == "__main__":
    unittest.main()
