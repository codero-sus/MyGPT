"""Named agents the mind can spawn and run — ported from CORTEX (codero-sus/agi).

Agents are slices of one mind: a mission, a tool whitelist, and a trace that
trains the core. No shell, no root. The `code` tool drives MyGPT's coding
agent (plan → code → run → inspect → repair).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .tokenizer import normalize

if TYPE_CHECKING:
    from .brain import Brain

MAX_STEPS = 8
MAX_AGENTS = 24
MAX_RUNS_KEPT = 30
TOOL_NAMES = ("knowledge", "memory", "math", "python", "code",
              "note", "hash", "now")
RESERVED = {"mygpt", "system", "root", "admin", "user"}

SEED = [
    {
        "name": "Coder",
        "mission": "Write and run code: plan, compose, execute, inspect, repair.",
        "tools": ["code", "python", "math", "note"],
    },
    {
        "name": "Researcher",
        "mission": "Gather what the mind knows, write a brief, teach it back.",
        "tools": ["knowledge", "memory", "note"],
    },
    {
        "name": "Critic",
        "mission": "Attack a claim. Name holes, not vibes.",
        "tools": ["knowledge", "memory"],
    },
    {
        "name": "Tutor",
        "mission": "Explain from what we know, then leave a note.",
        "tools": ["knowledge", "memory", "note"],
    },
    {
        "name": "Operator",
        "mission": "Compute, hash, run snippets, note. Never a shell.",
        "tools": ["math", "python", "hash", "now", "note"],
    },
]


@dataclass
class AgentSpec:
    id: str
    name: str
    mission: str
    tools: list[str]
    created_by: str = "mygpt"
    created: float = 0.0
    runs: int = 0
    last_run: float | None = None

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "mission": self.mission,
                "tools": list(self.tools), "created_by": self.created_by,
                "created": self.created, "runs": self.runs,
                "last_run": self.last_run}

    @classmethod
    def from_dict(cls, d: dict) -> "AgentSpec":
        tools = [t for t in (d.get("tools") or []) if t in TOOL_NAMES]
        return cls(id=d.get("id") or uuid.uuid4().hex[:10],
                   name=str(d.get("name") or "agent")[:40],
                   mission=str(d.get("mission") or "")[:400],
                   tools=tools or ["knowledge"],
                   created_by=str(d.get("created_by") or "user")[:24],
                   created=float(d.get("created") or time.time()),
                   runs=int(d.get("runs") or 0),
                   last_run=d.get("last_run"))


@dataclass
class AgentRun:
    goal: str
    markdown: str
    steps: list[dict] = field(default_factory=list)
    confidence: float = 0.6
    agent: str = "Operator"
    result: str = ""

    def as_dict(self) -> dict:
        return {"agent": self.agent, "goal": self.goal, "steps": self.steps,
                "confidence": self.confidence, "result": self.result}


class Roster:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.agents: list[AgentSpec] = []
        self.runs: list[dict] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                self.agents = [AgentSpec.from_dict(x) for x in raw.get("agents") or []]
                self.runs = raw.get("runs") or []
            except Exception:
                self.agents, self.runs = [], []
        if not self.agents:
            now = time.time()
            self.agents = [AgentSpec(id=uuid.uuid4().hex[:10], name=s["name"],
                                     mission=s["mission"], tools=list(s["tools"]),
                                     created_by="mygpt", created=now)
                           for s in SEED]
            self._save()

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"agents": [a.as_dict() for a in self.agents],
                       "runs": self.runs[-MAX_RUNS_KEPT:]}, f,
                      ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self) -> list[dict]:
        with self._lock:
            return [a.as_dict() for a in self.agents]

    def recent_runs(self, k: int = 8) -> list[dict]:
        with self._lock:
            return list(reversed(self.runs[-k:]))

    def get(self, key: str) -> AgentSpec | None:
        k = (key or "").strip().lower()
        with self._lock:
            for a in self.agents:
                if a.id == key or a.name.lower() == k:
                    return a
        return None

    def default(self) -> AgentSpec:
        return self.get("Coder") or self.agents[0]

    def create(self, name: str, mission: str, tools: list[str] | None = None,
               created_by: str = "user") -> AgentSpec:
        name = re.sub(r"[^A-Za-z0-9_\-]+", "", (name or "").strip())[:40]
        if not name or name.lower() in RESERVED:
            raise ValueError("name is reserved or empty")
        tools = [t.lower().strip() for t in (tools or [])
                 if t.lower().strip() in TOOL_NAMES]
        if not tools:
            tools = ["knowledge", "memory", "note"]
        with self._lock:
            for a in self.agents:
                if a.name.lower() == name.lower():
                    a.mission = (mission or a.mission)[:400]
                    a.tools = tools
                    self._save()
                    return a
            if len(self.agents) >= MAX_AGENTS:
                raise ValueError("roster full (24)")
            spec = AgentSpec(id=uuid.uuid4().hex[:10], name=name,
                             mission=(mission or "Help.").strip()[:400],
                             tools=tools, created_by=created_by[:24],
                             created=time.time())
            self.agents.append(spec)
            self._save()
            return spec

    def delete(self, key: str) -> bool:
        with self._lock:
            before = len(self.agents)
            self.agents = [a for a in self.agents
                           if a.id != key and a.name.lower() != key.lower()]
            changed = len(self.agents) != before
            if changed:
                if not self.agents:
                    now = time.time()
                    self.agents = [AgentSpec(id=uuid.uuid4().hex[:10],
                                             name=s["name"], mission=s["mission"],
                                             tools=list(s["tools"]),
                                             created_by="mygpt", created=now)
                                   for s in SEED]
                self._save()
            return changed

    def record_run(self, spec: AgentSpec, run: AgentRun) -> None:
        with self._lock:
            spec.runs += 1
            spec.last_run = time.time()
            self.runs.append({"t": round(time.time()), **run.as_dict()})
            self.runs = self.runs[-MAX_RUNS_KEPT:]
            self._save()


# ----------------------------------------------------------------- commands
def parse_spawn(text: str) -> dict | None:
    t = text.strip()
    m = re.match(r"^(?:create|spawn|new)\s+agent\s+([A-Za-z][\w\-]{0,32})"
                 r"\s*(?:[—\-:]|that)\s*(.+)$", t, re.I)
    if not m:
        m = re.match(r"^agent new\s+([A-Za-z][\w\-]{0,32})\s*[:—]\s*(.+)$", t, re.I)
    if not m:
        return None
    name, rest = m.group(1), m.group(2).strip()
    tools: list[str] = []
    tm = re.search(r"\btools?\s*:\s*([a-z0-9,\s/]+)$", rest, re.I)
    if tm:
        tools = [x.strip().lower() for x in re.split(r"[,/]", tm.group(1)) if x.strip()]
        rest = rest[: tm.start()].strip(" ,;—-")
    rest = re.sub(r"^(mission\s*:\s*)", "", rest, flags=re.I)
    return {"name": name, "mission": rest, "tools": tools}


def parse_run(text: str) -> tuple[str, str] | None:
    t = text.strip()
    m = re.match(r"^@([A-Za-z][\w\-]{0,32})\s+(.+)$", t)
    if m:
        return m.group(1), m.group(2).strip()
    m = re.match(r"^(?:run|ask)\s+([A-Za-z][\w\-]{0,32})\s*[:—]\s*(.+)$", t, re.I)
    if m:
        return m.group(1), m.group(2).strip()
    return None


def wants_agent(text: str) -> bool:
    """Explicit agent/coding commands (natural coding asks also land here)."""
    t = text.strip()
    if parse_run(t) or parse_spawn(t):
        return True
    if re.match(r"^(do|code|python|agent|handle this|work on)\s*:", t, re.I):
        return True
    if "```" in t:
        return True
    if re.search(r"\bwrite (?:a |me )?(?:python )?(?:code|program|script|function)\b",
                 t, re.I):
        return True
    return False


def goal_of(text: str) -> str:
    t = re.sub(r"^(please\s+)?(do:|code:|python:|agent:|handle this:|work on:)\s*",
               "", text.strip(), flags=re.I)
    parsed = parse_run(t)
    if parsed:
        return parsed[1][:240]
    return (t[:240] or text.strip()[:240])


# ---------------------------------------------------------------- execution
def act(brain: "Brain", user: str, agent_name: str | None = None) -> AgentRun:
    roster = brain.roster
    named = parse_run(user)
    if named:
        spec = roster.get(named[0])
        goal = named[1]
        if spec is None:
            return AgentRun(goal,
                            f"No agent named {named[0]}. Spawn one with "
                            f"`create agent {named[0]} — mission: …`",
                            [{"kind": "parse", "text": f"unknown agent {named[0]}"}],
                            0.2, named[0])
    else:
        goal = goal_of(user)
        if agent_name:
            spec = roster.get(agent_name) or roster.default()
        elif "```" in user or re.match(r"^(code|python)\s*:", user, re.I) or \
                re.search(r"\b(write|code|compute|calculate|program|script)\b",
                          user, re.I):
            spec = roster.get("Coder") or roster.default()
        else:
            spec = roster.default()
    return run_agent(brain, spec, goal, user)


def run_agent(brain: "Brain", spec: AgentSpec, goal: str, raw: str = "") -> AgentRun:
    steps: list[dict] = []
    findings: list[str] = []

    def add(kind: str, text: str, code: str | None = None) -> None:
        s = {"kind": kind, "text": text}
        if code:
            s["code"] = code
        steps.append(s)

    add("parse", f"{spec.name} takes goal: {goal}")
    add("strategy", f"Mission: {spec.mission} · Tools: {', '.join(spec.tools)} · no shell.")

    for tool in spec.tools[:MAX_STEPS]:
        bit, thought, code = _use(brain, tool, goal, raw or goal, spec)
        add("act", thought, code)
        if bit:
            findings.append(bit)

    if not findings:
        add("critique", "Toolkit produced nothing. Honest miss, not a hallucination.")
        md = (f"{spec.name}: {goal}\n\nMission: {spec.mission}\n\n"
              "No tool in this agent's whitelist returned evidence. "
              "Broaden tools or teach me.")
        run = AgentRun(goal, md, steps, 0.25, spec.name)
        _wrap_up(brain, spec, run)
        return run

    add("decide", f"{spec.name} commits {len(findings)} observation(s).")
    result = findings[0]
    md = (f"{spec.name}: {goal}\n\nMission: {spec.mission}\n"
          f"Tools: {', '.join(spec.tools)} · hits {len(findings)}\n\n"
          f"Result\n{result}\n\nTrace\n" +
          "\n".join(f"- {f[:160]}" for f in findings))
    conf = min(0.9, 0.4 + 0.08 * len(findings))
    run = AgentRun(goal, md, steps, round(conf, 3), spec.name, result=result)
    _wrap_up(brain, spec, run)
    return run


def _wrap_up(brain: "Brain", spec: AgentSpec, run: AgentRun) -> None:
    """The trace trains the core; the run is kept in the desk."""
    brain.roster.record_run(spec, run)
    brain.store.log_event("agent-run", {"agent": spec.name, "goal": run.goal[:80],
                                        "conf": run.confidence})
    trace = f"agent {spec.name}: {run.goal}\n{run.markdown}"
    brain.lm.observe(trace)
    brain.trainer.submit(trace[:1800], steps=2)
    brain.save()


def _use(brain: "Brain", tool: str, goal: str, raw: str,
         spec: AgentSpec) -> tuple[str | None, str, str | None]:
    if tool == "knowledge":
        hits = brain.memory.search(normalize(goal), k=3)
        hits = [(p, s) for p, s in hits if s >= 0.3]
        if not hits:
            return None, "knowledge: miss", None
        blob = "; ".join(f"{p['q']}: {p['a'][:160]}" for p, _ in hits)
        return f"Knowledge — {blob}", "knowledge: " + ", ".join(p["q"] for p, _ in hits), None
    if tool == "memory":
        facts = brain.store.facts_about(goal, k=5)
        if not facts:
            return None, "memory: miss", None
        blob = "; ".join(f"{f.subject} {f.predicate} {f.obj}" for f in facts[:5])
        return f"Memory — {blob}", f"memory: {blob[:180]}", None
    if tool == "math":
        expr = brain._find_math(goal) or brain._find_math(raw)
        if not expr:
            return None, "math: n/a", None
        val = brain._math(expr)
        if val is None:
            return None, "math: could not evaluate", None
        return f"Math → {expr.strip(' =?')} = {val}", f"math → {val}", None
    if tool == "python":
        code = _extract_code(goal) or _extract_code(raw)
        if not code:
            return None, "python: no snippet given", None
        from .sandbox import run_python
        out = run_python(code)
        body = out["output"] or out["error"]
        return f"Python `{_clip(code, 80)}` → {_clip(body, 300)}", \
            f"python: {_clip(body, 80)}", code
    if tool == "code":
        from . import coding
        r = coding.solve(goal)
        if not r["ok"]:
            for fam_step in r["steps"]:
                if fam_step["kind"] == "plan":
                    return None, f"code: {fam_step['text']}", None
            return None, "code: no solution", None
        brain._coder_family_used(r["family"])
        return (f"Code ({r['family']}) → {r['answer'][:280]}",
                f"code: {r['family']} → {_clip(r['answer'], 80)}", r["code"])
    if tool == "note":
        brain.store.add_fact(spec.name.lower(), "note", goal[:200], 0.8)
        return f"Note stored: {goal[:120]}", "note: stored", None
    if tool == "hash":
        m = re.search(r"(?:hash|sha-?256)\s+(?:of\s+)?(.+)$", goal, re.I)
        payload = (m.group(1) if m else goal).strip()
        digest = hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()
        return f"SHA-256 `{_clip(payload, 40)}` → `{digest}`", "hash", None
    if tool == "now":
        import datetime as dt
        utc = dt.datetime.now(dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            ist = utc.astimezone(ZoneInfo("Asia/Kolkata"))
            ist_s = ist.strftime("%Y-%m-%d %H:%M:%S IST")
        except Exception:
            ist_s = ""
        return f"Now {utc.strftime('%Y-%m-%d %H:%M:%S UTC')}" + (f" · {ist_s}" if ist_s else ""), \
            "now", None
    return None, f"{tool}: unknown", None


def _extract_code(text: str) -> str | None:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if m:
        return m.group(1).strip()
    m = re.match(r"^python\s*:\s*(.+)$", text.strip(), re.S | re.I)
    if m:
        return m.group(1).strip()
    return None


def _clip(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t if len(t) <= n else t[: n - 1] + "…"
