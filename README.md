# MyGPT

**A self-training chatbot that improves over time — pure Python, NumPy brain, Flask WebUI.**

Made with ❤️ by **[codero-sus](https://github.com/codero-sus)** — all credits to them.
🌐 Website: [the-codero.web.app](https://the-codero.web.app/) ·
⭐ GitHub: [github.com/codero-sus](https://github.com/codero-sus) ·
📜 What's new: [CHANGELOG.md](CHANGELOG.md)

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
./run.sh            # Linux / macOS — creates a venv, installs deps,
                    # starts on http://localhost:8000
run.bat             # Windows — same, in Command Prompt / PowerShell
```

or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # .venv\Scripts\pip on Windows
.venv/bin/python app.py                        # .venv\Scripts\python app.py
```

Set `PORT` to change the port (default `8000`). All learned state lives in `data/` —
delete that folder to give MyGPT amnesia and start over.

**Python location (optional)** — the launcher scripts (`run.sh` / `run.bat`,
`updater.sh` / `updater.bat` — Linux, macOS and Windows all use the same
rules) resolve the interpreter in this order; the first valid one wins:

1. **`python.env`** in the project root (optional file) — `PYTHON=<path>`
2. the **`2PY2` environment variable** — a "second python" for users with a
   portable or embeddable Python (the name means a *second* python, not python2)
3. the project `.venv`, then `python3` / `python` on PATH

```
# python.env examples
PYTHON=.venv/bin/python          # Linux/macOS venv (default)
PYTHON=.venv\Scripts\python.exe  # Windows venv
PYTHON=/usr/bin/python3          # or any absolute path

# or, for portable/embeddable Python users:
set 2PY2=D:\python-embed\python.exe    (Windows)
export 2PY2=~/portable/python3.12      (note: set via env/printenv, the name
                                        starts with a digit)
```

Delete `python.env` and leave `2PY2` unset and everything falls back to the
project `.venv` automatically.

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
   `./updater.sh --check`) reads the head commit of the pinned branch of
   `codero-sus/MyGPT` and the version declared there via the GitHub API.
   The branch is resolved as: `MYGPT_UPDATE_REF` env var → the git branch
   this copy is checked out on (**so it always updates from *this* branch**)
   → the shipped default `arena/01a0f6e2-mygpt`.
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
code, MyGPT composes a snippet from a built-in template library of **247 code
families** (primes, fibonacci, factorials, digit sums, palindromes, anagrams,
statistics, gcd/lcm, base conversion, dates & weekdays, geometry, armstrong
numbers, powers of two, unit conversion, word counts, sorting/searching,
file/CSV/JSON I/O, classes, HTTP, regex, ciphers, matrices — plus games like
hangman and rock-paper-scissors, small apps like todo and contacts, and Python
idioms such as decorators, generators, dataclasses, enums, comprehensions,
argparse CLIs and unittest skeletons) and returns it in a
**fenced code block inside the chat reply** — nothing is ever run and nothing
is ever written to files. The library is split in two: **84 families** authored
in `mygpt/codegen.py` and a **163-family data pack** in
`mygpt/snippets_more.py` (algorithms, data structures, string/date/JSON
tooling, maths, files, classes, testing, CLI, security helpers) that registers
itself at import time. If no template matches, MyGPT says so honestly and
points the user to **codero-sus on GitHub** for more:

```
👉 For more code and full projects, visit codero-sus on GitHub:
   https://github.com/codero-sus
```

The same link is credited in the sidebar and after every code reply.

## Local LLM back ends · Cortex LLMHoster & Ollama

MyGPT can route the open-ended questions it can't answer on its own to a
**locally hosted model** — either under
[Cortex LLMHoster](https://github.com/codero-sus/Cortex_LLMHoster) (a
free-to-use local model hoster that manages llama.cpp/GGUF models or any
OpenAI-compatible local engine) or under [Ollama](https://ollama.com) (native
`/api/*` JSON API). The model bar above the chat picks the engine: *Auto
(brain → Cortex → Ollama)*, *MyGPT self-trained brain*, or a specific hosted
model.

**Auto-probe.** A background thread probes both hosts every 20 seconds, logs
when one appears or disappears, and the WebUI follows — start a host and it
shows up in the picker on its own. In *Auto* mode Cortex LLMHoster is tried
before Ollama. If **neither** host is present, MyGPT shows an install hint
(and occasionally mentions it in chat) pointing to Cortex LLMHoster by
codero-sus or Ollama; its self-trained brain keeps answering regardless.

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

### Ollama

Configure under **Mind → “Local LLM · Ollama”** (server URL, model,
enable/learn toggles, *Save & test connection*), or via environment:

```
MYGPT_OLLAMA_URL=http://127.0.0.1:11434  # OLLAMA_HOST also honoured
MYGPT_OLLAMA_MODEL=                      # blank = first installed model
MYGPT_OLLAMA_ENABLED=1                   # 0 to disable
MYGPT_OLLAMA_LEARN=1                     # 0 to not internalise answers
```

### Model checkpoints (`_model_trained/`)

Cortex and Ollama *serve* models; **MyGPT's own NumPy brain is what trains**.
Trained weights can be snapshotted on demand into `./_model_trained/`
(`<name>/lm_weights.npz` + `meta.json`):

* **WebUI** — Mind → *Model checkpoints* (optional label + quick training
  round), with Load/Delete per checkpoint; loading one makes it the active
  brain.
* **Chat** — say *“checkpoint the model”* or *“train and save the model”*
  (the latter trains first, then snapshots).

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
| 1b | **Maths pack** — 65 rules: factorials, fibonacci, primes, gcd/lcm, square roots, logs, trigonometry, statistics, percentages, geometry, units, roman numerals, bases, interest and more (`/api/math`) |
| 1c | **Text pack** — 55 rules: case, title case, base64/hex/url/rot13, sha256/md5/crc32, line tools, JSON pretty/minify, CSV→Markdown, extract emails/urls/numbers, pig latin, palindromes, lorem, slugify, censor and more (`/api/text`) |
| 2 | Learned skill files in `skills/` (pattern-matched) |
| 3 | Code requests → fenced code block in chat + codero-sus GitHub link |
| 4 | Semantic facts about you (`what is my name?`) |
| 5 | Learned Q→A memory pairs (TF-IDF retrieval); 👍 reinforces, 👎+correction replaces |
| 5b | **Cortex LLMHoster** — a locally hosted model answers the rest (optional, learned back into memory) |
| 6 | Admits ignorance and asks to be taught |

## The WebUI

* **Chat** — answers **stream in word-by-word** (Server-Sent Events), rate every
  answer 👍/👎, correct it inline, teach-it chips on unknowns,
  collapsible chain-of-thought traces, per-reply latency (⏱ ms), a **⧉ copy**
  button on every reply, **copy buttons inside every code block**, dependency-free
  **Python syntax highlighting**, quick-start suggestion chips, **conversation
  restore after page reload**, **day dividers** between dates, an unread badge
  on the jump-to-latest button, and **⬇️ export** (Markdown) plus JSON/CSV
  endpoints
* **Find & clean** — a live **chat search** box (Ctrl+K) that filters the
  transcript, and a **🗑 clear** button that wipes the visible transcript and its
  saved copy while keeping everything you taught (double-click any message to
  copy it)
* **Comfort** — 🌓 **light/dark theme** (follows your system on first visit) and
  A−/A+ **text-size controls**, both remembered in localStorage; a
  **print stylesheet** so Ctrl+P prints just the conversation; drag & drop a
  chat export anywhere on the chat panel to import it; a character counter near
  the 4000 limit; ↑ in an empty composer recalls your last message
* **Composer** — multi-line textarea: **Enter sends, Shift+Enter newlines,
  Escape clears, `/` focuses**; drafts survive reloads (localStorage); a
  floating **jump-to-latest** button appears when you scroll up; failed sends
  get a **↻ retry** chip; hover any message for its timestamp; the top-bar dot
  shows online/offline state
* **Model picker** — a dropdown right next to the send button picks which
  engine answers (Auto / brain / a specific Cortex or Ollama model); the
  status bar shows the active engine and the auto-probe state
* **Learn tab** — teach Q→A pairs, **bulk-teach** many pairs at once
  (`question :: answer`, up to 100 per batch), browse what it knows (with
  weights), and **search the memory layer** with ranked scores
* **Keyboard shortcuts** — Enter send · Shift+Enter newline · Escape clear ·
  `/` focus · `?` shortcuts dialog · Ctrl+K search · Ctrl+B sidebar ·
  Alt+1/2/3 tabs · Ctrl+Shift+E export · Ctrl+Shift+L clear chat
* **Comfort & accessibility** (v1.10) — 📐 **density** (compact/comfortable),
  ◐ **high contrast**, 🎞 **reduced motion**, ◧ **collapsible sidebar**,
  🔔 sound chime and 🖥 **desktop notifications** (with title-badge flash when
  the tab is hidden); everything is remembered. Pinned-message strip (max 8),
  hover **copy / pin / quote** on every message, **✏️ edit-last**, **⧉ copy-all**,
  **⤒ first**, **🔗 share** (Web Share API → clipboard fallback), **🖨 print**
  with a print stylesheet, plus a **skip-to-composer** link, `role="log"`
  transcript, `aria-busy` while a reply is streaming and `:focus-visible`
  outlines throughout
* **Never lose a message** (v1.10) — messages typed while offline queue in
  localStorage and flush automatically on reconnect; polling pauses after 5
  idle minutes to save battery; the status tooltip shows measured round-trip
  ping (probed every 45 s)
* **Growth tab** — loss chart, vitals, Train now, Dream, activity log, and a
  Software-updates card (manual check + confirmed branch-pinned install)
* **Mind tab** — the CORTEX loop: trainer status, **🧪 on-demand
  self-evaluation** with per-question results, constitution, semantic facts
  (with forget buttons), lessons, skills, goals, chat import, **Cortex
  LLMHoster** and **Ollama** backend cards, and **Model checkpoints**
  (snapshot/train/load/delete under `_model_trained/`)
* **Code asks** — answered with a fenced code block in chat (never run, never
  written to files), plus a link to codero-sus on GitHub
* **Local LLM** — open questions can be answered by a model hosted by Cortex
  LLMHoster or Ollama, with live connection status and the hosted model list;
  checkpoints can be **downloaded as zip** (weights + metadata)

## Efficiency notes

* Memory retrieval prunes candidates via an inverted token index; tokenizer is
  memoised; training reuses cached token-id encodings of the append-only corpus
* Cortex/Ollama clients use keep-alive connections; probes are TTL-cached;
  full state writes are debounced (user-critical ones — teach, feedback,
  checkpoints — flush immediately, anything pending flushes on shutdown)
* The WebUI dedupes `/api/stats` polling and only auto-scrolls when you're
  already near the bottom
* `codegen.has_template()`, `mathx.solve()` and `textfx.solve()` are
  `lru_cache`d — they are pure and sit on the per-message hot path
* Seed texts are deduplicated when loaded, so a repeated line can never
  double-weight a fact

## Tests

**451 tests** — 116 smoke tests plus 335 in `tests/test_v110.py`. A generator
emits one test *per template family* (every canonical ask must match its own
regex and return the family's own code, syntax-checked), one per maths rule and
one per text rule, plus seed-knowledge, Brain-wiring and API tests for the 11
new endpoints. Smoke coverage also spans the tokenizer, memory (including the
mixed-vocabulary crash regression), 60+ code templates, word-form math,
unit/temperature/roman conversions, list statistics, percent maths, the
language model, checkpoints (including path-traversal guards), episodes, the
backend clients (safe against dead ports), the full Brain pipeline, and every
API endpoint (including SSE streaming, bulk teaching, search, validation and
JSON error handlers):

```bash
.venv/bin/python -m unittest discover -s tests    # .venv\Scripts\python on Windows
```

No extra dependencies — stdlib `unittest` only. Every test boots a throwaway
Brain in a temp dir, so your real `data/` is never touched.

## Architecture

```
app.py                  Flask server + JSON API
python.env              optional Python location for the launcher scripts
run.sh / run.bat        start the WebUI (Linux/macOS and Windows)
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
| GET    | `/api/health`   | — (version, uptime, backend reachability) |
| GET    | `/api/ping`     | — (minimal round-trip probe)           |
| POST   | `/api/chat`     | `{"message": "…"}` (≤ 4000 chars)      |
| POST   | `/api/feedback` | `{"msg_id", "verdict": "up"\|"down", "correction"?}` |
| POST   | `/api/teach`    | `{"question", "answer"}`               |
| POST   | `/api/train`    | `{"epochs": 10}`                       |
| POST   | `/api/improve`  | — (force a medium improvement cycle)   |
| POST   | `/api/eval`     | — (run the self-eval battery now, per-question results) |
| GET    | `/api/export`   | — (download the conversation as Markdown) |
| GET    | `/api/history`  | `?limit=30` (recent turns; restores the chat view on reload) |
| GET    | `/api/checkpoint/download` | `?name=…` (checkpoint weights + meta as zip) |
| POST   | `/api/forget`   | `{"q": "user name"}` (drop facts)      |
| POST   | `/api/import`   | multipart `file` (chat export)         |
| GET    | `/api/dream`    | —                                       |
| GET    | `/api/cortex`   | — (live Cortex LLMHoster status probe) |
| POST   | `/api/cortex`   | `{"enabled", "base_url", "api_base", "model", "api_key", "learn"}` |
| GET    | `/api/ollama`   | — (live Ollama status probe)           |
| POST   | `/api/ollama`   | `{"enabled", "base_url", "model", "learn"}` |
| GET    | `/api/backends` | — (model picker: backends, models, checkpoints) |
| POST   | `/api/backends/select` | `{"backend": "brain"\|"cortex"\|"ollama"\|"auto", "model"?}` |
| POST   | `/api/checkpoint` | `{"label"?, "note"?, "train"?}` — snapshot weights to `_model_trained/` |
| GET    | `/api/checkpoints` | — (list saved checkpoints)          |
| POST   | `/api/checkpoint/load` | `{"name"}` — load weights as the active brain |
| POST   | `/api/checkpoint/delete` | `{"name"}`                      |
| GET    | `/api/update/check` | — (branch-pinned update check via GitHub) |
| POST   | `/api/update/install` | `{"commit_sha"}` confirmed from a fresh check |
| GET    | `/api/stats`    | — (includes `version`, `author`, `website`, `mind`, `goals`, `cortex`, `ollama`, github) |
| GET    | `/api/memory`   | —                                       |
| GET    | `/api/version`  | — (version + author links)             |
| POST   | `/api/chat/stream` | `{"message": "…"}` — SSE token stream + final JSON |
| GET    | `/api/events/stream` | — (SSE snapshot of recent self-learning events) |
| GET    | `/api/memory/search` | `?q=…&k=5` (ranked retrieval with scores) |
| GET    | `/api/memory/list` | `?offset=0&limit=50` (paginated memory) |
| GET    | `/api/suggest`  | `?q=frag` (question-title autocomplete) |
| GET    | `/api/analytics` | — (counters, intent/mode histograms, busiest hours, top memories) |
| POST   | `/api/teach/bulk` | `{"pairs": [{"question", "answer"}, …]}` — up to 100 |
| POST   | `/api/clear`    | — (clear the transcript; learned knowledge is kept) |
| GET    | `/api/checkpoint/info` | `?name=…` (single checkpoint metadata) |
| GET    | `/api/backends/models` | — (every answerable engine in one list) |
| GET    | `/api/export.json` / `/api/export.csv` | — (structured transcript exports) |
| GET    | `/api/math`     | `?q=…` (≤400) — maths pack, falls back to arithmetic |
| GET    | `/api/text`     | `?q=…` (≤2000) — text pack; 404 lists every rule |
| GET    | `/api/rules`    | — (inventory: maths, text and code rule names) |
| GET    | `/api/convert`  | `?q=…` (unit/temperature conversion only) |
| GET    | `/api/roman`    | `?q=…` (roman numerals both ways) |
| GET    | `/api/echo`     | `?q=…` (round-trip probe with length + server time) |
| GET    | `/api/uptime`   | — (seconds, formatted, started-at)       |
| GET    | `/api/endpoints`| — (self-describing route list)           |
| GET    | `/api/metrics`  | — (Prometheus-style text metrics)        |
| POST   | `/api/chat/batch` | `{"messages": […]} `— up to 10, returns a `results` array |
| GET    | `/api/quote`    | — (a random constitution principle)      |
| GET    | `/robots.txt` · `/manifest.json` | — (crawler policy · PWA manifest) |

All `/api/*` responses send permissive CORS headers and support `OPTIONS`
preflight, so local scripts and dashboards can call MyGPT directly. Every
response also carries `X-MyGPT-Version`, a per-request `X-Request-Id` (echoed
back if you supply one) and a `Server-Timing` duration header.

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

## Author & credits

**Author:** MyGPT is made with ❤️ by [codero-sus](https://github.com/codero-sus) —
all credit goes to them. 🌐 Website: [the-codero.web.app](https://the-codero.web.app/)

Credits and thanks, all by codero-sus:

* **MyGPT** — this project: the self-training chatbot, WebUI, updater and
  launcher scripts — [codero-sus/MyGPT](https://github.com/codero-sus/MyGPT)
* **CORTEX** — the self-learning loop (facts, self-critique, constitution,
  skills, self-eval, background training, dreaming, System-2 chains, episodic
  memory, goals, import) is ported from
  [codero-sus/agi](https://github.com/codero-sus/agi)
* **Cortex LLMHoster** — the optional local-LLM hosting server MyGPT can route
  open questions to — [codero-sus/Cortex_LLMHoster](https://github.com/codero-sus/Cortex_LLMHoster)
* **Ollama** — third-party local model runner supported as an extra chat
  backend ([ollama.com](https://ollama.com))
* **Flask & NumPy** — third-party dependencies, under their own licenses

Visit **[github.com/codero-sus](https://github.com/codero-sus)** for the full
project family and **[the-codero.web.app](https://the-codero.web.app/)** for
the author's website.
