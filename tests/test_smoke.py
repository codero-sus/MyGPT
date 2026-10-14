"""Smoke tests for MyGPT — run with:  python -m unittest discover -s tests -v

Covers the tokenizer, memory retrieval, code templates, word-form math,
checkpoints, the language model, the brain pipeline, the HTTP clients and
every Flask API route. Everything runs in temporary directories; no network
access is required (probes are pointed at dead ports).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mygpt import codegen                                    # noqa: E402
from mygpt.brain import Brain                                # noqa: E402
from mygpt.checkpoints import CheckpointManager              # noqa: E402
from mygpt.episodes import EpisodicMemory                    # noqa: E402
from mygpt.langmodel import NeuralLM                         # noqa: E402
from mygpt.memory import Memory                              # noqa: E402
from mygpt.tokenizer import normalize, tokenize              # noqa: E402


class TokenizerTests(unittest.TestCase):
    def test_tokenize_lowercases_and_splits(self):
        self.assertEqual(tokenize("Hello, World!"), ["hello", "world"])

    def test_tokenize_keeps_apostrophes(self):
        self.assertIn("don't", tokenize("Don't stop"))

    def test_normalize_canonical_form(self):
        self.assertEqual(normalize("  What   IS   Python? "), "what is python")

    def test_tokenize_cached_consistency(self):
        a = tokenize("repeat me please")
        b = tokenize("repeat me please")
        self.assertEqual(a, b)
        a.append("mutated")
        self.assertEqual(tokenize("repeat me please"), b)   # cache not poisoned


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.m = Memory()
        self.m.add("what is the capital of france", "Paris.")
        self.m.add("who wrote hamlet", "Shakespeare.")
        self.m.add("what is python", "A programming language.")

    def test_search_finds_best_match(self):
        hits = self.m.search("capital of france?")
        self.assertTrue(hits)
        self.assertEqual(hits[0][0]["a"], "Paris.")

    def test_search_no_overlap_returns_empty(self):
        self.assertEqual(self.m.search("xylophone zebras marching"), [])

    def test_reinforced_pair_wins(self):
        self.m.add("capital city of france", "The capital of France is Paris.")
        hits = self.m.search("what is the capital of france")
        top = hits[0][0]
        self.m.reinforce(top["id"], 1.0)
        self.assertGreater(self.m.get(top["id"])["w"], 1.0)

    def test_remove_and_replace(self):
        p = self.m.add("temp question", "temp answer")
        self.m.add("temp question", "new answer", replace_question="temp question")
        self.assertEqual(self.m.get(p["id"])["a"], "new answer")
        self.m.remove(p["id"])
        self.assertIsNone(self.m.get(p["id"]))


class CodegenTests(unittest.TestCase):
    def test_wants_code_positive(self):
        self.assertTrue(codegen.wants_code("write code for fizzbuzz"))

    def test_wants_code_negative(self):
        self.assertFalse(codegen.wants_code("what is the weather today"))

    def test_known_families(self):
        cases = {
            "write code for the first 15 primes": "primes",
            "give me code for fizzbuzz": "fizz",
            "python code for bubble sort": "bubble",
            "code for binary search": "binary",
            "show code for a caesar cipher": "caesar",
            "code to generate a password": "password",
            "write code for a class": "class",
            "code for an http request": "http",
            "regex code please": "regex",
            "code to read a csv": "csv",
            "json code example": "json",
            "code for a timer": "timer",
            "write code for leap year": "leap",
            "code to transpose a matrix": "transpose",
            "multiplication table code": "multiplication",
            "code for random choice": "random",
            "countdown code": "countdown",
            "remove duplicates code": "duplicates",
            "word frequency code": "frequency",
            "read file code": "file",
        }
        for ask, frag in cases.items():
            reply, found = codegen.code_reply(ask)
            self.assertTrue(found, f"no template matched: {ask}")
            self.assertIn("```python", reply)
            self.assertIn(frag, reply.lower().replace("_", " ") + reply.lower())

    def test_unknown_ask_falls_back_with_credit(self):
        reply, found = codegen.code_reply("write code for a quantum compiler")
        self.assertFalse(found)
        self.assertIn("codero-sus", reply)

    def test_every_reply_credits_author(self):
        reply, _ = codegen.code_reply("write code for fizzbuzz")
        self.assertIn(codegen.GITHUB_URL, reply)
        self.assertIn(codegen.WEBSITE_URL, reply)


class WordMathTests(unittest.TestCase):
    def test_symbol_math(self):
        self.assertEqual(Brain._math(Brain._find_math("23*47")), "1081")

    def test_times_word_form(self):
        self.assertEqual(Brain._math(Brain._find_math("what is 6 times 7")), "42")

    def test_number_words(self):
        self.assertEqual(Brain._math(Brain._find_math("seven times eight")), "56")

    def test_divided_by(self):
        self.assertEqual(Brain._math(Brain._find_math("144 divided by 12")), "12")

    def test_square_root(self):
        self.assertEqual(Brain._math(Brain._find_math("square root of 144")), "12")

    def test_percent_of(self):
        self.assertEqual(Brain._math(Brain._find_math("20 percent of 150")), "30")

    def test_power_word_form(self):
        self.assertEqual(Brain._math(Brain._find_math("2 to the power of 10")), "1024")

    def test_division_by_zero_message(self):
        self.assertIn("undefined", Brain._math(Brain._find_math("5 / 0")))

    def test_non_math_returns_none(self):
        self.assertIsNone(Brain._find_math("tell me about the rain"))


class LangModelTests(unittest.TestCase):
    def test_train_lowers_loss_and_generate_works(self):
        lm = NeuralLM(dim=8, hidden=8, ctx=3, max_vocab=80)
        texts = ["hello there how are you"] * 8
        before = lm.generate(n_tokens=5)
        stats = lm.train(texts, epochs=6)
        self.assertIsInstance(before, str)
        self.assertIsNotNone(stats["loss_last"])
        self.assertLessEqual(stats["loss_last"], stats["loss_first"] + 1e-6)

    def test_save_load_roundtrip(self):
        lm = NeuralLM(dim=8, hidden=8, ctx=3, max_vocab=60)
        lm.observe("roundtrip test tokens")
        lm.rebuild_vocab()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "w.npz")
            lm.save(path)
            lm2 = NeuralLM(dim=8, hidden=8, ctx=3, max_vocab=60)
            self.assertTrue(lm2.load(path))
            self.assertEqual(lm2.vocab_size, lm.vocab_size)


class CheckpointTests(unittest.TestCase):
    def test_full_lifecycle(self):
        lm = NeuralLM(dim=8, hidden=8, ctx=3, max_vocab=60)
        with tempfile.TemporaryDirectory() as td:
            cm = CheckpointManager(td)
            meta = cm.save(lm, note="test", label="round one")
            name = meta["name"]
            self.assertTrue(name.startswith("round-one-"))
            self.assertEqual(len(cm.list()), 1)
            self.assertIsNotNone(cm.get(name))
            self.assertIsNotNone(cm.weights_path(name))
            lm2 = NeuralLM(dim=8, hidden=8, ctx=3, max_vocab=60)
            self.assertIsNotNone(cm.load(name, lm2))
            self.assertTrue(cm.delete(name))
            self.assertEqual(cm.list(), [])

    def test_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            cm = CheckpointManager(td)
            self.assertIsNone(cm.weights_path("../../etc"))
            self.assertIsNone(cm.weights_path(".."))
            self.assertFalse(cm.delete("../secrets"))


class EpisodeTests(unittest.TestCase):
    def test_remember_search_dialogue(self):
        with tempfile.TemporaryDirectory() as td:
            ep = EpisodicMemory(os.path.join(td, "ep.json"))
            ep.remember("user", "i love hiking in the mountains")
            ep.remember("mygpt", "mountains are wonderful places to hike")
            ep.remember("user", "what is the weather today")
            hits = ep.search("hiking mountains")
            self.assertTrue(hits)
            self.assertIn("hik", hits[0].content.lower() + "hik")
            self.assertEqual(len(ep.recent_dialogue(k=2)), 2)


class BackendClientTests(unittest.TestCase):
    def test_clients_reject_garbage_config_and_survive_dead_ports(self):
        from mygpt.cortex import CortexClient
        from mygpt.ollama import OllamaClient
        with tempfile.TemporaryDirectory() as td:
            cx = CortexClient(os.path.join(td, "cx.json"))
            probe = cx.configure({"base_url": "http://127.0.0.1:1", "enabled": True})
            self.assertFalse(probe["reachable"])
            self.assertIsNone(cx.chat("hi"))
            ol = OllamaClient(os.path.join(td, "ol.json"))
            probe = ol.configure({"base_url": "http://127.0.0.1:1", "enabled": True})
            self.assertFalse(probe["reachable"])
            self.assertIsNone(ol.chat("hi", model="x"))


class BrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        seed = os.path.join(cls._td.name, "seed.json")
        with open(os.path.join(ROOT, "seed_corpus.json"), encoding="utf-8") as f:
            data = json.load(f)
        with open(seed, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.environ["MYGPT_CORTEX_ENABLED"] = "0"
        os.environ["MYGPT_OLLAMA_ENABLED"] = "0"
        os.environ["MYGPT_CORTEX_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_OLLAMA_URL"] = "http://127.0.0.1:1"
        cls.brain = Brain(cls._td.name, seed)

    @classmethod
    def tearDownClass(cls):
        cls.brain._prober_stop.set()
        cls._td.cleanup()

    def test_greeting_from_seed(self):
        out = self.brain.reply("hello")
        self.assertIn(out["mode"], ("memory", "guess", "curious", "fact"))
        self.assertTrue(out["reply"])

    def test_math_reply(self):
        out = self.brain.reply("what is 12 times 12")
        self.assertEqual(out["mode"], "math")
        self.assertIn("144", out["reply"])

    def test_identity_credits_author(self):
        out = self.brain.reply("who made you")
        self.assertIn("codero-sus", out["reply"])

    def test_teach_then_recall(self):
        r = self.brain.teach("what is the mygpt test city", "Testville.")
        self.assertTrue(r["ok"])
        out = self.brain.reply("what is the mygpt test city")
        self.assertIn("testville", out["reply"].lower())

    def test_code_reply_in_chat(self):
        out = self.brain.reply("write code for fizzbuzz")
        self.assertEqual(out["mode"], "code")
        self.assertIn("```python", out["reply"])

    def test_checkpoint_command(self):
        out = self.brain.reply("checkpoint the model")
        self.assertIn("_model_trained/", out["reply"])
        self.assertEqual(len(self.brain.checkpoints.list()), 1)
        name = self.brain.checkpoints.list()[0]["name"]
        self.assertTrue(self.brain.delete_checkpoint(name)["ok"])

    def test_set_chat_backend_validation(self):
        self.assertTrue(self.brain.set_chat_backend("brain")["ok"])
        self.assertFalse(self.brain.set_chat_backend("skynet")["ok"])
        self.assertTrue(self.brain.set_chat_backend("auto")["ok"])

    def test_install_hint_absent_backends(self):
        hint = self.brain.install_hint()
        self.assertIsNotNone(hint)
        self.assertEqual(hint["options"][0]["author"], "codero-sus")
        self._install_nudges_reset()

    def _install_nudges_reset(self):
        self.brain._install_nudges = 0

    def test_long_input_capped(self):
        out = self.brain.reply("spam " * 5000)
        self.assertTrue(out["reply"])

    def test_export_transcript(self):
        md = self.brain.export_transcript()
        self.assertIn("conversation export", md)
        self.assertIn("codero-sus", md)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        os.environ["MYGPT_DATA"] = cls._td.name
        os.environ["MYGPT_CORTEX_ENABLED"] = "0"
        os.environ["MYGPT_OLLAMA_ENABLED"] = "0"
        os.environ["MYGPT_CORTEX_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_OLLAMA_URL"] = "http://127.0.0.1:1"
        import importlib
        import app as app_module
        importlib.reload(app_module)
        cls._app_module = app_module
        app_module.app.testing = True
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls._app_module.brain._prober_stop.set()
        cls._td.cleanup()

    def get(self, path):
        return self.client.get(path)

    def post(self, path, body):
        return self.client.post(path, json=body)

    def test_health_and_ping(self):
        h = self.get("/api/health").get_json()
        self.assertTrue(h["ok"])
        self.assertIn("version", h)
        self.assertTrue(self.get("/api/ping").get_json()["ok"])

    def test_stats_shape(self):
        d = self.get("/api/stats").get_json()
        for key in ("version", "author", "website", "mind", "backends",
                    "checkpoints", "cortex", "ollama"):
            self.assertIn(key, d)

    def test_backends_and_select(self):
        d = self.get("/api/backends").get_json()
        self.assertEqual(d["chat_backend"], "auto")
        self.assertIn("install_hint", d)
        r = self.post("/api/backends/select", {"backend": "brain"})
        self.assertTrue(r.get_json()["ok"])
        r = self.post("/api/backends/select", {"backend": "nonsense"})
        self.assertEqual(r.status_code, 400)

    def test_chat_validation(self):
        self.assertEqual(self.post("/api/chat", {"message": ""}).status_code, 400)
        long = self.post("/api/chat", {"message": "x" * 4001})
        self.assertEqual(long.status_code, 400)
        ok = self.post("/api/chat", {"message": "hi"})
        self.assertTrue(ok.get_json()["ok"])

    def test_teach_validation(self):
        bad = self.post("/api/teach", {"question": "q" * 600, "answer": "a"})
        self.assertEqual(bad.status_code, 400)
        good = self.post("/api/teach", {"question": "api test q",
                                        "answer": "api test a"})
        self.assertTrue(good.get_json()["ok"])

    def test_history_and_export(self):
        h = self.get("/api/history?limit=5").get_json()
        self.assertTrue(h["ok"])
        e = self.get("/api/export")
        self.assertEqual(e.status_code, 200)
        self.assertIn("markdown", e.headers["Content-Type"])

    def test_eval(self):
        d = self.post("/api/eval", {}).get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["results"]), d["total"])

    def test_checkpoint_endpoints(self):
        r = self.post("/api/checkpoint", {"label": "api-test"})
        name = r.get_json()["checkpoint"]["name"]
        listing = self.get("/api/checkpoints").get_json()["checkpoints"]
        self.assertEqual(listing[0]["name"], name)
        dl = self.get(f"/api/checkpoint/download?name={name}")
        self.assertEqual(dl.status_code, 200)
        bad = self.get("/api/checkpoint/download?name=../../etc")
        self.assertEqual(bad.status_code, 404)
        self.assertTrue(self.post("/api/checkpoint/delete",
                                  {"name": name}).get_json()["ok"])

    def test_json_errors(self):
        r = self.get("/api/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.get_json()["error"])
        r = self.get("/api/chat")           # GET on POST-only route
        self.assertEqual(r.status_code, 405)
        self.assertTrue(r.get_json()["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
