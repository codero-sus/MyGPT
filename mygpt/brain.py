"""The Brain: ties memory + language model + feedback into one self-training loop.

Flow of a conversation turn:
    1. Try to answer from learned memory (TF-IDF retrieval).
    2. Fall back to small built-in skills (arithmetic).
    3. Otherwise admit ignorance and ask to be taught.

Flow of learning:
    * thumbs-up   -> reinforce matched pair, append exchange to LM corpus
    * thumbs-down -> weaken pair; if corrected, learn the right answer
    * teach       -> add a brand new pair
    * every few learning events the language model retrains automatically and
      its loss is recorded -> visible in the Growth dashboard.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import uuid

from .langmodel import NeuralLM
from .memory import Memory
from .tokenizer import normalize

STRONG_MATCH = 0.52      # confident recall
WEAK_MATCH = 0.30        # a guess worth offering
AUTO_TRAIN_EVERY = 5     # learning events between automatic training rounds
AUTO_TRAIN_EPOCHS = 6

TEACH_REPLIES = [
    "I don't know that yet — but you can teach me! Add an answer in the Teach panel and I'll remember it forever.",
    "That's not in my memory yet. Teach me via the panel on the right and I'll have it next time.",
    "I haven't learned that one. If you teach me now, it becomes permanent training data.",
]
MATH_RE = re.compile(r"^[\s0-9+\-*/().%^]+$")


class Brain:
    def __init__(self, data_dir: str, seed_path: str) -> None:
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.lm = NeuralLM()
        self.memory = Memory()
        self.corpus: list[str] = []
        self.pending: dict[str, dict] = {}     # msg_id -> last-reply record
        self.started = time.time()
        self.counters = {
            "messages": 0, "up": 0, "down": 0, "corrections": 0,
            "teachings": 0, "train_rounds": 0, "events_since_train": 0,
        }
        self.loss_history: list[dict] = []
        self.events: list[str] = []

        self._seed_path = seed_path
        self._load()

    # ---------------------------------------------------------------- setup
    def _load(self) -> None:
        mem_path = os.path.join(self.data_dir, "memory.json")
        cor_path = os.path.join(self.data_dir, "corpus.json")
        met_path = os.path.join(self.data_dir, "metrics.json")
        lm_path = os.path.join(self.data_dir, "lm_weights.npz")

        self.lm.load(lm_path)

        if os.path.exists(mem_path):
            with open(mem_path, encoding="utf-8") as f:
                self.memory.load_list(json.load(f))
        if os.path.exists(cor_path):
            with open(cor_path, encoding="utf-8") as f:
                self.corpus = json.load(f)
        if os.path.exists(met_path):
            with open(met_path, encoding="utf-8") as f:
                meta = json.load(f)
                self.counters.update(meta.get("counters", {}))
                self.loss_history = meta.get("loss_history", [])
                self.events = meta.get("events", [])

        if not self.memory.pairs and os.path.exists(self._seed_path):
            with open(self._seed_path, encoding="utf-8") as f:
                seed = json.load(f)
            for item in seed.get("pairs", []):
                self.memory.add(item["q"], item["a"])
            for line in seed.get("texts", []):
                self._ingest(line, train=False)
            self._log("seeded with starter knowledge")
            self.train(epochs=12, reason="initial training")
        elif self.corpus:
            for line in self.corpus:
                self.lm.observe(line)

    def save(self) -> None:
        self._write("memory.json", self.memory.to_list())
        self._write("corpus.json", self.corpus[-5000:])
        self._write("metrics.json", {
            "counters": self.counters,
            "loss_history": self.loss_history[-200:],
            "events": self.events[-40:],
        })
        self.lm.save(os.path.join(self.data_dir, "lm_weights.npz"))

    def _write(self, name: str, obj) -> None:
        tmp = os.path.join(self.data_dir, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.data_dir, name))

    def _log(self, text: str) -> None:
        self.events.append({"t": round(time.time()), "text": text})
        self.events = self.events[-40:]

    # ------------------------------------------------------------- utilities
    def _ingest(self, text: str, train: bool = True) -> None:
        self.corpus.append(text)
        self.lm.observe(text)
        if train:
            self._maybe_auto_train()

    def _maybe_auto_train(self) -> None:
        self.counters["events_since_train"] += 1
        if self.counters["events_since_train"] >= AUTO_TRAIN_EVERY:
            self.train(epochs=AUTO_TRAIN_EPOCHS, reason="auto training")

    def train(self, epochs: int = 10, reason: str = "manual") -> dict:
        if not self.corpus:
            return {"ok": False, "error": "corpus is empty"}
        t0 = time.time()
        # Grow vocabulary if the corpus is pressing against the cap.
        if len(self.lm.word_counts) > self.lm.vocab_size * 0.8:
            self.lm.rebuild_vocab()
        stats = self.lm.train(self.corpus, epochs=epochs)
        took_ms = int((time.time() - t0) * 1000)
        self.counters["train_rounds"] += 1
        self.counters["events_since_train"] = 0
        point = {
            "t": round(time.time()), "loss": round(stats["loss_last"], 4),
            "epochs": epochs, "reason": reason,
            "vocab": self.lm.vocab_size, "took_ms": took_ms,
        }
        self.loss_history.append(point)
        self._log(f"training round #{self.counters['train_rounds']}: "
                  f"loss {point['loss']} ({reason}, {took_ms} ms)")
        self.save()
        return {"ok": True, **point}

    # ------------------------------------------------------------------ chat
    def reply(self, user_text: str) -> dict:
        text = user_text.strip()
        qn = normalize(text)
        self.counters["messages"] += 1
        msg_id = uuid.uuid4().hex[:10]

        record = {"id": msg_id, "user": text, "mode": None, "pair_id": None,
                  "confidence": 0.0}

        # 1) arithmetic skill -------------------------------------------------
        expr = self._find_math(text)
        if expr:
            result = self._math(expr)
            if result is not None:
                record.update(mode="math", confidence=1.0,
                              reply=f"{expr.strip(' =?')} = {result}")
                return self._finalize(record)

        # 2) learned memory ----------------------------------------------------
        matches = self.memory.search(qn, k=1)
        if matches:
            pair, score = matches[0]
            if score >= STRONG_MATCH:
                record.update(mode="memory", pair_id=pair["id"],
                              confidence=score, reply=pair["a"])
                return self._finalize(record)
            if score >= WEAK_MATCH:
                record.update(mode="guess", pair_id=pair["id"],
                              confidence=score,
                              reply=f"{pair['a']}\n(I'm only {round(score*100)}% sure — "
                                    f"use 👍/👎 so I can learn.)")
                return self._finalize(record)

        # 3) unknown -> ask to be taught ---------------------------------------
        record.update(mode="curious", confidence=0.0,
                      reply=random.choice(TEACH_REPLIES), teach_prompt=True)
        return self._finalize(record)

    def _finalize(self, record: dict) -> dict:
        self.pending[record["id"]] = record
        if len(self.pending) > 200:
            for k in list(self.pending)[:len(self.pending) - 200]:
                self.pending.pop(k, None)
        out = {k: record.get(k) for k in
               ("id", "reply", "mode", "confidence", "teach_prompt")}
        return out

    @staticmethod
    def _find_math(text: str) -> str | None:
        """Find an arithmetic expression: either the whole message or embedded."""
        if MATH_RE.match(text) and re.search(r"[+\-*/%^]", text):
            return text
        m = re.search(r"[(]*\d[\d\s+\-*/().%^]*[+\-*/%^][\d\s().]*\d", text)
        return m.group(0) if m else None

    @staticmethod
    def _math(text: str) -> str | None:
        expr = text.replace("^", "**").replace(",", ".")
        try:
            value = eval(expr, {"__builtins__": {}}, {})  # digits/operators only
            if isinstance(value, complex) or value != value:
                return None
            if abs(value) > 1e15:
                return f"{value:.6e}"
            if float(value).is_integer():
                return str(int(value))
            return f"{value:.6g}"
        except Exception:
            return None

    # -------------------------------------------------------------- feedback
    def feedback(self, msg_id: str, verdict: str,
                 correction: str | None = None) -> dict:
        record = self.pending.get(msg_id)
        if record is None:
            return {"ok": False, "error": "unknown message"}
        if verdict not in ("up", "down"):
            return {"ok": False, "error": "bad verdict"}

        user_q = normalize(record["user"])
        if verdict == "up":
            self.counters["up"] += 1
            if record["pair_id"]:
                self.memory.reinforce(record["pair_id"], +0.25)
            self._ingest(f"user: {record['user']} mygpt: {_strip_md(record['reply'])}")
            self._log("positive feedback received — reinforced")
            self.save()
            return {"ok": True, "message": "Noted — that answer got stronger. 💪"}

        # thumbs down
        self.counters["down"] += 1
        if record["pair_id"]:
            self.memory.reinforce(record["pair_id"], -0.35)
        if correction and correction.strip():
            self.counters["corrections"] += 1
            self.memory.add(user_q, correction.strip(),
                            replace_question=user_q if record["pair_id"] else None)
            self._ingest(f"user: {record['user']} mygpt: {correction.strip()}")
            self._log(f"correction learned: '{user_q[:30]}…'")
            self.save()
            return {"ok": True, "message": "Thanks — I replaced that answer with yours."}
        self.save()
        return {"ok": True,
                "message": "Understood. Tell me the right answer and I'll learn it."}

    def teach(self, question: str, answer: str) -> dict:
        q, a = question.strip(), answer.strip()
        if not q or not a:
            return {"ok": False, "error": "question and answer are required"}
        qn = normalize(q)
        self.counters["teachings"] += 1
        self.memory.add(qn, a, replace_question=qn)
        self._ingest(f"user: {q} mygpt: {a}")
        self._log(f"taught: '{qn[:36]}'")
        self.save()
        return {"ok": True, "pairs": len(self.memory.pairs)}

    # ----------------------------------------------------------------- extra
    def dream(self, n_tokens: int = 40) -> str:
        text = self.lm.generate(n_tokens=n_tokens)
        return text or "… my weights are still too young to dream."

    def stats(self) -> dict:
        tokens = sum(len(t.split()) for t in self.corpus)
        return {
            "counters": self.counters,
            "pairs": len(self.memory.pairs),
            "vocab_size": self.lm.vocab_size,
            "corpus_lines": len(self.corpus),
            "tokens_trained": tokens,
            "loss_history": self.loss_history[-60:],
            "events": list(reversed(self.events[-12:])),
            "last_loss": self.loss_history[-1]["loss"] if self.loss_history else None,
            "uptime_s": int(time.time() - self.started),
        }

    def recent_pairs(self, limit: int = 12) -> list[dict]:
        items = sorted(self.memory.pairs, key=lambda p: p.get("created", 0),
                       reverse=True)[:limit]
        return [{"id": p["id"], "q": p["q"], "a": p["a"],
                 "w": round(p["w"], 2), "hits": p["hits"]} for p in items]


def _strip_md(text: str) -> str:
    return re.sub(r"[*_()\[\]]", "", text).strip()
