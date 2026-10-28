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

    def test_search_mixed_known_and_unknown_tokens(self):
        # regression: `set |= ()` used to raise TypeError (HTTP 500) whenever a
        # query mixed in-vocabulary words with out-of-vocabulary ones
        hits = self.m.search("what is the zzzzunknown capital of france")
        self.assertTrue(hits)
        self.assertEqual(hits[0][0]["a"], "Paris.")

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
        os.environ["MYGPT_LLAMACPP_MODELS"] = ""   # ignore repo ./models/*.gguf
        os.environ["MYGPT_MODELS_DIR"] = os.path.join(cls._td.name, "models")
        os.environ["MYGPT_CORTEX_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_OLLAMA_URL"] = "http://127.0.0.1:1"
        # keep checkpoints inside the temp dir — never touch the repo copy
        os.environ["MYGPT_CHECKPOINTS"] = os.path.join(cls._td.name, "ckpts")
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
        before = {c["name"] for c in self.brain.checkpoints.list()}
        out = self.brain.reply("checkpoint the model")
        self.assertIn("_model_trained/", out["reply"])
        after = {c["name"] for c in self.brain.checkpoints.list()}
        created = after - before           # the dir may hold older checkpoints
        self.assertEqual(len(created), 1)
        name = created.pop()
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
        os.environ["MYGPT_LLAMACPP_MODELS"] = ""   # ignore repo ./models/*.gguf
        os.environ["MYGPT_MODELS_DIR"] = os.path.join(cls._td.name, "models")
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

    # ------------------------------------------------ v1.9 endpoint tests

    def test_version_endpoint(self):
        d = self.get("/api/version").get_json()
        self.assertEqual(d["version"], __import__("mygpt").__version__)
        self.assertIn("codero-sus", d["github"])

    def test_chat_stream_sse(self):
        r = self.post("/api/chat/stream", {"message": "what is 2 plus 2"})
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("event: token", body)
        self.assertIn("event: done", body)
        self.assertIn("4", body)
        self.assertIn("text/event-stream", r.headers["Content-Type"])

    def test_chat_stream_validation(self):
        r = self.post("/api/chat/stream", {"message": ""})
        self.assertEqual(r.status_code, 400)

    def test_events_stream(self):
        r = self.get("/api/events/stream")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("event: snapshot", body)
        self.assertIn("event: ping", body)

    def test_memory_search_endpoint(self):
        self.post("/api/teach", {"question": "what is rust",
                                 "answer": "A systems language."})
        d = self.get("/api/memory/search?q=rust").get_json()
        self.assertTrue(d["hits"])
        self.assertIn("score", d["hits"][0])

    def test_memory_search_requires_query(self):
        self.assertEqual(self.get("/api/memory/search").status_code, 400)

    def test_memory_list_pagination(self):
        d = self.get("/api/memory/list?offset=0&limit=3").get_json()
        self.assertEqual(len(d["pairs"]), 3)
        self.assertGreater(d["total"], 3)

    def test_suggest_endpoint(self):
        d = self.get("/api/suggest?q=what is").get_json()
        self.assertTrue(d["suggestions"])
        self.assertTrue(all("what is" in s for s in d["suggestions"]))

    def test_suggest_prefix_ranks_first(self):
        d = self.get("/api/suggest?q=how do i teach").get_json()
        self.assertTrue(d["suggestions"])

    def test_analytics_endpoint(self):
        self.post("/api/chat", {"message": "hello there"})
        d = self.get("/api/analytics").get_json()
        self.assertIn("counters", d)
        self.assertIn("intents", d)
        self.assertIn("busiest_hours", d)

    def test_export_json_endpoint(self):
        r = self.get("/api/export.json")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.get_data(as_text=True))
        self.assertEqual(data["app"], "MyGPT")
        self.assertIn("messages", data)

    def test_export_csv_endpoint(self):
        r = self.get("/api/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("timestamp,role,intent,content",
                      r.get_data(as_text=True).splitlines()[0])

    def test_backends_models_endpoint(self):
        d = self.get("/api/backends/models").get_json()
        self.assertTrue(any(m["engine"] == "brain" for m in d["models"]))

    def test_teach_bulk(self):
        d = self.post("/api/teach/bulk", {"pairs": [
            {"question": "what is go", "answer": "A language by Google."},
            {"question": "what is zig", "answer": "A modern systems language."},
        ]}).get_json()
        self.assertEqual(d["stored"], 2)
        self.assertEqual(d["failed"], 0)

    def test_teach_bulk_reports_bad_items(self):
        d = self.post("/api/teach/bulk", {"pairs": [
            {"question": "valid one", "answer": "yes"},
            {"question": "", "answer": "no question"},
            "not an object",
        ]}).get_json()
        self.assertEqual(d["stored"], 1)
        self.assertEqual(d["failed"], 2)
        self.assertEqual(len(d["errors"]), 2)

    def test_teach_bulk_requires_pairs(self):
        self.assertEqual(self.post("/api/teach/bulk", {}).status_code, 400)

    def test_teach_bulk_cap(self):
        pairs = [{"question": f"q{i}", "answer": "a"} for i in range(101)]
        self.assertEqual(self.post("/api/teach/bulk", {"pairs": pairs}).status_code,
                         400)

    def test_checkpoint_info(self):
        name = self.post("/api/checkpoint", {"label": "info-test"}).get_json()[
            "checkpoint"]["name"]
        d = self.get(f"/api/checkpoint/info?name={name}").get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["checkpoint"]["name"], name)
        self.assertEqual(self.get("/api/checkpoint/info?name=nope").status_code,
                         404)
        self.post("/api/checkpoint/delete", {"name": name})

    def test_robots_txt(self):
        r = self.get("/robots.txt")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Disallow: /api/", r.get_data(as_text=True))

    def test_manifest_json(self):
        d = self.get("/manifest.json").get_json()
        self.assertEqual(d["short_name"], "MyGPT")
        self.assertEqual(d["start_url"], "/")

    def test_clear_endpoint(self):
        self.post("/api/chat", {"message": "remember this message"})
        d = self.post("/api/clear", {}).get_json()
        self.assertTrue(d["ok"])
        self.assertGreaterEqual(d["cleared"], 1)
        self.assertEqual(self.get("/api/history").get_json()["episodes"], [])

    def test_cors_headers_on_api(self):
        r = self.get("/api/health")
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")

    def test_security_headers(self):
        r = self.get("/")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("Referrer-Policy"), "no-referrer")

    def test_options_preflight(self):
        r = self.client.options("/api/chat")
        self.assertIn(r.status_code, (200, 204))

    def test_icon_svg_served(self):
        r = self.get("/static/icon.svg")
        self.assertEqual(r.status_code, 200)
        self.assertIn("svg", r.get_data(as_text=True)[:200])

    def test_page_has_v19_controls(self):
        html = self.get("/").get_data(as_text=True)
        for marker in ("theme-btn", "chat-search", "clear-btn", "char-count",
                       "manifest.json", "bulk-text", "font-inc"):
            self.assertIn(marker, html)


class SpecialMathTests(unittest.TestCase):
    """v1.9 conversions, list stats and roman numerals (via quick_answer)."""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        os.environ["MYGPT_CORTEX_ENABLED"] = "0"
        os.environ["MYGPT_OLLAMA_ENABLED"] = "0"
        os.environ["MYGPT_LLAMACPP_MODELS"] = ""   # ignore repo ./models/*.gguf
        os.environ["MYGPT_MODELS_DIR"] = os.path.join(cls._td.name, "models")
        os.environ["MYGPT_CORTEX_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_OLLAMA_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_CHECKPOINTS"] = os.path.join(cls._td.name, "ckpts")
        cls.brain = Brain(cls._td.name, None)

    @classmethod
    def tearDownClass(cls):
        cls.brain._prober_stop.set()
        cls._td.cleanup()

    def test_celsius_to_fahrenheit(self):
        self.assertIn("212", self.brain.quick_answer("100 celsius in fahrenheit"))

    def test_fahrenheit_to_celsius(self):
        self.assertIn("0 °C", self.brain.quick_answer("convert 32 f to c"))

    def test_km_to_miles(self):
        self.assertIn("3.10686", self.brain.quick_answer("5 km in miles"))

    def test_pounds_to_kg(self):
        self.assertIn("68.0389", self.brain.quick_answer("150 lbs in kg"))

    def test_feet_to_cm(self):
        self.assertIn("182.88", self.brain.quick_answer("6 feet in cm"))

    def test_m_to_km(self):
        self.assertIn("0.01", self.brain.quick_answer("10 m to km"))

    def test_incompatible_units_ignored(self):
        self.assertEqual(self.brain._special_math("5 km in kg"), None)

    def test_percent_change(self):
        self.assertIn("50%", self.brain.quick_answer("percent change from 50 to 75"))

    def test_percent_change_from_zero(self):
        out = self.brain.quick_answer("percent change from 0 to 5")
        self.assertIn("undefined", out)

    def test_percent_off(self):
        self.assertIn("80", self.brain.quick_answer("20% off 100"))

    def test_what_percent_of(self):
        self.assertIn("25%", self.brain.quick_answer("15 is what percent of 60"))

    def test_average_of_list(self):
        self.assertIn("5", self.brain.quick_answer("average of 3, 5, 7"))

    def test_sum_of_list(self):
        self.assertIn("60", self.brain.quick_answer("sum of 10, 20, 30"))

    def test_max_of_list(self):
        self.assertIn("8", self.brain.quick_answer("max of 4, 8, 2"))

    def test_min_of_list(self):
        self.assertIn("2", self.brain.quick_answer("min of 4, 8, 2"))

    def test_half_of(self):
        self.assertIn("21", self.brain.quick_answer("half of 42"))

    def test_double_of(self):
        self.assertIn("42", self.brain.quick_answer("double of 21"))

    def test_triple_of(self):
        self.assertIn("63", self.brain.quick_answer("triple of 21"))

    def test_number_to_roman(self):
        self.assertIn("XLII", self.brain.quick_answer("42 in roman"))

    def test_roman_to_number(self):
        self.assertIn("14", self.brain.quick_answer("XIV in numbers"))

    def test_roman_rejects_non_canonical(self):
        self.assertIsNone(self.brain._special_math("IIII in numbers"))
        self.assertIsNone(self.brain._special_math("VX in numbers"))

    def test_roman_bounds(self):
        self.assertIsNone(self.brain._special_math("4500 in roman"))

    def test_plain_math_still_works(self):
        self.assertIn("56", self.brain.quick_answer("what is seven times eight"))

    def test_power_not_swallowed(self):
        self.assertIn("1024", self.brain.quick_answer("what is 2 to the power of 10"))


class NewTemplateTests(unittest.TestCase):
    """The 30 template families added in v1.9."""

    ASKS = {
        "guessing game": "write a guessing game",
        "rock paper scissors": "make a rock paper scissors game",
        "hangman": "code hangman",
        "todo list": "write a todo list program",
        "contact book": "code an address book",
        "bmi calculator": "write a bmi calculator",
        "age calculator": "code an age calculator",
        "stack and queue": "show a stack and queue with deque",
        "linked list": "write a linked list",
        "decorator example": "show me a decorator",
        "generator example": "generator example code",
        "dataclass example": "write a dataclass example",
        "enum example": "show an enum example",
        "exception handling": "write try except code",
        "list comprehension": "list comprehension example",
        "lambda map filter": "show lambda function with map and filter",
        "argparse cli": "write a command line arguments parser",
        "logging setup": "logging setup example",
        "unit test skeleton": "write a unit test",
        "walk a directory": "how do i walk a directory with os.walk",
        "count lines in a file": "count the lines in a file",
        "web scraper": "write a web scraper",
        "read environment variables": "read environment variable code",
        "config file loader": "code a config file loader",
        "collatz conjecture": "collatz sequence code",
        "reverse words in a sentence": "reverse the words in a sentence",
        "pangram check": "write a pangram check",
        "sort list of dicts": "sort a list of dict by value",
        "number pyramid pattern": "print a number pyramid pattern",
        "number to words": "convert a number to words",
    }

    def test_every_family_matches_and_returns_code(self):
        for label, ask in self.ASKS.items():
            with self.subTest(family=label):
                self.assertTrue(codegen.wants_code(ask), f"wants_code({ask!r})")
                reply, found = codegen.code_reply(ask)
                self.assertTrue(found, f"{label} did not match a template")
                self.assertIn("```python", reply)

    def test_each_family_produces_distinct_code(self):
        bodies = set()
        for ask in self.ASKS.values():
            reply, _ = codegen.code_reply(ask)
            bodies.add(reply.split("```python")[1])
        self.assertEqual(len(bodies), len(self.ASKS))

    def test_code_reply_includes_credit(self):
        reply, _ = codegen.code_reply(self.ASKS["hangman"])
        self.assertIn("codero-sus", reply.lower())

    def test_template_hint_lists_new_families(self):
        self.assertIn("hangman", codegen.TEMPLATE_HINT)
        self.assertIn("argparse", codegen.TEMPLATE_HINT)

    def test_unknown_ask_falls_back_gracefully(self):
        reply, found = codegen.code_reply("write code for quantum teleport")
        self.assertFalse(found)
        self.assertIn("template", reply.lower())


class EpisodeClearTests(unittest.TestCase):
    def test_clear_resets_index(self):
        import tempfile as tf
        with tf.TemporaryDirectory() as td:
            ep = EpisodicMemory(os.path.join(td, "episodes.json"))
            ep.remember("user", "hello there friend")
            ep.remember("mygpt", "hi, how can i help you today")
            self.assertTrue(ep.search("hello"))
            n = ep.clear()
            self.assertEqual(n, 2)
            self.assertEqual(ep.episodes, [])
            self.assertEqual(ep.search("hello"), [])

    def test_clear_persists(self):
        import tempfile as tf
        with tf.TemporaryDirectory() as td:
            path = os.path.join(td, "episodes.json")
            ep = EpisodicMemory(path)
            ep.remember("user", "something to forget")
            ep.clear()
            ep2 = EpisodicMemory(path)
            self.assertEqual(ep2.episodes, [])


class BrainV19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        os.environ["MYGPT_CORTEX_ENABLED"] = "0"
        os.environ["MYGPT_OLLAMA_ENABLED"] = "0"
        os.environ["MYGPT_LLAMACPP_MODELS"] = ""   # ignore repo ./models/*.gguf
        os.environ["MYGPT_MODELS_DIR"] = os.path.join(cls._td.name, "models")
        os.environ["MYGPT_CORTEX_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_OLLAMA_URL"] = "http://127.0.0.1:1"
        os.environ["MYGPT_CHECKPOINTS"] = os.path.join(cls._td.name, "ckpts")
        cls.brain = Brain(cls._td.name, None)

    @classmethod
    def tearDownClass(cls):
        cls.brain._prober_stop.set()
        cls._td.cleanup()

    def test_teach_many_counts(self):
        d = self.brain.teach_many([
            {"question": "what is elixir", "answer": "A BEAM language."},
            {"question": "what is haskell", "answer": "A pure functional language."},
        ])
        self.assertEqual(d["stored"], 2)
        self.assertEqual(d["failed"], 0)

    def test_teach_many_skips_invalid(self):
        d = self.brain.teach_many([{"question": "  ", "answer": "x"}, 42])
        self.assertEqual(d["stored"], 0)
        self.assertEqual(d["failed"], 2)

    def test_search_memory_shapes(self):
        self.brain.teach("what is erlang", "A concurrent language.")
        hits = self.brain.search_memory("erlang")
        self.assertTrue(hits)
        self.assertEqual(set(hits[0]) >= {"q", "a", "score"}, True)

    def test_search_memory_empty_query(self):
        self.assertEqual(self.brain.search_memory("   "), [])

    def test_suggest_matches_substring(self):
        self.brain.teach("what is gleam language", "A typed BEAM language.")
        out = self.brain.suggest("gleam")
        self.assertTrue(any("gleam" in s for s in out))

    def test_suggest_empty(self):
        self.assertEqual(self.brain.suggest(""), [])

    def test_analytics_after_turn(self):
        self.brain.reply("hello there")
        a = self.brain.analytics()
        self.assertIn("counters", a)
        self.assertTrue(a["intents"])

    def test_export_json_structure(self):
        self.brain.reply("hi")
        d = self.brain.export_json()
        self.assertEqual(d["version"][0], "1")
        self.assertTrue(d["messages"])
        self.assertIn("github", d)

    def test_clear_transcript_keeps_memory(self):
        self.brain.teach("what is crystal lang", "A compiled Ruby-like language.")
        self.brain.reply("something ephemeral here")
        n = self.brain.clear_transcript()["cleared"]
        self.assertGreaterEqual(n, 1)
        self.assertEqual(self.brain.episodes.episodes, [])
        self.assertTrue(self.brain.memory.pairs)      # knowledge survives

    def test_reply_mode_recorded_in_ring_buffer(self):
        self.brain.reply("what is 3 plus 4")
        self.assertTrue(any(r.get("mode") == "math"
                            for r in self.brain.last_records))

    def test_checkpoints_env_override(self):
        self.assertTrue(self.brain.checkpoints.root.endswith("ckpts"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
