"""The Brain: memory + language model + CORTEX-style self-improvement loop.

Flow of a conversation turn:
    1. Built-in skills (arithmetic) and learned skill files
    2. Semantic facts extracted from earlier turns ("my name is …")
    3. Learned memory pairs (TF-IDF retrieval)
    4. Otherwise admit ignorance and ask to be taught

Self-learning (ported from codero-sus/agi, "CORTEX"):
    * light pass after every turn: fact extraction, self-critique -> lessons,
      background Adam steps queued on the exchange
    * medium pass every 5 turns: skill synthesis, constitution promotion,
      self-eval battery, corpus training, consolidation
    * heavy pass: background trainer with dream replay + debounced checkpoints
"""

from __future__ import annotations

import atexit
import json
import os
import random
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from .episodes import EpisodicMemory
from .goals import Goals
from .langmodel import NeuralLM
from .memory import Memory
from .reason import Article, Reasoner
from .selflearn import SelfImprovement, classify_intent
from .skills import SkillRegistry, ensure_starter_skills
from .store import SelfLearnStore
from .tokenizer import normalize
from .trainer import BackgroundTrainer
from . import codegen
from . import importers
from . import mathx
from . import textfx
from .checkpoints import CheckpointManager
from .cortex import CortexClient
from .hf_backend import HFClient
from .llamacpp_backend import LlamaCppClient
from .ollama import OllamaClient
from .transformer import TransformerLM

STRONG_MATCH = 0.52      # confident recall
WEAK_MATCH = 0.30        # a guess worth offering
AUTO_TRAIN_EVERY = 5     # curated-learning events between blocking train rounds
AUTO_TRAIN_EPOCHS = 6
PROBE_INTERVAL_S = 20.0     # background auto-probe of local LLM backends
SAVE_MIN_GAP_S = 1.0        # debounce full state writes to disk

TEACH_REPLIES = [
    "I don't know that yet — but you can teach me! Add an answer in the Teach panel and I'll remember it forever.",
    "That's not in my memory yet. Teach me via the panel on the right and I'll have it next time.",
    "I haven't learned that one. If you teach me now, it becomes permanent training data.",
]
MATH_RE = re.compile(r"^[\s0-9+\-*/().%^]+$")
CHECKPOINT_RE = re.compile(
    r"\b(check ?point|save (?:the |my |a )?model|snapshot (?:the )?model)\b", re.I)
TRAIN_RE = re.compile(r"\btrain\b", re.I)


class Brain:
    def __init__(self, data_dir: str, seed_path: str, skills_dir: str | None = None):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        # --- language model architecture -------------------------------------
        # v1.11: the default brain is a small decoder-only *transformer*
        # (multi-head causal self-attention, pre-LN, tied embeddings, learned
        # positional embeddings). MYGPT_ARCH=mlp keeps the original feed-forward
        # network, and a saved MLP checkpoint is loaded into it automatically so
        # nobody's existing brain is orphaned by the upgrade.
        self.arch = (os.environ.get("MYGPT_ARCH", "transformer") or
                     "transformer").strip().lower()
        self.lm = self._make_lm(self.arch)
        self.memory = Memory()
        self.store = SelfLearnStore(os.path.join(data_dir, "selflearn.json"))
        self.episodes = EpisodicMemory(os.path.join(data_dir, "episodes.json"))
        self.goals = Goals(os.path.join(data_dir, "goals.json"))
        self.skills_root = Path(skills_dir) if skills_dir else \
            Path(__file__).resolve().parent.parent / "skills"
        ensure_starter_skills(self.skills_root)
        self.skills = SkillRegistry(self.skills_root)
        self.reasoner = Reasoner(self)
        self.corpus: list[str] = []
        self.pending: dict[str, dict] = {}     # msg_id -> last-reply record
        self.started = time.time()
        self.counters = {
            "messages": 0, "up": 0, "down": 0, "corrections": 0,
            "teachings": 0, "train_rounds": 0, "events_since_train": 0,
            "turns": 0, "cycles": 0, "imports": 0,
        }
        self.loss_history: list[dict] = []
        self.events: list[dict] = []
        self.last_records: deque = deque(maxlen=200)   # analytics ring buffer

        self.trainer = BackgroundTrainer(self.lm, save_fn=self.save)
        self.trainer.dream_source = self._dream_text
        # a queued round reports back here, so finished background work lands in
        # the loss history and counters exactly like an explicit round does
        self.trainer.on_round = self._on_background_round
        self.improver = SelfImprovement(self)
        self.cortex = CortexClient(os.path.join(data_dir, "cortex.json"))
        self.ollama = OllamaClient(os.path.join(data_dir, "ollama.json"))
        # v1.11 in-process backends: llama.cpp (GGUF) and 🤗 transformers
        # Drop a .gguf into <project root>/models/ and the engine turns on.
        # MYGPT_MODELS_DIR relocates that folder, and setting it to an empty
        # string (or a folder with no .gguf in it) keeps the engine off — the
        # test suite relies on that so a demo model in the repo can't make
        # "no local LLM installed" cases pass by accident.
        models_env = os.environ.get("MYGPT_MODELS_DIR")
        if models_env is None:
            models_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "models")
        else:
            models_dir = models_env or None
        self.llamacpp = LlamaCppClient(
            os.path.join(data_dir, "llamacpp.json"), models_dir=models_dir)
        self.hf = HFClient(os.path.join(data_dir, "hf.json"))
        # checkpoints live in <project root>/_model_trained (next to data/)
        # checkpoints default to <project root>/_model_trained; the
        # MYGPT_CHECKPOINTS env var relocates them (tests, custom datadirs)
        self.checkpoints = CheckpointManager(
            os.environ.get(
                "MYGPT_CHECKPOINTS",
                os.path.join(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))),
                    "_model_trained")))
        # which engine answers open chat questions (brain/cortex/ollama/auto)
        self.chat_backend = "auto"
        self.chat_model = ""
        self._backends_path = os.path.join(data_dir, "backends.json")

        # background auto-probe of the local LLM backends (Cortex & Ollama)
        self._probe_state: dict = {"cortex": None, "ollama": None,
                                   "llamacpp": None, "hf": None,
                                   "last_check": 0}
        self._install_nudges = 0
        self._prober_stop = threading.Event()
        self._prober = threading.Thread(target=self._auto_probe_loop,
                                        daemon=True, name="backend-prober")
        # debounced persistence: full 7-file state writes are coalesced when
        # they land within SAVE_MIN_GAP_S of each other (chat turns hammer
        # save()); anything pending is flushed on shutdown
        self._last_save = 0.0
        self._save_pending = False
        # The background trainer also saves (it flushes checkpoints when idle),
        # so serialise the write itself — two threads interleaving json writes
        # would corrupt data/memory.json rather than merely race.
        self._save_lock = threading.RLock()
        atexit.register(self._flush_on_exit)

        self._seed_path = seed_path
        self._load()
        self._prober.start()

    # ---------------------------------------------------------------- setup
    def _load(self) -> None:
        mem_path = os.path.join(self.data_dir, "memory.json")
        cor_path = os.path.join(self.data_dir, "corpus.json")
        met_path = os.path.join(self.data_dir, "metrics.json")
        lm_path = os.path.join(self.data_dir, "lm_weights.npz")

        # A checkpoint from a *different* architecture is refused by the model
        # (both loaders return False rather than half-loading). The decision to
        # re-tokenise the corpus is taken *after* the corpus is read below —
        # checking here would always see an empty corpus and silently boot a
        # brain that only knows <pad>/<unk>.
        lm_loaded = self.lm.load(lm_path)

        if os.path.exists(mem_path):
            with open(mem_path, encoding="utf-8") as f:
                self.memory.load_list(json.load(f))
        if os.path.exists(cor_path):
            with open(cor_path, encoding="utf-8") as f:
                self.corpus = json.load(f)
        if os.path.exists(met_path):
            with open(met_path, encoding="utf-8") as f:
                meta = json.load(f)
                saved = meta.get("counters", {})
                for k, v in saved.items():
                    self.counters[k] = v
                self.loss_history = meta.get("loss_history", [])
                self.events = meta.get("events", [])

        # Seeding is additive and idempotent: first boot imports the whole
        # starter corpus, and every later boot merges only the pairs/texts an
        # update added — so new seed knowledge reaches existing data/ folders
        # instead of being ignored because memory is no longer empty.
        first_boot = not self.memory.pairs
        if self._seed_path and os.path.exists(self._seed_path):
            with open(self._seed_path, encoding="utf-8") as f:
                seed = json.load(f)
            known = {normalize(p["q"]) for p in self.memory.pairs}
            added = 0
            for item in seed.get("pairs", []):
                key = normalize(item["q"])
                if key in known:
                    continue
                known.add(key)
                self.memory.add(item["q"], item["a"])
                added += 1
            seen = {normalize(c) for c in self.corpus}
            fresh = [ln for ln in seed.get("texts", [])
                     if normalize(ln) not in seen]
            for line in fresh:
                self._ingest(line, train=False)
                seen.add(normalize(line))
            if added or fresh:
                self._log(f"seeded with starter knowledge "
                          f"(+{added} pairs, +{len(fresh)} texts)")
            if first_boot:
                self.train(epochs=12, reason="initial training")
            elif added:
                self.train(epochs=4, reason="seed update training")
        if not first_boot and self.corpus:
            for line in self.corpus:
                self.lm.observe(line)

        # Weights from another architecture (or a fresh transformer brain with
        # an existing corpus) need their vocabulary rebuilt before they can do
        # anything useful — otherwise the model would only know <pad>/<unk>.
        if (not lm_loaded) and self.corpus:
            for line in self.corpus[:20000]:
                self.lm.observe(line)
            self.lm.rebuild_vocab()
            self._log(f"re-tokenised {len(self.corpus)} corpus lines for the "
                      f"{getattr(self.lm, 'arch', 'mlp')} brain")
            for line in self.corpus[-40:]:
                self.trainer.submit(line, steps=2)

        # chat-backend selection (brain/cortex/ollama/auto)
        if os.path.exists(self._backends_path):
            try:
                with open(self._backends_path, encoding="utf-8") as f:
                    bc = json.load(f)
                if bc.get("chat_backend") in ("brain", "cortex", "ollama", "auto"):
                    self.chat_backend = bc["chat_backend"]
                if isinstance(bc.get("chat_model"), str):
                    self.chat_model = bc["chat_model"]
            except (OSError, ValueError):
                pass

    # ------------------------------------------------- backends & checkpoints
    def set_chat_backend(self, backend: str, model: str = "") -> dict:
        backend = (backend or "auto").strip().lower()
        if backend not in ("brain", "cortex", "ollama", "llamacpp", "hf", "auto"):
            return {"ok": False, "error": "backend must be brain, cortex, ollama, "
                                          "llamacpp, hf or auto"}
        self.chat_backend = backend
        self.chat_model = (model or "").strip()
        self._write("backends.json", {"chat_backend": self.chat_backend,
                                       "chat_model": self.chat_model})
        self._log(f"chat backend set to {self.chat_backend}"
                  + (f" ({self.chat_model})" if self.chat_model else ""))
        return {"ok": True, "chat_backend": self.chat_backend,
                "chat_model": self.chat_model}

    def backends(self) -> dict:
        """Everything the WebUI needs to render the model picker."""
        return {
            "chat_backend": self.chat_backend,
            "chat_model": self.chat_model,
            "options": {
                "brain": {"label": f"MyGPT self-trained "
                                   f"{getattr(self.lm, 'arch', 'mlp')} brain",
                          "available": True,
                          "arch": getattr(self.lm, "arch", "mlp"),
                          "params": getattr(self.lm, "param_count", lambda: 0)()},
                "cortex": self.cortex.probe(),
                "ollama": self.ollama.probe(),
                "llamacpp": self.llamacpp.probe(),
                "hf": self.hf.probe(),
            },
            "arch": getattr(self.lm, "arch", "mlp"),
            "checkpoints": self.checkpoints.list(),
            "auto_probe": {"interval_s": PROBE_INTERVAL_S,
                           **self._probe_state},
            "install_hint": self.install_hint(),
        }

    # ----------------------------------------------------------- auto-probe
    def _auto_probe_loop(self) -> None:
        """Quietly watch for local LLM backends coming and going."""
        # first probe shortly after boot, then on the steady interval
        wait = 1.0
        while not self._prober_stop.wait(wait):
            try:
                self._auto_probe_once()
            except Exception:
                pass
            wait = PROBE_INTERVAL_S

    def _auto_probe_once(self) -> None:
        labels = (("cortex", self.cortex, "Cortex LLMHoster"),
                  ("ollama", self.ollama, "Ollama"),
                  ("llamacpp", self.llamacpp, "llama.cpp (GGUF)"),
                  ("hf", self.hf, "transformers"))
        for key, client, label in labels:
            # presence = server answers, regardless of the enable toggle
            up = bool(client.health())
            prev = self._probe_state.get(key)
            if up and prev is None:
                self._log(f"auto-probe: {label} detected at {client.base_url}")
            elif up and prev is False:
                self._log(f"auto-probe: {label} back online at {client.base_url}")
            elif not up and prev is True:
                self._log(f"auto-probe: {label} went offline")
            self._probe_state[key] = up
        self._probe_state["last_check"] = round(time.time())

    def any_local_llm(self) -> bool:
        """True when at least one local LLM engine is actually usable."""
        return any((self.cortex.health(), self.ollama.health(),
                    self.llamacpp.health(), self.hf.health()))

    def install_hint(self) -> dict | None:
        """Install suggestions when neither Cortex nor Ollama is present."""
        if self.any_local_llm():
            return None
        return {
            "title": "No local LLM detected",
            "message": "Install a local model host so MyGPT can route the "
                       "open questions it can't answer to a real model. "
                       "MyGPT keeps answering with its self-trained brain "
                       "either way.",
            "options": [
                {"name": "Cortex LLMHoster", "author": "codero-sus",
                 "repo": "https://github.com/codero-sus/Cortex_LLMHoster",
                 "website": "https://the-codero.web.app/",
                 "hint": "pip install cortex-llmhoster, then run "
                         "`cortex-llmhoster`"},
                {"name": "Ollama", "url": "https://ollama.com",
                 "hint": "install Ollama, run `ollama serve`, then "
                         "`ollama pull <model>`"},
            ],
        }

    def _chat_install_nudge(self) -> str | None:
        """Occasionally suggest installing a local LLM host in chat."""
        if self._install_nudges >= 2 or self.any_local_llm():
            return None
        self._install_nudges += 1
        return ("💡 Tip: I don't see a local LLM host yet. Install "
                "Cortex LLMHoster (by codero-sus — "
                "https://github.com/codero-sus/Cortex_LLMHoster) or Ollama "
                "(https://ollama.com) and I can route open questions to a "
                "real model. My own brain keeps answering either way.")

    def checkpoint(self, label: str = "", note: str = "") -> dict:
        """Snapshot the current trained weights into _model_trained/."""
        from . import __version__
        loss = self.loss_history[-1]["loss"] if self.loss_history else None
        meta = self.checkpoints.save(
            self.lm, note=note, mygpt_version=__version__, loss=loss,
            epochs=self.counters.get("train_rounds"),
            corpus_lines=len(self.corpus), label=label)
        self._log(f"model checkpoint saved: {meta['name']}")
        self.save(force=True)
        return meta

    def load_checkpoint(self, name: str) -> dict:
        meta = self.checkpoints.load(name, self.lm)
        if not meta:
            return {"ok": False, "error": f"checkpoint '{name}' not found"}
        self._log(f"loaded model checkpoint: {name}")
        self.save(force=True)            # make the checkpoint the live weights
        return {"ok": True, **meta}

    def delete_checkpoint(self, name: str) -> dict:
        if not self.checkpoints.delete(name):
            return {"ok": False, "error": f"checkpoint '{name}' not found"}
        self._log(f"deleted model checkpoint: {name}")
        return {"ok": True, "name": name}

    def _maybe_checkpoint_command(self, text: str) -> str | None:
        """'checkpoint the model' / 'train and save the model' → snapshot."""
        if not CHECKPOINT_RE.search(text):
            return None
        if TRAIN_RE.search(text):
            self.train(epochs=AUTO_TRAIN_EPOCHS, reason="checkpoint request",
                       requirement="background")
        meta = self.checkpoint(note=text[:120])
        return (f"✅ Saved a trained-model checkpoint to "
                f"`_model_trained/{meta['name']}/` "
                f"(vocab {meta['vocab']}, loss {meta['loss']}). "
                f"You can load it back anytime from the Model checkpoints panel.")

    def _backend_answer(self, text: str, qn: str):
        """Ask the selected local LLM back end(s). Returns (answer, engine,
        learned) or None. Deterministic routes always run first; this only
        fills the gaps the self-trained brain can't."""
        # In "auto" mode Cortex LLMHoster is deliberately tried first —
        # codero-sus' own hoster gets the quiet priority; Ollama is the
        # fallback. The UI stays neutral about this ordering.
        engines = []
        if self.chat_backend in ("auto", "cortex"):
            engines.append(("cortex", self.cortex))
        if self.chat_backend in ("auto", "ollama"):
            engines.append(("ollama", self.ollama))
        # in-process engines run before the networked ones when chosen
        # explicitly; in "auto" they come last so a running host wins
        if self.chat_backend == "llamacpp":
            engines.insert(0, ("llamacpp", self.llamacpp))
        elif self.chat_backend == "hf":
            engines.insert(0, ("hf", self.hf))
        elif self.chat_backend == "auto":
            engines += [("llamacpp", self.llamacpp), ("hf", self.hf)]
        if self.chat_backend == "brain" or not engines:
            return None
        history = [{"role": "user" if e["role"] == "user" else "assistant",
                    "content": e["content"]}
                   for e in self.episodes.recent_dialogue(k=6)]
        for name, client in engines:
            if not client.available():
                continue
            # a user-picked model applies to its own engine only
            model = self.chat_model if self.chat_backend == name else None
            answer = client.chat(text, history, model=model)
            if answer:
                if client.learn:
                    # internalise the hosted answer so the self-trained brain
                    # owns this knowledge next time
                    self.memory.add(qn, answer[:600], replace_question=qn)
                    self._ingest(f"user: {text} mygpt: {answer[:600]}")
                return answer, name, bool(client.learn)
        return None

    def save(self, force: bool = False) -> None:
        """Persist full state. Debounced: rapid consecutive calls (one per
        chat turn) coalesce into a single disk write; pass force=True for
        user-critical state (teach, checkpoints, corrections)."""
        now = time.time()
        if not force and now - self._last_save < SAVE_MIN_GAP_S:
            self._save_pending = True
            return
        self._last_save = now
        self._save_pending = False
        self._write_locked()

    def _write_locked(self) -> None:
        """The actual writes, serialised against the trainer's own flushes."""
        with self._save_lock:
            self._write_state()

    def _write_state(self) -> None:
        self._write("memory.json", self.memory.to_list())
        self._write("corpus.json", self.corpus[-5000:])
        self._write("metrics.json", {
            "counters": self.counters,
            "loss_history": self.loss_history[-200:],
            "events": self.events[-40:],
        })
        self.store.save()
        self.episodes.save()
        self.goals.save()
        self.lm.save(os.path.join(self.data_dir, "lm_weights.npz"))

    def _flush_on_exit(self) -> None:
        """atexit hook: never lose a debounced write on clean shutdown."""
        if self._save_pending:
            try:
                self.save(force=True)
            except Exception:
                pass

    def _write(self, name: str, obj) -> None:
        tmp = os.path.join(self.data_dir, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(self.data_dir, name))

    def _log(self, text: str) -> None:
        self.events.append({"t": round(time.time()), "text": text})
        self.events = self.events[-40:]

    # ------------------------------------------------------------- utilities
    def _ingest(self, text: str, train: bool = True) -> None:
        self.corpus.append(text)
        self.lm.observe(text)
        if train:
            self._maybe_auto_train()

    def _maybe_auto_train(self) -> None:
        """Count a learning event and, every AUTO_TRAIN_EVERY of them, queued.

        The round is handed to the background trainer rather than run here: this
        is called from inside a chat turn, and a round is seconds of locked CPU
        on the very thread that owes the user an answer.
        """
        self.counters["events_since_train"] += 1
        if self.counters["events_since_train"] >= AUTO_TRAIN_EVERY:
            self.train(epochs=AUTO_TRAIN_EPOCHS, reason="auto training",
                       requirement="background")

    def train(self, epochs: int = 10, reason: str = "manual",
              requirement: str = "explicit") -> dict:
        """Train the brain.

        ``requirement`` says who is asking:

        * ``"explicit"`` (default) — you asked, so block and do the work now.
          ``/api/train`` and the first-boot round use this.
        * ``"background"`` — upkeep nobody is waiting on (seed updates, the
          checkpoint command's "train and save"). The trainer queue does the
          epochs, so the request returns in milliseconds and the round runs
          **while the app is idle**, at the configured duty cycle.

        Before v1.11.0 this distinction did not exist: ``_maybe_auto_train``
        called this method from inside the chat turn, so every fifth learning
        event blocked the answer for the whole round (seconds, with the model
        locked). That is exactly the stall the background trainer exists to
        avoid — it just was not the path being used.
        """
        if requirement == "background":
            return self._submit_background_round(epochs, reason)
        if not self.corpus:
            return {"ok": False, "error": "corpus is empty"}
        t0 = time.time()
        # Grow vocabulary if the corpus is pressing against the cap.
        if len(self.lm.word_counts) > self.lm.vocab_size * 0.8:
            self.lm.rebuild_vocab()
        stats = self.lm.train(self.corpus, epochs=epochs)
        took_ms = int((time.time() - t0) * 1000)
        self._record_round(stats, epochs, reason, took_ms)
        return {"ok": True, **self.loss_history[-1]}

    def _submit_background_round(self, epochs: int, reason: str) -> dict:
        """Queue a full round for the background trainer; return immediately."""
        if not self.corpus:
            return {"ok": False, "error": "corpus is empty"}
        queued = self.trainer.submit_round(self.corpus, epochs=epochs,
                                           reason=reason)
        if not queued:
            return {"ok": True, "deferred": False, "queued": False,
                    "reason": reason,
                    "note": "a round is already queued or the queue is full"}
        self._log(f"queued a background training round "
                  f"({epochs} epochs, {reason})")
        return {"ok": True, "deferred": True, "queued": True, "epochs": epochs,
                "reason": reason,
                "note": "training runs in the background while the app is idle"}

    def _record_round(self, stats: dict, epochs: int, reason: str,
                      took_ms: int) -> dict:
        """Book-keeping shared by explicit rounds and finished background ones."""
        last = stats.get("loss_last")
        self.counters["train_rounds"] += 1
        self.counters["events_since_train"] = 0
        point = {
            "t": round(time.time()),
            "loss": (round(last, 4) if last is not None else None),
            "epochs": epochs, "reason": reason,
            "vocab": self.lm.vocab_size, "took_ms": took_ms,
        }
        self.loss_history.append(point)
        self._log(f"training round #{self.counters['train_rounds']}: "
                  f"loss {point['loss']} ({reason}, {took_ms} ms)")
        self.goals.nudge("become-more-capable", 0.01)
        self.save()
        return point

    def _on_background_round(self, result: dict) -> None:
        """Called by the trainer thread when a queued round finishes."""
        stats = {"loss_last": result.get("loss_last")}
        point = self._record_round(stats, result.get("epochs", 0),
                                   f"{result.get('reason', 'auto')} (background)",
                                   result.get("took_ms", 0))
        self.store.log_metric("bg_round_cpu_ms", float(result.get("cpu_ms", 0)))
        self._log(f"background round finished: loss {point['loss']} "
                  f"({result.get('cpu_ms', 0)} ms of CPU)")

    # ------------------------------------------------------------------ chat
    def reply(self, user_text: str) -> dict:
        # hard cap: pathological inputs shouldn't blow up tokenizer/training
        text = user_text.strip()[:4000]
        qn = normalize(text)
        self.counters["messages"] += 1
        intent = classify_intent(text)
        msg_id = uuid.uuid4().hex[:10]
        record = {"id": msg_id, "user": text, "mode": None, "pair_id": None,
                  "confidence": 0.0, "intent": intent}
        self.episodes.remember("user", text)

        # 0) special math: conversions, list stats, roman numerals ------------
        special = self._special_math(text)
        if special:
            record.update(mode="math", confidence=1.0, reply=special)
            return self._after_turn(record, extract=False)

        # 0b) maths pack (v1.10): factorials, stats, geometry, finance ---------
        solved = mathx.solve(text)
        if solved:
            name, answer = solved
            record.update(mode="math", confidence=1.0, reply=answer)
            self._log(f" maths pack: {name}")
            return self._after_turn(record, extract=False)

        # 0c) text pack (v1.10): transforms, encodings, extraction --------------
        done = textfx.solve(text)
        if done:
            name, answer = done
            record.update(mode="skill", confidence=1.0, reply=answer,
                          skill=f"text:{name}")
            return self._after_turn(record, extract=False)

        # 1) arithmetic skill -------------------------------------------------
        expr = self._find_math(text)
        if expr:
            result = self._math(expr)
            if result is not None:
                record.update(mode="math", confidence=1.0,
                              reply=f"{expr.strip(' =?')} = {result}")
                return self._after_turn(record, extract=False)

        # 2) learned skill files (procedural memory) ---------------------------
        skill = self.skills.match(text)
        if skill:
            ctx = {"user": text, "brain": self, "store": self.store,
                   "memory": self.memory, "counts": dict(self.counters)}
            out = self.skills.run(skill.name, ctx, text=text)
            record.update(mode="skill", confidence=0.9, reply=out,
                          skill=skill.name)
            return self._after_turn(record, extract=False)

        # 3) code requests → answer with a code block in chat ------------------
        if codegen.wants_code(text):
            reply_text, found = codegen.code_reply(text)
            record.update(mode="code", confidence=0.85 if found else 0.3,
                          reply=reply_text)
            self._log("code request answered in chat"
                      + ("" if found else " (no template matched)"))
            return self._after_turn(record, extract=False)

        # 3b) model commands → checkpoint / train-and-checkpoint ---------------
        ckpt_reply = self._maybe_checkpoint_command(text)
        if ckpt_reply:
            record.update(mode="skill", confidence=1.0, reply=ckpt_reply)
            return self._after_turn(record, extract=False)

        # 4) new facts about the user ------------------------------------------
        extracted = self.store.extract_from_user(text)
        if extracted:
            parts = []
            for subj, pred, obj in extracted:
                self.store.add_fact(subj, pred, obj, 0.9)
                self.store.log_event("fact", {"subject": subj, "predicate": pred,
                                              "object": obj})
                parts.append(f"{subj} {pred} {obj}")
            record.update(mode="fact", confidence=1.0,
                          reply="Got it — stored as semantic fact" +
                                ("s" if len(parts) > 1 else "") + ": " +
                                "; ".join(parts) +
                                ". I'll remember that across sessions.")
            return self._after_turn(record, extract=False)

        # 5) recall stored personal facts ---------------------------------------
        fact_reply = self._fact_answer(qn)
        if fact_reply:
            record.update(mode="fact", confidence=0.95, reply=fact_reply)
            return self._after_turn(record)

        # 6) learned memory ------------------------------------------------------
        matches = self.memory.search(qn, k=1)
        if matches:
            pair, score = matches[0]
            if score >= STRONG_MATCH:
                record.update(mode="memory", pair_id=pair["id"],
                              confidence=score, reply=pair["a"])
                return self._after_turn(record)

        # 6b) selected local LLM back end fills knowledge gaps -----------------
        #     (Cortex LLMHoster and/or Ollama — both are inference/hosting
        #      runtimes; MyGPT's own brain answers when backend == "brain")
        hosted = self._backend_answer(text, qn)
        if hosted:
            answer, engine, learned = hosted
            record.update(mode=engine, confidence=0.8, reply=answer)
            self._log(f"open question answered by {engine}"
                      + ("" if learned else " (not learned)"))
            return self._after_turn(record)

        if matches:
            pair, score = matches[0]
            if score >= WEAK_MATCH:
                record.update(mode="guess", pair_id=pair["id"],
                              confidence=score,
                              reply=f"{pair['a']}\n(I'm only {round(score*100)}% sure — "
                                    f"use 👍/👎 so I can learn.)")
                return self._after_turn(record)

        # 7) unknown -> ask to be taught -----------------------------------------
        record.update(mode="curious", confidence=0.0,
                      reply=random.choice(TEACH_REPLIES), teach_prompt=True)
        return self._after_turn(record)

    def _after_turn(self, record: dict, extract: bool = True) -> dict:
        """Finalize the reply: attach a chain of thought, remember the episode,
        then run the CORTEX light-pass self-improvement."""
        self.episodes.remember("mygpt", record["reply"])
        record["chain"] = self._build_chain(record).as_dict()
        # curious replies may have been rewritten by the System-2 chain, so the
        # "install a local LLM" suggestion is attached here, after the chain
        if record["mode"] == "curious":
            nudge = self._chat_install_nudge()
            if nudge:
                record["reply"] += "\n\n" + nudge

        self.pending[record["id"]] = record
        self.last_records.append({"mode": record.get("mode"),
                                  "intent": record.get("intent", "chat"),
                                  "ts": time.time()})
        if len(self.pending) > 200:
            for k in list(self.pending)[:len(self.pending) - 200]:
                self.pending.pop(k, None)

        if extract:
            self.improver.after_turn(record["user"], record["reply"],
                                     record.get("intent", "chat"))

        return {k: record.get(k) for k in
                ("id", "reply", "mode", "confidence", "teach_prompt", "skill",
                 "chain")}

    def _build_chain(self, record: dict):
        """System-1 trace for fast modes; full System-2 deliberation otherwise."""
        from .reason import FAST_MODES, question_kind
        mode = record["mode"]
        # Compare questions need both sides — never short-circuit on one match.
        needs_deliberation = question_kind(record["user"]) == "compare"
        if mode in FAST_MODES and not needs_deliberation:
            return self.reasoner.wrap_fast(record["user"], mode, record["reply"])
        qn = normalize(record["user"])
        articles = [Article(p["q"], p["a"])
                    for p, s in self.memory.search(qn, k=3) if s >= 0.25]
        memories = self.episodes.search(record["user"], k=4)
        # skip bookkeeping facts (imports) so real memories ground the chain
        facts = [f for f in self.store.facts_about(qn, k=4) if f.subject != "import"]
        chain = self.reasoner.deliberate(record["user"],
                                         record.get("intent", "chat"),
                                         memories, facts, articles,
                                         record["reply"])
        if mode == "curious" and chain.answer:
            record["reply"] = (chain.answer.rstrip() +
                               " Teach me an answer in the Learn panel and it "
                               "becomes permanent knowledge.")
            chain.answer = record["reply"]
        return chain

    def _fact_answer(self, qn: str) -> str | None:
        if not re.search(r"\b(my|me|i|mine)\b", qn) and "note" not in qn:
            return None
        facts = [f for f in self.store.facts_about(qn, k=4) if f.subject == "user"]
        if not facts:
            return None
        parts = []
        for f in facts:
            pred = f.predicate.replace("_", " ")
            if f.predicate == "name":
                parts.append(f"your name is {f.obj}")
            elif f.predicate == "lives_in":
                parts.append(f"you live in {f.obj}")
            elif f.predicate == "likes":
                parts.append(f"you like {f.obj}")
            elif f.predicate == "works":
                parts.append(f"you work {f.obj}")
            elif f.predicate == "note":
                parts.append(f"you noted: {f.obj}")
            elif f.predicate.startswith("favorite"):
                parts.append(f"your {f.predicate.split('_', 1)[1]} is {f.obj}")
            else:
                parts.append(f"{pred}: {f.obj}")
        return ("From what you told me earlier — " + "; ".join(parts) +
                ". (semantic facts, extracted and stored automatically)")

    _NUM_WORDS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100,
    }

    @staticmethod
    def _word_math(text: str) -> str:
        """Rewrite spoken arithmetic ('6 times 7', 'seven plus eight',
        'square root of 144', '20 percent of 150') into symbols."""
        low = " " + text.lower() + " "
        rules = (
            (r" times ", " * "), (r" multiplied by ", " * "),
            (r" plus ", " + "), (r" added to ", " + "),
            (r" minus ", " - "), (r" subtracted from ", " - "),
            (r" divided by ", " / "), (r" over ", " / "),
            (r" to the power of ", " ^ "), (r" squared ", " ^ 2 "),
            (r" mod ", " % "),
            (r" square root of ", " sqrt "), (r" sqrt of ", " sqrt "),
            (r" percent of ", " %of "), (r"%\s*of ", " %of "),
        )
        for pat, repl in rules:
            low = re.sub(pat, repl, low)
        # number words -> digits ("seven times eight" handled after operators)
        for word, val in Brain._NUM_WORDS.items():
            low = re.sub(rf"\b{word}\b", f" {val} ", low)
        low = re.sub(r"\s+", " ", low)
        return low

    @staticmethod
    def _find_math(text: str) -> str | None:
        """Find an arithmetic expression: either the whole message or embedded."""
        text = Brain._word_math(text)
        m = re.search(r"sqrt\s*(\d+(?:\.\d+)?)", text)
        if m:
            return f"({m.group(1)}) ** 0.5"
        m = re.search(r"(\d+(?:\.\d+)?)\s*%of\s*(\d+(?:\.\d+)?)", text)
        if m:
            return f"{m.group(1)} / 100 * {m.group(2)}"
        if MATH_RE.match(text) and re.search(r"[+\-*/%^]", text):
            return text
        m = re.search(r"[(]*\d[\d\s+\-*/().%^]*[+\-*/%^][\d\s().]*\d", text)
        return m.group(0) if m else None

    @staticmethod
    def _math(text: str) -> str | None:
        expr = text.replace("^", "**").replace(",", ".")
        try:
            value = eval(expr, {"__builtins__": {}}, {})  # digits/operators only
        except ZeroDivisionError:
            return "undefined — division by zero"
        except Exception:
            return None
        try:
            if isinstance(value, complex) or value != value:
                return None
            if abs(value) > 1e15:
                return f"{value:.6e}"
            if float(value).is_integer():
                return str(int(value))
            return f"{value:.6g}"
        except Exception:
            return None

    # ------------------------------------------------ special math (v1.9)
    _UNITS = {  # canonical: meters / kilograms
        "m": ("len", 1.0), "meter": ("len", 1.0), "meters": ("len", 1.0),
        "metre": ("len", 1.0), "metres": ("len", 1.0),
        "km": ("len", 1000.0), "kms": ("len", 1000.0),
        "cm": ("len", 0.01), "cms": ("len", 0.01),
        "mm": ("len", 0.001),
        "mile": ("len", 1609.344), "miles": ("len", 1609.344),
        "mi": ("len", 1609.344),
        "inch": ("len", 0.0254), "inches": ("len", 0.0254),
        "foot": ("len", 0.3048), "feet": ("len", 0.3048), "ft": ("len", 0.3048),
        "yard": ("len", 0.9144), "yards": ("len", 0.9144),
        "kg": ("mass", 1.0), "kgs": ("mass", 1.0), "kilo": ("mass", 1.0),
        "kilos": ("mass", 1.0), "kilogram": ("mass", 1.0),
        "kilograms": ("mass", 1.0),
        "g": ("mass", 0.001), "gram": ("mass", 0.001), "grams": ("mass", 0.001),
        "pound": ("mass", 0.45359237), "pounds": ("mass", 0.45359237),
        "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237),
        "ounce": ("mass", 0.028349523), "ounces": ("mass", 0.028349523),
        "oz": ("mass", 0.028349523),
    }
    _TEMP_IN = {"c": "c", "celsius": "c", "°c": "c",
                "f": "f", "fahrenheit": "f", "°f": "f"}
    _ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
              (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
              (5, "V"), (4, "IV"), (1, "I"))

    @staticmethod
    def _to_roman(n: int) -> str:
        out = []
        for val, sym in Brain._ROMAN:
            while n >= val:
                out.append(sym)
                n -= val
        return "".join(out) or "0"

    @staticmethod
    def _from_roman(s: str) -> int | None:
        vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total, prev = 0, 0
        for ch in reversed(s.upper()):
            v = vals.get(ch)
            if v is None:
                return None
            total += v if v >= prev else -v
            prev = max(prev, v)
        # reject non-canonical spellings like "IIII" or "VX"
        if total < 1 or total > 3999 or Brain._to_roman(total) != s.upper():
            return None
        return total

    @staticmethod
    def _fmt(x: float) -> str:
        return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:.6g}"

    @classmethod
    def _special_math(cls, text: str) -> str | None:
        """Conversions and list stats that plain arithmetic can't express."""
        low = " " + text.lower().strip() + " "
        # percent change from A to B
        m = re.search(r"percent(?:age)? change from (-?\d+(?:\.\d+)?) to "
                      r"(-?\d+(?:\.\d+)?)", low)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if a == 0:
                return "undefined — percent change from zero"
            return f"percent change {cls._fmt(a)} → {cls._fmt(b)} = " \
                   f"{cls._fmt((b - a) / abs(a) * 100)}%"
        # X% off Y
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s*off\s*"
                      r"(-?\d+(?:\.\d+)?)", low)
        if m:
            off, price = float(m.group(1)), float(m.group(2))
            return f"{cls._fmt(off)}% off {cls._fmt(price)} = " \
                   f"{cls._fmt(price * (1 - off / 100))}"
        # A is what percent of B
        m = re.search(r"(-?\d+(?:\.\d+)?) is what percent(?:age)? of "
                      r"(-?\d+(?:\.\d+)?)", low)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            if b == 0:
                return "undefined — division by zero"
            return f"{cls._fmt(a)} is {cls._fmt(a / b * 100)}% of {cls._fmt(b)}"
        # average / mean / sum / total / max / min of a number list
        m = re.search(r"(?:average|mean|sum|total|max(?:imum)?|min(?:imum)?) "
                      r"of ([\d]+(?:[\s,.]+[\d]+)*)", low)
        if m:
            nums = [float(n) for n in re.split(r"[\s,.]+| and ", m.group(1))
                    if n.strip()]
            if nums:
                kind = m.group(0).split(" of ")[0].strip()
                val = {"average": sum(nums) / len(nums),
                       "mean": sum(nums) / len(nums),
                       "sum": sum(nums), "total": sum(nums),
                       "max": max(nums), "maximum": max(nums),
                       "min": min(nums), "minimum": min(nums)}[kind]
                return f"{kind} of {', '.join(cls._fmt(n) for n in nums)} = " \
                       f"{cls._fmt(val)}"
        # half / double / triple of X
        m = re.search(r"\b(half|double|twice|triple|thrice) of "
                      r"(-?\d+(?:\.\d+)?)", low)
        if m:
            op, x = m.group(1), float(m.group(2))
            val = x / 2 if op == "half" else x * 2 if op in ("double", "twice") \
                else x * 3
            return f"{op} of {cls._fmt(x)} = {cls._fmt(val)}"
        # number -> roman
        m = re.search(r"(-?\d{1,4})\s*(?:in|to|as)\s*roman", low)
        if m and 1 <= int(m.group(1)) <= 3999:
            return f"{m.group(1)} in roman numerals = {cls._to_roman(int(m.group(1)))}"
        # roman -> number
        m = re.search(r"\b([ivxlcdm]{2,10})\b\s*(?:in|to|as)\s*"
                      r"(?:numbers?|decimal|digits)", low)
        if m:
            val = cls._from_roman(m.group(1))
            if val is not None:
                return f"{m.group(1).upper()} = {val}"
        # temperature conversion
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*°?\s*(c|celsius|f|fahrenheit)\b"
                      r"\s*(?:in|to|into)\s*°?\s*(c|celsius|f|fahrenheit)\b",
                      low)
        if m:
            x = float(m.group(1))
            src, dst = m.group(2)[0], m.group(3)[0]
            if src == dst:
                return None
            val = x * 9 / 5 + 32 if src == "c" else (x - 32) * 5 / 9
            return f"{cls._fmt(x)} °{src.upper()} = {cls._fmt(val)} °{dst.upper()}"
        # length / mass conversion
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*(°?\s*[a-z]+)\s*"
                      r"(?:in|to|into)\s*(°?\s*[a-z]+)", low)
        if m:
            src = m.group(2).strip().lstrip("°")
            dst = m.group(3).strip().lstrip("°")
            s, d = cls._UNITS.get(src), cls._UNITS.get(dst)
            if s and d and s[0] == d[0] and src != dst:
                val = float(m.group(1)) * s[1] / d[1]
                return f"{cls._fmt(float(m.group(1)))} {src} = " \
                       f"{cls._fmt(val)} {dst}"
        return None

    # ------------------------------------------------------- quick answering
    def quick_answer(self, text: str) -> str:
        """Side-effect-free answer used by the self-eval battery."""
        special = self._special_math(text)
        if special:
            return special
        solved = mathx.solve(text)
        if solved:
            return solved[1]
        done = textfx.solve(text)
        if done:
            return done[1]
        expr = self._find_math(text)
        if expr:
            result = self._math(expr)
            if result is not None:
                return f"{expr} = {result}"
        qn = normalize(text)
        if "principle" in qn:
            return "; ".join(self.store.principles)
        matches = self.memory.search(qn, k=1)
        if matches and matches[0][1] >= WEAK_MATCH:
            return matches[0][0]["a"]
        facts = [f for f in self.store.facts_about(qn, k=3) if f.subject == "user"]
        if facts:
            return " ".join(f"{f.subject} {f.predicate} {f.obj}" for f in facts)
        return ""

    # -------------------------------------------------------------- feedback
    def feedback(self, msg_id: str, verdict: str,
                 correction: str | None = None) -> dict:
        record = self.pending.get(msg_id)
        if record is None:
            return {"ok": False, "error": "unknown message"}
        if verdict not in ("up", "down"):
            return {"ok": False, "error": "bad verdict"}

        user_q = normalize(record["user"])
        if verdict == "up":
            self.counters["up"] += 1
            if record["pair_id"]:
                self.memory.reinforce(record["pair_id"], +0.25)
            self._ingest(f"user: {record['user']} mygpt: {_strip_md(record['reply'])}")
            self._log("positive feedback received — reinforced")
            self.save(force=True)
            return {"ok": True, "message": "Noted — that answer got stronger. 💪"}

        # thumbs down
        self.counters["down"] += 1
        if record["pair_id"]:
            self.memory.reinforce(record["pair_id"], -0.35)
        if correction and correction.strip():
            self.counters["corrections"] += 1
            self.memory.add(user_q, correction.strip(),
                            replace_question=user_q if record["pair_id"] else None)
            self._ingest(f"user: {record['user']} mygpt: {correction.strip()}")
            self._log(f"correction learned: '{user_q[:30]}…'")
            self.save(force=True)
            return {"ok": True, "message": "Thanks — I replaced that answer with yours."}
        self.save(force=True)
        return {"ok": True,
                "message": "Understood. Tell me the right answer and I'll learn it."}

    def teach(self, question: str, answer: str) -> dict:
        q, a = question.strip(), answer.strip()
        if not q or not a:
            return {"ok": False, "error": "question and answer are required"}
        qn = normalize(q)
        self.counters["teachings"] += 1
        self.memory.add(qn, a, replace_question=qn)
        self._ingest(f"user: {q} mygpt: {a}")
        self._log(f"taught: '{qn[:36]}'")
        self.save(force=True)
        return {"ok": True, "pairs": len(self.memory.pairs)}

    def teach_many(self, pairs: list) -> dict:
        """Bulk teaching: validate + store many Q→A pairs in one call."""
        stored, errors = 0, []
        for i, item in enumerate(pairs[:100]):
            if not isinstance(item, dict):
                errors.append({"index": i, "error": "not an object"})
                continue
            q = item.get("question") or item.get("q") or ""
            a = item.get("answer") or item.get("a") or ""
            if not isinstance(q, str) or not isinstance(a, str):
                errors.append({"index": i, "error": "question/answer must be text"})
                continue
            q, a = q.strip()[:500], a.strip()[:4000]
            if not q or not a:
                errors.append({"index": i, "error": "empty question or answer"})
                continue
            qn = normalize(q)
            self.memory.add(qn, a, replace_question=qn)
            self._ingest(f"user: {q} mygpt: {a}")
            stored += 1
        if stored:
            self.counters["teachings"] += stored
            self._log(f"bulk taught {stored} pair(s)")
            self.save(force=True)
        return {"ok": stored > 0 or not errors, "stored": stored,
                "failed": len(errors), "errors": errors,
                "pairs": len(self.memory.pairs)}

    def clear_transcript(self) -> dict:
        """Wipe the visible/saved conversation only — learned knowledge stays."""
        n = self.episodes.clear()
        self.pending.clear()
        self.last_records.clear()
        self._log(f"transcript cleared ({n} episode(s) forgotten)")
        return {"ok": True, "cleared": n}

    def search_memory(self, query: str, k: int = 5) -> list[dict]:
        """Ranked search over the memory layer (question, answer, score)."""
        qn = normalize(query)
        if not qn:
            return []
        return [{"q": p["q"], "a": p["a"], "weight": round(p.get("w", 1.0), 3),
                 "hits": p.get("hits", 0), "score": round(float(s), 4),
                 "id": p.get("id")}
                for p, s in self.memory.search(qn, k=k)]

    def suggest(self, fragment: str, k: int = 6) -> list[str]:
        """Question-title autocomplete from everything the memory layer knows."""
        frag = normalize(fragment)
        if not frag:
            return []
        scored = []
        for p in self.memory.pairs:
            q = p["q"]
            if frag in q:
                scored.append((0 if q.startswith(frag) else 1, len(q), q))
        scored.sort()
        return [q for _, _, q in scored[:k]]

    def analytics(self) -> dict:
        """Aggregate counters, per-intent / per-mode histograms and activity."""
        modes: dict[str, int] = {}
        intents: dict[str, int] = {}
        for rec in self.last_records:
            key = rec.get("mode") or "none"
            modes[key] = modes.get(key, 0) + 1
            ik = rec.get("intent") or "chat"
            intents[ik] = intents.get(ik, 0) + 1
        per_hour: dict[str, int] = {}
        for ep in self.episodes.episodes:
            key = time.strftime("%Y-%m-%d %H:00", time.localtime(ep.get("ts", 0)))
            per_hour[key] = per_hour.get(key, 0) + 1
        counts = self.store.counts()
        return {
            "counters": dict(self.counters),
            "pairs": len(self.memory.pairs),
            "episodes": len(self.episodes.episodes),
            "facts": counts["facts"],
            "modes": modes,
            "intents": intents,
            "busiest_hours": sorted(per_hour.items(),
                                    key=lambda kv: -kv[1])[:8],
            "self_eval_score": (self.store.metric_series("self_eval", 1) or
                                [{"v": None}])[-1].get("v"),
            "top_memories": sorted(
                ({"q": p["q"], "hits": p.get("hits", 0)} for p in self.memory.pairs),
                key=lambda d: -d["hits"])[:10],
        }

    def export_json(self) -> dict:
        """Structured transcript export (roles, intents, timestamps, replies)."""
        from . import __version__          # imported late to avoid a cycle
        return {
            "app": "MyGPT",
            "version": __version__,
            "author": codegen.AUTHOR,
            "github": codegen.GITHUB_URL,
            "generated": int(time.time()),
            "counters": dict(self.counters),
            "messages": [
                {"ts": ep.get("ts"), "role": ep.get("role"),
                 "content": ep.get("content"), "intent": ep.get("intent",
                                                                  "unknown")}
                for ep in self.episodes.episodes],
        }

    # ------------------------------------------------------------ improvement
    def improve_cycle(self, reason: str = "manual") -> list[dict]:
        return self.improver.cycle(reason=reason)

    def run_self_eval(self) -> dict:
        """Run the self-evaluation battery on demand; score is charted too."""
        report = self.improver.self_eval_report()
        self.store.log_metric("self_eval", report["score"])
        self.store.log_event("self_eval", {"score": report["score"],
                                           "hits": report["hits"],
                                           "total": report["total"],
                                           "reason": "manual"})
        self._log(f"self-evaluation: {report['hits']}/{report['total']} "
                  f"({round(report['score'] * 100)}%)")
        self.save()
        return report

    def export_transcript(self) -> str:
        """Render the episodic conversation history as Markdown."""
        from datetime import datetime
        lines = ["# MyGPT — conversation export", "",
                 f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 f"Episodes: {len(self.episodes.episodes)}", "", "---", ""]
        prev_role = None
        for ep in self.episodes.episodes:
            ts = datetime.fromtimestamp(ep["ts"]).strftime("%H:%M:%S")
            who = "🧑 You" if ep["role"] == "user" else "🤖 MyGPT"
            if ep["role"] != prev_role:
                lines.append(f"**{who}** · {ts}")
                prev_role = ep["role"]
            lines.append(f"> {ep['content']}")
            lines.append("")
        lines += ["---", "", "Made with ❤️ by codero-sus — "
                  "https://github.com/codero-sus · https://the-codero.web.app/"]
        return "\n".join(lines)

    def forget(self, query: str) -> int:
        n = self.store.forget_facts(query)
        if n:
            self.store.log_event("forget", {"q": query, "removed": n})
            self.save()
        return n

    def _dream_text(self) -> str:
        """Distilled mind state the idle trainer re-learns (dream replay)."""
        principles = "\n".join(f"- {p}" for p in self.store.principles[-8:])
        facts = "; ".join(f"{f.subject} {f.predicate} {f.obj}"
                          for f in self.store.all_facts(k=12))
        lessons = "\n".join(self.store.lessons(k=6))
        dialogue = "\n".join(self.corpus[-8:])
        episodes = "\n".join(f"{e['role']}: {e['content'][:160]}"
                             for e in self.episodes.recent_dialogue(k=6))
        return (f"I am MyGPT, a self-training chatbot.\n"
                f"Principles:\n{principles}\nFacts: {facts}\n"
                f"Lessons:\n{lessons}\nDialogue:\n{dialogue}\n"
                f"Recent episodes:\n{episodes}")[:4000]

    def _log_safe(self, message: str) -> None:
        """Log before the event buffer exists (early __init__ failures)."""
        if hasattr(self, "events"):
            self._log(message)
        else:                                        # pragma: no cover
            print(f"[mygpt] {message}")

    def _make_lm(self, arch: str):
        """Build the language model for `arch` ('transformer' or 'mlp').

        The transformer is the same public API as NeuralLM, so the trainer,
        checkpoints and generation code all work unchanged. If a *transformer*
        cannot be built (very old NumPy, exotic platform) we fall back to the
        MLP rather than refusing to boot.
        """
        if arch in ("mlp", "ffn", "neural"):
            self.arch = "mlp"
            return NeuralLM()
        try:
            model = TransformerLM(
                dim=int(os.environ.get("MYGPT_DIM", 64) or 64),
                heads=int(os.environ.get("MYGPT_HEADS", 4) or 4),
                blocks=int(os.environ.get("MYGPT_BLOCKS", 2) or 2),
                ctx=int(os.environ.get("MYGPT_CTX", 6) or 6),
                dropout=float(os.environ.get("MYGPT_DROPOUT", 0.0) or 0.0),
                lr=float(os.environ.get("MYGPT_LR", 3e-3) or 3e-3),
            )
            self.arch = "transformer"
            return model
        except Exception as exc:                     # pragma: no cover
            self._log_safe(f"transformer unavailable ({exc}); using the MLP brain")
            self.arch = "mlp"
            return NeuralLM()

    def model_card(self) -> dict:
        """Human-readable description of the brain that is loaded right now."""
        lm = self.lm
        card = {
            "arch": getattr(lm, "arch", "mlp"),
            "vocab": lm.vocab_size,
            "params": (lm.param_count() if hasattr(lm, "param_count")
                       else int(getattr(lm, "E", None).size if getattr(lm, "E", None) is not None else 0)),
            "context": getattr(lm, "ctx", 4),
            "corpus_lines": len(self.corpus),
            "tokens_trained": sum(len(t.split()) for t in self.corpus),
            "loss_history": self.loss_history[-40:],
            "last_loss": (self.loss_history[-1]["loss"]
                          if self.loss_history else None),
            "training_steps": getattr(lm, "step_count", 0),
            "checkpoints": len(self.checkpoints.list()),
            "backends": self.backend_summary(),
        }
        if hasattr(lm, "describe"):
            card.update({k: v for k, v in lm.describe().items()
                         if k not in ("params", "vocab")})
        return card

    def backend_summary(self) -> dict:
        """Which engines can answer right now, and why not when they can't."""
        return {
            "brain": {"available": True, "label": "MyGPT self-trained brain",
                      "arch": getattr(self.lm, "arch", "mlp")},
            "cortex": {**self.cortex.probe(), "available": self.cortex.available()},
            "ollama": {**self.ollama.probe(), "available": self.ollama.available()},
            "llamacpp": {**self.llamacpp.probe(),
                         "available": self.llamacpp.available()},
            "hf": {**self.hf.probe(), "available": self.hf.available()},
        }

    def import_history(self, filename: str, data: bytes) -> dict:
        """Absorb an exported chat history (WhatsApp/ChatGPT/Claude/Telegram/…)."""
        return importers.absorb(self, filename, data)

    # ----------------------------------------------------------------- extra
    def dream(self, n_tokens: int = 40) -> str:
        text = self.lm.generate(n_tokens=n_tokens)
        return text or "… my weights are still too young to dream."

    def stats(self) -> dict:
        counts = self.store.counts()
        return {
            "counters": self.counters,
            "pairs": len(self.memory.pairs),
            "vocab_size": self.lm.vocab_size,
            "arch": getattr(self.lm, "arch", "mlp"),
            "params": (self.lm.param_count() if hasattr(self.lm, "param_count")
                       else None),
            "training_steps": getattr(self.lm, "step_count", 0),
            "corpus_lines": len(self.corpus),
            "tokens_trained": sum(len(t.split()) for t in self.corpus),
            "loss_history": self.loss_history[-60:],
            "events": list(reversed(self.events[-12:])),
            "last_loss": self.loss_history[-1]["loss"] if self.loss_history else None,
            "uptime_s": int(time.time() - self.started),
            # self-learning (CORTEX loop)
            "constitution_version": self.store.constitution_version,
            "principles": len(self.store.principles),
            "facts": counts["facts"],
            "lessons": counts["lessons"],
            "episodes": len(self.episodes.episodes),
            "imports": self.counters.get("imports", 0),
            "goals": self.goals.snapshot(),
            "github": codegen.GITHUB_URL,
            "author": codegen.AUTHOR,
            "website": codegen.WEBSITE_URL,
            "cortex": self.cortex.probe(),
            "ollama": self.ollama.probe(),
            "backends": self.backends(),   # includes auto_probe + install_hint
            "checkpoints": self.checkpoints.list(),
            "mind": {
                "facts": [{"subject": f.subject, "predicate": f.predicate,
                            "object": f.obj, "confidence": f.confidence}
                           for f in self.store.all_facts(k=24)],
                "lessons": list(reversed(self.store.lessons(k=16))),
                "principles": self.store.principles,
                "constitution_version": self.store.constitution_version,
                "skills": self.skills.list(),
                "trainer": self.trainer.snapshot(),
                "self_eval": self.store.metric_series("self_eval", 40),
                "bg_loss": self.store.metric_series("loss", 80),
                "events": self.store.recent_events(24),
                "improver": self.improver.snapshot(),
            },
        }

    def recent_pairs(self, limit: int = 12) -> list[dict]:
        items = sorted(self.memory.pairs, key=lambda p: p.get("created", 0),
                       reverse=True)[:limit]
        return [{"id": p["id"], "q": p["q"], "a": p["a"],
                 "w": round(p["w"], 2), "hits": p["hits"]} for p in items]


def _strip_md(text: str) -> str:
    return re.sub(r"[*_()\[\]]", "", text).strip()
