#!/usr/bin/env python3
"""Fetch a public-domain text corpus into MyGPT's live corpus.

The brain's language model is only as good as the text it trains on. MyGPT's
seed corpus is 86 curated lines — enough to verify learning, far too little to
generalise from (measured: held-out perplexity worse than uniform guessing).
This tool pulls a real corpus from GitHub and merges it into
``data/corpus.json``, the file Brain loads at boot and the background trainer
keeps learning from.

Sources (all fetched from github.com only):

* ``tiny-shakespeare`` — karpathy/char-rnn's tiny-shakespeare (~1MB of public
  domain Shakespeare), the standard tiny-LM benchmark text.

The corpus is *data*, not code: it is downloaded into ``data/`` and never
committed. Existing corpus lines are kept first and duplicates are dropped, so
running the tool twice never double-weights anything (the same guarantee the
seed loader gives). If a running MyGPT has the corpus open, stop it first —
it rewrites ``data/corpus.json`` from memory on save.

Usage::

    python tools/fetch_corpus.py                     # tiny-shakespeare, 180-word chunks
    python tools/fetch_corpus.py --words 120 --limit 500
    python tools/fetch_corpus.py --offline-file /tmp/input.txt   # no network
    python tools/fetch_corpus.py --dry-run           # count, write nothing

License: MyGPT Personal-Use License (see LICENSE). All credit to codero-sus —
https://github.com/codero-sus
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = {
    "tiny-shakespeare": {
        "repo": "https://github.com/karpathy/char-rnn",
        "branch": "master",
        "path": os.path.join("data", "tinyshakespeare", "input.txt"),
        "cache": "char-rnn",
    },
}

# Brain rewrites corpus.json from memory as ``self.corpus[-5000:]`` on save
# (mygpt/brain.py), so never import more than fits under that cap or the tail
# would silently vanish the next time the app saves.
MAX_LINES = 5000
WARN_LINES = 4500


def chunk_words(text: str, words_per_chunk: int) -> list[str]:
    """Split text into whitespace-separated chunks of roughly N words.

    Line breaks inside the source are collapsed to single spaces — the LM
    tokenises on words anyway, and a chunk boundary mid-sentence costs at most
    one window's worth of context.
    """
    if words_per_chunk < 1:
        raise ValueError("words_per_chunk must be >= 1")
    words = " ".join(text.split()).split(" ")
    words = [w for w in words if w]
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        piece = " ".join(words[i:i + words_per_chunk])
        if piece:
            chunks.append(piece)
    return chunks


def load_source_text(source: str, offline_file: str | None = None,
                     data_dir: str = "data") -> str:
    """Return the raw corpus text, cloning the GitHub repo once if needed."""
    if offline_file:
        with open(offline_file, encoding="utf-8") as fh:
            return fh.read()
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}; known: {sorted(SOURCES)}")
    spec = SOURCES[source]
    cache = os.path.join(ROOT, data_dir, ".cache", spec["cache"])
    marker = os.path.join(cache, spec["path"])
    if not os.path.exists(marker):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        print(f"cloning {spec['repo']} (shallow) ...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", spec["branch"],
             spec["repo"], cache],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    with open(marker, encoding="utf-8") as fh:
        return fh.read()


def merge_corpus(existing: list[str], new_chunks: list[str]) -> list[str]:
    """Existing lines first (their positions never move), then unseen ones."""
    seen: set[str] = set()
    out: list[str] = []
    for line in list(existing) + list(new_chunks):
        if not isinstance(line, str):
            continue
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def corpus_path(data_dir: str = "data") -> str:
    return os.path.join(ROOT, data_dir, "corpus.json")


def load_corpus(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [t for t in data if isinstance(t, str)] if isinstance(data, list) else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default="tiny-shakespeare",
                    help="corpus to fetch (default: tiny-shakespeare)")
    ap.add_argument("--words", type=int, default=180,
                    help="words per corpus chunk (default: 180)")
    ap.add_argument("--limit", type=int, default=0,
                    help="max chunks to import (0 = all)")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--offline-file",
                    help="read corpus text from this file instead of GitHub")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be imported, write nothing")
    args = ap.parse_args(argv)

    text = load_source_text(args.source, args.offline_file, args.data_dir)
    chunks = chunk_words(text, args.words)
    if args.limit > 0:
        chunks = chunks[:args.limit]

    path = corpus_path(args.data_dir)
    existing = load_corpus(path)
    merged = merge_corpus(existing, chunks)
    added = len(merged) - len(existing)

    print(f"source text: {len(text):,} chars, "
          f"{len(' '.join(text.split()).split()):,} words")
    print(f"chunks: {len(chunks):,} x {args.words} words "
          f"(added {added:,} new, skipped {len(chunks) - added:,} duplicates)")
    print(f"corpus:  {path}  ({len(existing)} -> {len(merged)} lines)")

    if len(merged) > WARN_LINES:
        print(f"warning: {len(merged)} lines exceeds the {MAX_LINES}-line cap "
              f"MyGPT keeps on save — the tail would be dropped on the next "
              f"save. Use --limit to import at most "
              f"{MAX_LINES - len(existing)} more.", file=sys.stderr)
        if len(merged) > MAX_LINES and not args.dry_run:
            print("refusing to write; lower --limit.", file=sys.stderr)
            return 1

    if args.dry_run:
        print("dry run: nothing written.")
        return 0

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False,
                                     dir=os.path.dirname(path)) as tmp:
        json.dump(merged, tmp, ensure_ascii=False)
        tmp.write("\n")
        os.replace(tmp.name, path)
    print("done. Restart MyGPT (or let it boot) to train on the grown corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
