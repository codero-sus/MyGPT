"""Intrinsic and user-assigned goals — ported from CORTEX (codero-sus/agi)."""

from __future__ import annotations

import json
import os
import time

SEED_GOALS = [
    {
        "id": "become-more-capable",
        "title": "Become more capable",
        "why": "Compound skills, memory, and neural loss so tomorrow's replies beat today's.",
        "status": "active",
        "progress": 0.1,
    },
    {
        "id": "know-the-user",
        "title": "Know the user",
        "why": "Store durable facts, preferences, and names. Use them without being creepy.",
        "status": "active",
        "progress": 0.05,
    },
    {
        "id": "keep-constitution",
        "title": "Keep the constitution intact while growing",
        "why": "Self-modification is only improvement if values survive it.",
        "status": "active",
        "progress": 0.4,
    },
]


class Goals:
    def __init__(self, path: str) -> None:
        self.path = path
        self.items: list[dict] = []
        self.load()
        if not self.items:
            self.items = [dict(g, created=time.time()) for g in SEED_GOALS]
            self.save()

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception:
                self.items = []

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def add(self, title: str, why: str = "") -> dict:
        title = title.strip()[:160]
        for g in self.items:
            if g.get("title", "").lower() == title.lower():
                return g
        g = {"id": f"g-{int(time.time()*1000)}", "title": title,
             "why": why.strip()[:400], "status": "active", "progress": 0.0,
             "created": time.time()}
        self.items.append(g)
        if len(self.items) > 40:
            keep = {s["id"] for s in SEED_GOALS}
            self.items = [x for x in self.items if x.get("id") in keep] + self.items[-20:]
        self.save()
        return g

    def nudge(self, goal_id: str, amount: float) -> None:
        for g in self.items:
            if g["id"] == goal_id:
                g["progress"] = float(min(1.0, max(0.0, g.get("progress", 0) + amount)))
                if g["progress"] >= 1:
                    g["status"] = "done"
                self.save()
                return

    def active(self) -> list[dict]:
        return [g for g in self.items if g.get("status") == "active"]

    def snapshot(self) -> list[dict]:
        return list(self.items)[-12:]
