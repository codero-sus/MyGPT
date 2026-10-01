"""Long-term memory: Q -> A pairs retrieved with TF-IDF cosine similarity.

Every pair the bot is taught (or corrected into) lives here. Feedback
reinforces or weakens pair weights; retrieval picks the strongest match.
"""

from __future__ import annotations

import math
import time
import uuid
from collections import Counter

import numpy as np

from .tokenizer import tokenize

# High-frequency filler words ignored during retrieval so that "what is X"
# style questions match on their *content* words, not their scaffolding.
STOPWORDS = {
    "what", "is", "are", "was", "were", "the", "a", "an", "of", "to",
    "do", "does", "did", "you", "your", "my", "me", "i", "am", "it",
    "in", "on", "for", "and", "or", "how", "who", "why", "when", "where",
    "can", "could", "would", "should", "tell", "please", "about", "there",
}


def _stem(word: str) -> str:
    """Crude suffix stripping so 'quasars' recalls 'quasar' etc."""
    if len(word) > 4:
        for suffix in ("ing", "es", "ed", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[: -len(suffix)]
    return word


def content_tokens(text: str) -> list[str]:
    """Stemmed tokens carrying meaning; falls back to all tokens if only stopwords."""
    tokens = tokenize(text)
    kept = [_stem(t) for t in tokens if t not in STOPWORDS]
    return kept or [_stem(t) for t in tokens]


class Memory:
    def __init__(self) -> None:
        self.pairs: list[dict] = []      # {id, q, a, w, created, hits}
        self._dirty = True
        self._vec_cache: dict[str, np.ndarray] = {}
        self._idf: dict[str, float] = {}

    # -------------------------------------------------------------- mutation
    def add(self, question: str, answer: str, weight: float = 1.0,
            replace_question: str | None = None) -> dict:
        """Add a pair; optionally replace the answer of an existing one."""
        if replace_question is not None:
            for p in self.pairs:
                if p["q"] == replace_question:
                    p["a"] = answer
                    p["w"] = weight
                    self._dirty = True
                    return p
        pair = {
            "id": uuid.uuid4().hex[:10],
            "q": question.strip(),
            "a": answer.strip(),
            "w": weight,
            "created": time.time(),
            "hits": 0,
        }
        self.pairs.append(pair)
        self._dirty = True
        return pair

    def remove(self, pair_id: str) -> None:
        self.pairs = [p for p in self.pairs if p["id"] != pair_id]
        self._dirty = True

    def reinforce(self, pair_id: str, delta: float) -> None:
        for p in self.pairs:
            if p["id"] == pair_id:
                p["w"] = max(0.05, p["w"] + delta)
                if delta > 0:
                    p["hits"] += 1
                break

    def get(self, pair_id: str) -> dict | None:
        return next((p for p in self.pairs if p["id"] == pair_id), None)

    # ------------------------------------------------------------ retrieval
    def _rebuild_index(self) -> None:
        df: Counter = Counter()
        for p in self.pairs:
            df.update(set(content_tokens(p["q"])))
        n = max(1, len(self.pairs))
        self._idf = {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}
        self._vec_cache.clear()
        self._dirty = False

    def _vectorize(self, tokens: list[str]) -> np.ndarray | None:
        if not tokens:
            return None
        tf = Counter(tokens)
        vec = np.zeros(len(self._idf), dtype=np.float32)
        index = {w: i for i, w in enumerate(self._idf)}
        for w, c in tf.items():
            i = index.get(w)
            if i is not None:
                vec[i] = (1.0 + math.log(c)) * self._idf[w]
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else None

    def _pair_vec(self, pair: dict) -> np.ndarray | None:
        if pair["id"] not in self._vec_cache:
            self._vec_cache[pair["id"]] = self._vectorize(content_tokens(pair["q"]))
        return self._vec_cache[pair["id"]]

    def search(self, question: str, k: int = 3) -> list[tuple[dict, float]]:
        """Return up to k (pair, score) matches sorted by similarity."""
        if self._dirty:
            self._rebuild_index()
        qv = self._vectorize(content_tokens(question))
        if qv is None or not self.pairs:
            return []
        scored = []
        for p in self.pairs:
            pv = self._pair_vec(p)
            if pv is None or pv.shape != qv.shape:
                continue
            sim = float(np.dot(pv, qv))
            # gentle weight bonus so reinforced answers surface first
            score = sim * (0.85 + 0.15 * min(1.0, p["w"]))
            scored.append((p, round(score, 4)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]

    # ------------------------------------------------------------ persistence
    def to_list(self) -> list[dict]:
        return [dict(p) for p in self.pairs]

    def load_list(self, items: list[dict]) -> None:
        self.pairs = [dict(p) for p in items]
        self._dirty = True
