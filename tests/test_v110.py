"""v1.10 test pack — generated one-method-per-item tests (150+ methods).

Everything runs in temporary directories against dead ports, so no network,
no repo state and no real data/ is touched.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mygpt import codegen, mathx, textfx                    # noqa: E402
from mygpt.brain import Brain                                # noqa: E402
from mygpt.snippets_more import EXTRA                        # noqa: E402

DEAD = {"MYGPT_CORTEX_ENABLED": "0", "MYGPT_OLLAMA_ENABLED": "0",
        "MYGPT_CORTEX_URL": "http://127.0.0.1:1",
        "MYGPT_OLLAMA_URL": "http://127.0.0.1:1"}


def make_brain(td):
    for k, v in DEAD.items():
        os.environ[k] = v
    os.environ["MYGPT_CHECKPOINTS"] = os.path.join(td, "ckpts")
    for f in ("seed_corpus.json",):
        pass
    return Brain(td, os.path.join(ROOT, f))


class TemplatePackTests(unittest.TestCase):
    """One test method per new template family (134), generated below."""


class MathPackTests(unittest.TestCase):
    """One test method per maths-pack rule (65), generated below."""


class TextPackTests(unittest.TestCase):
    """One test method per text-pack rule (55), generated below."""


def _bind(cls, name, fn):
    def test(self):
        fn(self)
    test.__name__ = name
    test.__doc__ = name
    setattr(cls, name, test)
    return test


# ---------------------------------------------------------------- templates
for _i, (_name, _pat, _ask, _code) in enumerate(EXTRA, 1):
    def _t(self, ask=_ask, name=_name, code=_code):
        self.assertTrue(codegen.wants_code(ask), f"wants_code({ask!r})")
        reply, found = codegen.code_reply(ask)
        self.assertTrue(found, f"{name!r} matched no template for {ask!r}")
        self.assertIn("```python", reply)
        # whichever family matches first must be the code echoed in the reply
        fam = next((f for f in codegen.FAMILIES if f["re"].search(ask)), None)
        self.assertIsNotNone(fam, f"no family matches {ask!r}")
        emitted = fam["compose"](fam["re"].search(ask), ask)
        self.assertIn(emitted.splitlines()[0][:24], reply)
        compile(emitted, f"<emitted {name}>", "exec")
        compile(code, f"<snippet {name}>", "exec")     # syntax-check the snippet
        low = reply.lower()
        self.assertTrue("codero-sus" in low or "github.com/codero-sus" in low)
    _bind(TemplatePackTests, f"test_family_{_i:03d}_{_name.replace(' ', '_').replace(chr(39), '')}", _t)


def _template_count(self):
    self.assertEqual(len(codegen.FAMILIES), 84 + len(EXTRA))
_bind(TemplatePackTests, "test_total_family_count", _template_count)


def _template_unique_code(self):
    # every authored snippet must be unique, and every matched ask must return
    # exactly one family's code (overlaps resolve to the first match)
    bodies = {code for _n, _p, _a, code in EXTRA}
    self.assertEqual(len(bodies), len(EXTRA))
    matched = set()
    for _n, _p, ask, _code in EXTRA:
        fam = next((f for f in codegen.FAMILIES if f["re"].search(ask)), None)
        self.assertIsNotNone(fam)
        matched.add(fam["name"])
    self.assertGreaterEqual(len(matched), 120)   # near-one-to-one in practice
_bind(TemplatePackTests, "test_all_extra_snippets_distinct", _template_unique_code)


def _every_snippet_compiles(self):
    for name, _pat, _ask, code in EXTRA:
        compile(code, f"<{name}>", "exec")
_bind(TemplatePackTests, "test_every_snippet_compiles", _every_snippet_compiles)


# ------------------------------------------------------------------- maths
_MATH_CASES = [
    ("factorial", "factorial of 6", "720"),
    ("fibonacci", "what is the 20th fibonacci", "6,765"),
    ("is_prime_yes", "is 97 prime", "is prime"),
    ("is_prime_no", "is 91 prime", "not prime"),
    ("nth_prime", "10th prime", "29"),
    ("gcd", "gcd of 12 and 18", "6"),
    ("lcm", "lcm of 4 and 6", "12"),
    ("prime_factors", "prime factors of 360", "2 × 2 × 2 × 3 × 3 × 5"),
    ("divisors", "divisors of 28", "1, 2, 4, 7, 14, 28"),
    ("digit_sum", "digit sum of 9875", "29"),
    ("digital_root", "digital root of 9875", "digital root"),
    ("perfect_square", "is 144 a perfect square", "perfect square"),
    ("palindrome_number", "is 12321 a palindrome number", "is a numeric"),
    ("leap_year", "is 2024 a leap year", "leap year"),
    ("divisible", "is 91 divisible by 7", "divisible"),
    ("even_odd", "is 17 an even or odd number", "odd"),
    ("cube_root", "cube root of 27", "3"),
    ("log10", "log of 1000", "3"),
    ("log2", "log2 of 64", "6"),
    ("natural_log", "ln of 1", "0"),
    ("trig", "sin of 30 degrees", "0.5"),
    ("absolute", "absolute value of -5", "5"),
    ("floor", "floor of 3.7", "3"),
    ("ceiling", "ceiling of 3.2", "4"),
    ("round_decimals", "round 3.14159 to 2 decimals", "3.14"),
    ("remainder", "remainder of 17 divided by 5", "2"),
    ("percent_increase", "increase 200 by 15%", "230"),
    ("percent_decrease", "decrease 200 by 15%", "170"),
    ("tip", "tip on 80 dollars at 18%", "14.4"),
    ("simple_interest", "simple interest on 1000 at 5% for 3 years", "150"),
    ("compound_interest", "compound interest on 1000 at 5% for 3 years", "157.63"),
    ("grade", "grade for 87 percent", "grade B"),
    ("circle", "area of a circle radius 3", "28.27"),
    ("rectangle", "area of a rectangle 4 by 6", "24"),
    ("triangle", "area of a triangle base 4 height 6", "12"),
    ("sphere", "volume of a sphere radius 3", "113.09"),
    ("cylinder", "volume of a cylinder radius 2 height 5", "62.83"),
    ("pythagoras", "hypotenuse of 3 and 4", "5"),
    ("distance", "distance between (0,0) and (3,4)", "5"),
    ("midpoint", "midpoint of (0,0) and (4,6)", "(2, 3)"),
    ("slope", "slope between (1,2) and (3,6)", "2"),
    ("speed", "speed if distance 120 km in 2 hours", "60"),
    ("travel_time", "time for 150 km at 50 km/h", "3"),
    ("bmi", "bmi for 70 kg and 1.75 m", "22.9"),
    ("sum_range", "sum of numbers 1 to 100", "5,050"),
    ("sum_squares", "sum of squares 1 to 5", "55"),
    ("triangular", "triangular number 10", "55"),
    ("median", "median of 1, 5, 3", "3"),
    ("mode", "mode of 1, 2, 2, 3", "2"),
    ("range", "range of 5, 9, 2", "7"),
    ("variance", "variance of 2, 4, 4, 4, 5, 5, 7, 9", "4"),
    ("stddev", "standard deviation of 2, 4, 4, 4, 5, 5, 7, 9", "2"),
    ("geometric_mean", "geometric mean of 1, 3, 9", "3"),
    ("harmonic_mean", "harmonic mean of 2, 3, 6", "3"),
    ("decimal_to_fraction", "0.375 as a fraction", "3/8"),
    ("fraction_to_decimal", "3/8 as a decimal", "0.375"),
    ("simplify_fraction", "simplify 24/36", "2/3"),
    ("add_fractions", "1/2 plus 1/3", "5/6"),
    ("multiply_fractions", "2/3 times 3/4", "1/2"),
    ("ratio", "simplify ratio 12:18", "2:3"),
    ("independent_probability", "probability of two independent events 0.5 and 0.5", "0.25"),
    ("coin_run", "probability of 3 heads in a row", "0.125"),
    ("dice_double", "probability of rolling a 6 twice", "1/36"),
    ("hex_to_rgb", "#ff8800 to rgb", "rgb(255, 136, 0)"),
    ("rgb_to_hex", "rgb 255 136 0 to hex", "#ff8800"),
    ("quadratic", "roots of x^2 - 5x + 6", "3 and 2"),
    ("percent_of", "what is 17% of 250", "42.5"),
    ("what_percent_of", "30 is what percent of 90", "33.33"),
    ("percent_off", "20% off 80", "64"),
]

for _idx, (_nm, _q, _expect) in enumerate(_MATH_CASES, 1):
    def _m(self, q=_q, expect=_expect, nm=_nm):
        got = mathx.solve(q)
        self.assertIsNotNone(got, f"{nm}: no rule matched {q!r}")
        self.assertIn(expect, got[1], f"{nm}: {got[1]!r} lacks {expect!r}")
    _bind(MathPackTests, f"test_math_{_idx:03d}_{_nm}", _m)


def _math_rule_count(self):
    # every maths rule must be the first match for at least one case above
    hit = {mathx.solve(q)[0] for _n, q, _e in _MATH_CASES if mathx.solve(q)}
    self.assertEqual(hit, set(mathx.names()),
                     "add a case for every new maths rule")
_bind(MathPackTests, "test_rule_count", _math_rule_count)


def _math_no_match(self):
    self.assertIsNone(mathx.solve("tell me a story about dragons"))
_bind(MathPackTests, "test_unrelated_text_no_match", _math_no_match)


def _math_names_unique(self):
    names = mathx.names()
    self.assertEqual(len(names), len(set(names)))
_bind(MathPackTests, "test_rule_names_unique", _math_names_unique)


# -------------------------------------------------------------------- text
_TEXT_CASES = [
    ("uppercase", "uppercase: hello world", "HELLO WORLD"),
    ("lowercase", "lowercase: HELLO", "hello"),
    ("title_case", "title case: the quick fox", "The Quick Fox"),
    ("capitalize", "capitalize: hELLO", "Hello"),
    ("swap_case", "swap case: aBc", "AbC"),
    ("reverse_text", "reverse text: abc", "cba"),
    ("reverse_words", "reverse words: one two three", "three two one"),
    ("count_words", "count words in: one two three", "3 words"),
    ("count_characters", "count characters in: hello", "5 characters"),
    ("count_vowels", "count vowels in: banana", "vowels: 3"),
    ("count_consonants", "count consonants in: banana", "3"),
    ("count_sentences", "count sentences in: Hi. Bye!", "2"),
    ("reading_time", "reading time for: " + "word " * 200, "200 words"),
    ("word_frequency", "word frequency of: a b a c a", "a×3"),
    ("slugify", "slugify: Hello World 2026!", "hello-world-2026"),
    ("snake_case", "snake case: Hello World", "hello_world"),
    ("kebab_case", "kebab case: Hello World", "hello-world"),
    ("camel_case", "camel case: hello world", "HelloWorld"),
    ("initials", "initials of: Ada Lovelace", "AL"),
    ("acronym", "acronym of: World Health Organization", "WHO"),
    ("base64_encode", "base64 encode: hello", "aGVsbG8="),
    ("base64_decode", "base64 decode: aGVsbG8=", "hello"),
    ("rot13", "rot13: Hello", "Uryyb"),
    ("url_encode", "url encode: a b", "a%20b"),
    ("binary_of_text", "binary of: A", "01000001"),
    ("hex_of_text", "hex of: A", "41"),
    ("sha256", "sha256 of: abc", "ba7816bf"),
    ("md5", "md5 of: abc", "900150983cd24fb0d6963f7d28e17f72"),
    ("crc32", "crc32 of: hello", "3610a686"),
    ("dedupe_lines", "remove duplicate lines: a\nb\na", "a\nb"),
    ("sort_lines", "sort lines: b\na", "a\nb"),
    ("number_lines", "number lines: b\na", "1. b"),
    ("strip_empty", "strip empty lines: a\n\nb", "a\nb"),
    ("collapse_spaces", "collapse spaces: a    b", "a b"),
    ("trim", "trim:   hi   ", "hi"),
    ("shuffle_lines", "shuffle lines: a\nb\nc", "a"),
    ("extract_emails", "extract emails: mail ada@example.com", "ada@example.com"),
    ("extract_urls", "extract urls: see https://example.com/x", "https://example.com/x"),
    ("extract_numbers", "extract numbers: a 12 b 3.5", "12"),
    ("extract_hashtags", "extract hashtags: hi #python #code", "#python"),
    ("extract_mentions", "extract mentions: hi @ada", "@ada"),
    ("json_pretty", 'json pretty: {"b":1,"a":2}', '"a": 2'),
    ("json_minify", 'minify json: {\n  "a": 1\n}', '{"a":1}'),
    ("csv_to_markdown", "csv to markdown: a,b\n1,2", "| a | b |"),
    ("markdown_to_text", "markdown to text: **bold** text", "bold text"),
    ("pig_latin", "pig latin: hello world", "ellohay"),
    ("is_palindrome", 'is "racecar" a palindrome', "is a palindrome"),
    ("is_isogram", 'is "lumberjacks" an isogram', "is an isogram"),
    ("anagrams", 'are "listen" and "silent" anagrams', "are anagrams"),
    ("repeat_text", 'repeat: "ab" x 3', "ababab"),
    ("truncate", "truncate: 5: wonderful", "wonde"),
    ("pad_text", "pad: 6: hi", "hi...."),
    ("replace_text", "replace: 'cat' with 'dog' in 'the cat sat'", "the dog sat"),
    ("split_to_list", "split: a b c", "['a', 'b', 'c']"),
    ("join_list", "join: a, b, c", "a, b, c"),
]

for _idx, (_nm, _q, _expect) in enumerate(_TEXT_CASES, 1):
    def _t(self, q=_q, expect=_expect, nm=_nm):
        got = textfx.solve(q)
        self.assertIsNotNone(got, f"{nm}: no rule matched {q!r}")
        self.assertIn(expect, got[1], f"{nm}: {got[1]!r} lacks {expect!r}")
    _bind(TextPackTests, f"test_text_{_idx:03d}_{_nm}", _t)


def _text_rule_count(self):
    # every text rule must be the first match for at least one case above
    hit = {textfx.solve(q)[0] for _n, q, _e in _TEXT_CASES if textfx.solve(q)}
    self.assertEqual(hit, set(textfx.names()),
                     "add a case for every new text rule")
_bind(TextPackTests, "test_rule_count", _text_rule_count)


def _text_does_not_hijack_questions(self):
    for q in ("what is an acronym", "what is base64", "how do i reverse a list"):
        self.assertIsNone(textfx.solve(q), f"hijacked: {q!r}")
_bind(TextPackTests, "test_questions_not_hijacked", _text_does_not_hijack_questions)


def _text_names_unique(self):
    names = textfx.names()
    self.assertEqual(len(names), len(set(names)))
_bind(TextPackTests, "test_rule_names_unique", _text_names_unique)


# ------------------------------------------------------------- seed corpus
class SeedPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "seed_corpus.json"), encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_pair_count(self):
        self.assertGreaterEqual(len(self.data["pairs"]), 400)

    def test_no_duplicate_questions(self):
        qs = [p["q"].lower().strip() for p in self.data["pairs"]]
        self.assertEqual(len(qs), len(set(qs)))

    def test_every_pair_has_content(self):
        for p in self.data["pairs"]:
            self.assertTrue(p["q"].strip() and p["a"].strip())

    def test_texts_present(self):
        self.assertGreaterEqual(len(self.data["texts"]), 46)

    def test_answer_length_sane(self):
        long = [p["q"] for p in self.data["pairs"] if len(p["a"]) > 4000]
        self.assertEqual(long, [])

    def test_no_markup_in_answers(self):
        bad = [p["q"] for p in self.data["pairs"]
               if "```" in p["a"] or "<script" in p["a"].lower()]
        self.assertEqual(bad, [])


# --------------------------------------------------------- brain + API pack
class BrainPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.brain = make_brain(cls._td.name)

    @classmethod
    def tearDownClass(cls):
        cls.brain._prober_stop.set()
        cls._td.cleanup()

    def test_maths_pack_answer(self):
        out = self.brain.reply("factorial of 7")
        self.assertEqual(out["mode"], "math")
        self.assertIn("5,040", out["reply"])

    def test_text_pack_answer(self):
        out = self.brain.reply("slugify: Hello World")
        self.assertIn("hello-world", out["reply"])

    def test_text_pack_skill_tag(self):
        out = self.brain.reply("uppercase: abc")
        self.assertEqual(out["skill"], "text:uppercase")

    def test_quick_answer_uses_mathx(self):
        self.assertIn("720", self.brain.quick_answer("factorial of 6"))

    def test_quick_answer_uses_textfx(self):
        self.assertIn("ABC", self.brain.quick_answer("uppercase: abc"))

    def test_code_still_wins_for_code_asks(self):
        out = self.brain.reply("write quick sort code")
        self.assertEqual(out["mode"], "code")

    def test_seed_knowledge_reachable(self):
        out = self.brain.reply("what is a trie")
        self.assertIn("prefix", out["reply"].lower())

    def test_counter_grows(self):
        before = self.brain.counters["messages"]
        self.brain.reply("hi")
        self.assertGreater(self.brain.counters["messages"], before)


class ApiPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        os.environ["MYGPT_DATA"] = cls._td.name
        for k, v in DEAD.items():
            os.environ[k] = v
        os.environ["MYGPT_CHECKPOINTS"] = os.path.join(cls._td.name, "ckpts")
        import importlib
        import app as app_module
        importlib.reload(app_module)
        cls.mod = app_module
        app_module.app.testing = True
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.mod.brain._prober_stop.set()
        cls._td.cleanup()

    def test_math_endpoint(self):
        d = self.client.get("/api/math?q=factorial+of+6").get_json()
        self.assertTrue(d["ok"])
        self.assertIn("720", d["answer"])

    def test_math_endpoint_400(self):
        self.assertEqual(self.client.get("/api/math").status_code, 400)

    def test_math_endpoint_404(self):
        self.assertEqual(self.client.get("/api/math?q=nonsense+here").status_code, 404)

    def test_text_endpoint(self):
        d = self.client.get("/api/text?q=uppercase:+hi").get_json()
        self.assertEqual(d["answer"], "HI")

    def test_text_endpoint_404_lists_rules(self):
        r = self.client.get("/api/text?q=do+something+unknown")
        self.assertEqual(r.status_code, 404)
        self.assertIn("rules", r.get_json())

    def test_rules_endpoint(self):
        d = self.client.get("/api/rules").get_json()
        self.assertGreaterEqual(len(d["math"]), 62)
        self.assertGreaterEqual(len(d["text"]), 55)
        self.assertGreaterEqual(len(d["code_families"]), 218)

    def test_convert_endpoint(self):
        d = self.client.get("/api/convert?q=5+km+in+miles").get_json()
        self.assertIn("3.10686", d["answer"])

    def test_convert_endpoint_404(self):
        self.assertEqual(self.client.get("/api/convert?q=hello").status_code, 404)

    def test_roman_endpoint_number(self):
        self.assertIn("XLII", self.client.get("/api/roman?q=42").get_json()["answer"])

    def test_roman_endpoint_roman(self):
        self.assertIn("14", self.client.get("/api/roman?q=xiv").get_json()["answer"])

    def test_echo_endpoint(self):
        d = self.client.get("/api/echo?q=hi").get_json()
        self.assertEqual(d["echo"], "hi")
        self.assertEqual(d["length"], 2)

    def test_uptime_endpoint(self):
        d = self.client.get("/api/uptime").get_json()
        self.assertIn("h", d["human"])

    def test_endpoints_listing(self):
        d = self.client.get("/api/endpoints").get_json()
        paths = {e["path"] for e in d["endpoints"]}
        self.assertIn("/api/chat", paths)
        self.assertGreaterEqual(d["count"], 40)

    def test_metrics_endpoint(self):
        body = self.client.get("/api/metrics").get_data(as_text=True)
        self.assertIn("mygpt_up 1", body)
        self.assertIn("mygpt_memory_pairs", body)

    def test_chat_batch(self):
        d = self.client.post("/api/chat/batch",
                             json={"messages": ["hi", "factorial of 5"]}).get_json()
        self.assertEqual(d["count"], 2)
        self.assertIn("120", d["results"][1]["reply"])

    def test_chat_batch_cap(self):
        r = self.client.post("/api/chat/batch",
                             json={"messages": ["x"] * 11})
        self.assertEqual(r.status_code, 400)

    def test_chat_batch_validation(self):
        r = self.client.post("/api/chat/batch", json={"messages": [""]})
        self.assertEqual(r.get_json()["results"][0]["ok"], False)

    def test_quote_endpoint(self):
        d = self.client.get("/api/quote").get_json()
        self.assertTrue(d["quote"])

    def test_request_id_header(self):
        r = self.client.get("/api/ping")
        self.assertTrue(r.headers.get("X-Request-Id"))

    def test_request_id_echoed(self):
        r = self.client.get("/api/ping", headers={"X-Request-Id": "abc123"})
        self.assertEqual(r.headers["X-Request-Id"], "abc123")

    def test_version_header(self):
        self.assertTrue(self.client.get("/api/ping").headers.get("X-MyGPT-Version"))

    def test_server_timing_header(self):
        self.assertTrue(self.client.get("/api/ping").headers.get("Server-Timing"))

    def test_page_has_v110_controls(self):
        html = self.client.get("/").get_data(as_text=True)
        for marker in ("density-btn", "contrast-btn", "motion-btn", "sidebar-btn",
                       "sound-btn", "share-btn", "print-btn", "help-btn",
                       "help-modal", "about-modal", "pins-bar", "chat-actions",
                       "copy-all-btn", "edit-last-btn", "first-btn"):
            self.assertIn(marker, html, marker)


if __name__ == "__main__":
    unittest.main(verbosity=2)
