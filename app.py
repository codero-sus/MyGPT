#!/usr/bin/env python3
"""MyGPT — self-training chatbot with a Flask WebUI.

Author: codero-sus — https://github.com/codero-sus · https://the-codero.web.app/

Run:  python app.py   (then open http://localhost:8000)

License: MyGPT Personal-Use License (see LICENSE). Free to download and run
unmodified for personal, non-commercial use. Redistribution, sale,
sublicensing, modification and commercial use require written permission.
"""

from __future__ import annotations

import json
import os
import threading
import time

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file)

from mygpt import __version__, updater
from mygpt.brain import Brain

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MYGPT_DATA", os.path.join(ROOT, "data"))
SEED_PATH = os.path.join(ROOT, "seed_corpus.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024  # 25MB import cap + slack
brain = Brain(DATA_DIR, SEED_PATH)
_lock = threading.Lock()
_update_lock = threading.Lock()   # one update at a time (mirrors Cortex)


@app.get("/")
def index():
    return render_template("index.html")


MAX_CHAT_CHARS = 4000
MAX_TEACH_Q = 500
MAX_TEACH_A = 4000
MAX_BULK_PAIRS = 100


@app.after_request
def _cors_and_security(resp):
    """Permissive CORS for local scripts + a few hardening headers."""
    if request.path.startswith("/api/"):
        resp.headers.setdefault("Access-Control-Allow-Origin", "*")
        resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        resp.headers.setdefault("Access-Control-Allow-Methods",
                                "GET, POST, OPTIONS")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


def _validate_message(raw):
    """Shared chat-message validation → (message, error_response|None)."""
    if not isinstance(raw, str) or not raw.strip():
        return None, (jsonify({"ok": False, "error": "empty message"}), 400)
    if len(raw) > MAX_CHAT_CHARS:
        return None, (jsonify({
            "ok": False,
            "error": f"message too long (max {MAX_CHAT_CHARS} chars)"}), 400)
    return raw, None


@app.post("/api/chat")
def chat():
    message, err = _validate_message(
        (request.get_json(silent=True) or {}).get("message", ""))
    if err:
        return err
    with _lock:
        result = brain.reply(message)
        brain.save()
    return jsonify({"ok": True, **result})


@app.post("/api/chat/stream")
def chat_stream():
    """Server-Sent Events: word-by-word reply plus a final JSON event."""
    message, err = _validate_message(
        (request.get_json(silent=True) or {}).get("message", ""))
    if err:
        return err
    with _lock:
        result = brain.reply(message)
        brain.save()
    reply = result.get("reply", "")

    def gen():
        words = reply.split(" ")
        for i, w in enumerate(words):
            chunk = w if i == 0 else " " + w
            yield "event: token\ndata: " + json.dumps({"t": chunk}) + "\n\n"
        payload = dict(result)
        yield "event: done\ndata: " + json.dumps(payload) + "\n\n"

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/health")
def health():
    """Lightweight liveness probe (no locks beyond quick cached reads)."""
    return jsonify({
        "ok": True,
        "version": __version__,
        "uptime_s": int(time.time() - brain.started),
        "cortex": brain.cortex.probe().get("reachable", False),
        "ollama": brain.ollama.probe().get("reachable", False),
    })


@app.get("/api/ping")
def ping():
    return jsonify({"ok": True, "pong": int(time.time())})


@app.get("/api/version")
def version():
    """Version + author links for scripts and health dashboards."""
    return jsonify({"ok": True, "version": __version__,
                    "author": "codero-sus",
                    "github": "https://github.com/codero-sus",
                    "website": "https://the-codero.web.app/"})


@app.route("/api/<path:_path>", methods=["OPTIONS", "GET", "POST", "PUT",
                                         "PATCH", "DELETE"])
def api_catch_all(_path):
    """CORS preflight for any /api route; everything else stays a JSON 404."""
    if request.method == "OPTIONS":
        return ("", 204)
    known = any(rule.rule == request.path and "<" not in rule.rule
                for rule in app.url_map.iter_rules())
    if known:                      # real endpoint, just the wrong verb
        return jsonify({"ok": False, "error": "method not allowed"}), 405
    return jsonify({"ok": False,
                    "error": f"no such endpoint: /api/{_path}"}), 404


@app.get("/api/memory/search")
def memory_search():
    """Ranked retrieval over the memory layer: ?q=…&k=…"""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "query 'q' required"}), 400
    k = max(1, min(25, int(request.args.get("k", 5))))
    with _lock:
        hits = brain.search_memory(q, k=k)
    return jsonify({"ok": True, "query": q, "hits": hits})


@app.post("/api/clear")
def clear_transcript():
    """Clear the conversation transcript (learned knowledge is kept)."""
    with _lock:
        result = brain.clear_transcript()
        brain.save()
    return jsonify(result)


@app.get("/api/memory/list")
def memory_list():
    """Paginated memory listing: ?offset=…&limit=…"""
    offset = max(0, int(request.args.get("offset", 0)))
    limit = max(1, min(200, int(request.args.get("limit", 50))))
    with _lock:
        pairs = brain.memory.pairs
        total = len(pairs)
        page = [{"q": p["q"], "a": p["a"], "hits": p.get("hits", 0)}
                for p in pairs[offset:offset + limit]]
    return jsonify({"ok": True, "total": total, "offset": offset,
                    "limit": limit, "pairs": page})


@app.get("/api/suggest")
def suggest():
    """Question-title autocomplete: ?q=frag → up to 6 completions."""
    frag = (request.args.get("q") or "").strip()
    with _lock:
        items = brain.suggest(frag) if frag else []
    return jsonify({"ok": True, "suggestions": items})


@app.get("/api/analytics")
def analytics():
    """Counters, mode/intent histograms, busiest hours, top memories."""
    with _lock:
        return jsonify({"ok": True, **brain.analytics()})


@app.get("/api/export.json")
def export_json():
    """Structured transcript export (JSON) for archiving or analysis."""
    with _lock:
        data = brain.export_json()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(json.dumps(data, ensure_ascii=False, indent=2),
                    mimetype="application/json", headers={
                        "Content-Disposition":
                            f'attachment; filename="mygpt-{stamp}.json"'})


@app.get("/api/export.csv")
def export_csv():
    """Transcript as CSV (ts, role, intent, content) — spreadsheet friendly."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "role", "intent", "content"])
    with _lock:
        for ep in brain.episodes.episodes:
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S",
                                      time.localtime(ep.get("ts", 0))),
                        ep.get("role", ""), ep.get("intent", "chat"),
                        ep.get("content", "")])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition":
            f'attachment; filename="mygpt-{stamp}.csv"'})


@app.get("/api/backends/models")
def backends_models():
    """Every answerable engine in one call: brain + Cortex + Ollama models."""
    with _lock:
        info = brain.backends()
    models = [{"engine": "brain", "id": "brain", "label": "🧠 MyGPT Brain"}]
    for host_name in ("cortex", "ollama"):
        host = info.get(host_name) or {}
        for mid in (host.get("models") or []):
            models.append({"engine": host_name, "id": mid,
                           "label": f"{host_name}/{mid}"})
    return jsonify({"ok": True, "models": models,
                    "selected": info.get("selected"),
                    "current": info.get("model") or "auto"})


@app.get("/api/events/stream")
def events_stream():
    """SSE snapshot of recent self-learning events, then a keepalive ping."""
    def gen():
        with _lock:
            events = brain.store.recent_events(10)
        yield "event: snapshot\ndata: " + json.dumps(
            {"events": events}) + "\n\n"
        yield "event: ping\ndata: " + json.dumps({"t": int(time.time())}) + "\n\n"

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/teach/bulk")
def teach_bulk():
    """Teach up to 100 Q→A pairs in one request.

    Body: {"pairs": [{"question": …, "answer": …}, …]}
    """
    body = request.get_json(silent=True) or {}
    pairs = body.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        return jsonify({"ok": False,
                        "error": "body must be {\"pairs\": [...]}"}), 400
    if len(pairs) > MAX_BULK_PAIRS:
        return jsonify({"ok": False,
                        "error": f"too many pairs (max {MAX_BULK_PAIRS})"}), 400
    with _lock:
        result = brain.teach_many(pairs)
    return jsonify(result), (200 if result["stored"] else 400)


@app.get("/api/checkpoint/info")
def checkpoint_info():
    """Metadata for a single checkpoint: ?name=…"""
    name = (request.args.get("name") or "").strip()
    with _lock:
        meta = brain.checkpoints.get(name)
    if not meta:
        return jsonify({"ok": False,
                        "error": f"checkpoint '{name}' not found"}), 404
    return jsonify({"ok": True, "checkpoint": meta})


@app.get("/robots.txt")
def robots():
    """Politely keep crawlers out of the JSON API."""
    body = ("User-agent: *\n"
            "Allow: /$\n"
            "Disallow: /api/\n"
            "Crawl-delay: 10\n")
    return Response(body, mimetype="text/plain")


@app.get("/manifest.json")
def manifest():
    """Web app manifest so browsers offer 'install to desktop'."""
    return jsonify({
        "name": "MyGPT — self-training chatbot by codero-sus",
        "short_name": "MyGPT",
        "description": ("A self-learning chatbot in pure Python + NumPy, "
                        "by codero-sus."),
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b0e14",
        "theme_color": "#0b0e14",
        "icons": [{"src": "/static/icon.svg", "sizes": "any",
                   "type": "image/svg+xml", "purpose": "any"}],
    })


@app.errorhandler(404)
def err_404(_exc):
    return jsonify({"ok": False, "error": "not found"}), 404


@app.errorhandler(405)
def err_405(_exc):
    # The OPTIONS catch-all also matches unknown /api paths, so a wrong-method
    # hit there must stay a 404. Real endpoints keep a proper 405.
    known = any(rule.rule == request.path and "<" not in rule.rule
                for rule in app.url_map.iter_rules())
    if not known:
        return jsonify({"ok": False,
                        "error": f"no such endpoint: {request.path}"}), 404
    return jsonify({"ok": False, "error": "method not allowed"}), 405


@app.errorhandler(413)
def err_413(_exc):
    return jsonify({"ok": False, "error": "payload too large"}), 413


@app.errorhandler(500)
def err_500(_exc):
    return jsonify({"ok": False, "error": "internal server error"}), 500


@app.post("/api/feedback")
def feedback():
    body = request.get_json(silent=True) or {}
    with _lock:
        result = brain.feedback(body.get("msg_id", ""),
                                body.get("verdict", ""),
                                body.get("correction"))
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/teach")
def teach():
    body = request.get_json(silent=True) or {}
    q = body.get("question", "")
    a = body.get("answer", "")
    if not isinstance(q, str) or not isinstance(a, str):
        return jsonify({"ok": False, "error": "question and answer must be text"}), 400
    if len(q) > MAX_TEACH_Q or len(a) > MAX_TEACH_A:
        return jsonify({"ok": False,
                        "error": f"too long (question max {MAX_TEACH_Q}, "
                                 f"answer max {MAX_TEACH_A} chars)"}), 400
    with _lock:
        result = brain.teach(q, a)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/train")
def train():
    body = request.get_json(silent=True) or {}
    epochs = max(1, min(100, int(body.get("epochs", 10))))
    with _lock:
        result = brain.train(epochs=epochs, reason="manual")
    return jsonify(result)


@app.get("/api/dream")
def dream():
    with _lock:
        text = brain.dream()
    return jsonify({"ok": True, "text": text})


@app.post("/api/improve")
def improve():
    """Force a medium self-improvement cycle (skills, constitution, self-eval)."""
    with _lock:
        events = brain.improve_cycle(reason="manual")
    return jsonify({"ok": True, "events": events})


@app.post("/api/eval")
def evaluate():
    """Run the self-evaluation battery now (math, identity, knowledge,
    principles) and return the per-question results."""
    with _lock:
        report = brain.run_self_eval()
    return jsonify({"ok": True, **report})


@app.get("/api/export")
def export_chat():
    """Download the conversation history as a Markdown transcript."""
    with _lock:
        text = brain.export_transcript()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(text, mimetype="text/markdown", headers={
        "Content-Disposition":
            f'attachment; filename="mygpt-transcript-{stamp}.md"'})


@app.get("/api/history")
def history():
    """Recent conversation turns so the WebUI can restore the chat view
    after a page reload."""
    limit = max(1, min(100, int(request.args.get("limit", 30))))
    with _lock:
        items = brain.episodes.episodes[-limit:]
    return jsonify({"ok": True, "episodes": [
        {"id": e["id"], "ts": e["ts"], "role": e["role"],
         "content": e["content"]} for e in items]})


@app.post("/api/forget")
def forget():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "empty query"}), 400
    with _lock:
        n = brain.forget(q)
    return jsonify({"ok": True, "removed": n})


@app.post("/api/import")
def import_history():
    """Absorb an exported chat history: WhatsApp .txt/.zip, ChatGPT
    conversations.json, Claude JSON, Telegram result.json, messages JSONL/CSV."""
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"ok": False, "error": "no file uploaded"}), 400
    data = f.read()
    with _lock:
        result = brain.import_history(f.filename, data)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.get("/api/cortex")
def cortex_status():
    """Cortex LLMHoster backend status (live probe)."""
    with _lock:
        return jsonify({"ok": True, **brain.cortex.probe(force=True)})


@app.post("/api/cortex")
def cortex_config():
    """Update the Cortex LLMHoster backend settings and re-test the link.

    Accepts any of: enabled, learn (bools), base_url, api_base, model,
    api_key (strings).
    """
    body = request.get_json(silent=True) or {}
    with _lock:
        probe = brain.cortex.configure(body)
        brain._log("Cortex LLMHoster settings updated "
                   f"({'on' if brain.cortex.enabled else 'off'})")
    return jsonify({"ok": True, **probe})


@app.get("/api/ollama")
def ollama_status():
    """Ollama backend status (live probe)."""
    with _lock:
        return jsonify({"ok": True, **brain.ollama.probe(force=True)})


@app.post("/api/ollama")
def ollama_config():
    """Update the Ollama backend settings and re-test the link.

    Accepts any of: enabled, learn (bools), base_url, url, model (strings).
    """
    body = request.get_json(silent=True) or {}
    with _lock:
        probe = brain.ollama.configure(body)
        brain._log("Ollama settings updated "
                   f"({'on' if brain.ollama.enabled else 'off'})")
    return jsonify({"ok": True, **probe})


@app.get("/api/backends")
def backends():
    """Chat model picker: available backends, models, current selection,
    plus trained-model checkpoints."""
    with _lock:
        return jsonify({"ok": True, **brain.backends()})


@app.post("/api/backends/select")
def backends_select():
    """Choose which engine answers chat: brain / cortex / ollama / auto."""
    body = request.get_json(silent=True) or {}
    with _lock:
        result = brain.set_chat_backend(body.get("backend", "auto"),
                                        body.get("model", ""))
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/checkpoint")
def checkpoint_create():
    """Snapshot the current trained model into _model_trained/.

    Optional body: {"label": "...", "note": "...", "train": true}
    (train=true runs a quick training round before snapshotting).
    """
    body = request.get_json(silent=True) or {}
    with _lock:
        train_info = None
        if body.get("train"):
            train_info = brain.train(epochs=6, reason="checkpoint")
        meta = brain.checkpoint(label=body.get("label", ""),
                                note=body.get("note", ""))
    return jsonify({"ok": True, "checkpoint": meta, "train": train_info})


@app.get("/api/checkpoints")
def checkpoints_list():
    with _lock:
        return jsonify({"ok": True,
                        "checkpoints": brain.checkpoints.list(),
                        "dir": "_model_trained"})


@app.post("/api/checkpoint/load")
def checkpoint_load():
    """Load a saved checkpoint's weights as the active chat model."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "checkpoint name required"}), 400
    with _lock:
        result = brain.load_checkpoint(name)
    return jsonify(result), (200 if result.get("ok") else 404)


@app.post("/api/checkpoint/delete")
def checkpoint_delete():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "checkpoint name required"}), 400
    with _lock:
        result = brain.delete_checkpoint(name)
    return jsonify(result), (200 if result.get("ok") else 404)


@app.get("/api/checkpoint/download")
def checkpoint_download():
    """Download a checkpoint folder (weights + metadata) as a zip."""
    import io
    import zipfile
    name = (request.args.get("name") or "").strip()
    with _lock:
        meta = brain.checkpoints.get(name)
        wpath = brain.checkpoints.weights_path(name)
        if not meta or not wpath:
            return jsonify({"ok": False,
                            "error": f"checkpoint '{name}' not found"}), 404
        meta_bytes = json.dumps(meta, ensure_ascii=False,
                                indent=2).encode("utf-8")
        with open(wpath, "rb") as f:
            weights = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}/lm_weights.npz", weights)
        z.writestr(f"{name}/meta.json", meta_bytes)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True,
                     download_name=f"{name}.zip")


@app.get("/api/update/check")
def update_check():
    """Manual, branch-pinned update check against codero-sus/MyGPT."""
    try:
        info = updater.check_for_updates(__version__)
    except updater.UpdateError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    return jsonify({"ok": True, **info.as_dict(),
                    "last_update": updater.last_update(DATA_DIR)})


@app.post("/api/update/install")
def update_install():
    """Install a confirmed update. Requires the commit SHA from a fresh check."""
    body = request.get_json(silent=True) or {}
    confirmed = body.get("commit_sha")
    if not isinstance(confirmed, str) or not confirmed:
        return jsonify({"ok": False,
                        "error": "Confirm the commit ID shown by the update check."}), 400
    with _update_lock:
        try:
            info = updater.check_for_updates(__version__)
            if not info.update_available:
                return jsonify({
                    "ok": False,
                    "error": f"MyGPT {__version__} is already at the latest branch "
                             f"version ({info.latest_version})."}), 409
            if info.commit_sha != confirmed:
                return jsonify({
                    "ok": False,
                    "error": "The update branch changed after your check. "
                             "Check again and confirm the new commit."}), 409
            summary = updater.install_from_commit(confirmed, ROOT, ref=info.source_ref)
        except updater.UpdateError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
    return jsonify({
        "ok": True,
        "current_version": info.current_version,
        "installed_version": info.latest_version,
        "source_repository": info.source_repository,
        "source_ref": info.source_ref,
        "commit_sha": info.commit_sha,
        "replaced": summary["replaced"],
        "preserved": summary["preserved"],
        "restart_required": True,
        "message": "The update was installed. Restart MyGPT to load the new version.",
    })


@app.get("/api/stats")
def stats():
    with _lock:
        return jsonify({"ok": True, "version": __version__, **brain.stats()})


@app.get("/api/memory")
def memory():
    with _lock:
        return jsonify({"ok": True, "pairs": brain.recent_pairs(20)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, threaded=True)
