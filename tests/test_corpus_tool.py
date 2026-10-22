"""The corpus fetch tool must be safe to run twice and safe to run offline.

The numbers in the v1.12.0 report come from a corpus this tool imported; if it
duplicates lines, double-weights facts (the bug the seed loader guards
against); if it silently truncates under Brain's 5000-line save cap, the tail
of the corpus vanishes the next time the app saves. These tests pin both.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location(
    "mygpt_fetch_corpus", os.path.join(ROOT, "tools", "fetch_corpus.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class ChunkTests(unittest.TestCase):
    def test_chunks_have_the_requested_size(self):
        text = " ".join(f"w{i}" for i in range(1000))
        chunks = fetch.chunk_words(text, 180)
        self.assertEqual(len(chunks), 6)            # 5 full + remainder
        self.assertEqual(len(chunks[0].split()), 180)
        self.assertEqual(len(chunks[-1].split()), 100)

    def test_line_breaks_are_collapsed(self):
        chunks = fetch.chunk_words("one\ntwo\n\nthree", 2)
        self.assertEqual(chunks, ["one two", "three"])

    def test_rejects_nonsense_size(self):
        with self.assertRaises(ValueError):
            fetch.chunk_words("some text", 0)


class MergeTests(unittest.TestCase):
    def test_existing_lines_keep_their_position_and_new_ones_dedupe(self):
        merged = fetch.merge_corpus(["b", "a"], ["a", "c", "c", "d"])
        self.assertEqual(merged, ["b", "a", "c", "d"])

    def test_junk_is_dropped(self):
        merged = fetch.merge_corpus(["ok", "", "  ", 7], ["fine"])  # type: ignore
        self.assertEqual(merged, ["ok", "fine"])


class OfflineEndToEndTests(unittest.TestCase):
    def test_offline_file_feeds_the_live_corpus_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.txt")
            words = " ".join(f"tok{i}" for i in range(40))
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(words)

            data_dir = os.path.join(tmp, "data")
            rc = fetch.main(["--offline-file", src, "--words", "10",
                             "--data-dir", data_dir])
            self.assertEqual(rc, 0)
            path = fetch.corpus_path(data_dir)
            first = fetch.load_corpus(path)
            self.assertEqual(len(first), 4)         # 40 words / 10 per chunk

            # running it again must not duplicate anything
            rc = fetch.main(["--offline-file", src, "--words", "10",
                             "--data-dir", data_dir])
            self.assertEqual(rc, 0)
            self.assertEqual(fetch.load_corpus(path), first)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.txt")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("some words here " * 20)
            data_dir = os.path.join(tmp, "data")
            rc = fetch.main(["--offline-file", src, "--words", "5",
                             "--data-dir", data_dir, "--dry-run"])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(fetch.corpus_path(data_dir)))

    def test_refuses_to_exceed_the_save_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.txt")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(" ".join(f"t{i}" for i in range(fetch.MAX_LINES * 10 + 1)))
            data_dir = os.path.join(tmp, "data")
            rc = fetch.main(["--offline-file", src, "--words", "1",
                             "--data-dir", data_dir])
            self.assertEqual(rc, 1)                 # refused
            self.assertFalse(os.path.exists(fetch.corpus_path(data_dir)))

    def test_limit_stops_under_the_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "input.txt")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(" ".join(f"t{i}" for i in range(6000)))
            data_dir = os.path.join(tmp, "data")
            rc = fetch.main(["--offline-file", src, "--words", "1",
                             "--limit", "3000", "--data-dir", data_dir])
            self.assertEqual(rc, 0)
            self.assertEqual(len(fetch.load_corpus(fetch.corpus_path(data_dir))),
                             3000)


if __name__ == "__main__":
    unittest.main()
