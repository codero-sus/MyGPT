"""Cortex LLMHoster client — optional local LLM backend for MyGPT.

Cortex LLMHoster (https://github.com/codero-sus/Cortex_LLMHoster) is a
free-to-use *local* model hoster: it manages llama.cpp GGUF models (or any
OpenAI-compatible local engine) on your own machine and exposes an
OpenAI-compatible API. No cloud inference, no provider account.

MyGPT integrates with Cortex purely as an HTTP **client** of that
OpenAI-compatible API (Cortex is source-available under a restrictive
personal-use license, so it is used unmodified, as a separate service):

    GET  /health                  -> {"status": "ok"}
    GET  /ready                   -> readiness of the hosted model(s)
    GET  {api_base}/models        -> OpenAI-style model list
    POST {api_base}/chat/completions  (OpenAI chat format)

Behaviour: when the Cortex backend is enabled *and* reachable, open-ended
questions MyGPT cannot answer from its own math/skills/facts/memory are
answered by the locally hosted model, and (optionally) learned into MyGPT's
own memory + corpus so the self-training brain internalises them.  When
Cortex is disabled or unreachable MyGPT transparently falls back to its own
self-trained answers — nothing breaks.

Configuration (persisted in ``data/cortex.json``; env vars seed defaults):

    MYGPT_CORTEX_URL       e.g. http://127.0.0.1:8624   (default)
    MYGPT_CORTEX_API_BASE  OpenAI route prefix, default /v1
    MYGPT_CORTEX_API_KEY   local bearer secret (Cortex CORTEX_API_KEY)
    MYGPT_CORTEX_MODEL     model id to request (empty = Cortex default)
    CORTEX_API_KEY         also honoured as a fallback for the key
"""

from __future__ import annotations

import http.client
import json
import os
import time
from urllib.parse import urlparse

DEFAULT_URL = "http://127.0.0.1:8624"
DEFAULT_API_BASE = "/v1"
HEALTH_OK_TTL = 15.0      # cache a successful health check this long
HEALTH_BAD_TTL = 4.0      # ... and a failed one this long (avoid hammering)
PROBE_TTL = 8.0           # cache the full probe (incl. model list) this long
CHAT_TIMEOUT = 60.0       # local generation can take a while
PROBE_TIMEOUT = 4.0
PROJECT_URL = "https://github.com/codero-sus/Cortex_LLMHoster"
HTTP_ERROR = {"__cortex_http_error__": True}   # sentinel: server alive, 4xx/5xx


class CortexClient:
    """Talks to a Cortex LLMHoster server over its OpenAI-compatible API."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        env = os.environ
        self.base_url: str = env.get("MYGPT_CORTEX_URL", DEFAULT_URL).rstrip("/")
        self.api_base: str = env.get("MYGPT_CORTEX_API_BASE", DEFAULT_API_BASE)
        self.api_key: str = env.get("MYGPT_CORTEX_API_KEY") or env.get("CORTEX_API_KEY", "")
        self.model: str = env.get("MYGPT_CORTEX_MODEL", "")
        self.enabled: bool = env.get("MYGPT_CORTEX_ENABLED", "1") not in ("0", "false", "no")
        self.learn: bool = env.get("MYGPT_CORTEX_LEARN", "1") not in ("0", "false", "no")
        self.timeout: float = CHAT_TIMEOUT
        self.answers = 0                     # how many cortex answers served
        self._health: tuple[float, bool] = (0.0, False)
        self._conn: http.client.HTTPConnection | None = None
        self._conn_key: tuple | None = None
        self._probe_cache: tuple[float, dict | None] = (0.0, None)
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
        for key in ("base_url", "api_base", "api_key", "model"):
            if isinstance(saved.get(key), str):
                setattr(self, key, saved[key])
        for key in ("enabled", "learn"):
            if isinstance(saved.get(key), bool):
                setattr(self, key, saved[key])
        self.base_url = self.base_url.rstrip("/")
        if not self.api_base.startswith("/"):
            self.api_base = "/" + self.api_base

    def save(self) -> None:
        if not self.config_path:
            return
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "enabled": self.enabled, "base_url": self.base_url,
                "api_base": self.api_base, "api_key": self.api_key,
                "model": self.model, "learn": self.learn,
            }, f, ensure_ascii=False)
        os.replace(tmp, self.config_path)

    def configure(self, changes: dict) -> dict:
        """Apply user-supplied settings, persist, then re-probe the server."""
        if isinstance(changes.get("enabled"), bool):
            self.enabled = changes["enabled"]
        if isinstance(changes.get("learn"), bool):
            self.learn = changes["learn"]
        for key in ("base_url", "api_base", "model", "api_key"):
            val = changes.get(key)
            if isinstance(val, str):
                setattr(self, key, val.strip())
        self.base_url = self.base_url.rstrip("/") or DEFAULT_URL
        if not self.api_base.startswith("/"):
            self.api_base = "/" + self.api_base
        self._health = (0.0, False)          # invalidate cache
        self._probe_cache = (0.0, None)
        self._close_conn()                   # base_url may have changed
        self.save()
        return self.probe(force=True)

    # ------------------------------------------------------------------ http
    def _headers(self, auth: bool = True) -> dict:
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json"}
        if auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _close_conn(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        self._conn, self._conn_key = None, None

    def _connect(self) -> http.client.HTTPConnection | None:
        """One keep-alive connection per (host, port) — reused across
        probes/chats instead of a fresh TCP handshake per request."""
        parsed = urlparse(self.base_url)
        key = (parsed.hostname, parsed.port or 80)
        if self._conn is not None and self._conn_key == key:
            return self._conn
        self._close_conn()
        if not parsed.hostname:
            return None
        try:
            self._conn = http.client.HTTPConnection(parsed.hostname, key[1])
            self._conn_key = key
        except (OSError, ValueError):
            self._conn, self._conn_key = None, None
        return self._conn

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: float = PROBE_TIMEOUT, auth: bool = True):
        """Returns parsed JSON on 2xx, HTTP_ERROR when the server answered
        with 4xx/5xx (it is alive), or None when it is unreachable."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._headers(auth)
        prefix = urlparse(self.base_url).path or ""
        for attempt in (0, 1):
            conn = self._connect()
            if conn is None:
                return None
            conn.timeout = timeout
            try:
                conn.request(method, prefix + path, body=data, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()          # always drain: keep-alive reuse
            except (OSError, ValueError, TimeoutError,
                    http.client.HTTPException):
                self._close_conn()
                if attempt == 0:
                    continue               # stale keep-alive → one fresh retry
                return None
            if resp.status >= 400:
                return HTTP_ERROR          # alive, but rejected the request
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except ValueError:
                return None
        return None

    # --------------------------------------------------------------- queries
    def health(self) -> bool:
        """Is the Cortex server alive? Cached briefly to stay cheap."""
        now = time.time()
        ts, ok = self._health
        if now - ts < (HEALTH_OK_TTL if ok else HEALTH_BAD_TTL):
            return ok
        resp = self._request("GET", "/health", auth=False)
        ok = bool(resp) and resp.get("status") == "ok"
        self._health = (now, ok)
        return ok

    def available(self) -> bool:
        return self.enabled and self.health()

    def models(self) -> list[dict]:
        resp = self._request("GET", f"{self.api_base}/models")
        if not resp or not isinstance(resp.get("data"), list):
            return []
        return [{"id": m.get("id", "?"),
                 "runtime": m.get("runtime", ""),
                 "capabilities": m.get("capabilities", [])}
                for m in resp["data"] if isinstance(m, dict)]

    def chat(self, question: str, history: list[dict] | None = None,
             model: str | None = None) -> str | None:
        """Ask the locally hosted model via /v1/chat/completions.

        Returns the assistant text, or None when anything goes wrong — the
        caller falls back to MyGPT's own brain.
        """
        messages = [{"role": "system",
                     "content": ("You are MyGPT's local large-language-model "
                                 "back end, hosted by Cortex LLMHoster. Be "
                                 "helpful, direct and concise.")}]
        for turn in (history or [])[-6:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})
        body: dict = {"messages": messages, "stream": False,
                      "temperature": 0.7}
        chosen = model or self.model
        if chosen:
            body["model"] = chosen
        resp = self._request("POST", f"{self.api_base}/chat/completions",
                             body=body, timeout=self.timeout)
        if resp is None:                      # connection failed
            self._health = (time.time(), False)
            return None
        if resp is HTTP_ERROR:                # e.g. 400 "no model configured":
            return None                       # server is alive, nothing to do
        try:
            choice = resp["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None
        text = (text or "").strip()
        if text:
            self.answers += 1
        return text or None

    # ---------------------------------------------------------------- status
    def probe(self, force: bool = False) -> dict:
        """Snapshot for the WebUI / /api/stats."""
        now = time.time()
        ts, cached = self._probe_cache
        if not force and cached is not None and now - ts < PROBE_TTL:
            return cached
        if force:
            self._health = (0.0, False)
        reachable = self.health()
        models = self.models() if reachable else []
        reason = None
        if reachable and not models:
            reason = ("connected, but no models are configured in Cortex yet "
                      "(add one in the Cortex dashboard, then it answers here)")
        elif not reachable and self.enabled:
            reason = (f"no Cortex LLMHoster server at {self.base_url} — start "
                      f"one with `cortex-llmhoster`, or MyGPT keeps answering "
                      f"with its self-trained brain")
        result = {
            "enabled": self.enabled,
            "reachable": reachable,
            "base_url": self.base_url,
            "api_base": self.api_base,
            "model": self.model,
            "learn": self.learn,
            "models": models,
            "answers": self.answers,
            "reason": reason,
            "project_url": PROJECT_URL,
        }
        self._probe_cache = (time.time(), result)
        return result
