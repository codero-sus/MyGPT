"""Ollama client — optional local LLM backend for MyGPT.

Ollama (https://ollama.com) is a popular local model runner. Like Cortex
LLMHoster it is an *inference/hosting* runtime — it runs already-trained
models; it does not train them. MyGPT talks to it purely as an HTTP client of
Ollama's native JSON API:

    GET  /api/version     -> {"version": "..."}          (liveness)
    GET  /api/tags        -> {"models": [{"name": ...}]} (installed models)
    POST /api/chat        -> {"message": {"content": ...}} (chat completion)

Behaviour mirrors the Cortex backend: when Ollama is enabled *and* reachable,
open-ended questions MyGPT can't answer from its own math/skills/facts/memory
can be answered by the selected Ollama model and (optionally) learned back
into MyGPT's memory + corpus. When Ollama is disabled/unreachable MyGPT falls
back to its self-trained brain — nothing breaks.

Configuration (persisted in ``data/ollama.json``; env vars seed defaults):

    MYGPT_OLLAMA_URL     e.g. http://127.0.0.1:11434  (default)
    OLLAMA_HOST          also honoured as a fallback base URL
    MYGPT_OLLAMA_MODEL   model name to use (empty = first installed model)
    MYGPT_OLLAMA_ENABLED 0/false/no to disable
    MYGPT_OLLAMA_LEARN   0/false/no to not internalise answers
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
HEALTH_OK_TTL = 15.0
HEALTH_BAD_TTL = 4.0
CHAT_TIMEOUT = 120.0       # local generation can be slow
PROBE_TIMEOUT = 4.0
PROJECT_URL = "https://ollama.com"
HTTP_ERROR = {"__ollama_http_error__": True}


class OllamaClient:
    """Talks to an Ollama server over its native JSON API."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        env = os.environ
        base = env.get("MYGPT_OLLAMA_URL") or env.get("OLLAMA_HOST") or DEFAULT_URL
        self.base_url: str = base.rstrip("/")
        self.model: str = env.get("MYGPT_OLLAMA_MODEL", "")
        self.enabled: bool = env.get("MYGPT_OLLAMA_ENABLED", "1") not in ("0", "false", "no")
        self.learn: bool = env.get("MYGPT_OLLAMA_LEARN", "1") not in ("0", "false", "no")
        self.timeout: float = CHAT_TIMEOUT
        self.answers = 0
        self._health: tuple[float, bool] = (0.0, False)
        self._load()

    # ------------------------------------------------------------- settings
    def _load(self) -> None:
        if not self.config_path or not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        for key in ("base_url", "model"):
            if isinstance(saved.get(key), str):
                setattr(self, key, saved[key])
        for key in ("enabled", "learn"):
            if isinstance(saved.get(key), bool):
                setattr(self, key, saved[key])
        self.base_url = self.base_url.rstrip("/") or DEFAULT_URL

    def save(self) -> None:
        if not self.config_path:
            return
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "enabled": self.enabled, "base_url": self.base_url,
                "model": self.model, "learn": self.learn,
            }, f, ensure_ascii=False)
        os.replace(tmp, self.config_path)

    def configure(self, changes: dict) -> dict:
        if isinstance(changes.get("enabled"), bool):
            self.enabled = changes["enabled"]
        if isinstance(changes.get("learn"), bool):
            self.learn = changes["learn"]
        for key in ("base_url", "model"):
            val = changes.get(key)
            if isinstance(val, str):
                setattr(self, key, val.strip())
        self.base_url = self.base_url.rstrip("/") or DEFAULT_URL
        self._health = (0.0, False)
        self.save()
        return self.probe(force=True)

    # ------------------------------------------------------------------ http
    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: float = PROBE_TIMEOUT):
        """Parsed JSON on 2xx, HTTP_ERROR if alive-but-error, None if unreachable."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self._url(path), data=data, method=method,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError:
            return HTTP_ERROR
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return None
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            return None

    # --------------------------------------------------------------- queries
    def health(self) -> bool:
        now = time.time()
        ts, ok = self._health
        if now - ts < (HEALTH_OK_TTL if ok else HEALTH_BAD_TTL):
            return ok
        resp = self._request("GET", "/api/version")
        ok = isinstance(resp, dict) and "version" in resp
        if not ok:
            # very old / minimal builds: fall back to the root banner
            req = urllib.request.Request(self._url("/"), method="GET")
            try:
                with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as r:
                    ok = b"Ollama is running" in r.read()
            except (urllib.error.URLError, OSError, ValueError, TimeoutError):
                ok = False
        self._health = (now, ok)
        return ok

    def available(self) -> bool:
        return self.enabled and self.health()

    def models(self) -> list[dict]:
        resp = self._request("GET", "/api/tags")
        if resp is None or resp is HTTP_ERROR or not isinstance(resp.get("models"), list):
            return []
        out = []
        for m in resp["models"]:
            if not isinstance(m, dict):
                continue
            out.append({
                "id": m.get("name") or m.get("model") or "?",
                "size": m.get("size"),
                "family": (m.get("details") or {}).get("family", ""),
            })
        return out

    def _pick_model(self) -> str | None:
        if self.model:
            return self.model
        models = self.models()
        return models[0]["id"] if models else None

    def chat(self, question: str, history: list[dict] | None = None,
             model: str | None = None) -> str | None:
        model = model or self._pick_model()
        if not model:
            return None
        messages = []
        for turn in (history or [])[-6:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})
        body = {"model": model, "messages": messages, "stream": False,
                "options": {"temperature": 0.7}}
        resp = self._request("POST", "/api/chat", body=body, timeout=self.timeout)
        if resp is None:
            self._health = (time.time(), False)
            return None
        if resp is HTTP_ERROR:
            return None
        try:
            text = resp["message"]["content"]
        except (KeyError, TypeError):
            return None
        text = (text or "").strip()
        if text:
            self.answers += 1
        return text or None

    # ---------------------------------------------------------------- status
    def probe(self, force: bool = False) -> dict:
        if force:
            self._health = (0.0, False)
        reachable = self.health()
        models = self.models() if reachable else []
        reason = None
        if reachable and not models:
            reason = ("connected, but Ollama has no models yet "
                      "(run `ollama pull <model>`, then it answers here)")
        elif not reachable and self.enabled:
            reason = (f"no Ollama server at {self.base_url} — start one with "
                      f"`ollama serve`, or MyGPT keeps answering with its "
                      f"self-trained brain")
        return {
            "enabled": self.enabled,
            "reachable": reachable,
            "base_url": self.base_url,
            "model": self.model,
            "learn": self.learn,
            "models": models,
            "answers": self.answers,
            "reason": reason,
            "project_url": PROJECT_URL,
        }
