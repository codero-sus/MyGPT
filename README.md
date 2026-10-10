# MyGPT

**A self-training chatbot that improves over time — pure Python, NumPy brain, Flask WebUI.**

MyGPT is a tiny GPT-style assistant you can talk to, teach, and correct. Everything
you do becomes training data: its memory grows, its neural language model retrains,
and you can literally watch its loss curve drop in the built-in Growth dashboard.

No GPUs, no API keys, no cloud — the whole brain runs in NumPy.

> **License — semi-closed source.** MyGPT is free to download and run
> *unmodified* for personal, non-commercial use. Redistribution, republishing,
> sale, sublicensing, modification, and commercial use are **not** permitted
> without written permission. See [LICENSE](LICENSE).

The self-learning machinery is ported from
[**CORTEX**](https://github.com/codero-sus/agi) (`codero-sus/agi`): fact extraction,
self-critique, constitution growth, skill synthesis, self-eval, background training,
dream replay, **System-2 chain-of-thought**, **episodic memory**, **goals**, and
**chat-history import** ("import your other lives").

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

**Python location** — the launcher scripts (`run.sh`, `updater.sh`,
`updater.bat`) read the interpreter from **`python.env`** in the project root:

```
PYTHON=.venv/bin/python        # Linux/macOS venv (default)
PYTHON=.venv\Scripts\python.exe  # Windows venv
PYTHON=/usr/bin/python3        # or any absolute path
```

If `python.env` is absent or its path doesn't exist, the scripts fall back to
the project `.venv`, then `python3` / `python`.

## Software updates (branch-pinned, confirmed)

MyGPT ships with a **manual, branch-pinned updater** (modeled on the one in
[Cortex LLMHoster](https://github.com/codero-sus/Cortex_LLMHoster)). Nothing
runs by itself — use either the WebUI or the command-line scripts:

```bash
./updater.sh              # Linux / macOS — check, then ask before installing
./updater.sh --check      # only check, never install
./updater.sh --yes        # install without asking
updater.bat               # Windows — same options
```

1. **Check** — *Growth → Software updates → 🔎 Check for updates* (or
   `./updater.sh --check`) reads the head
   commit of the pinned branch of `codero-sus/MyGPT` (the branch MyGPT ships on;
   override with `MYGPT_UPDATE_REF`) and the version declared there via the
   GitHub API.
2. **Install** — only after you press *⬇️ Install update* and confirm the exact
   commit shown by the check. MyGPT downloads the immutable archive
   `github.com/codero-sus/MyGPT/archive/<sha>.zip`, verifies it looks like MyGPT,
   and syncs it over the app directory.
3. **Preserved** — your learned state is never touched: `data/` (memory, weights,
   facts, episodes, Cortex settings), `.git/`, `.venv/`, dotfiles, and locally
   auto-written `skills/handle_*.py` files all survive. Restart the server to
   finish the update.

If the branch moved between your check and install, the install refuses and asks
for a fresh confirmation — you always install exactly the commit you reviewed.

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

## System-2 chain of thought (from CORTEX)

Hard questions run a deliberative chain before the bot speaks — visible as a
collapsible 💭 trace under each reply:

1. **Parse** — restate the question and its kind (why/how/compare/what-if/plan/…)
2. **Strategy** — causal, mechanism, compare, counterfactual, means-ends,
   principled, retrieve, first-principles, compute
3. **Decompose** — 2–4 subquestions
4. **Retrieve / deduce** — taught knowledge, semantic facts, episodic memories
5. **Hypothesize** — competing candidates (grounded / first-principles /
   analogical / composer), scored
6. **Critique** — devil's advocate pokes holes and drops confidence
7. **Decide** — commit with a confidence

Fast paths (math, skills, facts, strong recall, greetings) stay System-1 with a
short trace. Compare questions always deliberate — both sides get characterized.

## Code requests → code blocks in chat

There is **no agentic coding and no code execution**. When the user asks for
code, MyGPT composes a snippet from a built-in template library (primes,
fibonacci, factorials, digit sums, palindromes, anagrams, statistics, gcd/lcm,
base conversion, dates & weekdays, circle/sphere/triangle geometry, armstrong
numbers, powers of two, unit conversion, word counts) and returns it in a
**fenced code block inside the chat reply** — nothing is ever run and nothing
is ever written to files. If no template matches, MyGPT says so honestly and
points the user to **codero-sus on GitHub** for more:

```
👉 For more code and full projects, visit codero-sus on GitHub:
   https://github.com/codero-sus
```

The same link is credited in the sidebar and after every code reply.

## Local LLM back end · Cortex LLMHoster

MyGPT can route the open-ended questions it can't answer on its own to a
**locally hosted model** running under
[Cortex LLMHoster](https://github.com/codero-sus/Cortex_LLMHoster) — a
free-to-use local model hoster that manages llama.cpp/GGUF models (or any
OpenAI-compatible local engine) and exposes an OpenAI-compatible API.

* **No cloud.** Cortex runs on your machine; prompts and answers never leave
  it. MyGPT talks to it purely over HTTP (`/v1/chat/completions`, `/v1/models`,
  `/health`) as an ordinary client — Cortex itself is used unmodified, per its
  personal-use license.
* **Self-training stays in charge.** Math, learned skills, code requests and
  semantic facts always win. Cortex is only consulted for the questions MyGPT
  would otherwise shrug at, and each hosted answer can be **learned back** into
  MyGPT's own memory + corpus so the NumPy brain owns that knowledge next time.
* **Graceful fallback.** If Cortex is disabled, unreachable, or has no model
  loaded, MyGPT silently answers with its self-trained brain. Nothing breaks.

Point MyGPT at a running Cortex in **Mind → “Local LLM · Cortex LLMHoster”**
(server URL, API base, model, optional bearer key, enable/learn toggles, and a
*Save & test connection* button), or seed it from the environment:

```
MYGPT_CORTEX_URL=http://127.0.0.1:8624   # Cortex default
MYGPT_CORTEX_API_BASE=/v1                # OpenAI route prefix
MYGPT_CORTEX_MODEL=                      # blank = Cortex default model
MYGPT_CORTEX_API_KEY=                    # Cortex CORTEX_API_KEY, if set
MYGPT_CORTEX_ENABLED=1                   # 0 to disable
MYGPT_CORTEX_LEARN=1                     # 0 to not internalise answers
```

## Episodic memory, goals, and importing your other lives

* **Episodes** — every turn is stored with a hashed-token embedding; recall is a
  NumPy matrix-vector product with a recency bonus
* **Goals** — intrinsic drives (`become-more-capable`, `know-the-user`,
  `keep-constitution`) nudged forward by the improvement loop
* **Import** — drop a WhatsApp `.txt/.zip`, ChatGPT `conversations.json`, Claude
  JSON, Telegram `result.json`, or messages JSONL/CSV onto the Mind tab. Turns
  become episodes and train the neural core in the background (25MB / 5000-turn cap)

## How it answers

| Priority | Source                                    |
|----------|-------------------------------------------|
| 1 | Arithmetic skill (`12*12`, `(3+4)*2`) |
| 2 | Learned skill files in `skills/` (pattern-matched) |
| 3 | Code requests → fenced code block in chat + codero-sus GitHub link |
| 4 | Semantic facts about you (`what is my name?`) |
| 5 | Learned Q→A memory pairs (TF-IDF retrieval); 👍 reinforces, 👎+correction replaces |
| 5b | **Cortex LLMHoster** — a locally hosted model answers the rest (optional, learned back into memory) |
| 6 | Admits ignorance and asks to be taught |

## The WebUI

* **Chat** — rate every answer 👍/👎, correct it inline, teach-it chips on unknowns,
  collapsible chain-of-thought traces
* **Learn tab** — teach Q→A pairs, browse what it knows (with weights)
* **Growth tab** — loss chart, vitals, Train now, Dream, activity log, and a
  Software-updates card (manual check + confirmed branch-pinned install)
* **Mind tab** — the CORTEX loop: trainer status, self-eval %, constitution,
  semantic facts (with forget buttons), lessons, skills, goals, chat import,
  and a **Cortex LLMHoster** card to connect/test a local model back end
* **Code asks** — answered with a fenced code block in chat (never run, never
  written to files), plus a link to codero-sus on GitHub
* **Local LLM** — open questions can be answered by a model hosted by Cortex
  LLMHoster, with live connection status and the hosted model list

## Architecture

```
app.py                  Flask server + JSON API
python.env              Python interpreter location for the launcher scripts
updater.sh / .bat       command-line updater (check → confirm → install)
mygpt/
  brain.py              orchestrator: reply / feedback / teach / train loop
  memory.py             long-term Q→A memory, TF-IDF cosine retrieval
  langmodel.py          feedforward neural LM (NumPy, Adam, backprop, thread-safe)
  store.py              facts, lessons, constitution, metrics, events  (CORTEX)
  selflearn.py          the self-improvement loop                       (CORTEX)
  trainer.py            background trainer + dream replay               (CORTEX)
  skills.py             skill registry: skills as Python files          (CORTEX)
  reason.py             System-2 chain-of-thought reasoner              (CORTEX)
  episodes.py           episodic memory, hashed embeddings, numpy index (CORTEX)
  goals.py              intrinsic goals nudged by the loop              (CORTEX)
  importers.py          WhatsApp/ChatGPT/Claude/Telegram/JSONL parsers  (CORTEX)
  codegen.py            code requests → fenced code blocks in chat (no exec)
  cortex.py             Cortex LLMHoster client — optional local LLM back end
  updater.py            manual, branch-pinned update check + confirmed install
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
| POST   | `/api/import`   | multipart `file` (chat export)         |
| GET    | `/api/dream`    | —                                       |
| GET    | `/api/cortex`   | — (live Cortex LLMHoster status probe) |
| POST   | `/api/cortex`   | `{"enabled", "base_url", "api_base", "model", "api_key", "learn"}` |
| GET    | `/api/update/check` | — (branch-pinned update check via GitHub) |
| POST   | `/api/update/install` | `{"commit_sha"}` confirmed from a fresh check |
| GET    | `/api/stats`    | — (includes `version`, `mind`, `goals`, `cortex`, github) |
| GET    | `/api/memory`   | —                                       |

## Honest scope

This is a small, transparent model of the self-improvement loop — learn from
feedback → train → measure improvement — not a foundation model. Its "GPT" has
~200k parameters and gets genuinely better at predicting the conversations it has,
which is exactly what the dashboard shows. Self-learning mechanics (facts,
critique, constitution, skills, self-eval, background training, dreaming) are
adapted from the CORTEX project (`codero-sus/agi`).

## License and permitted use

MyGPT is **semi-closed source** under the *MyGPT Personal-Use License*
(see [LICENSE](LICENSE)):

* ✅ Anyone may **download, install, and run an unmodified copy**, free of
  charge, for **personal, non-commercial** use.
* ❌ **Modification, redistribution, republishing, sale, sublicensing, and any
  commercial use** are **not permitted** without separate written permission.
* The built-in updater installs only official, unmodified archives published by
  the author; using it means accepting the then-current license.
* Third-party dependencies (Flask, NumPy) keep their own licenses.

Permission requests: contact the author via https://github.com/codero-sus.
