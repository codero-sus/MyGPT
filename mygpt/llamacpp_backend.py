"""llama.cpp backend — run a local GGUF model inside MyGPT.

``llama-cpp-python`` is the official Python binding for
`llama.cpp <https://github.com/ggml-org/llama.cpp>`_, the C++ inference engine
behind most local LLM tooling. Unlike Cortex LLMHoster or Ollama it is **not a
server**: it loads a ``.gguf`` file directly into this process, so MyGPT can
answer with a real quantised model without anything else running.

    pip install llama-cpp-python        # compiles llama.cpp (needs a C++ toolchain)

Configuration (persisted in ``data/llamacpp.json``; env vars seed defaults):

    MYGPT_LLAMACPP_MODEL    path to a .gguf file (or a directory to scan)
    MYGPT_LLAMACPP_ENABLED  0/false/no to disable
    MYGPT_LLAMACPP_LEARN    0/false/no to not internalise answers
    MYGPT_LLAMACPP_CTX      context window (default 2048)
    MYGPT_LLAMACPP_THREADS  CPU threads (default: all cores)
    MYGPT_LLAMACPP_GPU_LAYERS  layers to offload to GPU (default 0 = pure CPU)

With no model configured the client scans ``models/*.gguf`` and
``data/models/*.gguf`` so dropping a file in is enough to enable it.

Everything here degrades gracefully: if the package is missing, or the model
file is not there, ``available()`` is False, ``probe()`` explains exactly why,
and MyGPT's own self-trained brain keeps answering.
"""

from __future__ import annotations

import glob
import json
import os
import threading
import time

HEALTH_TTL = 10.0
PROJECT_URL = "https://github.com/ggml-org/llama.cpp"
DEFAULT_CTX = 2048
SYSTEM_PROMPT = ("You are MyGPT, a small local assistant. Answer briefly and "
                 "concretely. If you do not know something, say so.")
MAX_HISTORY_TURNS = 6


def _flag(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


class LlamaCppClient:
    """Loads a GGUF model with llama.cpp and answers chat turns with it."""

    def __init__(self, config_path: str | None = None, models_dir: str | None = None):
        self.config_path = config_path
        env = os.environ
        self.enabled = _flag(env.get("MYGPT_LLAMACPP_ENABLED"), True)
        self.learn = _flag(env.get("MYGPT_LLAMACPP_LEARN"), True)
        self.model_path = env.get("MYGPT_LLAMACPP_MODEL", "") or ""
        self.n_ctx = int(env.get("MYGPT_LLAMACPP_CTX", DEFAULT_CTX) or DEFAULT_CTX)
        self.n_threads = int(env.get("MYGPT_LLAMACPP_THREADS",
                                     os.cpu_count() or 4) or 4)
        self.n_gpu_layers = int(env.get("MYGPT_LLAMACPP_GPU_LAYERS", 0) or 0)
        self.max_tokens = int(env.get("MYGPT_LLAMACPP_MAX_TOKENS", 256) or 256)
        self.temperature = float(env.get("MYGPT_LLAMACPP_TEMPERATURE", 0.7) or 0.7)
        self.answers = 0
        self.last_error = ""
        self.loaded_model: str | None = None
        self.load_seconds: float | None = None
        self.effective_n_ctx: int | None = None
        self.models_dir = models_dir
        self._llm = None                      # the Llama instance, if loaded
        self._lock = threading.RLock()
        self._cache: tuple[float, dict] | None = None
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, encoding="utf-8") as handle:
                    saved = json.load(handle)
                for key in ("enabled", "learn", "model_path", "n_ctx",
                            "n_threads", "n_gpu_layers", "max_tokens",
                            "temperature"):
                    if key in saved:
                        setattr(self, key, saved[key])
            except Exception:
                pass

    # ------------------------------------------------------------------ config
    def configure(self, **kwargs) -> dict:
        """Change settings at runtime (used by /api/backends)."""
        clean = {}
        for key, value in kwargs.items():
            if key not in ("enabled", "learn", "model_path", "n_ctx",
                           "n_threads", "n_gpu_layers", "max_tokens",
                           "temperature"):
                continue
            if key in ("enabled", "learn"):
                value = bool(value)
            elif key == "model_path":
                value = str(value or "")
            elif key == "temperature":
                value = float(value)
            else:
                value = int(value)
            setattr(self, key, value)
            clean[key] = value
        if "model_path" in clean:
            self.unload()                     # a new model must be loaded fresh
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
                           "model_path": self.model_path, "n_ctx": self.n_ctx,
                           "n_threads": self.n_threads,
                           "n_gpu_layers": self.n_gpu_layers,
                           "max_tokens": self.max_tokens,
                           "temperature": self.temperature}, handle, indent=2)
        except Exception:
            pass

    # -------------------------------------------------------------- discovery
    def discover(self) -> list[str]:
        """Every .gguf file we can see: configured path, ./models, data/models."""
        found: list[str] = []
        if self.model_path:
            if os.path.isdir(self.model_path):
                found += sorted(glob.glob(os.path.join(self.model_path, "*.gguf")))
            elif os.path.exists(self.model_path):
                found.append(self.model_path)
        roots = [self.models_dir, "models", os.path.join("data", "models")]
        for root in roots:
            if not root:
                continue
            found += sorted(glob.glob(os.path.join(root, "*.gguf")))
            found += sorted(glob.glob(os.path.join(root, "**", "*.gguf"),
                                      recursive=True))
        seen, out = set(), []
        for path in found:
            real = os.path.realpath(path)
            if real not in seen and os.path.isfile(real):
                seen.add(real)
                out.append(real)
        return out

    def resolved_model(self) -> str:
        """The file we will actually load: explicit path, else the first found."""
        if self.model_path and os.path.isfile(self.model_path):
            return self.model_path
        if self.models_dir:
            local = sorted(glob.glob(os.path.join(self.models_dir, "*.gguf")))
            if local:
                return local[0]
        candidates = self.discover()
        return candidates[0] if candidates else ""

    # ------------------------------------------------------------------- state
    def package_available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
            return True
        except Exception as exc:
            self.last_error = f"llama-cpp-python not importable: {exc}"
            return False

    def available(self) -> bool:
        return bool(self.enabled and self.package_available()
                    and self.resolved_model())

    def health(self) -> bool:
        """Cheap liveness: package importable and a model file present."""
        return self.available()

    def probe(self) -> dict:
        if self._cache and time.time() - self._cache[0] < HEALTH_TTL:
            return dict(self._cache[1])
        package, version = False, ""
        try:
            import llama_cpp
            package, version = True, getattr(llama_cpp, "__version__", "")
        except Exception as exc:
            self.last_error = f"llama-cpp-python not importable: {exc}"
        model = self.resolved_model()
        reason = ""
        if not package:
            reason = ("llama-cpp-python is not installed — run "
                      "`pip install llama-cpp-python`")
        elif not model:
            reason = ("no .gguf model found — put one in ./models/ or set "
                      "MYGPT_LLAMACPP_MODEL=/path/to/model.gguf")
        elif not self.enabled:
            reason = "disabled"
        info = {
            "kind": "llamacpp",
            "label": "llama.cpp (local GGUF)",
            "enabled": self.enabled,
            "available": self.available(),
            "reachable": self.available(),
            "package": package,
            "package_version": version,
            "model": os.path.basename(model) if model else "",
            "model_path": model,
            "models": [{"name": os.path.basename(p),
                        "path": p,
                        "size_mb": round(os.path.getsize(p) / 1e6, 1)}
                       for p in self.discover()],
            "loaded": self.loaded_model,
            "load_seconds": self.load_seconds,
            "n_ctx": self.n_ctx,
            "effective_n_ctx": self.effective_n_ctx,
            "trained_context": self.model_context_length(model) if model else None,
            "n_threads": self.n_threads,
            "n_gpu_layers": self.n_gpu_layers,
            "answers": self.answers,
            "learn": self.learn,
            "reason": reason,
            "last_error": self.last_error,
            "project_url": PROJECT_URL,
            "install": "pip install llama-cpp-python",
        }
        self._cache = (time.time(), dict(info))
        return info

    @staticmethod
    def model_context_length(path: str) -> int | None:
        """The context the model was *trained* with, read from the GGUF header.

        Loading a context longer than the training context makes llama.cpp warn
        and can produce nonsense, so we clamp to it. Header-only read via the
        optional ``gguf`` package; returns None when it can't tell.
        """
        try:
            import gguf
            reader = gguf.GGUFReader(path)
        except Exception:
            return None
        try:
            arch = "llama"
            for field in reader.fields.values():
                if field.name == "general.architecture":
                    value = field.parts[-1]
                    arch = bytes(value).decode("utf-8", "ignore") if not isinstance(value, str) else value
                    break
            key = f"{arch}.context_length"
            field = reader.fields.get(key)
            if field is None:
                return None
            value = field.parts[-1]
            if hasattr(value, "item"):
                value = value.item()
            return int(value)
        except Exception:
            return None

    # ------------------------------------------------------------------- model
    def load(self, model_path: str | None = None):
        """Load (or return the cached) llama.cpp model. Raises on failure."""
        path = model_path or self.resolved_model()
        if not path:
            raise RuntimeError("no .gguf model configured")
        with self._lock:
            if self._llm is not None and self.loaded_model == path:
                return self._llm
            from llama_cpp import Llama        # imported lazily on purpose
            started = time.perf_counter()
            n_ctx = self.n_ctx
            trained = self.model_context_length(path)
            if trained and trained > 0:
                n_ctx = min(n_ctx, trained)    # never exceed the trained window
            self.effective_n_ctx = n_ctx
            self._llm = Llama(
                model_path=path, n_ctx=n_ctx, n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers, verbose=False, logits_all=False,
            )
            self.loaded_model = path
            self.load_seconds = round(time.perf_counter() - started, 2)
            self.last_error = ""
            self._cache = None
            return self._llm

    def unload(self) -> None:
        with self._lock:
            self._llm = None
            self.loaded_model = None
            self.load_seconds = None

    def _messages(self, text: str, history):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-MAX_HISTORY_TURNS:]:
            role = turn.get("role", "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": str(turn.get("content", ""))})
        messages.append({"role": "user", "content": text})
        return messages

    # ------------------------------------------------------------------- chat
    def chat(self, text: str, history=None, model: str | None = None) -> str | None:
        """Answer one turn with the local GGUF model (None if unavailable)."""
        if not self.available():
            return None
        try:
            llm = self.load(model)
            result = llm.create_chat_completion(
                messages=self._messages(text, history),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            answer = (result.get("choices", [{}])[0]
                      .get("message", {}).get("content", "") or "").strip()
            if not answer:
                return None
            self.answers += 1
            return answer
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def generate(self, prompt: str, max_tokens: int = 128,
                 temperature: float = 0.8, top_p: float = 0.95,
                 stop: list[str] | None = None) -> str | None:
        """Raw completion — used by the UI's 'continue this' feature."""
        if not self.available():
            return None
        try:
            llm = self.load()
            result = llm.create_completion(
                prompt=prompt, max_tokens=max_tokens, temperature=temperature,
                top_p=top_p, stop=stop or ["\\n\\n"],
            )
            return (result.get("choices", [{}])[0].get("text", "") or "").strip()
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def stats(self) -> dict:
        info = self.probe()
        return {"answers": self.answers, "loaded": self.loaded_model,
                "load_seconds": self.load_seconds,
                "model": info.get("model"), "available": info.get("available")}
