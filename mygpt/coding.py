"""The Coding Agent: plan → write code → run (sandbox) → inspect → repair.

MyGPT has no LLM, so "writing code" is genuine program synthesis: the task is
parsed into a family, a template composer emits real Python, the sandbox runs
it, and failures trigger bounded repair attempts. When a family is used often
enough, the agent writes a reusable skill file into skills/ — procedural
memory of code (the same trick CORTEX uses for skills).
"""

from __future__ import annotations

import re
from pathlib import Path

from .sandbox import run_python

SKILL_AFTER_USES = 3
MAX_REPAIRS = 2

# --------------------------------------------------------------------- tasks
# Each family: (regex, param builder, code composer). The composer returns the
# Python snippet the agent will execute in the sandbox.


def _nums(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"-?\d+(?:\.\d+)?", text):
        out.append(float(m.group(0)))
    return out


def _int(text: str, default: int = 10) -> int:
    n = _nums(text)
    return int(n[0]) if n else default


FAMILIES: list[dict] = []


def family(name: str, pattern: str):
    def deco(fn):
        FAMILIES.append({"name": name, "re": re.compile(pattern, re.I),
                         "compose": fn})
        return fn
    return deco


@family("primes_first", r"first (\d+) primes?")
def _primes_first(m, goal):
    n = int(m.group(1))
    return (
        f"n = {n}\n"
        "sieve = [True] * max(2, n * 20)\n"
        "primes = []\n"
        "i = 2\n"
        "while len(primes) < n and i < len(sieve):\n"
        "    if sieve[i]:\n"
        "        primes.append(i)\n"
        "        for j in range(i * i, len(sieve), i):\n"
        "            sieve[j] = False\n"
        "    i += 1\n"
        "print('ANSWER:', primes)\n"
    )


@family("primes_upto", r"primes? (?:up to|below|under|until) (\d+)")
def _primes_upto(m, goal):
    n = int(m.group(1))
    return (
        f"n = {n}\n"
        "sieve = [True] * (n + 1)\n"
        "sieve[:2] = [False, False]\n"
        "for i in range(2, int(n ** 0.5) + 1):\n"
        "    if sieve[i]:\n"
        "        for j in range(i * i, n + 1, i):\n"
        "            sieve[j] = False\n"
        "primes = [i for i, p in enumerate(sieve) if p]\n"
        "print('ANSWER:', primes)\n"
        "print('count:', len(primes))\n"
    )


@family("fibonacci", r"(?:first (\d+) fibonacci|fibonacci(?: number)?(?: of)?[ :]? ?(\d+)|fib\((\d+)\))")
def _fibonacci(m, goal):
    n = int(next(g for g in m.groups() if g))
    if re.search(r"first", goal, re.I):
        return (
            f"n = {n}\n"
            "a, b, out = 0, 1, []\n"
            "for _ in range(n):\n"
            "    out.append(a)\n"
            "    a, b = b, a + b\n"
            "print('ANSWER:', out)\n"
        )
    return (
        f"n = {n}\n"
        "a, b = 0, 1\n"
        "for _ in range(n):\n"
        "    a, b = b, a + b\n"
        "print('ANSWER:', a)\n"
    )


@family("factorial", r"factorial(?: of)? (\d+)|(\d+)!")
def _factorial(m, goal):
    n = int(next(g for g in m.groups() if g))
    return (
        f"n = {n}\n"
        "r = 1\n"
        "for i in range(2, n + 1):\n"
        "    r *= i\n"
        "print('ANSWER:', r)\n"
    )


@family("digits_sum", r"sum of (?:the )?digits (?:of )?(\d+)")
def _digits_sum(m, goal):
    return f"print('ANSWER:', sum(int(c) for c in str({m.group(1)})))\n"


@family("digits_reverse", r"reverse (?:the )?(?:number|digits? of) (\d+)")
def _digits_reverse(m, goal):
    return f"print('ANSWER:', int(str({m.group(1)})[::-1]))\n"


@family("palindrome_num", r"is (\d+) a palindrome")
def _palindrome_num(m, goal):
    n = m.group(1)
    return (
        f"s = str({n})\n"
        "print('ANSWER:', s == s[::-1])\n"
    )


@family("palindrome_word", r"is ([a-z]+) a palindrome")
def _palindrome_word(m, goal):
    w = m.group(1).lower()
    return (
        f"s = {w!r}.lower()\n"
        "print('ANSWER:', s == s[::-1])\n"
    )


@family("anagram", r"are ([a-z]+) and ([a-z]+) anagrams")
def _anagram(m, goal):
    return (
        f"a, b = {m.group(1).lower()!r}, {m.group(2).lower()!r}\n"
        "print('ANSWER:', sorted(a) == sorted(b))\n"
    )


@family("statistics", r"\b(mean|average|median|mode|std|stddev|standard deviation|variance|sum|min|max)\b of ([\d\s,.\-]+)")
def _statistics(m, goal):
    op = m.group(1).lower()
    data = ", ".join(x for x in re.findall(r"-?\d+(?:\.\d+)?", m.group(2)))
    fn = {"mean": "mean", "average": "mean", "median": "median", "mode": "mode",
          "std": "stdev", "stddev": "stdev", "standard deviation": "stdev",
          "variance": "variance", "sum": None, "min": None, "max": None}[op]
    if fn:
        return (
            "import statistics\n"
            f"data = [{data}]\n"
            f"print('ANSWER:', round(statistics.{fn}(data), 6))\n"
        )
    return f"data = [{data}]\nprint('ANSWER:', {op}(data))\n"


@family("gcd", r"(?:gcd|greatest common divisor)(?: of)? (\d+) and (\d+)")
def _gcd(m, goal):
    return (
        "import math\n"
        f"print('ANSWER:', math.gcd({m.group(1)}, {m.group(2)}))\n"
    )


@family("lcm", r"(?:lcm|least common multiple)(?: of)? (\d+) and (\d+)")
def _lcm(m, goal):
    return (
        "import math\n"
        f"print('ANSWER:', math.lcm({m.group(1)}, {m.group(2)}))\n"
    )


@family("base_to", r"(\d+) in (binary|hex|hexadecimal|octal)")
def _base_to(m, goal):
    base = {"binary": "bin", "hex": "hex", "hexadecimal": "hex", "octal": "oct"}[m.group(2).lower()]
    return f"print('ANSWER:', {base}({m.group(1)}))\n"


@family("base_convert", r"convert (\w+) from base (\d+) to base (\d+)")
def _base_convert(m, goal):
    return (
        f"value = int({m.group(1)!r}, {m.group(2)})\n"
        f"digits = '0123456789abcdefghijklmnopqrstuvwxyz'\n"
        f"b = {m.group(3)}\n"
        "out = ''\n"
        "n = value\n"
        "while n:\n"
        "    out = digits[n % b] + out\n"
        "    n //= b\n"
        "print('ANSWER:', out or '0')\n"
    )


@family("date_diff", r"days between (\d{4}-\d{2}-\d{2}) and (\d{4}-\d{2}-\d{2})")
def _date_diff(m, goal):
    return (
        "import datetime\n"
        f"a = datetime.date.fromisoformat({m.group(1)!r})\n"
        f"b = datetime.date.fromisoformat({m.group(2)!r})\n"
        "print('ANSWER:', abs((b - a).days))\n"
    )


@family("weekday", r"(?:what )?day(?: of the week)? (?:is|was|for) (\d{4}-\d{2}-\d{2})")
def _weekday(m, goal):
    return (
        "import datetime\n"
        f"d = datetime.date.fromisoformat({m.group(1)!r})\n"
        "print('ANSWER:', d.strftime('%A'))\n"
    )


@family("circle", r"(area|circumference) of (?:a )?circle (?:with )?r(?:adius)? (\d+(?:\.\d+)?)")
def _circle(m, goal):
    if m.group(1).lower() == "area":
        expr = "math.pi * r ** 2"
    else:
        expr = "2 * math.pi * r"
    return (
        "import math\n"
        f"r = {m.group(2)}\n"
        f"print('ANSWER:', round({expr}, 6))\n"
    )


@family("sphere", r"volume of (?:a )?sphere (?:with )?r(?:adius)? (\d+(?:\.\d+)?)")
def _sphere(m, goal):
    return (
        "import math\n"
        f"r = {m.group(1)}\n"
        "print('ANSWER:', round(4 / 3 * math.pi * r ** 3, 6))\n"
    )


@family("triangle", r"area of (?:a )?triangle (?:with )?base (\d+(?:\.\d+)?) (?:and )?height (\d+(?:\.\d+)?)")
def _triangle(m, goal):
    return f"print('ANSWER:', {m.group(1)} * {m.group(2)} / 2)\n"


@family("armstrong", r"is (\d+) (?:an )?armstrong")
def _armstrong(m, goal):
    return (
        f"n = {m.group(1)}\n"
        "s = str(n)\n"
        "total = sum(int(c) ** len(s) for c in s)\n"
        "print('ANSWER:', total == n)\n"
    )


@family("powers_of_two", r"powers of (?:2|two) (?:up to|below|under) (\d+)")
def _powers_of_two(m, goal):
    return (
        f"n = {m.group(1)}\n"
        "out, p = [], 1\n"
        "while p < n:\n"
        "    out.append(p)\n"
        "    p *= 2\n"
        "print('ANSWER:', out)\n"
    )


@family("unit_convert", r"(-?\d+(?:\.\d+)?)\s*(km|mi|kg|lb|c|f)\b (?:to|in) (km|mi|kg|lb|c|f)\b")
def _unit_convert(m, goal):
    v, a, b = float(m.group(1)), m.group(2).lower(), m.group(3).lower()
    table = {
        ("km", "mi"): f"{v} * 0.621371", ("mi", "km"): f"{v} / 0.621371",
        ("kg", "lb"): f"{v} * 2.20462", ("lb", "kg"): f"{v} / 2.20462",
        ("c", "f"): f"{v} * 9 / 5 + 32", ("f", "c"): f"({v} - 32) * 5 / 9",
    }
    if (a, b) not in table:
        raise ValueError(f"no conversion {a}→{b}")
    return f"print('ANSWER:', round({table[(a, b)]}, 4))\n"


@family("word_stats", r"(?:count|how many) (words|characters|letters|vowels) in ['“\"](.+?)['”\"]")
def _word_stats(m, goal):
    kind, text = m.group(1).lower(), m.group(2)
    if kind == "words":
        expr = f"len({text!r}.split())"
    elif kind == "characters":
        expr = f"len({text!r})"
    elif kind == "letters":
        expr = f"sum(c.isalpha() for c in {text!r})"
    else:
        expr = f"sum(c.lower() in 'aeiou' for c in {text!r})"
    return f"print('ANSWER:', {expr})\n"


@family("range_sum", r"sum of (?:all )?numbers from (\d+) to (\d+)")
def _range_sum(m, goal):
    return f"print('ANSWER:', sum(range({m.group(1)}, {m.group(2)} + 1)))\n"


@family("perfect_square", r"is (\d+) (?:a )?perfect square")
def _perfect_square(m, goal):
    return (
        "import math\n"
        f"n = {m.group(1)}\n"
        "r = math.isqrt(n)\n"
        "print('ANSWER:', r * r == n)\n"
    )


# ------------------------------------------------------------------- solving
def _extract_raw_code(goal: str) -> str | None:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", goal, re.S)
    if m:
        return m.group(1).strip()
    m = re.match(r"^python\s*:\s*(.+)$", goal.strip(), re.S | re.I)
    if m:
        return m.group(1).strip()
    return None


def solve(goal: str, skills=None) -> dict:
    """The coding loop. Returns {family, code, output, steps, ok, answer}."""
    steps: list[dict] = []
    goal = (goal or "").strip()

    # 0) already-learned skill for this family? (procedural memory hit)
    # 1) plan — pick a family
    chosen = None
    for fam in FAMILIES:
        m = fam["re"].search(goal)
        if m:
            try:
                code = fam["compose"](m, goal)
                chosen = fam["name"]
                steps.append({"kind": "plan",
                              "text": f"task parsed as `{fam['name']}` — composing code"})
                break
            except Exception as e:
                steps.append({"kind": "plan", "text": f"{fam['name']} failed to compose: {e}"})
    if chosen is None:
        code = _extract_raw_code(goal)
        if code:
            chosen = "raw-python"
            steps.append({"kind": "plan", "text": "using user-provided Python verbatim"})
        else:
            steps.append({"kind": "plan",
                          "text": "no code template matches this task — honest miss"})
            return {"ok": False, "family": None, "code": "", "output": "",
                    "answer": "", "steps": steps}

    steps.append({"kind": "code", "text": f"{len(code)} chars generated", "code": code})

    # 2) run / inspect / repair loop
    result = None
    for attempt in range(MAX_REPAIRS + 1):
        result = run_python(code)
        if result["ok"] and "ANSWER:" in result["output"]:
            steps.append({"kind": "run",
                          "text": f"attempt {attempt + 1}: exit ok in {result['duration_ms']} ms"})
            break
        if result["ok"]:
            steps.append({"kind": "run",
                          "text": f"attempt {attempt + 1}: ran but no ANSWER line"})
        else:
            steps.append({"kind": "inspect",
                          "text": f"attempt {attempt + 1} failed: {result['error'][:140]}"})
        if attempt >= MAX_REPAIRS:
            break
        # repair strategy 1: ensure common imports; 2: wrap final value in print
        if attempt == 0 and not code.startswith("import"):
            code = "import math, statistics, datetime\n" + code
            steps.append({"kind": "repair", "text": "adding safe imports and retrying"})
        else:
            code = code.rstrip() + "\nprint('ANSWER:', locals().get('result', 'done'))\n"
            steps.append({"kind": "repair", "text": "forcing an ANSWER line and retrying"})
        steps.append({"kind": "code", "text": "repaired code", "code": code})

    ok = bool(result and result["ok"])
    output = result["output"] if result else ""
    error = result["error"] if result and not result["ok"] else ""
    answer = ""
    m = re.search(r"ANSWER:\s*(.+)", output)
    if m:
        answer = m.group(1).strip()

    if ok and answer:
        steps.append({"kind": "decide", "text": f"verified output → {answer[:120]}"})
    else:
        steps.append({"kind": "decide",
                      "text": f"could not verify output ({error[:100] or 'no answer line'})"})

    return {"ok": ok and bool(answer), "family": chosen, "code": code,
            "output": output, "answer": answer, "steps": steps,
            "duration_ms": result["duration_ms"] if result else 0}


# --------------------------------------------------- learned skills (codegen)
SKILL_TEMPLATE = '''"""Auto-written by MyGPT's coding agent after repeated `{family}` tasks."""

def register(api):
    @api.skill(
        {skill_name!r},
        "Learned coding skill: {family} (written by the coding agent).",
        pattern={pattern!r},
    )
    def {fn_name}(ctx, text=""):
        from mygpt.coding import solve
        r = solve(ctx.get("user") or text)
        if r and r["ok"]:
            return f"\\u2705 {{r['answer']}}  (learned skill: {family})"
        return "The learned skill could not solve that one."
'''


def maybe_learn_skill(family_name: str, skills_dir: Path, registry,
                      use_counts: dict) -> str | None:
    """After enough uses of a family, write a reusable skill file for it."""
    n = use_counts.get(family_name, 0)
    if n < SKILL_AFTER_USES:
        return None
    skill_name = f"code_{family_name}"
    if skill_name in registry.skills:
        return None
    fam = next((f for f in FAMILIES if f["name"] == family_name), None)
    if fam is None:
        return None
    pattern = fam["re"].pattern
    code = SKILL_TEMPLATE.format(family=family_name, skill_name=skill_name,
                                 pattern=pattern,
                                 fn_name=re.sub(r"[^a-z0-9_]", "_", skill_name))
    path = registry.write_skill(skill_name, f"learned coding skill: {family_name}",
                                code)
    return f"wrote coding skill {path.name} for family `{family_name}`"
