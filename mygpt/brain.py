"""The Brain: memory + language model + CORTEX-style self-improvement loop.

Flow of a conversation turn:
    1. Built-in skills (arithmetic) and learned skill files
    2. Semantic facts extracted from earlier turns ("my name is …")
    3. Learned memory pairs (TF-IDF retrieval)
    4. Otherwise admit ignorance and ask to be taught

Self-learning (ported from codero-sus/agi, "CORTEX"):
    * light pass after every turn: fact extraction, self-critique -> lessons,
      background Adam steps queued on the exchange
    * medium pass every 5 turns: skill synthesis, constitution promotion,
      self-eval battery, corpus training, consolidation
    * heavy pass: background trainer with dream replay + debounced checkpoints
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from pathlib import Path

from .episodes import EpisodicMemory
from .goals import Goals
from .langmodel import NeuralLM
from .memory import Memory
from .reason import Article, Reasoner
from .selflearn import SelfImprovement, classify_intent
from .skills import SkillRegistry, ensure_starter_skills
from .store import SelfLearnStore
from .tokenizer import normalize
from .trainer import BackgroundTrainer
from . import codegen
from . import importers

STRONG_MATCH = 0.52      # confident recall
WEAK_MATCH = 0.30        # a guess worth offering
AUTO_TRAIN_EVERY = 5     # curated-learning events between blocking train rounds
AUTO_TRAIN_EPOCHS = 6

TEACH_REPLIES = [
    "I don't know that yet — but you can teach me! Add an answer in the Teach panel and I'll remember it forever.",
    "That's not in my memory yet. Teach me via the panel on the right and I'll have it next time.",
    "I haven't learned that one. If you teach me now, it becomes permanent training data.",
]
MATH_RE = re.compile(r"^[\s0-9+\-*/().%^]+$")


class Brain:
    def __init__(self, data_dir: str, seed_path: str, skills_dir: str | None = None):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.lm = NeuralLM()
        self.memory = Memory()
        self.store = SelfLearnStore(os.path.join(data_dir, "selflearn.json"))
        self.episodes = EpisodicMemory(os.path.join(data_dir, "episodes.json"))
        self.goals = Goals(os.path.join(data_dir, "goals.json"))
        self.skills_root = Path(skills_dir) if skills_dir else \
            Path(__file__).resolve().parent.parent / "skills"
        ensure_starter_skills(self.skills_root)
        self.skills = SkillRegistry(self.skills_root)
        self.reasoner = Reasoner(self)
        self.corpus: list[str] = []
        self.pending: dict[str, dict] = {}     # msg_id -> last-reply record
        self.started = time.time()
        self.counters = {
            "messages": 0, "up": 0, "down": 0, "corrections": 0,
            "teachings": 0, "train_rounds": 0, "events_since_train": 0,
            "turns": 0, "cycles": 0, "imports": 0,
        }
        self.loss_history: list[dict] = []
        self.events: list[dict] = []

        self.trainer = BackgroundTrainer(self.lm, save_fn=self.save)
        self.trainer.dream_source = self._dream_text
        self.improver = SelfImprovement(self)

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
                saved = meta.get("counters", {})
                for k, v in saved.items():
                    self.counters[k] = v
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
        self.store.save()
        self.episodes.save()
        self.goals.save()
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
        self.goals.nudge("become-more-capable", 0.01)
        self.save()
        return {"ok": True, **point}

    # ------------------------------------------------------------------ chat
    def reply(self, user_text: str) -> dict:
        text = user_text.strip()
        qn = normalize(text)
        self.counters["messages"] += 1
        intent = classify_intent(text)
        msg_id = uuid.uuid4().hex[:10]
        record = {"id": msg_id, "user": text, "mode": None, "pair_id": None,
                  "confidence": 0.0, "intent": intent}
        self.episodes.remember("user", text)

        # 1) arithmetic skill -------------------------------------------------
        expr = self._find_math(text)
        if expr:
            result = self._math(expr)
            if result is not None:
                record.update(mode="math", confidence=1.0,
                              reply=f"{expr.strip(' =?')} = {result}")
                return self._after_turn(record, extract=False)

        # 2) learned skill files (procedural memory) ---------------------------
        skill = self.skills.match(text)
        if skill:
            ctx = {"user": text, "brain": self, "store": self.store,
                   "memory": self.memory, "counts": dict(self.counters)}
            out = self.skills.run(skill.name, ctx, text=text)
            record.update(mode="skill", confidence=0.9, reply=out,
                          skill=skill.name)
            return self._after_turn(record, extract=False)

        # 3) code requests → answer with a code block in chat ------------------
        if codegen.wants_code(text):
            reply_text, found = codegen.code_reply(text)
            record.update(mode="code", confidence=0.85 if found else 0.3,
                          reply=reply_text)
            self._log("code request answered in chat"
                      + ("" if found else " (no template matched)"))
            return self._after_turn(record, extract=False)

        # 4) new facts about the user ------------------------------------------
        extracted = self.store.extract_from_user(text)
        if extracted:
            parts = []
            for subj, pred, obj in extracted:
                self.store.add_fact(subj, pred, obj, 0.9)
                self.store.log_event("fact", {"subject": subj, "predicate": pred,
                                              "object": obj})
                parts.append(f"{subj} {pred} {obj}")
            record.update(mode="fact", confidence=1.0,
                          reply="Got it — stored as semantic fact" +
                                ("s" if len(parts) > 1 else "") + ": " +
                                "; ".join(parts) +
                                ". I'll remember that across sessions.")
            return self._after_turn(record, extract=False)

        # 5) recall stored personal facts ---------------------------------------
        fact_reply = self._fact_answer(qn)
        if fact_reply:
            record.update(mode="fact", confidence=0.95, reply=fact_reply)
            return self._after_turn(record)

        # 6) learned memory ------------------------------------------------------
        matches = self.memory.search(qn, k=1)
        if matches:
            pair, score = matches[0]
            if score >= STRONG_MATCH:
                record.update(mode="memory", pair_id=pair["id"],
                              confidence=score, reply=pair["a"])
                return self._after_turn(record)
            if score >= WEAK_MATCH:
                record.update(mode="guess", pair_id=pair["id"],
                              confidence=score,
                              reply=f"{pair['a']}\n(I'm only {round(score*100)}% sure — "
                                    f"use 👍/👎 so I can learn.)")
                return self._after_turn(record)

        # 7) unknown -> ask to be taught -----------------------------------------
        record.update(mode="curious", confidence=0.0,
                      reply=random.choice(TEACH_REPLIES), teach_prompt=True)
        return self._after_turn(record)

    def _after_turn(self, record: dict, extract: bool = True) -> dict:
        """Finalize the reply: attach a chain of thought, remember the episode,
        then run the CORTEX light-pass self-improvement."""
        self.episodes.remember("mygpt", record["reply"])
        record["chain"] = self._build_chain(record).as_dict()

        self.pending[record["id"]] = record
        if len(self.pending) > 200:
            for k in list(self.pending)[:len(self.pending) - 200]:
                self.pending.pop(k, None)

        if extract:
            self.improver.after_turn(record["user"], record["reply"],
                                     record.get("intent", "chat"))

        return {k: record.get(k) for k in
                ("id", "reply", "mode", "confidence", "teach_prompt", "skill",
                 "chain")}

    def _build_chain(self, record: dict):
        """System-1 trace for fast modes; full System-2 deliberation otherwise."""
        from .reason import FAST_MODES, question_kind
        mode = record["mode"]
        # Compare questions need both sides — never short-circuit on one match.
        needs_deliberation = question_kind(record["user"]) == "compare"
        if mode in FAST_MODES and not needs_deliberation:
            return self.reasoner.wrap_fast(record["user"], mode, record["reply"])
        qn = normalize(record["user"])
        articles = [Article(p["q"], p["a"])
                    for p, s in self.memory.search(qn, k=3) if s >= 0.25]
        memories = self.episodes.search(record["user"], k=4)
        # skip bookkeeping facts (imports) so real memories ground the chain
        facts = [f for f in self.store.facts_about(qn, k=4) if f.subject != "import"]
        chain = self.reasoner.deliberate(record["user"],
                                         record.get("intent", "chat"),
                                         memories, facts, articles,
                                         record["reply"])
        if mode == "curious" and chain.answer:
            record["reply"] = (chain.answer.rstrip() +
                               " Teach me an answer in the Learn panel and it "
                               "becomes permanent knowledge.")
            chain.answer = record["reply"]
        return chain

    def _fact_answer(self, qn: str) -> str | None:
        if not re.search(r"\b(my|me|i|mine)\b", qn) and "note" not in qn:
            return None
        facts = [f for f in self.store.facts_about(qn, k=4) if f.subject == "user"]
        if not facts:
            return None
        parts = []
        for f in facts:
            pred = f.predicate.replace("_", " ")
            if f.predicate == "name":
                parts.append(f"your name is {f.obj}")
            elif f.predicate == "lives_in":
                parts.append(f"you live in {f.obj}")
            elif f.predicate == "likes":
                parts.append(f"you like {f.obj}")
            elif f.predicate == "works":
                parts.append(f"you work {f.obj}")
            elif f.predicate == "note":
                parts.append(f"you noted: {f.obj}")
            elif f.predicate.startswith("favorite"):
                parts.append(f"your {f.predicate.split('_', 1)[1]} is {f.obj}")
            else:
                parts.append(f"{pred}: {f.obj}")
        return ("From what you told me earlier — " + "; ".join(parts) +
                ". (semantic facts, extracted and stored automatically)")

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

    # ------------------------------------------------------- quick answering
    def quick_answer(self, text: str) -> str:
        """Side-effect-free answer used by the self-eval battery."""
        expr = self._find_math(text)
        if expr:
            result = self._math(expr)
            if result is not None:
                return f"{expr} = {result}"
        qn = normalize(text)
        if "principle" in qn:
            return "; ".join(self.store.principles)
        matches = self.memory.search(qn, k=1)
        if matches and matches[0][1] >= WEAK_MATCH:
            return matches[0][0]["a"]
        facts = [f for f in self.store.facts_about(qn, k=3) if f.subject == "user"]
        if facts:
            return " ".join(f"{f.subject} {f.predicate} {f.obj}" for f in facts)
        return ""

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

    # ------------------------------------------------------------ improvement
    def improve_cycle(self, reason: str = "manual") -> list[dict]:
        return self.improver.cycle(reason=reason)

    def forget(self, query: str) -> int:
        n = self.store.forget_facts(query)
        if n:
            self.store.log_event("forget", {"q": query, "removed": n})
            self.save()
        return n

    def _dream_text(self) -> str:
        """Distilled mind state the idle trainer re-learns (dream replay)."""
        principles = "\n".join(f"- {p}" for p in self.store.principles[-8:])
        facts = "; ".join(f"{f.subject} {f.predicate} {f.obj}"
                          for f in self.store.all_facts(k=12))
        lessons = "\n".join(self.store.lessons(k=6))
        dialogue = "\n".join(self.corpus[-8:])
        episodes = "\n".join(f"{e['role']}: {e['content'][:160]}"
                             for e in self.episodes.recent_dialogue(k=6))
        return (f"I am MyGPT, a self-training chatbot.\n"
                f"Principles:\n{principles}\nFacts: {facts}\n"
                f"Lessons:\n{lessons}\nDialogue:\n{dialogue}\n"
                f"Recent episodes:\n{episodes}")[:4000]

    def import_history(self, filename: str, data: bytes) -> dict:
        """Absorb an exported chat history (WhatsApp/ChatGPT/Claude/Telegram/…)."""
        return importers.absorb(self, filename, data)

    # ----------------------------------------------------------------- extra
    def dream(self, n_tokens: int = 40) -> str:
        text = self.lm.generate(n_tokens=n_tokens)
        return text or "… my weights are still too young to dream."

    def stats(self) -> dict:
        counts = self.store.counts()
        return {
            "counters": self.counters,
            "pairs": len(self.memory.pairs),
            "vocab_size": self.lm.vocab_size,
            "corpus_lines": len(self.corpus),
            "tokens_trained": sum(len(t.split()) for t in self.corpus),
            "loss_history": self.loss_history[-60:],
            "events": list(reversed(self.events[-12:])),
            "last_loss": self.loss_history[-1]["loss"] if self.loss_history else None,
            "uptime_s": int(time.time() - self.started),
            # self-learning (CORTEX loop)
            "constitution_version": self.store.constitution_version,
            "principles": len(self.store.principles),
            "facts": counts["facts"],
            "lessons": counts["lessons"],
            "episodes": len(self.episodes.episodes),
            "imports": self.counters.get("imports", 0),
            "goals": self.goals.snapshot(),
            "github": codegen.GITHUB_URL,
            "mind": {
                "facts": [{"subject": f.subject, "predicate": f.predicate,
                            "object": f.obj, "confidence": f.confidence}
                           for f in self.store.all_facts(k=24)],
                "lessons": list(reversed(self.store.lessons(k=16))),
                "principles": self.store.principles,
                "constitution_version": self.store.constitution_version,
                "skills": self.skills.list(),
                "trainer": self.trainer.snapshot(),
                "self_eval": self.store.metric_series("self_eval", 40),
                "bg_loss": self.store.metric_series("loss", 80),
                "events": self.store.recent_events(24),
                "improver": self.improver.snapshot(),
            },
        }

    def recent_pairs(self, limit: int = 12) -> list[dict]:
        items = sorted(self.memory.pairs, key=lambda p: p.get("created", 0),
                       reverse=True)[:limit]
        return [{"id": p["id"], "q": p["q"], "a": p["a"],
                 "w": round(p["w"], 2), "hits": p["hits"]} for p in items]


def _strip_md(text: str) -> str:
    return re.sub(r"[*_()\[\]]", "", text).strip()
