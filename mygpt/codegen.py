"""Code replies: when the user asks for code, answer with a code block in chat.

No agents, no sandbox, nothing written to files — MyGPT composes a snippet
from its built-in template library and hands it over in a fenced code block,
then points the user to codero-sus on GitHub for more.
"""

from __future__ import annotations

import re

GITHUB_URL = "https://github.com/codero-sus"
GITHUB_PROMPT = (f"👉 For more code and full projects, visit codero-sus on "
                 f"GitHub: {GITHUB_URL}")

CODE_ASK = re.compile(
    r"\b(write|show|give|generate|make|need|want|code)\b.{0,40}"
    r"\b(code|program|script|function|snippet)\b"
    r"|\bcode (?:for|to)\b|\bpython code\b|\bin python\b",
    re.I,
)

FAMILIES: list[dict] = []


def family(name: str, pattern: str):
    def deco(fn):
        FAMILIES.append({"name": name, "re": re.compile(pattern, re.I),
                         "compose": fn})
        return fn
    return deco


@family("primes (first N)", r"first (\d+) primes?|primes?\b(?: numbers?)?(?! ?(?:up to|below|under|until))")
def _primes_first(m, goal):
    n = int(m.group(1)) if m.group(1) else 10
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
        "print(primes)\n"
    )


@family("primes up to N", r"primes? (?:up to|below|under|until) (\d+)")
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
        "print([i for i, p in enumerate(sieve) if p])\n"
    )


@family("fibonacci", r"(?:first (\d+) fibonacci|fibonacci(?: number)?(?: of)?[ :]? ?(\d+)|fib\((\d+)\)|fibonacci)")
def _fibonacci(m, goal):
    n = int(next((g for g in m.groups() if g), "10"))
    if re.search(r"first", goal, re.I):
        return (
            f"n = {n}\n"
            "a, b, out = 0, 1, []\n"
            "for _ in range(n):\n"
            "    out.append(a)\n"
            "    a, b = b, a + b\n"
            "print(out)\n"
        )
    return (
        f"n = {n}\n"
        "a, b = 0, 1\n"
        "for _ in range(n):\n"
        "    a, b = b, a + b\n"
        "print(a)\n"
    )


@family("factorial", r"factorial(?: of)? (\d+)|(\d+)!|factorial")
def _factorial(m, goal):
    n = int(next((g for g in m.groups() if g), "5"))
    return (
        f"n = {n}\n"
        "r = 1\n"
        "for i in range(2, n + 1):\n"
        "    r *= i\n"
        "print(r)\n"
    )


@family("sum of digits", r"sum of (?:the )?digits (?:of )?(\d+)")
def _digits_sum(m, goal):
    return f"print(sum(int(c) for c in str({m.group(1)})))\n"


@family("reverse a number", r"reverse (?:the )?(?:number|digits? of) (\d+)")
def _digits_reverse(m, goal):
    return f"print(int(str({m.group(1)})[::-1]))\n"


@family("reverse a string", r"reverse (?:a |the )?(?:string|word|text)(?: ['“\"]?([A-Za-z0-9 _\-]+)['”\"]?)?")
def _str_reverse(m, goal):
    s = (m.group(1) or "hello").strip() or "hello"
    return f"s = {s!r}\nprint(s[::-1])\n"


@family("palindrome check (number)", r"is (\d+) a palindrome|check (?:if |whether )?(?:the )?(?:number )?(\d+)(?: is)?(?: a)? palindrome")
def _palindrome_num(m, goal):
    n = m.group(1) or m.group(2) or "121"
    return f"s = str({n})\nprint(s == s[::-1])\n"


@family("palindrome check (word)", r"is ([a-z]+) a palindrome|palindrome (?:of|check) ([a-z]+)|palindrome")
def _palindrome_word(m, goal):
    w = (m.group(1) or m.group(2) or "level").lower()
    return f"s = {w!r}.lower()\nprint(s == s[::-1])\n"


@family("anagram check", r"are ([a-z]+) and ([a-z]+) anagrams|anagram (?:of|check) ([a-z]+) and ([a-z]+)")
def _anagram(m, goal):
    a = m.group(1) or m.group(3)
    b = m.group(2) or m.group(4)
    return f"a, b = {a.lower()!r}, {b.lower()!r}\nprint(sorted(a) == sorted(b))\n"


@family("statistics (mean/median/…)", r"\b(mean|average|median|mode|std|standard deviation|variance|sum|min|max)\b of ([\d\s,.\-]+)")
def _statistics(m, goal):
    op = m.group(1).lower()
    data = ", ".join(re.findall(r"-?\d+(?:\.\d+)?", m.group(2)))
    fn = {"mean": "mean", "average": "mean", "median": "median", "mode": "mode",
          "std": "stdev", "standard deviation": "stdev",
          "variance": "variance", "sum": None, "min": None, "max": None}[op]
    if fn:
        return (
            "import statistics\n"
            f"data = [{data}]\n"
            f"print(round(statistics.{fn}(data), 6))\n"
        )
    return f"data = [{data}]\nprint({op}(data))\n"


@family("gcd", r"(?:gcd|greatest common divisor)(?: of)? (\d+) and (\d+)|(?:gcd|greatest common divisor)\b")
def _gcd(m, goal):
    a = m.group(1) or "48"
    b = m.group(2) or "36"
    code = f"import math\nprint(math.gcd({a}, {b}))\n"
    if re.search(r"\blcm\b", goal, re.I):
        code += f"print(math.lcm({a}, {b}))\n"
    return code


@family("lcm", r"(?:lcm|least common multiple)(?: of)? (\d+) and (\d+)|(?:lcm|least common multiple)\b")
def _lcm(m, goal):
    a = m.group(1) or "4"
    b = m.group(2) or "6"
    return f"import math\nprint(math.lcm({a}, {b}))\n"


@family("base conversion (to binary/hex/octal)",
        r"(\d+) (?:in|to|into) (binary|hex|hexadecimal|octal)|convert (\d+) to (binary|hex|hexadecimal|octal)")
def _base_to(m, goal):
    num = m.group(1) or m.group(3)
    base_name = (m.group(2) or m.group(4)).lower()
    base = {"binary": "bin", "hex": "hex", "hexadecimal": "hex",
            "octal": "oct"}[base_name]
    return f"print({base}({num}))\n"


_BASE_WORDS = {"binary": 2, "octal": 8, "decimal": 10, "hex": 16,
               "hexadecimal": 16}


def _base_val(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        v = int(s)
        return v if 2 <= v <= 36 else None
    return _BASE_WORDS.get(s)


@family("base conversion (any base)",
        r"convert(?:ing)? (\w+) from (?:base )?(\w+) to (?:base )?(\w+)")
def _base_convert(m, goal):
    src, dst = _base_val(m.group(2)), _base_val(m.group(3))
    if src is None or dst is None:
        raise ValueError("unknown base name")
    return (
        f"value = int({m.group(1)!r}, {src})\n"
        "digits = '0123456789abcdefghijklmnopqrstuvwxyz'\n"
        f"b = {dst}\n"
        "out = ''\n"
        "n = value\n"
        "while n:\n"
        "    out = digits[n % b] + out\n"
        "    n //= b\n"
        "print(out or '0')\n"
    )


@family("days between dates", r"days between (\d{4}-\d{2}-\d{2}) and (\d{4}-\d{2}-\d{2})")
def _date_diff(m, goal):
    return (
        "import datetime\n"
        f"a = datetime.date.fromisoformat({m.group(1)!r})\n"
        f"b = datetime.date.fromisoformat({m.group(2)!r})\n"
        "print(abs((b - a).days))\n"
    )


@family("weekday of a date", r"(?:what )?day(?: of the week)? (?:is|was|for) (\d{4}-\d{2}-\d{2})")
def _weekday(m, goal):
    return (
        "import datetime\n"
        f"d = datetime.date.fromisoformat({m.group(1)!r})\n"
        "print(d.strftime('%A'))\n"
    )


@family("circle area/circumference", r"(area|circumference) of (?:a )?circle(?: (?:with )?r(?:adius)? (\d+(?:\.\d+)?))?")
def _circle(m, goal):
    expr = "math.pi * r ** 2" if m.group(1).lower() == "area" else "2 * math.pi * r"
    return f"import math\nr = {m.group(2) or 5}\nprint(round({expr}, 6))\n"


@family("sphere volume", r"volume of (?:a )?sphere (?:with )?r(?:adius)? (\d+(?:\.\d+)?)")
def _sphere(m, goal):
    return (f"import math\nr = {m.group(1)}\n"
            "print(round(4 / 3 * math.pi * r ** 3, 6))\n")


@family("triangle area", r"area of (?:a )?triangle (?:with )?base (\d+(?:\.\d+)?) (?:and )?height (\d+(?:\.\d+)?)")
def _triangle(m, goal):
    return f"print({m.group(1)} * {m.group(2)} / 2)\n"


@family("armstrong number", r"is (\d+) (?:an )?armstrong|armstrong (?:of|check) (\d+)|armstrong")
def _armstrong(m, goal):
    n = m.group(1) or m.group(2) or "153"
    return (
        f"n = {n}\n"
        "s = str(n)\n"
        "print(sum(int(c) ** len(s) for c in s) == n)\n"
    )


@family("powers of two", r"powers of (?:2|two) (?:up to|below|under) (\d+)|powers of (?:2|two)")
def _powers_of_two(m, goal):
    return (
        f"n = {m.group(1) or 64}\n"
        "out, p = [], 1\n"
        "while p < n:\n"
        "    out.append(p)\n"
        "    p *= 2\n"
        "print(out)\n"
    )


@family("unit conversion", r"(-?\d+(?:\.\d+)?)\s*(km|mi|kg|lb|c|f)\b (?:to|in) (km|mi|kg|lb|c|f)\b")
def _unit_convert(m, goal):
    v, a, b = float(m.group(1)), m.group(2).lower(), m.group(3).lower()
    table = {
        ("km", "mi"): f"{v} * 0.621371", ("mi", "km"): f"{v} / 0.621371",
        ("kg", "lb"): f"{v} * 2.20462", ("lb", "kg"): f"{v} / 2.20462",
        ("c", "f"): f"{v} * 9 / 5 + 32", ("f", "c"): f"({v} - 32) * 5 / 9",
    }
    if (a, b) not in table:
        raise ValueError(f"no conversion {a}->{b}")
    return f"print(round({table[(a, b)]}, 4))\n"


@family("word/char/vowel counts", r"(?:count|how many) (words|characters|letters|vowels) in ['“\"](.+?)['”\"]")
def _word_stats(m, goal):
    kind, text = m.group(1).lower(), m.group(2)
    expr = {"words": f"len({text!r}.split())",
            "characters": f"len({text!r})",
            "letters": f"sum(c.isalpha() for c in {text!r})",
            "vowels": f"sum(c.lower() in 'aeiou' for c in {text!r})"}[kind]
    return f"print({expr})\n"


@family("sum of a range", r"sum of (?:all )?numbers from (\d+) to (\d+)")
def _range_sum(m, goal):
    return f"print(sum(range({m.group(1)}, {m.group(2)} + 1)))\n"


@family("perfect square check", r"is (\d+) (?:a )?perfect square|perfect square")
def _perfect_square(m, goal):
    return (f"import math\nn = {m.group(1) or 25}\nr = math.isqrt(n)\n"
            "print(r * r == n)\n")


TEMPLATE_HINT = ("primes, fibonacci, factorials, digit sums, palindromes, "
                 "anagrams, statistics (mean/median/std), gcd/lcm, base "
                 "conversion, dates & weekdays, circle/sphere/triangle geometry, "
                 "armstrong numbers, powers of two, unit conversion and word counts")


def wants_code(text: str) -> bool:
    return bool(CODE_ASK.search(text))


def code_reply(text: str) -> tuple[str, bool]:
    """Return (chat reply with fenced code block, found_template?)."""
    for fam in FAMILIES:
        m = fam["re"].search(text)
        if not m:
            continue
        try:
            code = fam["compose"](m, text)
        except Exception:
            continue
        reply = (f"Here's Python for that ({fam['name']}) — paste it into any "
                 f"Python interpreter:\n\n```python\n{code.rstrip()}\n```\n\n"
                 f"I only show code in chat; I never run it or write files. "
                 f"You can also teach me knowledge in the Learn panel.\n\n"
                 f"{GITHUB_PROMPT}")
        return reply, True
    reply = ("I can compose snippets from my built-in templates — "
             f"{TEMPLATE_HINT}.\n\nI don't have a template for that one yet, "
             "and I only ever output code in chat (never to files). "
             f"Teach me related knowledge in the Learn panel, or:\n\n{GITHUB_PROMPT}")
    return reply, False
