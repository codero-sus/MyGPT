"""A decoder-only Transformer language model, in pure NumPy.

This is MyGPT's *own* brain, upgraded from the Bengio-style feed-forward net in
``langmodel.py`` to a real transformer:

    tokens -> token emb + learned positional emb
           -> N x [ LayerNorm -> multi-head causal self-attention -> residual
                    LayerNorm -> GELU feed-forward (4x)      -> residual ]
           -> LayerNorm -> tied output head (logits = h @ tok_emb.T)

Design notes (all of it is standard modern practice, deliberately kept small
enough to train on a laptop CPU):

* **pre-LN** blocks (LayerNorm before each sublayer) — stabler gradients than
  the original post-LN form, which is exactly what a tiny model needs.
* **Multi-head causal self-attention**, head-split from full-width Q/K/V
  projections, scaled dot-product with an upper-triangular mask.
* **Weight tying** between the token embedding and the output head — halves
  the parameter count for a 4000-word vocab and is what GPT-2 does.
* **No biases** in the projections (LLaMA-style): fewer parameters, and no
  measurable loss for a model this size.
* **Adam** with warmup + cosine decay, global gradient-norm clipping, and
  inverted dropout on attention and residuals (train-time only).
* **Top-k / top-p / temperature / repetition-penalty sampling** for generation.

Correctness is not asserted, it is *verified*: ``tests/test_transformer.py``
runs a central-difference gradient check over every parameter tensor, so the
hand-written backward pass has to agree with the numerical derivative.

The class is a drop-in for :class:`mygpt.langmodel.NeuralLM` — it subclasses
it and reuses its vocabulary handling, corpus windowing, locking and encoding
cache, so the background trainer, checkpoints and the Brain keep working.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from .langmodel import BOS, EOS, NeuralLM, PAD, UNK

GELU_C = math.sqrt(2.0 / math.pi)
GELU_K = 0.044715


# --------------------------------------------------------------------- pieces
def layer_norm(x, g, b, eps=1e-5):
    """Forward LayerNorm. Returns (out, cache)."""
    mu = x.mean(axis=-1, keepdims=True)
    xc = x - mu
    var = (xc * xc).mean(axis=-1, keepdims=True)
    inv = 1.0 / np.sqrt(var + eps)
    xhat = xc * inv
    return g * xhat + b, (xhat, inv, g)


def layer_norm_backward(dout, cache):
    """Backward LayerNorm. Returns (dx, dg, db)."""
    xhat, inv, g = cache
    dg = (dout * xhat).sum(axis=tuple(range(dout.ndim - 1)))
    db = dout.sum(axis=tuple(range(dout.ndim - 1)))
    dxhat = dout * g
    dx = inv * (dxhat - dxhat.mean(axis=-1, keepdims=True)
                - xhat * (dxhat * xhat).mean(axis=-1, keepdims=True))
    return dx, dg, db


def gelu(x):
    # `x * x * x`, never `x ** 3`: numpy's float32 power operator takes the slow
    # generic path (measured 145x slower — 3.05 ms vs 0.021 ms on a (32,6,256)
    # array), and GELU is evaluated twice per training step, so this one
    # expression was most of the model's training time.
    x3 = x * x * x
    u = x + GELU_K * x3
    u *= GELU_C
    return 0.5 * x * (1.0 + np.tanh(u))


def gelu_backward(x):
    x2 = x * x
    u = x + GELU_K * (x2 * x)
    u *= GELU_C
    t = np.tanh(u)
    du = 1.0 + 3.0 * GELU_K * x2
    du *= GELU_C
    return 0.5 * (1.0 + t) + 0.5 * x * (1.0 - t * t) * du


def softmax_last(logits):
    z = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class TransformerLM(NeuralLM):
    """Decoder-only transformer LM. Drop-in replacement for ``NeuralLM``."""

    def __init__(self, dim: int = 64, heads: int = 4, blocks: int = 2,
                 ffn_mult: int = 4, ctx: int = 6, max_vocab: int = 4000,
                 lr: float = 3e-3, dropout: float = 0.0, warmup: int = 40,
                 total_steps: int = 800, rng_seed: int = 7,
                 dtype=np.float32):
        # The parent's __init__ calls self.rebuild_vocab(), which we override,
        # so the state that override needs must exist *before* it runs.
        self.params: dict[str, np.ndarray] = {}
        self.blocks = max(1, blocks)
        self.ffn_mult = ffn_mult
        self.heads = max(1, heads)
        self.dropout = float(dropout)
        self.warmup = warmup
        self.total_steps = total_steps
        self.step_count = 0
        self.dtype = dtype
        self.arch = "transformer"
        self._prev_vocab_index: dict[str, int] = {}

        # the parent builds vocabulary + encoders, then we own the weights
        super().__init__(dim=dim, hidden=dim, ctx=ctx, max_vocab=max_vocab,
                         lr=lr, rng_seed=rng_seed)
        # the parent's MLP weight names no longer apply
        for stale in ("W1", "b1"):
            setattr(self, stale, None)

    # ------------------------------------------------------------------ set-up
    def _build_weights(self, keep_known: bool = True) -> None:
        """(Re)create every parameter tensor, keeping known token rows."""
        d = self.dim
        V = len(self.idx2word)
        old = self.params.get("tok_emb")
        old_index = dict(self._prev_vocab_index)
        rng = self.rng
        scale = 0.02

        tok = rng.normal(0, scale, (V, d)).astype(self.dtype)
        if keep_known and old is not None:
            for i, w in enumerate(self.idx2word):
                j = old_index.get(w)
                if j is not None and j < old.shape[0]:
                    tok[i] = old[j]
        self.params["tok_emb"] = tok
        self.params["pos_emb"] = rng.normal(
            0, scale, (self.ctx, d)).astype(self.dtype)

        for i in range(self.blocks):
            for name, shape in (
                (f"b{i}_Wq", (d, d)), (f"b{i}_Wk", (d, d)),
                (f"b{i}_Wv", (d, d)), (f"b{i}_Wo", (d, d)),
                (f"b{i}_W1", (d, self.ffn_mult * d)),
                (f"b{i}_W2", (self.ffn_mult * d, d)),
            ):
                self.params[name] = (rng.normal(0, scale, shape)
                                     .astype(self.dtype))
            self.params[f"b{i}_g1"] = np.ones(d, dtype=self.dtype)
            self.params[f"b{i}_b1"] = np.zeros(d, dtype=self.dtype)
            self.params[f"b{i}_g2"] = np.ones(d, dtype=self.dtype)
            self.params[f"b{i}_b2"] = np.zeros(d, dtype=self.dtype)
        self.params["g_final"] = np.ones(d, dtype=self.dtype)
        self.params["b_final"] = np.zeros(d, dtype=self.dtype)
        self._adam, self._adam_t = {}, 0
        self._enc_cache.clear()

    def rebuild_vocab(self) -> None:
        """Rebuild the vocabulary, carrying known token rows across."""
        budget = max(0, self.max_vocab - len(SPECIAL_COUNT))
        top = [w for w, _ in self.word_counts.most_common(budget)]
        new_words = list(SPECIAL_COUNT) + [w for w in top
                                           if w not in SPECIAL_COUNT]
        self._prev_vocab_index = {w: i for i, w in enumerate(self.idx2word)}
        first = len(self.idx2word) == 0
        grown = self.params.get("tok_emb") is not None and \
            self.params["tok_emb"].shape[0] != len(new_words)
        self.idx2word = new_words
        self.word2idx = {w: i for i, w in enumerate(new_words)}
        if first or grown:
            self._build_weights(keep_known=grown)
        self._adam, self._adam_t = {}, 0
        self._enc_cache.clear()

    # ----------------------------------------------------------- architecture
    def describe(self) -> dict:
        """Human-readable architecture card for the UI/stats."""
        return {
            "arch": "transformer",
            "params": self.param_count(),
            "blocks": self.blocks,
            "heads": self.heads,
            "dim": self.dim,
            "ctx": self.ctx,
            "ffn_mult": self.ffn_mult,
            "dropout": self.dropout,
            "vocab": self.vocab_size,
            "vision": f"{self.blocks}x multi-head causal self-attention"
                      f" (dim {self.dim}, {self.heads} heads, ctx {self.ctx})",
            "training": "Adam + warmup/cosine LR, grad-clip 1.0, tied embeddings",
            "steps": self.step_count,
        }

    def param_count(self) -> int:
        return int(sum(p.size for p in self.params.values()))

    def _causal_mask(self, n: int):
        key = f"_mask{n}"
        cached = getattr(self, key, None)
        if cached is None:
            cached = np.triu(np.full((n, n), -1e30, dtype=np.float64), 1)
            setattr(self, key, cached)
        return cached

    # ---------------------------------------------------------------- forward
    def _forward(self, ctx_ids, training: bool = False,
                 all_positions: bool = False):
        """ctx_ids: (B, C) ints. Returns (logits, caches).

        Only the *last* position of each window is ever scored, so the default
        path projects just that one row through the vocabulary head — a factor
        of ``ctx`` cheaper than the full (B, C, V) tensor, and it makes the
        "which position does this prediction belong to" question disappear.
        ``all_positions=True`` keeps the full tensor for diagnostics such as the
        causality test.
        """
        B, C = ctx_ids.shape
        p = self.params
        tok = p["tok_emb"][ctx_ids]                       # (B, C, D)
        x = tok + p["pos_emb"][None, :C, :]               # (B, C, D)
        caches = []
        d = self.dim
        dh = d // self.heads

        for i in range(self.blocks):
            h, ln1 = layer_norm(x, p[f"b{i}_g1"], p[f"b{i}_b1"])
            q = h @ p[f"b{i}_Wq"]
            k = h @ p[f"b{i}_Wk"]
            v = h @ p[f"b{i}_Wv"]
            # split heads: (B, C, H, Dh) -> (B, H, C, Dh)
            qh = q.reshape(B, C, self.heads, dh).transpose(0, 2, 1, 3)
            kh = k.reshape(B, C, self.heads, dh).transpose(0, 2, 1, 3)
            vh = v.reshape(B, C, self.heads, dh).transpose(0, 2, 1, 3)
            scores = (qh @ kh.transpose(0, 1, 3, 2)) / math.sqrt(dh)
            scores = scores + self._causal_mask(C)
            attn = softmax_last(scores)
            ctx = attn @ vh                                 # (B, H, C, Dh)
            ctx_f = (ctx.transpose(0, 2, 1, 3).reshape(B, C, d))
            attn_out = ctx_f @ p[f"b{i}_Wo"]
            if training and self.dropout > 0:
                keep = 1.0 - self.dropout
                dmask = (self.rng.random(attn_out.shape) < keep) / keep
                attn_out = attn_out * dmask
            else:
                dmask = None
            x = x + attn_out

            h2, ln2 = layer_norm(x, p[f"b{i}_g2"], p[f"b{i}_b2"])
            pre = h2 @ p[f"b{i}_W1"]
            z = gelu(pre)
            ff = z @ p[f"b{i}_W2"]
            if training and self.dropout > 0:
                keep = 1.0 - self.dropout
                fmask = (self.rng.random(ff.shape) < keep) / keep
                ff = ff * fmask
            else:
                fmask = None
            x = x + ff

            caches.append({"ln1": ln1, "h": h, "q": q, "k": k, "v": v,
                           "qh": qh, "kh": kh, "vh": vh, "attn": attn,
                           "ctx": ctx, "ctx_f": ctx_f, "dmask": dmask,
                           "ln2": ln2, "h2": h2, "pre": pre, "z": z,
                           "fmask": fmask,
                           "x_in": None})

        x_final, ln_final = layer_norm(x, p["g_final"], p["b_final"])
        head = x_final if all_positions else x_final[:, -1]
        logits = head @ p["tok_emb"].T                      # tied head
        return logits, {"caches": caches, "ln_final": ln_final,
                        "x_final": x_final, "tok_rows": ctx_ids, "C": C}

    # --------------------------------------------------------------- backward
    def _backward(self, dlogits, caches):
        """dlogits: (B, V) or (B, C, V) -> dict of parameter gradients."""
        p = self.params
        d = self.dim
        grads = {name: np.zeros_like(p[name]) for name in p}
        x_final = caches["x_final"]
        rows = caches["tok_rows"]
        C = caches["C"]

        if dlogits.ndim == 2:
            # only the last position was scored; gradient flows there alone
            dx = np.zeros_like(x_final)
            dx[:, -1] = dlogits @ p["tok_emb"]
            grads["tok_emb"] += dlogits.T @ x_final[:, -1]
        else:
            dx = dlogits @ p["tok_emb"]
            grads["tok_emb"] += (dlogits.reshape(-1, dlogits.shape[-1]).T
                                 @ x_final.reshape(-1, d))
        B = dx.shape[0]
        dx, dg, db = layer_norm_backward(dx, caches["ln_final"])
        grads["g_final"] += dg
        grads["b_final"] += db

        for i in reversed(range(self.blocks)):
            c = caches["caches"][i]
            # Dropout masks the sublayer *branch* only: the residual carries
            # the gradient through untouched. Masking `dx` itself (as this
            # once did) corrupts every parameter's gradient as soon as
            # dropout > 0 — caught by test_gradient_with_dropout.
            #
            # ---- feed-forward
            d_ff = dx * c["fmask"] if c["fmask"] is not None else dx
            grads[f"b{i}_W2"] += c["z"].reshape(-1, c["z"].shape[-1]).T @ \
                d_ff.reshape(-1, d)
            dz = d_ff @ p[f"b{i}_W2"].T
            dpre = gelu_backward(c["pre"]) * dz           # ffn width
            grads[f"b{i}_W1"] += c["h2"].reshape(-1, d).T @ \
                dpre.reshape(-1, dpre.shape[-1])
            dh2 = dpre @ p[f"b{i}_W1"].T                  # back to model width
            dh2_ln, dg2, db2 = layer_norm_backward(dh2, c["ln2"])
            grads[f"b{i}_g2"] += dg2
            grads[f"b{i}_b2"] += db2
            dx = dx + dh2_ln                       # residual branch

            # ---- attention
            d_att = dx * c["dmask"] if c["dmask"] is not None else dx
            grads[f"b{i}_Wo"] += c["ctx_f"].reshape(-1, d).T @ \
                d_att.reshape(-1, d)
            dctx_f = d_att @ p[f"b{i}_Wo"].T
            dh = c["h"]
            dctx = dctx_f.reshape(B, C, self.heads, -1).transpose(0, 2, 1, 3)
            dattn = dctx @ c["vh"].transpose(0, 1, 3, 2)
            dvh = c["attn"].transpose(0, 1, 3, 2) @ dctx
            dscores = c["attn"] * (dattn - (dattn * c["attn"]).sum(
                axis=-1, keepdims=True))
            dscores = dscores / math.sqrt(d // self.heads)
            # the causal mask zeroes the strict upper triangle
            dscores = dscores * (self._causal_mask(C) == 0)
            dqh = dscores @ c["kh"]
            dkh = dscores.transpose(0, 1, 3, 2) @ c["qh"]
            dq = dqh.transpose(0, 2, 1, 3).reshape(B, C, d)
            dk = dkh.transpose(0, 2, 1, 3).reshape(B, C, d)
            dv = dvh.transpose(0, 2, 1, 3).reshape(B, C, d)
            grads[f"b{i}_Wq"] += dh.reshape(-1, d).T @ dq.reshape(-1, d)
            grads[f"b{i}_Wk"] += dh.reshape(-1, d).T @ dk.reshape(-1, d)
            grads[f"b{i}_Wv"] += dh.reshape(-1, d).T @ dv.reshape(-1, d)
            dh_total = dq @ p[f"b{i}_Wq"].T + dk @ p[f"b{i}_Wk"].T \
                + dv @ p[f"b{i}_Wv"].T
            dh_ln, dg1, db1 = layer_norm_backward(dh_total, c["ln1"])
            grads[f"b{i}_g1"] += dg1
            grads[f"b{i}_b1"] += db1
            dx = dx + dh_ln                        # residual branch

        # ---- embeddings (input side)
        np.add.at(grads["tok_emb"], rows, dx)
        np.add.at(grads["pos_emb"], np.arange(C), dx.sum(axis=0))
        return grads

    # ------------------------------------------------------------------- loss
    def _step(self, ctx_ids, targets):
        """One Adam step on a batch of windows. Returns mean loss.

        The prediction for the next token is read from the *last* position of
        each window (row ``b * C + C - 1`` of the flattened (B*C, V) logits).
        Indexing rows ``0..B-1`` instead — which this did originally — trains
        against mid-context logits that do not correspond to the targets at
        all; the finite-difference gradient check in tests/test_transformer.py
        is what caught it.
        """
        B = ctx_ids.shape[0]
        logits, caches = self._forward(ctx_ids, training=True)
        probs = softmax_last(logits)               # (B, V) — next-token only
        flat_t = targets.reshape(-1)
        loss = float(-np.log(probs[np.arange(B), flat_t] + 1e-12).mean())

        # d(-log p)/dlogits = p - onehot at the scored rows only
        dlogits = probs.copy()
        dlogits[np.arange(B), flat_t] -= 1.0
        dlogits /= B
        grads = self._backward(dlogits, caches)

        norm = float(np.sqrt(sum(float((g * g).sum())
                                 for g in grads.values())))
        if norm > 1.0:
            scale = 1.0 / norm
            grads = {k: g * scale for k, g in grads.items()}
        self.step_count += 1
        self._adam_update(grads, lr=self._lr_now())
        return loss

    def _lr_now(self) -> float:
        """Warmup then cosine decay — the schedule transformers are trained with."""
        step = max(1, self.step_count)
        if step <= self.warmup:
            return self.lr * step / self.warmup
        span = max(1, self.total_steps - self.warmup)
        progress = min(1.0, (step - self.warmup) / span)
        return self.lr * (0.5 * (1.0 + math.cos(math.pi * progress)) * 0.9 + 0.1)

    def _adam_update(self, grads, lr=None, beta1: float = 0.9,
                     beta2: float = 0.999, eps: float = 1e-8) -> None:
        """Adam over ``self.params`` (name-keyed, like the parent's version)."""
        lr = self.lr if lr is None else lr
        self._adam_t += 1
        t = self._adam_t
        for name, g in grads.items():
            m, v = self._adam.get(name, [np.zeros_like(g), np.zeros_like(g)])
            m = beta1 * m + (1 - beta1) * g
            v = beta2 * v + (1 - beta2) * (g * g)
            m_hat = m / (1 - beta1 ** t)
            v_hat = v / (1 - beta2 ** t)
            self.params[name] -= lr * m_hat / (np.sqrt(v_hat) + eps)
            self._adam[name] = [m, v]

    # ---------------------------------------------------------------- infer
    def perplexity(self, texts) -> float:
        """Perplexity of the corpus — scored at the window's last position."""
        losses = []
        with self.lock:
            for ctx, tgt in self._windows(texts):
                logits, _ = self._forward(ctx[None, :])
                probs = softmax_last(logits)
                losses.append(-math.log(float(probs[0, tgt]) + 1e-12))
        return float(np.exp(np.mean(losses))) if losses else float("nan")

    def next_token_probs(self, text: str, top: int = 5):
        """The model's own prediction for what comes next (debug/UI helper)."""
        ids = self.encode_text(text)
        ctx = (ids + [self.word2idx[BOS]] * self.ctx)[-self.ctx:]
        with self.lock:
            logits, _ = self._forward(np.array([ctx], dtype=np.int64))
        probs = softmax_last(logits)[0]
        order = np.argsort(probs)[::-1][:top]
        return [(self.idx2word[i], float(probs[i])) for i in order]

    def _filtered_probs(self, z, seen_words, top_k=12, top_p=0.95,
                        repetition_penalty=1.0, return_order=False):
        """Turn raw logits into sampling probabilities.

        Applies, in order: repetition penalty on already-generated words,
        top-k truncation, softmax, then top-p (nucleus) truncation with
        renormalisation. Split out from ``generate`` so the sampling policy can
        be tested deterministically instead of through noisy samples.
        """
        z = np.array(z, dtype=np.float64, copy=True)
        if repetition_penalty and repetition_penalty > 1.0 and len(seen_words):
            seen = {self.word2idx[w] for w in seen_words
                    if w in self.word2idx}
            for i in seen:
                z[i] = z[i] / repetition_penalty if z[i] > 0 \
                    else z[i] * repetition_penalty
        order = np.argsort(z)[::-1][:max(1, top_k)]
        zz = z[order]
        probs = np.exp(zz - zz.max())
        probs /= probs.sum()
        if top_p < 1.0:
            # standard nucleus sampling: keep the smallest set whose cumulative
            # probability reaches top_p — including the token that crosses it
            cumulative = np.cumsum(probs)
            keep = np.concatenate(([True], cumulative[:-1] < top_p))
            probs = np.where(keep, probs, 0.0)
            total = probs.sum()
            if total > 0:
                probs = probs / total
            else:
                probs = np.exp(zz - zz.max())
                probs /= probs.sum()
        if return_order:
            return probs, order
        return probs

    def generate(self, n_tokens: int = 30, temperature: float = 0.9,
                 top_k: int = 12, top_p: float = 0.95,
                 repetition_penalty: float = 1.0, prompt: str = "") -> str:
        """Sample text, optionally continuing ``prompt``.

        Adds top-p (nucleus) filtering and a repetition penalty on top of the
        parent's temperature/top-k — the things that make small models usable.
        """
        bos = self.word2idx[BOS]
        if prompt:
            ids = self.encode_text(prompt)
            ctx = ([bos] * self.ctx + ids)[-self.ctx:]
            out = [self.idx2word[i] for i in ids]
        else:
            ctx = [bos] * self.ctx
            out = []
        ctx = list(ctx)
        for _ in range(n_tokens):
            with self.lock:
                logits, _ = self._forward(
                    np.array([ctx[-self.ctx:]], dtype=np.int64))
            z = logits[0].astype(np.float64) / max(1e-3, temperature)
            probs, order = self._filtered_probs(
                z, out, top_k=top_k, top_p=top_p,
                repetition_penalty=repetition_penalty, return_order=True)
            if probs.sum() <= 0:
                order = np.argsort(z)[::-1][:1]
                probs = np.ones(1)
            pick = int(order[self.rng.choice(len(order), p=probs / probs.sum())])
            word = self.idx2word[pick]
            ctx.append(pick)
            if word == EOS:
                if out:
                    break
                continue
            if word in (BOS, PAD, UNK):
                continue
            out.append(word)
        return " ".join(out)

    def encode_text(self, text: str) -> list[int]:
        from .tokenizer import tokenize
        return self.encode(tokenize(text))

    # ------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        with self.lock:
            payload = {name: arr for name, arr in self.params.items()}
            payload["_meta"] = np.array(json.dumps({
                "arch": "transformer", "dim": self.dim, "heads": self.heads,
                "blocks": self.blocks, "ctx": self.ctx,
                "ffn_mult": self.ffn_mult, "steps": self.step_count,
            }), dtype=object)
            payload["vocab"] = np.array(self.idx2word, dtype=object)
            payload["counts"] = np.array(
                json.dumps(dict(self.word_counts.most_common())), dtype=object)
            np.savez_compressed(path, **payload)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with np.load(path, allow_pickle=True) as d:
            keys = set(d.files)
            if "tok_emb" not in keys or "_meta" not in keys:
                return False                      # an MLP checkpoint, not ours
            meta = json.loads(str(d["_meta"]))
            for key in list(self.params):
                if key in keys:
                    self.params[key] = d[key].astype(self.dtype)
            self.idx2word = list(d["vocab"])
            self.word2idx = {w: i for i, w in enumerate(self.idx2word)}
            from collections import Counter
            self.word_counts = Counter(json.loads(str(d["counts"])))
            self.step_count = int(meta.get("steps", 0))
            if self.params["tok_emb"].shape[0] != len(self.idx2word):
                self._build_weights(keep_known=True)
        self._adam, self._adam_t = {}, 0
        self._enc_cache.clear()
        return True


# The special tokens live in langmodel; keep a local alias so rebuild_vocab
# reads naturally.
from .langmodel import SPECIALS as SPECIAL_COUNT  # noqa: E402  (import order)
