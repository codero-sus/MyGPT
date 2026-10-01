# MyGPT

**A self-training chatbot that improves over time — pure Python, NumPy brain, Flask WebUI.**

MyGPT is a tiny GPT-style assistant you can talk to, teach, and correct. Everything
you do becomes training data: its memory grows, its neural language model retrains,
and you can literally watch its loss curve drop in the built-in Growth dashboard.

No GPUs, no API keys, no cloud — the whole brain runs in NumPy.

The self-improvement loop is ported from
[**CORTEX**](https://github.com/codero-sus/agi) (`codero-sus/agi`): fact extraction,
self-critique, constitution growth, skill synthesis, self-eval, background training
and dream replay.

## Quick start

```bash
./run.sh            # creates a venv, installs deps, starts on http://localhost:8000
```

or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Set `PORT` to change the port (default `8000`). All learned state lives in `data/` —
delete that folder to give MyGPT amnesia and start over.

## The self-learning loop (from CORTEX)

**Light pass — after every turn:**

1. **Fact extraction** — "my name is Ada and I live in Delhi" becomes semantic triples
   (`user name Ada`, `user lives_in Delhi`), recalled later when you ask about yourself
2. **Self-critique** — the reply is critiqued; weaknesses become *lessons*, and
   lessons starting with `Principle:` are promoted into the **constitution**
3. **Background training** — Adam steps on the exchange are queued to the trainer
   thread; the reply path never waits on gradients

**Medium pass — every 5 turns (or the 🔁 button in the Mind tab):**

4. **Skill synthesis** — if one intent keeps repeating, MyGPT *writes a new Python
   skill file* into `skills/` (procedural memory)
5. **Constitution promotion** — principle-lessons become permanent principles
6. **Self-eval battery** — 5 questions (math, identity, knowledge, principles) scored
   as a percentage and charted over time
7. **Corpus training** — principles + lessons + facts + taught pairs + dialogue go
   back into the trainer
8. **Consolidation** — periodic distilled lessons about what it now holds

**Heavy pass — background trainer:**

9. Queue-fed Adam steps with debounced checkpoints
10. **Dream replay** — when idle 20s, it re-learns a distilled snapshot of its own
    mind (preamble, facts, lessons, dialogue)

## How it answers

| Priority | Source                                    |
|----------|-------------------------------------------|
| 1 | Arithmetic skill (`12*12`, `(3+4)*2`) |
| 2 | Learned skill files in `skills/` (pattern-matched) |
| 3 | Semantic facts about you (`what is my name?`) |
| 4 | Learned Q→A memory pairs (TF-IDF retrieval); 👍 reinforces, 👎+correction replaces |
| 5 | Admits ignorance and asks to be taught |

## The WebUI

* **Chat** — rate every answer 👍/👎, correct it inline, teach-it chips on unknowns
* **Learn tab** — teach Q→A pairs, browse what it knows (with weights)
* **Growth tab** — loss chart, vitals, Train now, Dream, activity log
* **Mind tab** — the CORTEX loop: trainer status, self-eval %, constitution,
  semantic facts (with forget buttons), lessons, skills, improvement events

## Architecture

```
app.py                  Flask server + JSON API
mygpt/
  brain.py              orchestrator: reply / feedback / teach / train loop
  memory.py             long-term Q→A memory, TF-IDF cosine retrieval
  langmodel.py          feedforward neural LM (NumPy, Adam, backprop, thread-safe)
  store.py              facts, lessons, constitution, metrics, events  (CORTEX)
  selflearn.py          the self-improvement loop                       (CORTEX)
  trainer.py            background trainer + dream replay               (CORTEX)
  skills.py             skill registry: skills as Python files          (CORTEX)
  tokenizer.py          shared tokenizer
skills/                 procedural memory — starter + auto-written skills
seed_corpus.json        starter knowledge + LM pretraining text
templates/ static/      the WebUI
```

## API

| Method | Path            | Body                                  |
|--------|-----------------|----------------------------------------|
| POST   | `/api/chat`     | `{"message": "…"}`                     |
| POST   | `/api/feedback` | `{"msg_id", "verdict": "up"\|"down", "correction"?}` |
| POST   | `/api/teach`    | `{"question", "answer"}`               |
| POST   | `/api/train`    | `{"epochs": 10}`                       |
| POST   | `/api/improve`  | — (force a medium improvement cycle)   |
| POST   | `/api/forget`   | `{"q": "user name"}` (drop facts)      |
| GET    | `/api/dream`    | —                                       |
| GET    | `/api/stats`    | — (includes `mind` self-learning state)|
| GET    | `/api/memory`   | —                                       |

## Honest scope

This is a small, transparent model of the self-improvement loop — learn from
feedback → train → measure improvement — not a foundation model. Its "GPT" has
~200k parameters and gets genuinely better at predicting the conversations it has,
which is exactly what the dashboard shows. Self-learning mechanics (facts,
critique, constitution, skills, self-eval, background training, dreaming) are
adapted from the CORTEX project (`codero-sus/agi`).
