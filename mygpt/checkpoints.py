"""Model checkpoints — save/load trained MyGPT models to ``./_model_trained/``.

MyGPT trains its own NumPy language model. A *checkpoint* is a snapshot of the
trained weights plus a little metadata, written to ``_model_trained/<name>/``:

    _model_trained/
      model-20260211-103000/
        lm_weights.npz     the trained weights (same format as data/lm_weights.npz)
        meta.json          name, timestamp, loss, vocab, corpus size, mygpt version

Checkpoints let the user keep several trained versions and load any of them
back as the active chat model. These are MyGPT's own self-trained weights —
they are *not* GGUF/Ollama models, because MyGPT's brain is a small NumPy
network, not a llama.cpp model.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time

WEIGHTS_NAME = "lm_weights.npz"
META_NAME = "meta.json"


def _slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return slug[:32]


class CheckpointManager:
    """Manages trained-model snapshots under a root directory."""

    def __init__(self, root_dir: str):
        self.root = root_dir
        os.makedirs(self.root, exist_ok=True)

    # ------------------------------------------------------------------ save
    def save(self, lm, note: str = "", mygpt_version: str = "",
             loss: float | None = None, epochs: int | None = None,
             corpus_lines: int = 0, label: str = "") -> dict:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        slug = _slug(label)
        name = f"{slug}-{stamp}" if slug else f"model-{stamp}"
        folder = os.path.join(self.root, name)
        # avoid clobbering an existing folder created within the same second
        i = 2
        while os.path.exists(folder):
            folder = os.path.join(self.root, f"{name}-{i}")
            i += 1
        os.makedirs(folder, exist_ok=True)
        lm.save(os.path.join(folder, WEIGHTS_NAME))
        meta = {
            "name": os.path.basename(folder),
            "created": round(time.time()),
            "note": (note or "")[:200],
            "mygpt_version": mygpt_version,
            "loss": loss,
            "epochs": epochs,
            "vocab": getattr(lm, "vocab_size", None),
            "corpus_lines": corpus_lines,
        }
        with open(os.path.join(folder, META_NAME), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta

    # ------------------------------------------------------------------ list
    def list(self) -> list[dict]:
        items = []
        if not os.path.isdir(self.root):
            return items
        for entry in os.listdir(self.root):
            meta_path = os.path.join(self.root, entry, META_NAME)
            if not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            meta.setdefault("name", entry)
            items.append(meta)
        items.sort(key=lambda m: m.get("created", 0), reverse=True)
        return items

    def get(self, name: str) -> dict | None:
        for meta in self.list():
            if meta.get("name") == name:
                return meta
        return None

    def weights_path(self, name: str) -> str | None:
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            return None
        path = os.path.join(self.root, name, WEIGHTS_NAME)
        return path if os.path.isfile(path) else None

    # ------------------------------------------------------------------ load
    def load(self, name: str, lm) -> dict | None:
        """Load checkpoint `name` weights into the language model `lm`."""
        path = self.weights_path(name)
        if not path:
            return None
        if not lm.load(path):
            return None
        return self.get(name)

    # ---------------------------------------------------------------- delete
    def delete(self, name: str) -> bool:
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            return False
        folder = os.path.join(self.root, name)
        if not os.path.isdir(folder):
            return False
        shutil.rmtree(folder, ignore_errors=True)
        return True
