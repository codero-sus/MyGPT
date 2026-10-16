"""🤗 transformers backend — run a HuggingFace causal LM inside MyGPT.

The `transformers <https://github.com/huggingface/transformers>`_ library is the
standard way to run GPT/Llama/Qwen/Phi-family checkpoints in Python. This
client loads a causal LM (from the HuggingFace Hub **or** a local directory) and
answers chat turns with it, exactly like the Cortex/Ollama/llama.cpp backends.

    pip install transformers torch        # torch is required for weights

Configuration (persisted in ``data/hf.json``; env vars seed defaults):

    MYGPT_HF_MODEL      a repo id (``Qwen/Qwen2.5-0.5B-Instruct``) or a local
                        directory containing config.json + weights
    MYGPT_HF_ENABLED    0/false/no to disable
    MYGPT_HF_LEARN      0/false/no to not internalise answers (default 1)
    MYGPT_HF_DEVICE     ``cpu`` (default), ``cuda``, ``mps``, ``auto``
    MYGPT_HF_DTYPE      ``auto`` (default), ``float32``, ``bfloat16``, ...
    MYGPT_HF_MAX_TOKENS max new tokens per reply (default 256)
    MYGPT_HF_OFFLINE    1 to never touch the network (local dirs only)

Why a separate module from the llama.cpp one: this path is pure Python/PyTorch
(easy for GPUs and for any checkpoint on the Hub), while llama.cpp runs GGUF
files through C++ on the CPU. Both are optional; if neither is installed MyGPT
keeps answering from its own self-trained transformer.
"""

from __future__ import annotations

import json
import os
import threading
import time

HEALTH_TTL = 10.0
PROJECT_URL = "https://github.com/huggingface/transformers"
MAX_HISTORY_TURNS = 6
SYSTEM_PROMPT = ("You are MyGPT, a small local assistant. Answer briefly and "
                 "concretely. If you do not know something, say so.")


def _flag(value, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


class HFClient:
    """Loads a HuggingFace causal LM and answers turns with it."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        env = os.environ
        self.enabled = _flag(env.get("MYGPT_HF_ENABLED"), True)
        self.learn = _flag(env.get("MYGPT_HF_LEARN"), True)
        self.model = env.get("MYGPT_HF_MODEL", "") or ""
        self.device = env.get("MYGPT_HF_DEVICE", "cpu") or "cpu"
        self.dtype = env.get("MYGPT_HF_DTYPE", "auto") or "auto"
        self.max_tokens = int(env.get("MYGPT_HF_MAX_TOKENS", 256) or 256)
        self.temperature = float(env.get("MYGPT_HF_TEMPERATURE", 0.7) or 0.7)
        self.top_p = float(env.get("MYGPT_HF_TOP_P", 0.95) or 0.95)
        self.offline = _flag(env.get("MYGPT_HF_OFFLINE"), False)
        self.answers = 0
        self.load_seconds: float | None = None
        self.loaded_model: str | None = None
        self.last_error = ""
        self._pipe = None
        self._lock = threading.RLock()
        self._cache: tuple[float, dict] | None = None
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, encoding="utf-8") as handle:
                    saved = json.load(handle)
                for key in ("enabled", "learn", "model", "device", "dtype",
                            "max_tokens", "temperature", "top_p", "offline"):
                    if key in saved:
                        setattr(self, key, saved[key])
            except Exception:
                pass

    # ------------------------------------------------------------------ config
    def configure(self, **kwargs) -> dict:
        clean = {}
        allowed = ("enabled", "learn", "model", "device", "dtype", "max_tokens",
                   "temperature", "top_p", "offline")
        for key, value in kwargs.items():
            if key not in allowed:
                continue
            if key in ("enabled", "learn", "offline"):
                value = bool(value)
            elif key == "model":
                value = str(value or "")
            elif key == "max_tokens":
                value = int(value)
            else:
                value = float(value) if key in ("temperature", "top_p") else str(value)
            setattr(self, key, value)
            clean[key] = value
        if "model" in clean or "device" in clean or "dtype" in clean:
            self.unload()
        self._cache = None
        self._persist()
        return clean

    def _persist(self) -> None:
        if not self.config_path:
            return
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump({"enabled": self.enabled, "learn": self.learn,
                           "model": self.model, "device": self.device,
                           "dtype": self.dtype, "max_tokens": self.max_tokens,
                           "temperature": self.temperature, "top_p": self.top_p,
                           "offline": self.offline}, handle, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------- state
    def packages(self) -> tuple[bool, bool, str, str]:
        """(transformers?, torch?, transformers version, torch version)."""
        tf_ok = torch_ok = False
        tf_v = torch_v = ""
        try:
            import transformers
            tf_ok, tf_v = True, getattr(transformers, "__version__", "")
        except Exception as exc:
            self.last_error = f"transformers not importable: {exc}"
        try:
            import torch
            torch_ok, torch_v = True, getattr(torch, "__version__", "")
        except Exception:
            torch_ok = False
        return tf_ok, torch_ok, tf_v, torch_v

    def model_resolvable(self) -> tuple[bool, str]:
        """Can we name a checkpoint? (local dir verified, hub id assumed)."""
        if not self.model:
            return False, "no model configured (set MYGPT_HF_MODEL)"
        if os.path.isdir(self.model):
            has_config = os.path.exists(os.path.join(self.model, "config.json"))
            if not has_config:
                return False, f"{self.model} has no config.json"
            return True, "local directory"
        if self.offline:
            return False, "offline mode is on and the model is not a local directory"
        return True, "huggingface hub id (downloads on first use)"

    def available(self) -> bool:
        tf_ok, torch_ok, _v, _tv = self.packages()
        return bool(self.enabled and tf_ok and torch_ok
                    and self.model_resolvable()[0])

    def health(self) -> bool:
        return self.available()

    def probe(self) -> dict:
        if self._cache and time.time() - self._cache[0] < HEALTH_TTL:
            return dict(self._cache[1])
        tf_ok, torch_ok, tf_v, torch_v = self.packages()
        resolvable, why = self.model_resolvable()
        reason = ""
        if not tf_ok:
            reason = "transformers is not installed — run `pip install transformers`"
        elif not torch_ok:
            reason = ("PyTorch is not installed — run `pip install torch` "
                      "(transformers needs it to load weights)")
        elif not resolvable:
            reason = why
        elif not self.enabled:
            reason = "disabled"
        info = {
            "kind": "hf",
            "label": "🤗 transformers (local / Hub)",
            "enabled": self.enabled,
            "available": self.available(),
            "reachable": self.available(),
            "package": tf_ok,
            "package_version": tf_v,
            "torch": torch_ok,
            "torch_version": torch_v,
            "model": self.model,
            "model_note": why,
            "device": self.device,
            "dtype": self.dtype,
            "loaded": self.loaded_model,
            "load_seconds": self.load_seconds,
            "answers": self.answers,
            "learn": self.learn,
            "offline": self.offline,
            "max_tokens": self.max_tokens,
            "reason": reason,
            "last_error": self.last_error,
            "project_url": PROJECT_URL,
            "install": "pip install transformers torch",
        }
        self._cache = (time.time(), dict(info))
        return info

    # ------------------------------------------------------------------- model
    def _dtype_kwarg(self):
        if self.dtype in ("auto", "", None):
            return {}
        import torch
        mapping = {"float32": torch.float32, "float16": torch.float16,
                   "bfloat16": torch.bfloat16}
        chosen = mapping.get(str(self.dtype).lower())
        return {"torch_dtype": chosen} if chosen else {}

    def load(self):
        """Load (or return) the pipeline. Raises with a clear message."""
        with self._lock:
            if self._pipe is not None and self.loaded_model == self.model:
                return self._pipe
            tf_ok, torch_ok, _v, _tv = self.packages()
            if not tf_ok:
                raise RuntimeError("transformers is not installed")
            if not torch_ok:
                raise RuntimeError("PyTorch is not installed (needed for weights)")
            resolvable, why = self.model_resolvable()
            if not resolvable:
                raise RuntimeError(why)
            if self.offline:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from transformers import pipeline
            started = time.perf_counter()
            self._pipe = pipeline(
                "text-generation", model=self.model, device=self.device,
                **self._dtype_kwarg())
            self.loaded_model = self.model
            self.load_seconds = round(time.perf_counter() - started, 2)
            self.last_error = ""
            self._cache = None
            return self._pipe

    def unload(self) -> None:
        with self._lock:
            self._pipe = None
            self.loaded_model = None
            self.load_seconds = None

    def _prompt(self, text: str, history) -> str:
        """Chat template when the tokenizer has one, plain text otherwise."""
        turns = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-MAX_HISTORY_TURNS:]:
            role = turn.get("role", "user")
            if role in ("user", "assistant"):
                turns.append({"role": role,
                              "content": str(turn.get("content", ""))})
        turns.append({"role": "user", "content": text})
        try:
            pipe = self.load()
            tokenizer = getattr(pipe, "tokenizer", None)
            if tokenizer is not None and getattr(tokenizer, "chat_template", None):
                return tokenizer.apply_chat_template(
                    turns, tokenize=False, add_generation_prompt=True)
        except Exception:
            pass
        # no template: fall back to a readable transcript
        lines = [f"System: {SYSTEM_PROMPT}"]
        lines += [f"{'User' if t['role'] == 'user' else 'MyGPT'}: {t['content']}"
                  for t in turns[1:]]
        return "\n".join(lines) + "\nMyGPT:"

    # ------------------------------------------------------------------- chat
    def chat(self, text: str, history=None, model: str | None = None) -> str | None:
        if not self.available():
            return None
        try:
            pipe = self.load()
            prompt = self._prompt(text, history)
            out = pipe(prompt, max_new_tokens=self.max_tokens,
                       do_sample=self.temperature > 0,
                       temperature=max(1e-3, self.temperature),
                       top_p=self.top_p, pad_token_id=getattr(
                           getattr(pipe, "tokenizer", None), "eos_token_id", None),
                       return_full_text=False)
            answer = ""
            if isinstance(out, list) and out:
                item = out[0]
                if isinstance(item, dict):
                    generated = item.get("generated_text", "")
                    answer = generated if isinstance(generated, str) else ""
                    if isinstance(generated, list) and generated:
                        answer = str(generated[-1].get("content", ""))
            answer = answer.strip()
            if not answer:
                return None
            self.answers += 1
            return answer
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def generate(self, prompt: str, max_tokens: int = 128,
                 temperature: float = 0.8, top_p: float = 0.95) -> str | None:
        if not self.available():
            return None
        try:
            pipe = self.load()
            out = pipe(prompt, max_new_tokens=max_tokens,
                       do_sample=temperature > 0,
                       temperature=max(1e-3, temperature), top_p=top_p,
                       return_full_text=False)
            text = ""
            if isinstance(out, list) and out and isinstance(out[0], dict):
                text = out[0].get("generated_text", "") or ""
            return str(text).strip()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def stats(self) -> dict:
        info = self.probe()
        return {"answers": self.answers, "loaded": self.loaded_model,
                "load_seconds": self.load_seconds, "model": self.model,
                "available": info.get("available")}
