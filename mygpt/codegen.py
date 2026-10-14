"""Code replies: when the user asks for code, answer with a code block in chat.

No agents, no sandbox, nothing written to files — MyGPT composes a snippet
from its built-in template library and hands it over in a fenced code block,
then points the user to codero-sus on GitHub for more.
"""

from __future__ import annotations

import re

AUTHOR = "codero-sus"
GITHUB_URL = "https://github.com/codero-sus"
WEBSITE_URL = "https://the-codero.web.app/"
GITHUB_PROMPT = (f"👉 For more code and full projects, visit {AUTHOR} on "
                 f"GitHub: {GITHUB_URL} · Website: {WEBSITE_URL}")

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


@family("bubble sort", r"bubble ?sort|sort(?:ing)? (?:a )?(?:list|array)(?: of)?(?: numbers)?\b(?!.{0,20}(?:file|csv))")
def _bubble_sort(m, goal):
    return (
        "nums = [5, 2, 9, 1, 7]\n"
        "n = len(nums)\n"
        "for i in range(n):\n"
        "    for j in range(n - 1 - i):\n"
        "        if nums[j] > nums[j + 1]:\n"
        "            nums[j], nums[j + 1] = nums[j + 1], nums[j]\n"
        "print(nums)\n"
    )


@family("binary search", r"binary ?search")
def _binary_search(m, goal):
    return (
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        if arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1\n\n"
        "print(binary_search([1, 3, 5, 7, 9], 7))\n"
    )


@family("fizzbuzz", r"fizz ?buzz")
def _fizzbuzz(m, goal):
    return (
        "for i in range(1, 101):\n"
        "    print('Fizz' * (i % 3 == 0) + 'Buzz' * (i % 5 == 0) or i)\n"
    )


@family("prime check (single number)", r"(?:check )?(?:is|whether) (\d+) (?:a )?prime|prime check")
def _is_prime(m, goal):
    return (
        f"n = {m.group(1) or 29}\n"
        "if n < 2:\n"
        "    print(False)\n"
        "else:\n"
        "    print(all(n % i for i in range(2, int(n ** 0.5) + 1)))\n"
    )


@family("even or odd", r"even or odd|odd or even|(?:check )?(?:is|whether) (\d+) even")
def _even_odd(m, goal):
    return f"n = {m.group(1) or 7}\nprint('even' if n % 2 == 0 else 'odd')\n"


@family("read a file", r"read (?:a |the )?(?:text )?file|open (?:a )?file for reading")
def _file_read(m, goal):
    return (
        "path = 'notes.txt'\n"
        "with open(path, encoding='utf-8') as f:\n"
        "    for i, line in enumerate(f, 1):\n"
        "        print(i, line.rstrip())\n"
    )


@family("write a file", r"write (?:to )?(?:a |the )?(?:text )?file|append to (?:a )?file")
def _file_write(m, goal):
    mode = "a" if "append" in goal.lower() else "w"
    return (
        "path = 'notes.txt'\n"
        f"with open(path, '{mode}', encoding='utf-8') as f:\n"
        "    f.write('hello from MyGPT\\n')\n"
        "print('written:', path)\n"
    )


@family("word frequency (dict)", r"word (?:frequency|counts?)|count (?:the )?word(?: occurrence)?s?|most common words")
def _word_freq(m, goal):
    return (
        "from collections import Counter\n"
        "text = 'the quick brown fox jumps over the lazy dog the end'\n"
        "print(Counter(text.lower().split()).most_common(5))\n"
    )


@family("remove duplicates", r"remove duplicates|unique (?:values|elements|items)")
def _dedupe(m, goal):
    return (
        "items = [3, 1, 3, 2, 1, 5]\n"
        "print(list(dict.fromkeys(items)))   # keeps order\n"
    )


@family("class template", r"(?:a )?class (?:template|example|in python)|write (?:a )?class\b|code for (?:a )?class|__init__")
def _class_template(m, goal):
    return (
        "class Greeter:\n"
        "    def __init__(self, name: str) -> None:\n"
        "        self.name = name\n\n"
        "    def greet(self) -> str:\n"
        "        return f'Hello, {self.name}!'\n\n"
        "print(Greeter('world').greet())\n"
    )


@family("http GET request", r"http (?:get )?request|fetch (?:a )?(?:url|page|api)|download (?:a )?(?:url|page)")
def _http_get(m, goal):
    return (
        "import urllib.request\n"
        "url = 'https://api.github.com/users/codero-sus'\n"
        "req = urllib.request.Request(url, headers={'User-Agent': 'mygpt-demo'})\n"
        "with urllib.request.urlopen(req, timeout=10) as resp:\n"
        "    print(resp.status, resp.read()[:200])\n"
    )


@family("regex match", r"regex|regular expression")
def _regex_demo(m, goal):
    return (
        "import re\n"
        "text = 'Order #4521 shipped on 2026-03-14'\n"
        "print(re.search(r'#(\\d+)', text).group(1))\n"
        "print(re.findall(r'\\d{4}-\\d{2}-\\d{2}', text))\n"
    )


@family("read CSV", r"(?:read|parse|open) (?:a )?csv|csv file")
def _csv_read(m, goal):
    return (
        "import csv\n"
        "with open('data.csv', newline='', encoding='utf-8') as f:\n"
        "    for row in csv.DictReader(f):\n"
        "        print(row)\n"
    )


@family("json roundtrip", r"(?:read|write|parse|dump|load) json|json (?:file|roundtrip|code|example)")
def _json_demo(m, goal):
    return (
        "import json\n"
        "data = {'name': 'MyGPT', 'learns': True}\n"
        "text = json.dumps(data, indent=2)\n"
        "print(json.loads(text) == data)\n"
    )


@family("timer / context manager", r"timer|time (?:a )?(?:function|block|code)|measure (?:execution )?time|context manager")
def _timer_cm(m, goal):
    return (
        "import time\n"
        "from contextlib import contextmanager\n\n"
        "@contextmanager\n"
        "def timer(label='block'):\n"
        "    t0 = time.perf_counter()\n"
        "    yield\n"
        "    print(f'{label}: {time.perf_counter() - t0:.4f}s')\n\n"
        "with timer('demo'):\n"
        "    sum(range(1_000_000))\n"
    )


@family("random choice / dice", r"random (?:choice|pick|number|item)|roll (?:a )?(?:dice|die)|shuffle")
def _random_pick(m, goal):
    if re.search(r"dice|die", goal, re.I):
        return "import random\nprint(random.randint(1, 6))\n"
    if re.search(r"shuffle", goal, re.I):
        return ("import random\nitems = [1, 2, 3, 4, 5]\n"
                "random.shuffle(items)\nprint(items)\n")
    return ("import random\nitems = ['red', 'green', 'blue']\n"
            "print(random.choice(items))\n")


@family("multiplication table", r"multiplication table(?: of)?(?: (\d+))?|times table(?: of)?(?: (\d+))?")
def _mult_table(m, goal):
    n = m.group(1) or m.group(2) or "7"
    return (
        f"n = {n}\n"
        "for i in range(1, 11):\n"
        "    print(f'{n} x {i} = {n * i}')\n"
    )


@family("caesar cipher", r"caesar ?cipher|rot13|encrypt (?:a )?(?:string|message|text)")
def _caesar(m, goal):
    shift = 13 if re.search(r"rot ?13", goal, re.I) else 3
    return (
        f"shift = {shift}\n"
        "text = 'hello mygpt'\n"
        "out = ''.join(chr((ord(c) - 97 + shift) % 26 + 97) if c.isalpha() else c\n"
        "            for c in text.lower())\n"
        "print(out)\n"
    )


@family("password generator", r"(?:generate |random )?password(?: generator)?|strong password")
def _password_gen(m, goal):
    return (
        "import secrets, string\n"
        "alphabet = string.ascii_letters + string.digits + string.punctuation\n"
        "print(''.join(secrets.choice(alphabet) for _ in range(16)))\n"
    )


@family("countdown", r"countdown(?: (?:from|of) (\d+))?|count down")
def _countdown(m, goal):
    return (
        "import time\n"
        f"for i in range({m.group(1) or 5}, 0, -1):\n"
        "    print(i, flush=True)\n"
        "    time.sleep(1)\n"
        "print('liftoff!')\n"
    )


@family("matrix transpose", r"transpose (?:a )?(?:matrix|list of lists)|matrix transpose")
def _transpose(m, goal):
    return (
        "matrix = [[1, 2, 3], [4, 5, 6]]\n"
        "print([list(row) for row in zip(*matrix)])\n"
    )


@family("leap year check", r"leap year")
def _leap_year(m, goal):
    return (
        "year = 2026\n"
        "print(year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))\n"
    )


@family("digit count", r"(?:count|how many) digits(?: in| of)? (\d+)|digit count")
def _digit_count(m, goal):
    return f"print(len(str({m.group(1) or 123456})))\n"


@family("flatten a nested list", r"flatten (?:a )?(?:nested )?list|nested list")
def _flatten(m, goal):
    return (
        "nested = [[1, 2], [3, [4, 5]], [6]]\n"
        "def flatten(xs):\n"
        "    for x in xs:\n"
        "        if isinstance(x, list):\n"
        "            yield from flatten(x)\n"
        "        else:\n"
        "            yield x\n"
        "print(list(flatten(nested)))\n"
    )


@family("merge dictionaries", r"merge (?:two )?dict(?:ionaries)?|combine dicts")
def _dict_merge(m, goal):
    return (
        "a = {'x': 1, 'y': 2}\n"
        "b = {'y': 20, 'z': 30}\n"
        "print(a | b)          # Python 3.9+\n"
        "print({**a, **b})     # works everywhere\n"
    )


@family("zip two lists", r"zip (?:two )?lists|pair (?:up )?(?:two )?lists")
def _zip_lists(m, goal):
    return (
        "names = ['ada', 'grace', 'alan']\n"
        "scores = [95, 88, 91]\n"
        "print(dict(zip(names, scores)))\n"
    )


@family("f-string formatting", r"f-?string|format (?:a )?string|string formatting")
def _fstring(m, goal):
    return (
        "name, score = 'MyGPT', 0.9876\n"
        "print(f'{name} scored {score:.2%} on {2026:>4}')\n"
        "print(f'{name:=^20}')   # centred, padded\n"
    )


@family("set operations", r"set (?:operations|union|intersection|difference)|union|intersection")
def _set_ops(m, goal):
    return (
        "a = {1, 2, 3, 4}\n"
        "b = {3, 4, 5, 6}\n"
        "print('union       ', a | b)\n"
        "print('intersect  ', a & b)\n"
        "print('difference ', a - b)\n"
        "print('symmetric  ', a ^ b)\n"
    )


TEMPLATE_HINT = ("primes, fibonacci, factorials, digit sums, palindromes, "
                 "anagrams, statistics (mean/median/std), gcd/lcm, base "
                 "conversion, dates & weekdays, circle/sphere/triangle geometry, "
                 "armstrong numbers, powers of two, unit conversion, word counts, "
                 "sorting, binary search, fizzbuzz, file/CSV/JSON I/O, classes, "
                 "HTTP requests, regex, timers, randomness, caesar cipher, "
                 "passwords, countdowns, matrices, leap years, flattening, "
                 "dict merging, zipping, f-strings and set operations")


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
