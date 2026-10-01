"""Episodic memory with a numpy vector index.

Ported from CORTEX (github.com/codero-sus/agi): every dialogue turn becomes an
episode embedded by deterministic token hashing; recall is a matrix-vector
product with a recency bonus. Embeddings are cheap to recompute, so only the
raw episodes are persisted.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass

import numpy as np

DIM = 96
CAP = 2000


def _embed(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    toks = [t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if t]
    if not toks:
        toks = ["_empty"]
    for i, tok in enumerate(toks):
        h = hashlib.blake2b(tok.encode(), digest_size=8).digest()
        a = int.from_bytes(h[:4], "little")
        b = int.from_bytes(h[4:], "little")
        vec[a % DIM] += 1.0
        vec[b % DIM] -= 0.4
        vec[(a + i) % DIM] += 0.25
    n = float(np.linalg.norm(vec))
    return vec / n if n > 1e-9 else vec


@dataclass
class Episode:
    id: int
    ts: float
    role: str
    content: str
    score: float = 0.0


class EpisodicMemory:
    def __init__(self, path: str) -> None:
        self.path = path
        self.episodes: list[dict] = []       # {id, ts, role, content}
        self.working: list[dict] = []        # last 24 turns (working memory)
        self._mat: np.ndarray = np.zeros((0, DIM), dtype=np.float32)
        self._meta: list[tuple[int, float, str, str]] = []
        self._next_id = 1
        self._load()

    # ------------------------------------------------------------- mutation
    def remember(self, role: str, content: str) -> int:
        content = (content or "").strip()[:2000]
        if len(content) < 2:
            return -1
        rid = self._next_id
        self._next_id += 1
        self.episodes.append({"id": rid, "ts": time.time(), "role": role,
                              "content": content})
        self._append_index(rid, self.episodes[-1])
        self._cap()
        self.working.append({"role": role, "content": content})
        self.working = self.working[-24:]
        return rid

    def remember_many(self, items: list[tuple[str, str]]) -> int:
        n = 0
        ts = time.time()
        for role, content in items:
            content = (content or "").strip()[:2000]
            if len(content) < 2:
                continue
            rid = self._next_id
            self._next_id += 1
            ep = {"id": rid, "ts": ts, "role": role, "content": content}
            self.episodes.append(ep)
            self._append_index(rid, ep)
            n += 1
            if len(self.episodes) >= CAP:
                break
        self._cap()
        return n

    def _append_index(self, rid: int, ep: dict) -> None:
        vec = _embed(ep["content"])
        self._mat = (np.vstack([self._mat, vec.reshape(1, -1)])
                     if self._mat.size else vec.reshape(1, -1))
        self._meta.append((rid, float(ep["ts"]), ep["role"], ep["content"]))

    def _cap(self) -> None:
        if len(self.episodes) > CAP:
            cut = len(self.episodes) - CAP
            self.episodes = self.episodes[cut:]
            self._mat = self._mat[cut:]
            self._meta = self._meta[cut:]

    # ------------------------------------------------------------ retrieval
    def search(self, query: str, k: int = 5) -> list[Episode]:
        if self._mat.shape[0] == 0:
            return []
        q = _embed(query)
        scores = self._mat @ q
        k = min(k, scores.shape[0])
        # recent-item bonus so yesterday doesn't drown today
        recency = np.linspace(0.0, 0.08, scores.shape[0], dtype=np.float32)
        scores = scores + recency
        idx = np.argpartition(-scores, kth=k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        out: list[Episode] = []
        for i in idx:
            rid, ts, role, content = self._meta[int(i)]
            out.append(Episode(rid, ts, role, content, float(scores[int(i)])))
        return out

    def recent_dialogue(self, k: int = 8) -> list[dict]:
        return [{"role": e["role"], "content": e["content"]}
                for e in self.episodes[-k:]]

    # ------------------------------------------------------------ persistence
    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.episodes[-CAP:], f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.episodes = json.load(f)[-CAP:]
        except Exception:
            self.episodes = []
        for ep in self.episodes:
            self._append_index(int(ep["id"]), ep)
            self._next_id = max(self._next_id, int(ep["id"]) + 1)
        self.working = [{"role": e["role"], "content": e["content"]}
                        for e in self.episodes[-24:]]
