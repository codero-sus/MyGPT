"""Minimal word tokenizer shared by the language model and memory.

Both functions are memoised: the same strings (memory queries, fact
subjects, recent dialogue) are tokenised many times per turn, and
tokenization dominates the cheap parts of the reply path.
"""

import functools
import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")


@functools.lru_cache(maxsize=4096)
def _tokens(text: str) -> tuple:
    return tuple(_TOKEN_RE.findall(text.lower()))


def tokenize(text: str) -> list[str]:
    """Lowercase text and extract word tokens."""
    return list(_tokens(text))


@functools.lru_cache(maxsize=4096)
def normalize(text: str) -> str:
    """Canonical whitespace-joined token form of a sentence."""
    return " ".join(_tokens(text))
