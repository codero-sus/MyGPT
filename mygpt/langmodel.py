"""A tiny feedforward neural language model implemented in pure NumPy.

Architecture (Bengio et al. 2003 style):

    context tokens -> embeddings -> mean-pool -> tanh hidden -> softmax over vocab

The model is trained online with Adam on the running conversation corpus, so
its loss drops over time — the measurable core of "improves over time".
"""

from __future__ import annotations

import json
import os
import threading
from collections import Counter

import numpy as np

from .tokenizer import tokenize

PAD, UNK, BOS, EOS = "<pad>", "<unk>", "<bos>", "<eos>"
SPECIALS = [PAD, UNK, BOS, EOS]


class NeuralLM:
    def __init__(self, dim: int = 48, hidden: int = 128, ctx: int = 4,
                 max_vocab: int = 4000, lr: float = 4e-3, rng_seed: int = 7):
        self.dim = dim
        self.hidden = hidden
        self.ctx = ctx
        self.max_vocab = max_vocab
        self.lr = lr
        self.rng = np.random.default_rng(rng_seed)

        self.word_counts: Counter = Counter()
        self.word2idx: dict[str, int] = {}
        self.idx2word: list[str] = []
        # weights
        self.E: np.ndarray | None = None       # (V, D) input embeddings
        self.W1: np.ndarray | None = None      # (H, D) hidden projection
        self.b1: np.ndarray | None = None      # (H,)
        self.W_out: np.ndarray | None = None   # (V, H) output projection
        self.b_out: np.ndarray | None = None   # (V,)
        # Adam state
        self._adam: dict[str, list[np.ndarray]] = {}
        self._adam_t = 0
        # Guards weight updates against concurrent inference (background trainer).
        self.lock = threading.RLock()

        self.rebuild_vocab()

    # ------------------------------------------------------------------ vocab
    def observe(self, text: str) -> None:
        """Register text with the vocab counter (call before training)."""
        self.word_counts.update(tokenize(text))

    @property
    def vocab_size(self) -> int:
        return len(self.idx2word)

    def rebuild_vocab(self) -> None:
        """(Re)build vocabulary from word counts, keeping known embeddings."""
        budget = max(0, self.max_vocab - len(SPECIALS))
        top = [w for w, _ in self.word_counts.most_common(budget)]
        new_words = SPECIALS + top

        old_index = {w: i for i, w in enumerate(self.idx2word)}
        V = len(new_words)
        new_E = self.rng.uniform(-0.1, 0.1, (V, self.dim)).astype(np.float32)
        new_W_out = self.rng.uniform(-0.05, 0.05, (V, self.hidden)).astype(np.float32)
        new_b_out = np.zeros(V, dtype=np.float32)
        for i, w in enumerate(new_words):
            old = old_index.get(w)
            if old is not None and self.E is not None:
                new_E[i] = self.E[old]
                new_W_out[i] = self.W_out[old]
                new_b_out[i] = self.b_out[old]

        first_build = self.E is None
        self.idx2word = new_words
        self.word2idx = {w: i for i, w in enumerate(new_words)}
        self.E, self.W_out, self.b_out = new_E, new_W_out, new_b_out
        if first_build:
            self.W1 = self.rng.uniform(-0.05, 0.05,
                                       (self.hidden, self.dim)).astype(np.float32)
            self.b1 = np.zeros(self.hidden, dtype=np.float32)
        # Output layer may have changed size -> Adam state no longer valid.
        self._adam, self._adam_t = {}, 0

    def encode(self, tokens: list[str]) -> list[int]:
        unk = self.word2idx[UNK]
        return [self.word2idx.get(t, unk) for t in tokens]

    # ------------------------------------------------------------- data paths
    def _windows(self, texts: list[str]):
        """Yield (context_ids, target_id) over all texts."""
        bos = self.word2idx[BOS]
        eos = self.word2idx[EOS]
        for text in texts:
            ids = self.encode(tokenize(text))
            if not ids:
                continue
            ids = [bos] * self.ctx + ids + [eos]
            for i in range(self.ctx, len(ids)):
                yield np.array(ids[i - self.ctx:i], dtype=np.int64), ids[i]

    # ---------------------------------------------------------------- forward
    def _forward(self, ctx_ids: np.ndarray):
        """ctx_ids: (B, C). Returns (logits (B,V), cache)."""
        emb = self.E[ctx_ids]                        # (B, C, D)
        x = emb.mean(axis=1)                         # (B, D)
        h = np.tanh(x @ self.W1.T + self.b1)         # (B, H)
        logits = h @ self.W_out.T + self.b_out       # (B, V)
        return logits, (x, h)

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        z = logits - logits.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    # ------------------------------------------------------------------ train
    def train(self, texts: list[str], epochs: int = 5, batch_size: int = 32,
              max_windows: int = 20000) -> dict:
        """Train on the corpus; returns loss stats for this round."""
        if not texts:
            return {"loss_first": None, "loss_last": None, "windows": 0}

        windows = list(self._windows(texts))
        if len(windows) > max_windows:
            keep = self.rng.choice(len(windows), max_windows, replace=False)
            windows = [windows[i] for i in sorted(keep)]

        first_loss, last_loss = None, None
        with self.lock:
            for _ in range(epochs):
                self.rng.shuffle(windows)
                for b in range(0, len(windows), batch_size):
                    batch = windows[b:b + batch_size]
                    ctx = np.stack([w[0] for w in batch])
                    tgt = np.array([w[1] for w in batch], dtype=np.int64)
                    loss = self._step(ctx, tgt)
                    if first_loss is None:
                        first_loss = loss
                    last_loss = loss
        return {"loss_first": float(first_loss), "loss_last": float(last_loss),
                "windows": len(windows)}

    def train_step(self, text: str, max_windows: int = 64) -> float:
        """One Adam step on the windows of a single text (background training)."""
        windows = list(self._windows([text]))
        if not windows:
            return 0.0
        if len(windows) > max_windows:
            keep = self.rng.choice(len(windows), max_windows, replace=False)
            windows = [windows[i] for i in sorted(keep)]
        ctx = np.stack([w[0] for w in windows])
        tgt = np.array([w[1] for w in windows], dtype=np.int64)
        with self.lock:
            return self._step(ctx, tgt)

    def _step(self, ctx_ids: np.ndarray, targets: np.ndarray) -> float:
        B, C = ctx_ids.shape
        logits, (x, h) = self._forward(ctx_ids)
        probs = self._softmax(logits)
        loss = float(-np.log(probs[np.arange(B), targets] + 1e-12).mean())

        # ---- backward pass
        dlogits = probs.copy()
        dlogits[np.arange(B), targets] -= 1.0
        dlogits /= B                                 # (B, V)

        db_out = dlogits.sum(axis=0)                 # (V,)
        dW_out = dlogits.T @ h                       # (V, H)
        dh = dlogits @ self.W_out                    # (B, H)
        dt = dh * (1.0 - h * h)                      # (B, H)
        db1 = dt.sum(axis=0)                         # (H,)
        dW1 = dt.T @ x                               # (H, D)
        dx = dt @ self.W1                            # (B, D)

        dE = np.zeros_like(self.E)
        for j in range(C):
            np.add.at(dE, ctx_ids[:, j], dx / C)

        # clip global gradient norm, then Adam
        grads = {"E": dE, "W1": dW1, "b1": db1, "W_out": dW_out, "b_out": db_out}
        norm = float(np.sqrt(sum((g ** 2).sum() for g in grads.values())))
        if norm > 5.0:
            scale = 5.0 / norm
            grads = {k: g * scale for k, g in grads.items()}
        self._adam_update(grads)
        return loss

    def _adam_update(self, grads: dict[str, np.ndarray],
                     beta1: float = 0.9, beta2: float = 0.999,
                     eps: float = 1e-8) -> None:
        self._adam_t += 1
        t = self._adam_t
        for name, g in grads.items():
            m, v = self._adam.get(name, [np.zeros_like(g), np.zeros_like(g)])
            m = beta1 * m + (1 - beta1) * g
            v = beta2 * v + (1 - beta2) * (g * g)
            m_hat = m / (1 - beta1 ** t)
            v_hat = v / (1 - beta2 ** t)
            param = getattr(self, name)
            param -= self.lr * m_hat / (np.sqrt(v_hat) + eps)
            self._adam[name] = [m, v]

    # ------------------------------------------------------------------ infer
    def perplexity(self, texts: list[str]) -> float:
        losses = []
        with self.lock:
            for ctx, tgt in self._windows(texts):
                logits, _ = self._forward(ctx[None, :])
                probs = self._softmax(logits)
                losses.append(-np.log(probs[0, tgt] + 1e-12))
        return float(np.exp(np.mean(losses))) if losses else float("nan")

    def generate(self, n_tokens: int = 30, temperature: float = 0.9,
                 top_k: int = 12) -> str:
        """Sample a fresh sentence from the model ('dreaming')."""
        bos = self.word2idx[BOS]
        ctx = np.full((1, self.ctx), bos, dtype=np.int64)
        out: list[str] = []
        for _ in range(n_tokens):
            with self.lock:
                logits, _ = self._forward(ctx)
            z = logits[0] / max(1e-3, temperature)
            order = np.argsort(z)[::-1][:top_k]
            ez = np.exp(z[order] - z[order].max())
            p = ez / ez.sum()
            pick = int(order[self.rng.choice(len(order), p=p)])
            word = self.idx2word[pick]
            if word == EOS:
                if out:
                    break
                continue
            if word in (BOS, PAD, UNK):
                continue
            out.append(word)
            ctx[0, :-1] = ctx[0, 1:]
            ctx[0, -1] = pick
        return " ".join(out)

    # ------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        with self.lock:
            np.savez_compressed(
                path,
                E=self.E, W1=self.W1, b1=self.b1, W_out=self.W_out, b_out=self.b_out,
                vocab=np.array(self.idx2word, dtype=object),
                counts=json.dumps(dict(self.word_counts.most_common())),
            )

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with np.load(path, allow_pickle=True) as d:
            self.E = d["E"].astype(np.float32)
            self.W1 = d["W1"].astype(np.float32)
            self.b1 = d["b1"].astype(np.float32)
            self.W_out = d["W_out"].astype(np.float32)
            self.b_out = d["b_out"].astype(np.float32)
            self.idx2word = list(d["vocab"])
            self.word2idx = {w: i for i, w in enumerate(self.idx2word)}
            self.word_counts = Counter(json.loads(str(d["counts"])))
        self._adam, self._adam_t = {}, 0
        return True
