"""The self-improvement loop — ported from CORTEX (github.com/codero-sus/agi).

Light pass: after every turn — extract facts, critique the reply, queue
background gradient steps (non-blocking).
Medium pass: every N turns — skill synthesis, constitution promotion,
self-eval battery, corpus training, consolidation.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Brain


CYCLE_EVERY_TURNS = 5
CYCLE_TRAIN_STEPS = 8

SELF_TESTS = [
    ("What is 17 times 3?", ["51"]),
    ("what is your name", ["mygpt"]),
    ("who are you", ["mygpt", "learn", "self"]),
    ("what is python", ["python", "flask", "numpy", "language"]),
    ("Name one of your principles.", ["truth", "improve", "learn", "useful",
                                      "privacy", "memory", "coherent"]),
]


def _contains_any(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(n.lower() in low for n in needles)


def classify_intent(text: str) -> str:
    low = text.lower()
    from . import codegen as _codegen
    if _codegen.wants_code(text):
        return "code"
    if re.search(r"^[\s0-9+\-*/().%^]+$", text) and re.search(r"[+\-*/%^]", text):
        return "math"
    if re.search(r"\d[\d\s+\-*/().%^]*[+\-*/%^]", low):
        return "math"
    if re.search(r"\b(who are you|your name|what are you)\b", low):
        return "identity"
    if low.startswith(("note:", "take a note", "make a note")) or \
            re.search(r"\bremember that\b|\bdon't forget\b", low):
        return "remember"
    if re.search(r"^(hi|hello|hey|good morning|good evening|yo)\b", low):
        return "greeting"
    if "?" in text or re.match(r"^(what|why|how|when|where|who|which|can|do|is|are)\b", low):
        return "question"
    return "chat"


class SelfImprovement:
    def __init__(self, brain: "Brain"):
        self.brain = brain
        self._lock = threading.Lock()
        self.last_cycle = 0.0
        self.recent_intents: list[str] = []

    # ------------------------------------------------------------- light pass
    def after_turn(self, user: str, reply: str, intent: str) -> dict:
        brain = self.brain
        events: list[dict] = []

        extracted = brain.store.extract_from_user(user)
        for subj, pred, obj in extracted:
            brain.store.add_fact(subj, pred, obj, 0.9)
            events.append({"kind": "fact", "text": f"{subj} {pred} {obj}"})
            brain.store.log_event("fact", {"subject": subj, "predicate": pred,
                                           "object": obj})
        if extracted:
            brain.goals.nudge("know-the-user", 0.04)

        lesson = self._critique(user, reply, intent)
        if lesson:
            if brain.store.add_lesson(lesson, source="critic"):
                events.append({"kind": "lesson", "text": lesson})
                brain.store.log_event("lesson", {"text": lesson})

        self.recent_intents.append(intent)
        self.recent_intents = self.recent_intents[-20:]

        train_text = f"user: {user}\nmygpt: {reply}"
        brain.lm.observe(train_text)
        if brain.trainer.submit(train_text, steps=2):
            events.append({"kind": "train", "text": "queued neural steps"})
        loss = float(brain.trainer.last_loss or 0.0)
        if loss:
            brain.store.log_metric("loss", loss)

        brain.counters["turns"] = brain.counters.get("turns", 0) + 1
        brain.goals.nudge("become-more-capable", 0.002)
        if extracted:
            brain.save()

        if brain.counters["turns"] % CYCLE_EVERY_TURNS == 0:
            events.extend(self.cycle(reason="periodic"))

        return {"events": events, "loss": loss, "turns": brain.counters["turns"]}

    # ----------------------------------------------------------- medium pass
    def cycle(self, reason: str = "manual") -> list[dict]:
        with self._lock:
            return self._cycle(reason)

    def _cycle(self, reason: str) -> list[dict]:
        brain = self.brain
        events: list[dict] = []
        brain.counters["cycles"] = brain.counters.get("cycles", 0) + 1
        self.last_cycle = time.time()

        skill_ev = self._maybe_skill()
        if skill_ev:
            events.append(skill_ev)

        for lesson in brain.store.lessons(k=5):
            if lesson.lower().startswith("principle:"):
                text = lesson.split(":", 1)[1].strip()
                if brain.store.add_principle(text):
                    events.append({"kind": "constitution", "text": lesson})
                    brain.store.log_event("constitution", {"text": text})
                    brain.goals.nudge("keep-constitution", 0.03)

        score = self._self_eval()
        brain.store.log_metric("self_eval", score)
        events.append({"kind": "self-eval", "text": f"self-eval {score:.0%}"})
        brain.store.log_event("self-eval", {"score": score, "reason": reason})

        corpus = self._training_corpus()
        brain.trainer.submit(corpus, steps=CYCLE_TRAIN_STEPS)
        events.append({"kind": "train",
                       "text": f"queued {CYCLE_TRAIN_STEPS} cycle steps"})

        messages = brain.counters.get("messages", 0)
        counts = brain.store.counts()
        if messages and messages % 10 == 0:
            distilled = (
                f"After {messages} messages I hold {brain.counters.get('pairs', len(brain.memory.pairs))} "
                f"memory pairs, {counts['facts']} facts and {counts['lessons']} "
                f"lessons. I will retrieve before answering."
            )
            if brain.store.add_lesson(distilled, source="consolidate"):
                events.append({"kind": "consolidate", "text": distilled})

        brain.store.log_event("cycle", {"reason": reason, "events": len(events)})
        brain.save()
        return events

    # -------------------------------------------------------------- critique
    def _critique(self, user: str, reply: str, intent: str) -> str | None:
        if len(reply) < 8:
            return ("Principle: never answer with an empty or tiny reply; "
                    "explain or ask to be taught.")
        if reply.strip() == user.strip():
            return "Principle: do not parrot the user; add substance."
        if intent == "math" and not re.search(r"\d", reply):
            return "When the user asks for math, include the numeric result plainly."
        if intent == "identity" and "mygpt" not in reply.lower():
            return "When asked who I am, say I am MyGPT and how I learn."
        if "?" in user and len(reply) < 40:
            return "Questions deserve a reasoned answer, not a fragment."
        if intent == "remember":
            return "Persist user facts as triples and confirm what was stored."
        return None

    # -------------------------------------------------------- skill synthesis
    def _maybe_skill(self) -> dict | None:
        if len(self.recent_intents) < 4:
            return None
        counts = Counter(self.recent_intents)
        intent, n = counts.most_common(1)[0]
        if n < 3 or intent in ("chat", "identity", "unknown", "code"):
            return None
        name = f"handle_{intent}"
        if name in self.brain.skills.skills:
            return None
        code = (
            "def register(api):\n"
            f"    @api.skill({name!r}, 'Auto-written handler for repeated {intent} requests.', "
            "pattern=None)\n"
            f"    def {name}(ctx, text=''):\n"
            f"        return f'Using learned {intent} skill on: {{ctx.get(\"user\", text)}}'\n"
        )
        path = self.brain.skills.write_skill(name, f"auto {intent}", code)
        self.brain.store.log_event("skill", {"name": name, "path": path.name})
        return {"kind": "skill", "text": f"wrote skill {name} → {path.name}"}

    # -------------------------------------------------------------- self-eval
    def _self_eval(self) -> float:
        hits = 0
        for q, needles in SELF_TESTS:
            try:
                ans = self.brain.quick_answer(q)
            except Exception:
                ans = ""
            if _contains_any(ans, needles):
                hits += 1
        return hits / max(len(SELF_TESTS), 1)

    # --------------------------------------------------------- corpus builder
    def _training_corpus(self) -> str:
        brain = self.brain
        principles = "\n".join(f"- {p}" for p in brain.store.principles[-12:])
        preamble = (
            f"I am MyGPT, a self-training chatbot. Turns lived: "
            f"{brain.counters.get('turns', 0)}. Cycles: "
            f"{brain.counters.get('cycles', 0)}.\nConstitution:\n{principles}"
        )
        lessons = "\n".join(brain.store.lessons(k=12))
        facts = "; ".join(f"{f.subject} {f.predicate} {f.obj}"
                          for f in brain.store.all_facts(k=20))
        taught = "\n".join(f"{p['q']} {p['a']}"
                           for p in brain.memory.pairs[-6:])
        dialogue = "\n".join(brain.corpus[-10:])
        return (f"{preamble}\nLessons:\n{lessons}\nFacts:\n{facts}\n"
                f"Taught:\n{taught}\nDialogue:\n{dialogue}\n")

    def snapshot(self) -> dict:
        return {"last_cycle": self.last_cycle,
                "recent_intents": self.recent_intents[-8:]}
