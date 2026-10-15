"""v1.10 text pack — 45 text transformations you can ask for in chat.

Triggers are anchored at the start of the message so knowledge questions are
never hijacked ("what is an acronym" is knowledge; "acronym: World Health
Organization" is a command). Pure functions, no I/O.
"""

from __future__ import annotations

from functools import lru_cache

import base64
import hashlib
import json
import re
import zlib
from urllib.parse import quote

RULES: list[tuple[str, "re.Pattern", object]] = []


def rule(name: str, pattern: str):
    def deco(fn):
        RULES.append((name, re.compile(pattern, re.I), fn))
        return fn
    return deco


def _operand(m, low: str) -> str:
    """Text the command should act on: after a colon, in quotes, else tail."""
    tail = low[m.end():].strip()
    if not tail:
        return ""
    if tail[0] in ":\u2013-":
        return tail[1:].strip()
    quoted = re.match(r"""['"](.+?)['"]""", tail)
    if quoted:
        return quoted.group(1)
    return tail


@lru_cache(maxsize=512)
def solve(text: str) -> tuple[str, str] | None:
    low = text.strip()
    for name, rx, fn in RULES:
        m = rx.match(low)
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


VOWELS = set("aeiouAEIOU")

# ------------------------------------------------------------------ case packs
@rule("uppercase", r"uppercase(?:\s+this|\s+text)?[:：]?\s*")
def _upper(m, low):
    t = _operand(m, low)
    return t.upper() if t else None


@rule("lowercase", r"lowercase(?:\s+this|\s+text)?[:：]?\s*")
def _lower(m, low):
    t = _operand(m, low)
    return t.lower() if t else None


@rule("title case", r"(?:title ?case|titlecase)[:：]?\s*")
def _title(m, low):
    t = _operand(m, low)
    return t.title() if t else None


@rule("capitalize", r"capitali[sz]e[:：]?\s*")
def _cap(m, low):
    t = _operand(m, low)
    return t[0].upper() + t[1:].lower() if t else None


@rule("swap case", r"swap ?case[:：]?\s*")
def _swap(m, low):
    t = _operand(m, low)
    return t.swapcase() if t else None


@rule("reverse text", r"reverse (?:the )?(?:text|string|this)\b[:：]?\s*|reverse[:：]\s*")
def _rev(m, low):
    t = _operand(m, low)
    return t[::-1] if t else None


@rule("reverse words", r"reverse words[:：]?\s*")
def _revwords(m, low):
    t = _operand(m, low)
    return " ".join(t.split()[::-1]) if t else None


# -------------------------------------------------------------- counting packs
@rule("count words", r"count words(?: in| of)?[:：]?\s*")
def _cwords(m, low):
    t = _operand(m, low)
    return f"{len(t.split())} words" if t else None


@rule("count characters", r"count (?:characters|chars|letters)(?: in| of)?[:：]?\s*")
def _cchars(m, low):
    t = _operand(m, low)
    if not t:
        return None
    letters = sum(ch.isalpha() for ch in t)
    return (f"{len(t)} characters ({letters} letters, "
            f"{len(t.replace(' ', ''))} without spaces)")


@rule("count vowels", r"count vowels(?: in| of)?[:：]?\s*")
def _cvowels(m, low):
    t = _operand(m, low)
    if not t:
        return None
    v = sum(ch in VOWELS for ch in t)
    c = sum(ch.isalpha() and ch not in VOWELS for ch in t)
    return f"vowels: {v}, consonants: {c}"


@rule("count consonants", r"count consonants(?: in| of)?[:：]?\s*")
def _ccons(m, low):
    t = _operand(m, low)
    if not t:
        return None
    return f"consonants: {sum(ch.isalpha() and ch not in VOWELS for ch in t)}"


@rule("count sentences", r"count sentences(?: in| of)?[:：]?\s*")
def _csent(m, low):
    t = _operand(m, low)
    return f"{len(re.findall(r'[.!?]+', t)) or 1} sentence(s)" if t else None


@rule("reading time", r"(?:reading time|how long to read)(?: for| of)?[:：]?\s*")
def _reading(m, low):
    t = _operand(m, low)
    if not t:
        return None
    words = len(t.split())
    seconds = max(1, round(words / 200 * 60))
    return f"{words} words ≈ {seconds}s of reading (200 wpm)"


@rule("word frequency", r"(?:word frequency|count each word)(?: of| in)?[:：]?\s*")
def _freq(m, low):
    t = _operand(m, low)
    if not t:
        return None
    from collections import Counter
    top = Counter(re.findall(r"[a-z']+", t.lower())).most_common(5)
    return ", ".join(f"{w}×{n}" for w, n in top)


# ----------------------------------------------------------------- case styles
@rule("slugify", r"slugify[:：]?\s*")
def _slug(m, low):
    t = _operand(m, low)
    if not t:
        return None
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t.lower())).strip("-")


@rule("snake case", r"snake ?case[:：]?\s*")
def _snake(m, low):
    t = _operand(m, low)
    return "_".join(re.findall(r"[a-z0-9]+", t.lower())) if t else None


@rule("kebab case", r"kebab ?case[:：]?\s*")
def _kebab(m, low):
    t = _operand(m, low)
    return "-".join(re.findall(r"[a-z0-9]+", t.lower())) if t else None


@rule("camel case", r"(?:camel ?case|pascal ?case)[:：]?\s*")
def _camel(m, low):
    t = _operand(m, low)
    return "".join(w.title() for w in re.findall(r"[a-zA-Z0-9]+", t)) if t else None


@rule("initials", r"initials(?: of)?[:：]?\s*")
def _initials(m, low):
    t = _operand(m, low)
    return "".join(w[0].upper() for w in t.split() if w) if t else None


@rule("acronym", r"acronym(?: of| for)?[:：]?\s*")
def _acronym(m, low):
    t = _operand(m, low)
    return "".join(w[0].upper() for w in t.split() if w) if t else None


# ------------------------------------------------------------------- encodings
@rule("base64 encode", r"base64 (?:encode|of)[:：]?\s*")
def _b64e(m, low):
    t = _operand(m, low)
    return base64.b64encode(t.encode()).decode() if t else None


@rule("base64 decode", r"base64 decode[:：]?\s*")
def _b64d(m, low):
    t = _operand(m, low)
    if not t:
        return None
    try:
        return base64.b64decode(t + "=" * (-len(t) % 4)).decode()
    except Exception:
        return None


@rule("rot13", r"rot13[:：]?\s*")
def _rot13(m, low):
    t = _operand(m, low)
    if not t:
        return None
    import codecs
    return codecs.encode(t, "rot13")


@rule("url encode", r"(?:url ?encode|percent encode)[:：]?\s*")
def _urlenc(m, low):
    t = _operand(m, low)
    return quote(t) if t else None


@rule("binary of text", r"(?:binary|bits) of[:：]?\s*")
def _bino(m, low):
    t = _operand(m, low)
    return " ".join(f"{b:08b}" for b in t.encode()) if t else None


@rule("hex of text", r"hex(?:adecimal)? (?:of|for)[:：]?\s*")
def _hexo(m, low):
    t = _operand(m, low)
    return t.encode().hex(" ").upper() if t else None


@rule("sha256", r"sha ?256 (?:of|hash of|hash)[:：]?\s*")
def _sha(m, low):
    t = _operand(m, low)
    return hashlib.sha256(t.encode()).hexdigest() if t else None


@rule("md5", r"md5 (?:of|hash of|hash)[:：]?\s*")
def _md5(m, low):
    t = _operand(m, low)
    return hashlib.md5(t.encode()).hexdigest() if t else None


@rule("crc32", r"crc ?32 of[:：]?\s*")
def _crc(m, low):
    t = _operand(m, low)
    return f"{zlib.crc32(t.encode()) & 0xffffffff:08x}" if t else None


# ---------------------------------------------------------------- text repairs
@rule("remove duplicate lines", r"(?:remove |dedupe )duplicate lines[:：]?\s*")
def _dedupe_lines(m, low):
    t = _operand(m, low)
    if not t:
        return None
    seen, out = set(), []
    for line in t.splitlines():
        if line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


@rule("sort lines", r"sort lines[:：]?\s*")
def _sortlines(m, low):
    t = _operand(m, low)
    return "\n".join(sorted(t.splitlines())) if t else None


@rule("number lines", r"number (?:the )?lines[:：]?\s*")
def _numlines(m, low):
    t = _operand(m, low)
    if not t:
        return None
    return "\n".join(f"{i}. {line}" for i, line in enumerate(t.splitlines(), 1))


@rule("strip empty lines", r"(?:strip|remove) (?:empty|blank) lines[:：]?\s*")
def _stripempty(m, low):
    t = _operand(m, low)
    return "\n".join(l for l in t.splitlines() if l.strip()) if t else None


@rule("collapse spaces", r"collapse (?:white ?)?spaces[:：]?\s*")
def _collapse(m, low):
    t = _operand(m, low)
    return re.sub(r"\s+", " ", t).strip() if t else None


@rule("trim", r"trim[:：]?\s*")
def _trim(m, low):
    t = _operand(m, low)
    return t.strip() if t else None


@rule("shuffle lines", r"shuffle lines[:：]?\s*")
def _shuffle(m, low):
    t = _operand(m, low)
    if not t:
        return None
    import random
    lines = t.splitlines()
    random.shuffle(lines)
    return "\n".join(lines)


# ------------------------------------------------------------------ extraction
@rule("extract emails", r"(?:extract|find) emails?[:：]?\s*")
def _emails(m, low):
    t = _operand(m, low)
    if not t:
        return None
    found = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", t)
    return ", ".join(found) if found else "no emails found"


@rule("extract urls", r"(?:extract|find) urls?[:：]?\s*")
def _urls(m, low):
    t = _operand(m, low)
    if not t:
        return None
    found = re.findall(r"https?://[^\s,]+", t)
    return "\n".join(found) if found else "no urls found"


@rule("extract numbers", r"(?:extract|find) numbers[:：]?\s*")
def _numbers(m, low):
    t = _operand(m, low)
    if not t:
        return None
    found = re.findall(r"-?\d+(?:\.\d+)?", t)
    return ", ".join(found) if found else "no numbers found"


@rule("extract hashtags", r"(?:extract|find) hashtags[:：]?\s*")
def _hashtags(m, low):
    t = _operand(m, low)
    if not t:
        return None
    found = re.findall(r"#\w+", t)
    return ", ".join(found) if found else "no hashtags found"


@rule("extract mentions", r"(?:extract|find) mentions[:：]?\s*")
def _mentions(m, low):
    t = _operand(m, low)
    if not t:
        return None
    found = re.findall(r"@\w+", t)
    return ", ".join(found) if found else "no mentions found"


# ------------------------------------------------------------------- data files
@rule("json pretty", r"(?:json pretty|pretty ?print json|format json|prettify json)[:：]?\s*")
def _jsonpretty(m, low):
    t = _operand(m, low)
    if not t:
        return None
    try:
        return json.dumps(json.loads(t), indent=2, sort_keys=True)
    except Exception:
        return None


@rule("json minify", r"minify json[:：]?\s*")
def _jsonmin(m, low):
    t = _operand(m, low)
    if not t:
        return None
    try:
        return json.dumps(json.loads(t), separators=(",", ":"))
    except Exception:
        return None


@rule("csv to markdown", r"csv to markdown[:：]?\s*")
def _csvmd(m, low):
    t = _operand(m, low)
    if not t:
        return None
    rows = [r.split(",") for r in t.strip().splitlines() if r.strip()]
    if not rows:
        return None
    head, *body = rows
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * len(head)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(out)


@rule("markdown to text", r"(?:markdown to (?:plain )?text|strip markdown)[:：]?\s*")
def _mdtext(m, low):
    t = _operand(m, low)
    if not t:
        return None
    out = re.sub(r"`{1,3}[^`]*`{1,3}", "", t)
    out = re.sub(r"[*_#>]+", "", out)
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


# --------------------------------------------------------------- word games
@rule("pig latin", r"pig latin[:：]?\s*")
def _pig(m, low):
    t = _operand(m, low)
    if not t:
        return None

    def one(w):
        if not w.isalpha():
            return w
        if w[0] in VOWELS:
            return w + "way"
        i = next((k for k, ch in enumerate(w) if ch in VOWELS), len(w))
        return w[i:] + w[:i] + "ay"

    return " ".join(one(w) for w in t.split())


@rule("is palindrome", r"is ['\"]?(.+?)['\"]? a palindrome")
def _pal(m, _low):
    t = re.sub(r"[^a-z0-9]", "", m.group(1).lower())
    if not t:
        return None
    return (f"“{m.group(1)}” {'is' if t == t[::-1] else 'is not'} a palindrome")


@rule("is isogram", r"is ['\"]?(.+?)['\"]? an isogram")
def _iso(m, _low):
    t = re.sub(r"[^a-z]", "", m.group(1).lower())
    if not t:
        return None
    return (f"“{m.group(1)}” {'is' if len(set(t)) == len(t) else 'is not'} "
            f"an isogram")


@rule("are anagrams", r"are ['\"]?(.+?)['\"]? and ['\"]?(.+?)['\"]? anagrams")
def _anagram(m, _low):
    a = sorted(re.sub(r"[^a-z]", "", m.group(1).lower()))
    b = sorted(re.sub(r"[^a-z]", "", m.group(2).lower()))
    return (f"“{m.group(1)}” and “{m.group(2)}” are "
            f"{'' if a == b else 'not '}anagrams")


@rule("repeat text", r"repeat[:：]?\s*")
def _repeat(m, low):
    tail = low[m.end():].strip()
    mt = re.match(r"['\"](.+?)['\"]\s*(?:x|times)?\s*(\d{1,3})", tail, re.I)
    if not mt:
        return None
    return mt.group(1) * min(int(mt.group(2)), 200)


@rule("truncate", r"truncate(?: to)?[:：]?\s*")
def _truncate(m, low):
    tail = low[m.end():].strip()
    mt = re.match(r"(\d{1,4})\s*[:：]?\s*(.+)", tail)
    if not mt:
        return None
    n, t = int(mt.group(1)), mt.group(2)
    return t[:n] + ("…" if len(t) > n else "")


@rule("pad text", r"pad[:：]?\s*")
def _pad(m, low):
    tail = low[m.end():].strip()
    mt = re.match(r"(\d{1,4})\s*[:：]?\s*(.+)", tail)
    if not mt:
        return None
    return mt.group(2).ljust(int(mt.group(1)), ".")


@rule("replace text", r"replace[:：]?\s*")
def _replace(m, low):
    tail = low[m.end():].strip()
    mt = re.match(r"['\"](.+?)['\"]\s+(?:with|by)\s+['\"](.+?)['\"]\s+in\s+['\"](.+?)['\"]$",
                  tail, re.I)
    if not mt:
        return None
    return mt.group(3).replace(mt.group(1), mt.group(2))


@rule("split to list", r"split[:：]?\s*")
def _split(m, low):
    t = _operand(m, low)
    return repr(t.split()) if t else None


@rule("join list", r"join[:：]?\s*")
def _join(m, low):
    t = _operand(m, low)
    return ", ".join(p.strip() for p in re.split(r"[,;\n]+", t) if p.strip()) if t else None
