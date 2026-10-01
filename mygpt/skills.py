"""Procedural memory: skills are Python files the bot loads, runs, and writes.

Ported from CORTEX (github.com/codero-sus/agi). Each skill file defines
``register(api)`` and decorates handlers with ``@api.skill(name, description,
pattern)``. The self-improvement loop can synthesize brand-new skill files
when an intent keeps repeating.
"""

from __future__ import annotations

import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class Skill:
    name: str
    description: str
    handler: Callable[..., str]
    path: str = ""
    pattern: str | None = None


class SkillAPI:
    def __init__(self, path: Path):
        self.path = path
        self.skills: list[Skill] = []

    def skill(self, name: str, description: str, pattern: str | None = None):
        def deco(fn):
            self.skills.append(Skill(name, description, fn, str(self.path), pattern))
            return fn
        return deco


class SkillRegistry:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        self.skills.clear()
        for path in sorted(self.dir.glob("*.py")):
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        src = path.read_text(encoding="utf-8")
        ns: dict[str, Any] = {"__name__": f"skill_{path.stem}", "__file__": str(path)}
        try:
            exec(compile(src, str(path), "exec"), ns, ns)
        except Exception:
            return
        api = SkillAPI(path)
        reg = ns.get("register")
        if callable(reg):
            try:
                reg(api)
            except Exception:
                return
        for s in api.skills:
            self.skills[s.name] = s

    def list(self) -> list[dict]:
        return [{"name": s.name, "description": s.description,
                 "path": Path(s.path).name, "pattern": s.pattern}
                for s in self.skills.values()]

    def match(self, text: str) -> Skill | None:
        low = text.lower()
        for s in self.skills.values():
            if s.pattern and re.search(s.pattern, text, re.I):
                return s
            if s.name.replace("_", " ") in low:
                return s
        return None

    def run(self, name: str, ctx: dict, **kwargs) -> str:
        s = self.skills.get(name)
        if not s:
            return f"no skill named {name}"
        try:
            return str(s.handler(ctx, **kwargs))
        except TypeError:
            try:
                return str(s.handler(ctx))
            except Exception:
                return traceback.format_exc(limit=2)
        except Exception:
            return traceback.format_exc(limit=2)

    def write_skill(self, name: str, description: str, code: str) -> Path:
        slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or \
            f"skill_{int(time.time())}"
        path = self.dir / f"{slug}.py"
        path.write_text(code, encoding="utf-8")
        self._load_file(path)
        return path


# Starter skills are written on first boot if missing (like CORTEX's).

STARTER_NOTE = '''def register(api):
    @api.skill(
        "take_note",
        "Store a short note the user wants remembered as a fact.",
        pattern=r"^(note:|take a note|make a note)",
    )
    def take_note(ctx, text=""):
        msg = ctx.get("user") or text
        body = msg.split(":", 1)[-1].strip() if ":" in msg else msg
        store = ctx.get("store")
        if store is not None:
            store.add_fact("user", "note", body, 0.9)
        return f"Noted and stored as a fact: {body}"
'''

STARTER_STATUS = '''def register(api):
    @api.skill(
        "self_status",
        "Summarize who I am and how I am growing.",
        pattern=r"how (are|have) you (improving|growing|learning)",
    )
    def self_status(ctx, text=""):
        brain = ctx.get("brain")
        if brain is None:
            return "online"
        s = brain.stats()
        c = s["counters"]
        return (
            f"I'm MyGPT. Turns lived: {c['messages']}. Improvement cycles: "
            f"{c['cycles']}. Constitution v{s['constitution_version']} with "
            f"{s['principles']} principles. I hold {s['pairs']} memory pairs, "
            f"{s['facts']} facts and {s['lessons']} lessons. Last loss: "
            f"{s['last_loss']}."
        )
'''


def ensure_starter_skills(directory: Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, src in (("take_note.py", STARTER_NOTE), ("self_status.py", STARTER_STATUS)):
        path = directory / name
        if not path.exists():
            path.write_text(src, encoding="utf-8")
