"""v1.10 maths pack — 65 extra calculation rules answerable in plain words.

Each rule is (name, compiled regex, handler). `solve(text)` returns the first
rule that fires and its formatted answer, or None. Pure functions only: no
state, no I/O — so tests can hit every rule directly.
"""

from __future__ import annotations

from functools import lru_cache

import math
import re
import statistics
from fractions import Fraction
from math import comb, factorial, gcd

RULES: list[tuple[str, "re.Pattern", object]] = []


def rule(name: str, pattern: str):
    def deco(fn):
        RULES.append((name, re.compile(pattern, re.I), fn))
        return fn
    return deco


def _nums(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _fmt(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.6g}"


@lru_cache(maxsize=512)
def solve(text: str) -> tuple[str, str] | None:
    low = " " + text.lower().strip() + " "
    for name, rx, fn in RULES:
        m = rx.search(low)
        if not m:
            continue
        try:
            out = fn(m, low)
        except Exception:
            out = None
        if out:
            return name, out
    return None


def names() -> list[str]:
    return [n for n, _, _ in RULES]


# ---------------------------------------------------------------- number theory
@rule("factorial", r"factorial of (\d{1,3})|(\d{1,3})!")
def _fact(m, _low):
    n = int(m.group(1) or m.group(2))
    return f"{n}! = {factorial(n):,}" if n <= 200 else None


@rule("fibonacci nth", r"(\d{1,4})(?:st|nd|rd|th)? fibonacci|fibonacci number (\d{1,4})|fib\((\d{1,4})\)")
def _fib(m, _low):
    n = int(next(g for g in m.groups() if g))
    if n > 5000:
        return None
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return f"fibonacci {n} = {a:,}"


@rule("is prime", r"is (\d{1,9}) (?:a )?prime")
def _isprime(m, _low):
    n = int(m.group(1))
    prime = n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))
    return f"{n} is {'prime' if prime else 'not prime'}"


@rule("nth prime", r"(\d{1,5})(?:st|nd|rd|th) prime")
def _nthprime(m, _low):
    want, found, cand = int(m.group(1)), [], 2
    while len(found) < want and cand < 200000:
        if all(cand % p for p in found):
            found.append(cand)
        cand += 1
    return f"prime #{want} = {found[-1]:,}" if found else None


@rule("gcd lcm", r"(?:gcd|hcf|lcm) of (\d+) and (\d+)")
def _gcdlcm(m, low):
    a, b = int(m.group(1)), int(m.group(2))
    what = "gcd" if ("gcd" in low[m.start():m.start() + 4] or "hcf" in low[m.start():m.start() + 4]) else "lcm"
    return f"{what}({a}, {b}) = {gcd(a, b) if what == 'gcd' else a * b // gcd(a, b)}"


@rule("prime factors", r"prime factors? of (\d+)")
def _factors(m, _low):
    n, out, d = int(m.group(1)), [], 2
    while d * d <= n:
        while n % d == 0:
            out.append(d)
            n //= d
        d += 1
    if n > 1:
        out.append(n)
    return f"prime factors of {m.group(1)} = {' × '.join(map(str, out))}"


@rule("divisors", r"divisors of (\d+)")
def _divisors(m, _low):
    n = int(m.group(1))
    out = [d for d in range(1, n + 1) if n % d == 0]
    return f"divisors of {n}: {out} ({len(out)} of them)"


@rule("digit sum", r"digit sum of (\d+)")
def _digitsum(m, _low):
    return f"digit sum of {m.group(1)} = {sum(int(d) for d in m.group(1))}"


@rule("digital root", r"digital root of (\d+)")
def _root(m, _low):
    n = int(m.group(1))
    return f"digital root of {n} = 1 + (n - 1) % 9"


@rule("perfect square check", r"is (\d+) a perfect square")
def _square(m, _low):
    n = int(m.group(1))
    r = math.isqrt(n)
    return f"{n} is {'a' if r * r == n else 'not a'} perfect square"


@rule("palindrome number", r"is (\d+) a palindrome number")
def _pal(m, _low):
    return f"{m.group(1)} {'is' if m.group(1) == m.group(1)[::-1] else 'is not'} a numeric palindrome"


@rule("leap year", r"is (\d{4}) a leap year")
def _leap(m, _low):
    y = int(m.group(1))
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    return f"{y} is {'a leap year' if leap else 'not a leap year'}"


@rule("divisible by", r"is (\d+) divisible by (\d+)")
def _div(m, _low):
    a, b = int(m.group(1)), int(m.group(2))
    return f"{a} is {'divisible' if b and a % b == 0 else 'not divisible'} by {b}"


@rule("even or odd", r"is (\d+) (?:an )?(?:even|odd)(?: or (?:even|odd))? number")
def _evenodd(m, _low):
    n = int(m.group(1))
    return f"{n} is {'even' if n % 2 == 0 else 'odd'}"


# ------------------------------------------------------------------ arithmetic
@rule("nth root", r"(?:cube|third) root of (-?\d+(?:\.\d+)?)")
def _cuberoot(m, _low):
    x = float(m.group(1))
    return None if x < 0 else f"cube root of {_fmt(x)} = {_fmt(x ** (1 / 3))}"


@rule("log base 10", r"log(?:10)? of (\d+(?:\.\d+)?)")
def _log10(m, _low):
    x = float(m.group(1))
    return f"log10({_fmt(x)}) = {_fmt(math.log10(x))}" if x > 0 else None


@rule("log2", r"log2 of (\d+(?:\.\d+)?)")
def _log2(m, _low):
    x = float(m.group(1))
    return f"log2({_fmt(x)}) = {_fmt(math.log2(x))}" if x > 0 else None


@rule("natural log", r"(?:natural log|ln) of (\d+(?:\.\d+)?)")
def _ln(m, _low):
    x = float(m.group(1))
    return f"ln({_fmt(x)}) = {_fmt(math.log(x))}" if x > 0 else None


@rule("trig degrees", r"(sin|cos|tan) of (-?\d+(?:\.\d+)?) ?(?:degrees|deg)?")
def _trig(m, low):
    if "degrees" not in low and "deg" not in low:
        return None
    fn = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[m.group(1)]
    return f"{m.group(1)}({m.group(2)}°) = {_fmt(round(fn(math.radians(float(m.group(2)))), 6))}"


@rule("absolute value", r"absolute value of (-?\d+(?:\.\d+)?)")
def _abs(m, _low):
    return f"|{m.group(1)}| = {_fmt(abs(float(m.group(1))))}"


@rule("floor ceil", r"(floor|ceiling|ceil) of (-?\d+(?:\.\d+)?)")
def _floorceil(m, _low):
    fn = math.floor if m.group(1) == "floor" else math.ceil
    return f"{m.group(1)}({m.group(2)}) = {fn(float(m.group(2)))}"


@rule("round to n", r"round (-?\d+(?:\.\d+)?) to (\d) decimals?")
def _round(m, _low):
    return f"round({m.group(1)}, {m.group(2)}) = {round(float(m.group(1)), int(m.group(2)))}"


@rule("remainder", r"remainder of (\d+) divided by (\d+)")
def _rem(m, _low):
    a, b = int(m.group(1)), int(m.group(2))
    return None if b == 0 else f"{a} mod {b} = {a % b}"


# -------------------------------------------------------------------- percents
@rule("percent of", r"(?:what(?:'s| is) )?(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s*of (-?\d+(?:\.\d+)?)")
def _pct_of(m, _low):
    p, whole = float(m.group(1)), float(m.group(2))
    return f"{_fmt(p)}% of {_fmt(whole)} = {_fmt(p / 100 * whole)}"


@rule("what percent of", r"(-?\d+(?:\.\d+)?) (?:is )?what (?:%|percent(?:age)?) of (-?\d+(?:\.\d+)?)")
def _what_pct(m, _low):
    part, whole = float(m.group(1)), float(m.group(2))
    if whole == 0:
        return "undefined — cannot divide by zero"
    return f"{_fmt(part)} is {_fmt(part / whole * 100)}% of {_fmt(whole)}"


@rule("percent off", r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s*off (?:of )?(-?\d+(?:\.\d+)?)")
def _pct_off(m, _low):
    off, price = float(m.group(1)), float(m.group(2))
    return (f"{_fmt(off)}% off {_fmt(price)} = {_fmt(price * (1 - off / 100))} "
            f"(you save {_fmt(price * off / 100)})")


@rule("percent increase", r"increase (-?\d+(?:\.\d+)?) by (\d+(?:\.\d+)?)%")
def _inc(m, _low):
    x, p = float(m.group(1)), float(m.group(2))
    return f"increase {_fmt(x)} by {_fmt(p)}% = {_fmt(x * (1 + p / 100))}"


@rule("percent decrease", r"decrease (-?\d+(?:\.\d+)?) by (\d+(?:\.\d+)?)%")
def _dec(m, _low):
    x, p = float(m.group(1)), float(m.group(2))
    return f"decrease {_fmt(x)} by {_fmt(p)}% = {_fmt(x * (1 - p / 100))}"


@rule("tip", r"tip on (\d+(?:\.\d+)?) (?:dollars|rupees|bucks)? ?at (\d+(?:\.\d+)?)%")
def _tip(m, _low):
    bill, pct = float(m.group(1)), float(m.group(2))
    tip = bill * pct / 100
    return f"{_fmt(pct)}% tip on {_fmt(bill)} = {_fmt(tip)} (total {_fmt(bill + tip)})"


@rule("simple interest", r"simple interest on (\d+(?:\.\d+)?) at (\d+(?:\.\d+)?)% for (\d+(?:\.\d+)?) years?")
def _si(m, _low):
    p, r, t = float(m.group(1)), float(m.group(2)), float(m.group(3))
    i = p * r * t / 100
    return f"simple interest = {_fmt(i)} (total {_fmt(p + i)})"


@rule("compound interest", r"compound interest on (\d+(?:\.\d+)?) at (\d+(?:\.\d+)?)% for (\d+(?:\.\d+)?) years?")
def _ci(m, _low):
    p, r, t = float(m.group(1)), float(m.group(2)), float(m.group(3))
    total = p * (1 + r / 100) ** t
    return f"compound interest = {_fmt(total - p)} (total {_fmt(total)})"


@rule("grade letter", r"grade for (\d+(?:\.\d+)?) ?(?:percent|%)")
def _grade(m, _low):
    p = float(m.group(1))
    letter = ("A+" if p >= 95 else "A" if p >= 90 else "B" if p >= 80 else
              "C" if p >= 70 else "D" if p >= 60 else "F")
    return f"{_fmt(p)}% = grade {letter}"


# -------------------------------------------------------------------- geometry
@rule("circle area", r"area of a circle (?:with )?radius (\d+(?:\.\d+)?)")
def _circle(m, _low):
    r = float(m.group(1))
    return f"area = {_fmt(round(math.pi * r * r, 6))} (circumference {_fmt(round(2 * math.pi * r, 6))})"


@rule("rectangle area", r"area of a rectangle (\d+(?:\.\d+)?) by (\d+(?:\.\d+)?)")
def _rect(m, _low):
    w, h = float(m.group(1)), float(m.group(2))
    return f"area = {_fmt(w * h)}, perimeter = {_fmt(2 * (w + h))}"


@rule("triangle area", r"area of a triangle (?:with )?base (\d+(?:\.\d+)?) (?:and )?height (\d+(?:\.\d+)?)")
def _tri(m, _low):
    b, h = float(m.group(1)), float(m.group(2))
    return f"area = {_fmt(b * h / 2)}"


@rule("sphere volume", r"volume of a sphere (?:with )?radius (\d+(?:\.\d+)?)")
def _sphere(m, _low):
    r = float(m.group(1))
    return f"volume = {_fmt(round(4 / 3 * math.pi * r ** 3, 6))}"


@rule("cylinder volume", r"volume of a cylinder (?:with )?radius (\d+(?:\.\d+)?) (?:and )?height (\d+(?:\.\d+)?)")
def _cyl(m, _low):
    r, h = float(m.group(1)), float(m.group(2))
    return f"volume = {_fmt(round(math.pi * r * r * h, 6))}"


@rule("pythagoras", r"hypotenuse of (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)")
def _hyp(m, _low):
    a, b = float(m.group(1)), float(m.group(2))
    return f"hypotenuse = {_fmt(round(math.hypot(a, b), 6))}"


@rule("distance midpoint", r"(distance|midpoint)(?: of| between)? \((-?[\d.]+), ?(-?[\d.]+)\) and \((-?[\d.]+), ?(-?[\d.]+)\)")
def _dist(m, _low):
    x1, y1, x2, y2 = (float(m.group(i)) for i in (2, 3, 4, 5))
    if m.group(1) == "distance":
        return f"distance = {_fmt(round(math.hypot(x2 - x1, y2 - y1), 6))}"
    return f"midpoint = ({(x1 + x2) / 2:g}, {(y1 + y2) / 2:g})"


@rule("slope", r"slope (?:between )?\((-?[\d.]+), ?(-?[\d.]+)\) and \((-?[\d.]+), ?(-?[\d.]+)\)")
def _slope(m, _low):
    x1, y1, x2, y2 = (float(m.group(i)) for i in (1, 2, 3, 4))
    return None if x1 == x2 else f"slope = {_fmt(round((y2 - y1) / (x2 - x1), 6))}"


# ------------------------------------------------------------------ word maths
@rule("speed", r"speed (?:if|when|for) distance (\d+(?:\.\d+)?) ?km in (\d+(?:\.\d+)?) ?hours?")
def _speed(m, _low):
    d, t = float(m.group(1)), float(m.group(2))
    return None if t == 0 else f"speed = {_fmt(d / t)} km/h"


@rule("time", r"time (?:for|to cover) (\d+(?:\.\d+)?) ?km at (\d+(?:\.\d+)?) ?km/h")
def _time(m, _low):
    d, s = float(m.group(1)), float(m.group(2))
    return None if s == 0 else f"time = {_fmt(d / s)} hours ({_fmt(d / s * 60)} minutes)"


@rule("bmi", r"bmi (?:for|of) (\d+(?:\.\d+)?) ?kg and (\d+(?:\.\d+)?) ?m")
def _bmi(m, _low):
    w, h = float(m.group(1)), float(m.group(2))
    bmi = w / (h * h)
    band = ("underweight" if bmi < 18.5 else "normal" if bmi < 25 else
            "overweight" if bmi < 30 else "obese")
    return f"BMI = {_fmt(round(bmi, 1))} ({band})"


@rule("sum of range", r"sum of (?:all )?(?:the )?(?:numbers|integers) (?:from )?1 to (\d+)")
def _sumrange(m, _low):
    n = int(m.group(1))
    return f"1 + 2 + ... + {n} = {n * (n + 1) // 2:,}"


@rule("sum of squares", r"sum of squares (?:of )?(?:from )?1 to (\d+)")
def _sumsq(m, _low):
    n = int(m.group(1))
    return f"1² + 2² + ... + {n}² = {n * (n + 1) * (2 * n + 1) // 6:,}"


@rule("triangular number", r"triangular number (\d+)")
def _tri_n(m, _low):
    n = int(m.group(1))
    return f"triangular number {n} = {n * (n + 1) // 2:,}"


# ------------------------------------------------------------------ statistics
@rule("median", r"median of ([\d.,\s]+)")
def _median(m, _low):
    xs = _nums(m.group(1))
    return f"median of {len(xs)} values = {_fmt(statistics.median(xs))}"


@rule("mode", r"mode of ([\d.,\s]+)")
def _mode(m, _low):
    xs = _nums(m.group(1))
    return f"mode = {_fmt(statistics.mode(xs))}"


@rule("range", r"range of ([\d.,\s]+)")
def _range(m, _low):
    xs = _nums(m.group(1))
    return f"range = {_fmt(max(xs) - min(xs))} (min {_fmt(min(xs))}, max {_fmt(max(xs))})"


@rule("variance", r"variance of ([\d.,\s]+)")
def _var(m, _low):
    xs = _nums(m.group(1))
    return f"variance = {_fmt(round(statistics.pvariance(xs), 6))}"


@rule("stddev", r"standard deviation of ([\d.,\s]+)")
def _sd(m, _low):
    xs = _nums(m.group(1))
    return f"standard deviation = {_fmt(round(statistics.pstdev(xs), 6))}"


@rule("geometric mean", r"geometric mean of ([\d.,\s]+)")
def _gmean(m, _low):
    xs = _nums(m.group(1))
    return f"geometric mean = {_fmt(round(statistics.geometric_mean(xs), 6))}"


@rule("harmonic mean", r"harmonic mean of ([\d.,\s]+)")
def _hmean(m, _low):
    xs = _nums(m.group(1))
    return f"harmonic mean = {_fmt(round(statistics.harmonic_mean(xs), 6))}"


# ------------------------------------------------------------------- fractions
@rule("decimal to fraction", r"(-?\d*\.\d+) as a fraction")
def _tofrac(m, _low):
    f = Fraction(m.group(1)).limit_denominator(10_000)
    return f"{m.group(1)} = {f.numerator}/{f.denominator}"


@rule("fraction to decimal", r"(\d+)/(\d+) as a decimal")
def _todec(m, _low):
    a, b = int(m.group(1)), int(m.group(2))
    return None if b == 0 else f"{a}/{b} = {_fmt(round(a / b, 6))}"


@rule("simplify fraction", r"simplify (\d+)/(\d+)")
def _simplify(m, _low):
    f = Fraction(int(m.group(1)), int(m.group(2)))
    return f"{m.group(1)}/{m.group(2)} simplifies to {f.numerator}/{f.denominator}"


@rule("add fractions", r"(\d+)/(\d+) plus (\d+)/(\d+)")
def _addfrac(m, _low):
    f = Fraction(int(m.group(1)), int(m.group(2))) + Fraction(int(m.group(3)), int(m.group(4)))
    return f"sum = {f.numerator}/{f.denominator}" + (f" = {_fmt(float(f))}" if f.denominator != 1 else "")


@rule("multiply fractions", r"(\d+)/(\d+) times (\d+)/(\d+)")
def _mulfrac(m, _low):
    f = Fraction(int(m.group(1)), int(m.group(2))) * Fraction(int(m.group(3)), int(m.group(4)))
    return f"product = {f.numerator}/{f.denominator}" + (f" = {_fmt(float(f))}" if f.denominator != 1 else "")


@rule("ratio simplify", r"(?:simplify|reduce) ratio (\d+):(\d+)")
def _ratio(m, _low):
    a, b = int(m.group(1)), int(m.group(2))
    g = gcd(a, b) or 1
    return f"{a}:{b} simplifies to {a // g}:{b // g}"


# ------------------------------------------------------------------- probability
@rule("independent probability", r"probability of (?:two )?independent events (\d*\.?\d+) and (\d*\.?\d+)")
def _prob(m, _low):
    a, b = float(m.group(1)), float(m.group(2))
    return f"P(both) = {round(a * b, 6)} ({round(a * b * 100, 4)}%)"


@rule("coin run", r"probability of (\d+) heads in a row")
def _coin(m, _low):
    n = int(m.group(1))
    p = 0.5 ** n
    return f"P({n} heads in a row) = {p:.6g} ({p * 100:.4f}%)"


@rule("dice double", r"probability of rolling a (\d+) twice")
def _dice(m, _low):
    s = int(m.group(1))
    p = 1 / (s * s)
    return f"P(same face twice on a d{s}) = 1/{s * s} = {p * 100:.2f}%"


# ---------------------------------------------------------------------- colours
@rule("hex to rgb", r"#([0-9a-f]{6}) to rgb")
def _hextorgb(m, _low):
    h = m.group(1)
    return f"#{h} = rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


@rule("rgb to hex", r"rgb\s*\(?\s*(\d{1,3})[,\s]+(\d{1,3})[,\s]+(\d{1,3})\)?\s*(?:to|as|in) hex")
def _rgbtohex(m, _low):
    r, g, b = (max(0, min(255, int(m.group(i)))) for i in (1, 2, 3))
    return f"rgb({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}"


@rule("quadratic roots", r"roots of x\^2 ([+-]) (\d+)x ([+-]) (\d+)")
def _quad(m, _low):
    b = int(m.group(2)) * (1 if m.group(1) == '+' else -1)
    c = int(m.group(4)) * (1 if m.group(3) == '+' else -1)
    disc = b * b - 4 * c
    if disc < 0:
        return None
    r1, r2 = (-b + math.sqrt(disc)) / 2, (-b - math.sqrt(disc)) / 2
    return f"roots = {_fmt(round(r1, 6))} and {_fmt(round(r2, 6))}"
