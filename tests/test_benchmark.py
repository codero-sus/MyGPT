"""The benchmark tool has to be runnable, not just claimed.

The report quotes numbers from ``tools/benchmark.py``; these tests run the
same code paths so a broken benchmark fails the suite instead of quietly
printing plausible-looking nonsense (the first version of it trained on a
four-token vocabulary, because the corpus was never fed to the model — maths
that looked fine and meant nothing).
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mygpt.langmodel import SPECIALS                              # noqa: E402

spec = importlib.util.spec_from_file_location(
    "mygpt_benchmark", os.path.join(ROOT, "tools", "benchmark.py"))
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkToolTests(unittest.TestCase):

    def setUp(self):
        self.saved = {k: v for k, v in os.environ.items() if k.startswith("MYGPT_")}
        os.environ["MYGPT_MODELS_DIR"] = tempfile.mkdtemp()      # engine off
        os.environ["MYGPT_LLAMACPP_MODELS"] = ""

    def tearDown(self):
        for key in [k for k in os.environ if k.startswith("MYGPT_")]:
            os.environ.pop(key, None)
        os.environ.update(self.saved)

    def test_corpus_is_read_from_the_repo(self):
        texts = benchmark._corpus()
        self.assertGreater(len(texts), 50)
        self.assertTrue(all(isinstance(t, str) and t.strip() for t in texts))

    def test_split_is_deterministic_and_leaves_a_held_out_part(self):
        train_a, held_a = benchmark._split(benchmark._corpus())
        train_b, held_b = benchmark._split(benchmark._corpus())
        self.assertEqual((train_a, held_a), (train_b, held_b))
        self.assertTrue(train_a and held_a)
        self.assertEqual(set(train_a) & set(held_a), set())

    def test_architectures_learn_and_use_a_real_vocabulary(self):
        result = benchmark.benchmark_architectures(epochs=2, batch=32)
        self.assertEqual(set(result["models"]), {"transformer", "mlp"})
        for name, m in result["models"].items():
            with self.subTest(model=name):
                # A vocabulary of just <pad>/<unk>/<bos>/<eos> means the corpus
                # never reached the model: every perplexity below would be junk.
                self.assertGreater(m["vocab"], len(SPECIALS) + 10)
                self.assertGreater(m["params"], 1000)
                self.assertIsNotNone(m["loss_first"])
                self.assertLess(m["loss_last"], m["loss_first"],
                                "training must reduce the loss")
                self.assertLess(m["perplexity_train"],
                                m["perplexity_uniform_baseline"])
                self.assertTrue(m["generation_tokens_per_sec"] > 0)

    def test_gradient_check_passes_at_the_shipped_configuration(self):
        report = benchmark.grad_check(samples=3)
        self.assertLess(report["worst_relative_error"], 1e-3,
                        f"backward pass disagrees with numerical gradient "
                        f"on {report['worst_tensor']}")
        self.assertGreaterEqual(report["parameter_tensors"], 20)
        self.assertEqual(report["dtype"], "float64")

    def test_llamacpp_benchmark_is_skipped_cleanly_without_a_model(self):
        result = benchmark.benchmark_llamacpp()
        self.assertIsNone(result, "no model folder -> no llama.cpp numbers")

    def test_main_prints_a_table(self):
        buffer = io.StringIO()
        argv = sys.argv
        sys.argv = ["benchmark.py", "--epochs", "1", "--skip-grad-check"]
        try:
            with redirect_stdout(buffer):
                code = benchmark.main()
        finally:
            sys.argv = argv
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertIn("transformer", out)
        self.assertIn("mlp", out)


if __name__ == "__main__":
    unittest.main()
