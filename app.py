#!/usr/bin/env python3
"""MyGPT — self-training chatbot with a Flask WebUI.

Run:  python app.py   (then open http://localhost:8000)

License: MyGPT Personal-Use License (see LICENSE). Free to download and run
unmodified for personal, non-commercial use. Redistribution, sale,
sublicensing, modification and commercial use require written permission.
"""

from __future__ import annotations

import os
import threading

from flask import Flask, jsonify, render_template, request

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


@app.post("/api/chat")
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    if not message.strip():
        return jsonify({"ok": False, "error": "empty message"}), 400
    with _lock:
        result = brain.reply(message)
        brain.save()
    return jsonify({"ok": True, **result})


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
    with _lock:
        result = brain.teach(body.get("question", ""), body.get("answer", ""))
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
