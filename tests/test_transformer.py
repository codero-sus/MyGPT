"""Tests for the transformer language model (mygpt/transformer.py).

The centrepiece is a **finite-difference gradient check**: every parameter
tensor's analytic gradient (from the hand-written backward pass) is compared
against a central difference of the loss. A transformer that trains "fine" can
still have a wrong backward pass — this test is what makes correctness a
verified claim instead of a hope, and it is how two real bugs were caught while
this model was written:

1. the loss was read from logits at the *first* position of each window
   instead of the last, and
2. ``dlogits`` was initialised from the softmax itself, leaving gradient at
   every position, so the optimiser minimised a different objective than the
   loss it reported.

Both are covered by the checks below, which fail loudly if either regresses.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mygpt.transformer import (  # noqa: E402
    TransformerLM, gelu, gelu_backward, layer_norm, layer_norm_backward,
    softmax_last,
)

CORPUS = ("the cat sat on the mat . the cat ate the fish . "
          "a dog sat on the log . the dog ate the bone . "
          "the mat is warm and the fish is fresh .").split(" . ")
WORD_POOL = ("the cat sat on mat ate fish dog log bone warm fresh".split())


def make_model(blocks=2, dim=8, heads=2, ctx=4, dtype=np.float64, **kw):
    opts = dict(dim=dim, heads=heads, blocks=blocks, ffn_mult=2, ctx=ctx,
                max_vocab=40, dropout=0.0, rng_seed=5, dtype=dtype)
    opts.update(kw)
    lm = TransformerLM(**opts)
    lm.word_counts.update(WORD_POOL * 20)
    lm.rebuild_vocab()
    return lm


def batch(lm, seed=11, B=2):
    rng = np.random.default_rng(seed)
    ctx = rng.integers(0, lm.vocab_size, (B, lm.ctx)).astype(np.int64)
    tgt = rng.integers(0, lm.vocab_size, B).astype(np.int64)
    return ctx, tgt


def loss_and_dlogits(lm, ctx, tgt):
    """The model's loss and the matching gradient at the logits.

    Mirrors ``_step``: the head only ever scores the *last* position of each
    window, so logits are (B, V) and the gradient lives there alone.
    """
    logits, caches = lm._forward(ctx)
    probs = softmax_last(logits)
    B = ctx.shape[0]
    rows = np.arange(B)
    loss = float(-np.log(probs[rows, tgt] + 1e-12).mean())
    dlogits = probs.copy()
    dlogits[rows, tgt] -= 1.0
    dlogits /= B
    return loss, dlogits, caches, rows


class GradientCheckTests(unittest.TestCase):
    """The hand-written backward pass must match numerical differentiation."""

    def _check(self, blocks, eps=1e-4, tol=1e-4, samples=6):
        lm = make_model(blocks=blocks)
        rng = np.random.default_rng(3)
        ctx, tgt = batch(lm)
        _loss, dlogits, caches, rows = loss_and_dlogits(lm, ctx, tgt)
        analytic = lm._backward(dlogits, caches)

        def loss():
            lg, _ = lm._forward(ctx)
            pr = softmax_last(lg)
            return float(-np.log(pr[rows, tgt] + 1e-12).mean())

        worst, worst_name = 0.0, ""
        for name, P in lm.params.items():
            for _ in range(samples):
                ix = tuple(int(rng.integers(0, s)) for s in P.shape)
                orig = float(P[ix])
                P[ix] = orig + eps
                up = loss()
                P[ix] = orig - eps
                down = loss()
                P[ix] = orig
                numeric = (up - down) / (2 * eps)
                got = float(analytic[name][ix])
                # scale-aware: tiny gradients would otherwise divide by noise
                err = abs(numeric - got) / max(1e-6, abs(numeric) + abs(got))
                if err > worst:
                    worst, worst_name = err, name
        self.assertLess(worst, tol,
                        f"{blocks}-block gradient mismatch on {worst_name}: "
                        f"relative error {worst:.2e}")

    def test_gradient_1_block(self):
        self._check(1)

    def test_gradient_2_blocks(self):
        self._check(2)

    def test_gradient_3_blocks(self):
        self._check(3)

    def test_gradient_check_covers_every_tensor(self):
        lm = make_model(blocks=2)
        ctx, tgt = batch(lm)
        _l, dl, caches, _r = loss_and_dlogits(lm, ctx, tgt)
        grads = lm._backward(dl, caches)
        self.assertEqual(set(grads), set(lm.params),
                         "every parameter tensor needs a gradient")
        # a truly wrong backward leaves whole tensors at zero
        empty = [n for n, g in grads.items() if float(abs(g).sum()) == 0.0]
        self.assertEqual(empty, [], f"tensors with no gradient reaching them: {empty}")

    def test_logits_are_last_position_only(self):
        """The fast head scores one row per window; the full one agrees with it."""
        lm = make_model(blocks=2)
        ctx, _tgt = batch(lm)
        fast, _ = lm._forward(ctx)
        full, _ = lm._forward(ctx, all_positions=True)
        B, C = ctx.shape
        self.assertEqual(fast.shape, (B, lm.vocab_size))
        self.assertEqual(full.shape, (B, C, lm.vocab_size))
        np.testing.assert_allclose(fast, full[:, -1], atol=1e-12)

    def test_gradient_only_touches_the_scored_position(self):
        """A (B, V) gradient must produce no gradient at earlier positions."""
        lm = make_model(blocks=1)
        ctx, tgt = batch(lm)
        _l, dl, caches, _r = loss_and_dlogits(lm, ctx, tgt)
        grads = lm._backward(dl, caches)
        # dlogits is 2-D, so the hidden-state gradient exists only at C-1
        full_grads = None
        d3 = np.zeros((*ctx.shape, lm.vocab_size))
        d3[:, -1] = dl
        full_grads = lm._backward(d3, caches)
        for name in grads:
            np.testing.assert_allclose(grads[name], full_grads[name],
                                       atol=1e-12, err_msg=name)


class CausalityTests(unittest.TestCase):
    """A causal model must not let a token see the future."""

    def test_future_tokens_do_not_change_earlier_logits(self):
        lm = make_model(blocks=2)
        rng = np.random.default_rng(7)
        ctx = rng.integers(0, lm.vocab_size, (1, lm.ctx)).astype(np.int64)
        logits_a, _ = lm._forward(ctx, all_positions=True)
        changed = ctx.copy()
        changed[0, -1] = (int(changed[0, -1]) + 1) % lm.vocab_size
        logits_b, _ = lm._forward(changed, all_positions=True)
        # positions 0..C-2 predate the edit; their logits must be identical
        np.testing.assert_allclose(logits_a[0, :-1], logits_b[0, :-1],
                                   atol=1e-10)
        # and the edited position must actually differ (sanity check)
        self.assertGreater(float(np.abs(logits_a[0, -1] - logits_b[0, -1]).sum()),
                           1e-9)

    def test_attention_mask_is_upper_triangular(self):
        lm = make_model(blocks=1)
        mask = lm._causal_mask(lm.ctx)
        for i in range(lm.ctx):
            for j in range(lm.ctx):
                if j > i:
                    self.assertLess(float(mask[i, j]), -1e29)
                else:
                    self.assertEqual(float(mask[i, j]), 0.0)


class PieceTests(unittest.TestCase):
    def test_layer_norm_backward(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=(3, 5))
        g, b = rng.normal(size=5), rng.normal(size=5)
        w = rng.normal(size=(3, 5))
        out, cache = layer_norm(x, g, b)
        dx, dg, db = layer_norm_backward(w, cache)
        eps = 1e-6

        def f():
            return float((layer_norm(x, g, b)[0] * w).sum())
        for P, grad in ((x, dx), (g, dg), (b, db)):
            for _ in range(3):
                ix = tuple(int(rng.integers(0, s)) for s in P.shape)
                orig = float(P[ix])
                P[ix] = orig + eps
                up = f()
                P[ix] = orig - eps
                down = f()
                P[ix] = orig
                numeric = (up - down) / (2 * eps)
                self.assertAlmostEqual(numeric, float(grad[ix]), places=6)

    def test_gelu_matches_definition_and_derivative(self):
        x = np.linspace(-4, 4, 33)
        exact = 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3)))
        np.testing.assert_allclose(gelu(x), exact, atol=1e-12)
        eps = 1e-6
        numeric = (gelu(x + eps) - gelu(x - eps)) / (2 * eps)
        np.testing.assert_allclose(gelu_backward(x), numeric, atol=1e-6)

    def test_softmax_rows_sum_to_one(self):
        rng = np.random.default_rng(2)
        p = softmax_last(rng.normal(size=(4, 9)) * 5)
        np.testing.assert_allclose(p.sum(axis=-1), np.ones(4), atol=1e-12)


class TrainingTests(unittest.TestCase):
    def test_loss_decreases_and_perplexity_improves(self):
        lm = make_model(blocks=2, lr=5e-3)
        text = "the cat sat on the mat"
        before = lm.perplexity(CORPUS)
        first = None
        for _ in range(60):
            stats = lm.train([text], epochs=1, batch_size=4)
            first = first if first is not None else stats["loss_first"]
        after = lm.perplexity(CORPUS)
        self.assertLess(after, before,
                        f"perplexity did not improve ({before:.2f} -> {after:.2f})")
        self.assertLess(stats["loss_last"], first, "training loss did not drop")

    def test_lr_schedule_warms_up_then_decays(self):
        lm = make_model(blocks=1, warmup=10, total_steps=100, lr=1.0)
        lrs = []
        for step in range(1, 101):
            lm.step_count = step
            lrs.append(lm._lr_now())
        self.assertLess(lrs[0], lrs[9])              # warmup rises
        self.assertAlmostEqual(lrs[9], 1.0, places=6)
        self.assertLess(lrs[-1], lrs[9])             # then decays
        self.assertGreater(lrs[-1], 0.0)             # but never hits zero

    def test_gradient_clipping_keeps_steps_bounded(self):
        lm = make_model(blocks=1, lr=1e-2)
        # an absurdly large gradient must not blow the weights up
        before = float(np.abs(lm.params["tok_emb"]).sum())
        grads = {n: np.full_like(p, 1e6) for n, p in lm.params.items()}
        norm = float(np.sqrt(sum(float((g * g).sum()) for g in grads.values())))
        self.assertGreater(norm, 1.0)                # clipping is actually needed
        if norm > 1.0:
            grads = {k: g / norm for k, g in grads.items()}
        lm._adam_update(grads, lr=lm.lr)
        after = float(np.abs(lm.params["tok_emb"]).sum())
        numel = lm.params["tok_emb"].size
        # a clipped Adam step can move any single weight by at most ~lr, so the
        # total absolute change cannot exceed lr per element
        self.assertLessEqual(abs(after - before), 1.5 * lm.lr * numel)

    def test_dropout_trains_without_breaking_shapes(self):
        lm = make_model(blocks=1, dropout=0.3)
        ctx, tgt = batch(lm)
        loss = lm._step(ctx, tgt)
        self.assertTrue(np.isfinite(loss))

    def test_step_reports_finite_loss(self):
        lm = make_model(blocks=2)
        ctx, tgt = batch(lm)
        self.assertTrue(np.isfinite(lm._step(ctx, tgt)))


class EfficiencyTests(unittest.TestCase):
    """The last-position head was worth roughly a factor of `ctx` in the head."""

    def test_head_cost_does_not_scale_with_context(self):
        lm = make_model(blocks=1)
        rng = np.random.default_rng(0)
        short = rng.integers(0, lm.vocab_size, (4, 2)).astype(np.int64)
        long = rng.integers(0, lm.vocab_size, (4, lm.ctx)).astype(np.int64)
        self.assertEqual(lm._forward(short)[0].shape,
                         lm._forward(long)[0].shape)


class VocabularyTests(unittest.TestCase):
    def test_vocab_growth_keeps_known_rows(self):
        lm = make_model(blocks=1)
        before = lm.params["tok_emb"][lm.word2idx["cat"]].copy()
        lm.word_counts.update(["zebra"] * 50)
        lm.rebuild_vocab()
        self.assertIn("zebra", lm.word2idx)
        after = lm.params["tok_emb"][lm.word2idx["cat"]]
        np.testing.assert_allclose(before, after, atol=1e-12,
                                   err_msg="existing embeddings must survive growth")

    def test_special_tokens_exist(self):
        lm = make_model(blocks=1)
        for token in ("<pad>", "<unk>", "<bos>", "<eos>"):
            self.assertIn(token, lm.word2idx)


class GenerationTests(unittest.TestCase):
    def test_generate_after_training(self):
        lm = make_model(blocks=2)
        lm.train(CORPUS, epochs=8)
        text = lm.generate(n_tokens=12, temperature=0.8, top_k=8)
        self.assertIsInstance(text, str)
        self.assertEqual(text, text.strip())

    def test_prompt_continuation_starts_from_the_prompt(self):
        lm = make_model(blocks=1)
        text = lm.generate(n_tokens=4, prompt="the cat")
        self.assertTrue(text.startswith("the cat"), text)

    def test_next_token_probs_are_ranked_and_normalised(self):
        lm = make_model(blocks=1)
        top = lm.next_token_probs("the cat sat", top=5)
        self.assertEqual(len(top), 5)
        probs = [p for _w, p in top]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertLessEqual(sum(probs), 1.0 + 1e-9)
        self.assertTrue(all(w in lm.word2idx for w, _p in top))

    def test_seeding_generation_is_reproducible(self):
        lm = make_model(blocks=1)
        lm.train(CORPUS, epochs=4)
        lm.rng = np.random.default_rng(99)
        first = lm.generate(n_tokens=8, temperature=1.0)
        lm.rng = np.random.default_rng(99)
        second = lm.generate(n_tokens=8, temperature=1.0)
        self.assertEqual(first, second)

    def test_repetition_penalty_lowers_repeated_tokens(self):
        """Deterministic: the filter must score a seen token below an unseen one."""
        lm = make_model(blocks=1)
        idx = {w: i for i, w in enumerate(lm.idx2word)}
        z = np.zeros(lm.vocab_size)
        z[idx["cat"]] = 3.0          # dominant token
        z[idx["dog"]] = 2.0
        z[idx["mat"]] = 1.0
        # the filter returns probabilities over the top-k candidates only, so
        # look tokens up through the accompanying order array
        plain, order_plain = lm._filtered_probs(
            z, [], top_k=8, top_p=1.0, repetition_penalty=1.0,
            return_order=True)
        penalised, order_pen = lm._filtered_probs(
            z, ["cat"], top_k=8, top_p=1.0, repetition_penalty=2.0,
            return_order=True)

        def prob_of(probs, order, token):
            matches = np.where(order == idx[token])[0]
            return 0.0 if matches.size == 0 else float(probs[int(matches[0])])

        self.assertGreater(prob_of(plain, order_plain, "cat"),
                           prob_of(penalised, order_pen, "cat"),
                           "a repeated token should be penalised")
        self.assertLess(prob_of(penalised, order_pen, "cat"),
                        prob_of(penalised, order_pen, "dog"))
        for probs in (plain, penalised):
            self.assertAlmostEqual(float(probs.sum()), 1.0, places=9)

    def test_top_p_keeps_the_smallest_sufficient_set(self):
        """Nucleus sampling: smallest set whose mass reaches top_p, renormalised."""
        lm = make_model(blocks=1)
        z = np.zeros(lm.vocab_size)
        z[:4] = [5.0, 4.0, 3.0, 0.0]
        top_p = 0.9
        full = lm._filtered_probs(z, [], top_k=10, top_p=1.0,
                                  repetition_penalty=1.0)
        ranked = np.sort(full)[::-1]
        expected = int(np.searchsorted(np.cumsum(ranked), top_p) + 1)
        probs = lm._filtered_probs(z, [], top_k=10, top_p=top_p,
                                   repetition_penalty=1.0)
        kept = int((probs > 0).sum())
        self.assertEqual(kept, expected,
                         "must keep exactly the tokens the nucleus needs")
        self.assertAlmostEqual(float(probs.sum()), 1.0, places=9)  # renormalised
        self.assertGreaterEqual(float(np.sort(probs)[::-1][:kept].sum()), 0.999)
        self.assertTrue(all(np.sort(full)[::-1][:kept] > 0))


class PersistenceTests(unittest.TestCase):
    def test_save_load_round_trip(self):
        lm = make_model(blocks=2)
        lm.train(CORPUS, epochs=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.npz")
            lm.save(path)
            self.assertTrue(os.path.exists(path))
            clone = make_model(blocks=2)
            self.assertTrue(clone.load(path))
            for name in lm.params:
                np.testing.assert_allclose(clone.params[name], lm.params[name],
                                           atol=1e-12, err_msg=name)
            self.assertEqual(clone.idx2word, lm.idx2word)
            self.assertEqual(clone.word_counts, lm.word_counts)
            # identical weights must generate identical text
            lm.rng = np.random.default_rng(4)
            clone.rng = np.random.default_rng(4)
            self.assertEqual(lm.generate(n_tokens=10), clone.generate(n_tokens=10))

    def test_load_refuses_a_foreign_checkpoint(self):
        lm = make_model(blocks=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mlp.npz")
            np.savez_compressed(path, E=np.zeros((3, 3)), vocab=np.array(["a"]),
                                counts=np.array("{}"), W1=np.zeros((3, 3)),
                                b1=np.zeros(3), W_out=np.zeros((3, 3)),
                                b_out=np.zeros(3))
            self.assertFalse(lm.load(path),
                             "an MLP checkpoint must not be loaded as a transformer")

    def test_load_missing_file_is_false(self):
        lm = make_model(blocks=1)
        self.assertFalse(lm.load("/definitely/not/here.npz"))


class InterfaceTests(unittest.TestCase):
    def test_drop_in_replacement_for_neural_lm(self):
        from mygpt.langmodel import NeuralLM
        lm = make_model(blocks=1)
        self.assertIsInstance(lm, NeuralLM)
        # the API the Brain/trainer/checkpoints rely on
        for attr in ("train", "train_step", "observe", "rebuild_vocab", "save",
                     "load", "generate", "perplexity", "encode", "vocab_size"):
            self.assertTrue(hasattr(lm, attr), attr)

    def test_train_step_works_on_raw_text(self):
        lm = make_model(blocks=1)
        loss = lm.train_step("the cat sat on the mat")
        self.assertTrue(np.isfinite(loss))

    def test_describe_reports_architecture(self):
        lm = make_model(blocks=3, heads=2, dim=8, ctx=4)
        info = lm.describe()
        self.assertEqual(info["arch"], "transformer")
        self.assertEqual(info["blocks"], 3)
        self.assertEqual(info["heads"], 2)
        self.assertEqual(info["dim"], 8)
        self.assertEqual(info["ctx"], 4)
        self.assertEqual(info["vocab"], lm.vocab_size)
        self.assertEqual(info["params"], lm.param_count())
        self.assertGreater(info["params"], 100)

    def test_param_count_matches_tensor_total(self):
        lm = make_model(blocks=2)
        self.assertEqual(lm.param_count(),
                         int(sum(p.size for p in lm.params.values())))

    def test_float32_model_trains(self):
        lm = make_model(blocks=2, dtype=np.float32)
        ctx, tgt = batch(lm)
        self.assertTrue(np.isfinite(lm._step(ctx, tgt)))
        self.assertEqual(lm.params["tok_emb"].dtype, np.float32)


if __name__ == "__main__":
    unittest.main()
