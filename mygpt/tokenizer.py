"""Minimal word tokenizer shared by the language model and memory."""

import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    """Lowercase text and extract word tokens."""
    return _TOKEN_RE.findall(text.lower())


def normalize(text: str) -> str:
    """Canonical whitespace-joined token form of a sentence."""
    return " ".join(tokenize(text))
