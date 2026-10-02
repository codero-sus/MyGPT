#!/usr/bin/env python3
"""MyGPT — self-training chatbot with a Flask WebUI.

Run:  python app.py   (then open http://localhost:8000)
"""

from __future__ import annotations

import os
import threading

from flask import Flask, jsonify, render_template, request

from mygpt.brain import Brain

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MYGPT_DATA", os.path.join(ROOT, "data"))
SEED_PATH = os.path.join(ROOT, "seed_corpus.json")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024  # 25MB import cap + slack
brain = Brain(DATA_DIR, SEED_PATH)
_lock = threading.Lock()


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


@app.get("/api/agents")
def list_agents():
    with _lock:
        return jsonify({"ok": True, "agents": brain.roster.list(),
                        "runs": brain.roster.recent_runs(8)})


@app.post("/api/agents")
def create_agent():
    body = request.get_json(silent=True) or {}
    try:
        with _lock:
            spec = brain.roster.create(body.get("name", ""),
                                       body.get("mission", ""),
                                       body.get("tools") or [])
            brain.store.add_fact("agent", "spawned", spec.name, 0.9)
            brain.save()
        return jsonify({"ok": True, "agent": spec.as_dict()})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.post("/api/agents/delete")
def delete_agent():
    body = request.get_json(silent=True) or {}
    with _lock:
        ok = brain.roster.delete(body.get("key", ""))
    return jsonify({"ok": ok})


@app.post("/api/agents/run")
def run_agent_endpoint():
    body = request.get_json(silent=True) or {}
    goal = (body.get("goal") or "").strip()
    if not goal:
        return jsonify({"ok": False, "error": "empty goal"}), 400
    from mygpt import agents as agents_mod
    with _lock:
        spec = brain.roster.get(body.get("name", "")) if body.get("name") \
            else brain.roster.default()
        run = agents_mod.run_agent(brain, spec, goal[:240], goal)
    return jsonify({"ok": True, **run.as_dict()})


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


@app.get("/api/stats")
def stats():
    with _lock:
        return jsonify({"ok": True, **brain.stats()})


@app.get("/api/memory")
def memory():
    with _lock:
        return jsonify({"ok": True, "pairs": brain.recent_pairs(20)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, threaded=True)
