# MyGPT

**A self-training chatbot that improves over time — pure Python, NumPy brain, Flask WebUI.**

MyGPT is a tiny GPT-style assistant you can talk to, teach, and correct. Everything
you do becomes training data: its memory grows, its neural language model retrains,
and you can literally watch its loss curve drop in the built-in Growth dashboard.

No GPUs, no API keys, no cloud — the whole brain runs in NumPy.

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

## How it learns

| You do this                        | MyGPT does this                                              |
|------------------------------------|--------------------------------------------------------------|
| 👍 an answer                        | Reinforces the matched memory pair, adds the exchange to its training corpus |
| 👎 an answer + correction           | Replaces the wrong answer with yours and trains on it        |
| Teach it a fact (Learn tab)         | Stores a permanent Q→A pair and adds it to the corpus        |
| Chat                               | Every 5 learning events it auto-retrains its language model  |
| **Train now** (Growth tab)          | Full training round — watch the loss curve drop              |
| **Dream** (Growth tab)              | Samples a fresh sentence from the language model             |

When it doesn't know something, it admits it and asks to be taught.

## Architecture

```
app.py                  Flask server + JSON API
mygpt/
  brain.py              orchestrator: reply / feedback / teach / train loop
  memory.py             long-term Q→A memory, TF-IDF cosine retrieval
  langmodel.py          feedforward neural language model (NumPy, Adam, backprop)
  tokenizer.py          shared tokenizer
seed_corpus.json        starter knowledge + LM pretraining text
templates/ static/      the WebUI (chat, Learn tab, Growth dashboard)
```

* **Memory** — every learned Q→A pair is vectorized (stopword-filtered, stemmed
  TF-IDF) and retrieved by cosine similarity. Feedback re-weights pairs.
* **Language model** — a Bengio-style neural LM: context embeddings → mean-pool →
  tanh hidden → softmax over vocab, trained online with Adam and gradient clipping.
  Its loss after each training round is the number charted in the Growth tab.
* **Skills** — a deterministic arithmetic evaluator (`12*12`, `(3+4)*2`, …).

## API

| Method | Path            | Body                                  |
|--------|-----------------|----------------------------------------|
| POST   | `/api/chat`     | `{"message": "…"}`                     |
| POST   | `/api/feedback` | `{"msg_id", "verdict": "up"\|"down", "correction"?}` |
| POST   | `/api/teach`    | `{"question", "answer"}`               |
| POST   | `/api/train`    | `{"epochs": 10}`                       |
| GET    | `/api/dream`    | —                                       |
| GET    | `/api/stats`    | —                                       |
| GET    | `/api/memory`   | —                                       |

## Honest scope

This is a small, transparent model of the self-improvement loop — learn from
feedback → train → measure improvement — not a foundation model. Its "GPT" has
~200k parameters and gets genuinely better at predicting the conversations it has,
which is exactly what the dashboard shows.
