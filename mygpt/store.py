"""Self-learning state store: facts, lessons, constitution, metrics, events.

Ported from the CORTEX memory layer (github.com/codero-sus/agi) and adapted
to MyGPT's JSON persistence: semantic fact triples, self-critique lessons,
metrics (loss, self-eval) and an event log.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass


@dataclass
class Fact:
    ts: float
    subject: str
    predicate: str
    obj: str
    confidence: float


class SelfLearnStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self.facts: list[dict] = []
        self.lessons_list: list[dict] = []
        self.principles: list[str] = list(DEFAULT_PRINCIPLES)
        self.constitution_version = 1
        self.metrics: dict[str, list] = {"loss": [], "self_eval": []}
        self.events: list[dict] = []
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            self.facts = d.get("facts", [])
            self.lessons_list = d.get("lessons", [])
            self.principles = d.get("principles") or self.principles
            self.constitution_version = d.get("constitution_version", 1)
            self.metrics = d.get("metrics", {"loss": [], "self_eval": []})
            self.events = d.get("events", [])
        except Exception:
            pass

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "facts": self.facts[-400:],
                "lessons": self.lessons_list[-200:],
                "principles": self.principles,
                "constitution_version": self.constitution_version,
                "metrics": {k: v[-120:] for k, v in self.metrics.items()},
                "events": self.events[-60:],
            }, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ facts
    def add_fact(self, subject: str, predicate: str, obj: str,
                 confidence: float = 0.8) -> bool:
        subject, predicate, obj = (subject.strip()[:120], predicate.strip()[:80],
                                   obj.strip()[:400])
        if not subject or not obj:
            return False
        for f in self.facts:
            if (f["subject"], f["predicate"], f["obj"]) == (subject, predicate, obj):
                f["confidence"] = min(1.0, f["confidence"] + 0.05)
                f["ts"] = time.time()
                return False  # reinforced, not new
        self.facts.append({"ts": time.time(), "subject": subject,
                           "predicate": predicate, "obj": obj,
                           "confidence": round(confidence, 2)})
        return True

    def facts_about(self, query: str, k: int = 8) -> list[Fact]:
        q = query.lower()
        toks = [t for t in re.split(r"\W+", q) if len(t) > 2]
        hits = []
        for f in reversed(self.facts[-200:]):
            blob = f"{f['subject']} {f['predicate']} {f['obj']}".lower()
            if (toks and any(t in blob for t in toks)) or (q and q in blob):
                hits.append(Fact(f["ts"], f["subject"], f["predicate"],
                                 f["obj"], f["confidence"]))
        return hits[:k]

    def all_facts(self, k: int = 40) -> list[Fact]:
        return [Fact(f["ts"], f["subject"], f["predicate"], f["obj"],
                     f["confidence"]) for f in self.facts[-k:]]

    def forget_facts(self, query: str) -> int:
        q = query.lower().strip()
        if not q:
            return 0
        before = len(self.facts)
        self.facts = [f for f in self.facts
                      if q not in f"{f['subject']} {f['predicate']} {f['obj']}".lower()]
        return before - len(self.facts)

    # ---------------------------------------------------------------- lessons
    def add_lesson(self, text: str, source: str = "critic") -> bool:
        text = text.strip()[:500]
        if not text or any(l["text"] == text for l in self.lessons_list):
            return False
        self.lessons_list.append({"ts": time.time(), "text": text, "source": source})
        return True

    def lessons(self, k: int = 20) -> list[str]:
        return [l["text"] for l in self.lessons_list[-k:]]

    # ------------------------------------------------------------ constitution
    def add_principle(self, text: str) -> bool:
        text = text.strip()[:280]
        if not text:
            return False
        existing = [p.lower() for p in self.principles]
        if text.lower() in existing:
            return False
        if any(text.lower() in e or e in text.lower() for e in existing):
            return False
        self.principles.append(text)
        self.constitution_version += 1
        return True

    # ---------------------------------------------------------------- metrics
    def log_metric(self, name: str, value: float) -> None:
        self.metrics.setdefault(name, []).append(
            {"t": round(time.time()), "v": round(float(value), 4)})
        self.metrics[name] = self.metrics[name][-120:]

    def metric_series(self, name: str, k: int = 80) -> list[dict]:
        return self.metrics.get(name, [])[-k:]

    # ----------------------------------------------------------------- events
    def log_event(self, kind: str, payload: dict) -> None:
        self.events.append({"t": round(time.time()), "kind": kind, "payload": payload})
        self.events = self.events[-60:]

    def recent_events(self, k: int = 30) -> list[dict]:
        return list(reversed(self.events[-k:]))

    def counts(self) -> dict:
        return {"facts": len(self.facts), "lessons": len(self.lessons_list),
                "principles": len(self.principles),
                "events": len(self.events)}

    # ------------------------------------------------- fact extraction (CORTEX)
    _STOP_TAIL = re.compile(
        r"\s+(?:and|but|with|where|when|because|that|,|!|\?).*?$", re.I)

    @classmethod
    def _clean_value(cls, v: str) -> str:
        """Cut captured values at conjunctions so 'Ada and I live…' -> 'Ada'."""
        return cls._STOP_TAIL.sub("", v).strip(" .,!?")

    @classmethod
    def extract_from_user(cls, text: str) -> list[tuple[str, str, str]]:
        """Regex extraction of semantic triples from user messages (as CORTEX does)."""
        t = text.strip()
        found: list[tuple[str, str, str]] = []
        patterns = [
            (r"\bmy name is ([A-Za-z][\w\s\-]{1,40})", "user", "name"),
            (r"\bi am (?:called|named) ([A-Za-z][\w\s\-]{1,40})", "user", "name"),
            (r"\bcall me ([A-Za-z][\w\s\-]{1,40})", "user", "name"),
            (r"\bi live in ([A-Za-z][\w\s,\-]{1,60})", "user", "lives_in"),
            (r"\bi work (?:as|at) ([^\.\,\n]{2,60})", "user", "works"),
            (r"\bi like ([^\.\,\n]{2,60})", "user", "likes"),
            (r"\bi love ([^\.\,\n]{2,60})", "user", "likes"),
            (r"\b(?:please )?remember that (.+)", "user", "note"),
            (r"\bdon't forget (?:that )?(.+)", "user", "note"),
            (r"\bmy favorite (\w+) is ([^\.\,\n]{1,60})", "user", "favorite"),
        ]
        for pat, subj, pred in patterns:
            m = re.search(pat, t, re.I)
            if m:
                if pred == "favorite" and len(m.groups()) >= 2:
                    found.append((subj, f"favorite_{m.group(1).lower()}",
                                  cls._clean_value(m.group(2))))
                elif pred == "note":
                    found.append((subj, pred, m.group(1).strip().rstrip(".")))
                else:
                    found.append((subj, pred, cls._clean_value(m.group(1))))
        found = [(s, p, o) for s, p, o in found if o]
        return found


DEFAULT_PRINCIPLES = [
    "Seek truth. When uncertain, say so and ask to be taught.",
    "Improve after every interaction: remember, distill, train.",
    "Be useful without being sycophantic. Prefer the correct answer to the pleasing one.",
    "Protect the user's privacy. Facts are stored locally, nowhere else.",
    "Grow skills when a task repeats. Prefer reusable procedures over one-off replies.",
    "Keep a coherent self. Update beliefs when evidence demands it.",
    "Retrieve from memory before answering. Show what you know.",
]
