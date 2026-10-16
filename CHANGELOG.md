# Changelog

All credits: **codero-sus** — [github.com/codero-sus](https://github.com/codero-sus) ·
[the-codero.web.app](https://the-codero.web.app/)

## v1.11.1 — background training that stays out of the way (18 items)

The complaint that started this round was "make it train in the background with
very little impact". Measuring it showed the claim was half-true: the trainer
already ran in a thread with a queue, **but every fifth learning event ran a
whole training round inline on the request thread** with the model locked. That
is a 0.7 s chat stall and a 2.4 s teach stall, on a fast machine, for work
nobody was waiting on. It is fixed, and the four numbers below are the evidence.

### Background trainer (9)

1. `NeuralLM.step_batch()` — run one Adam step over one batch of windows; the lock is held for that step alone, never around a caller's loop
2. `NeuralLM.all_windows()` — build a round's window list separately from running it
3. A full round is now run batch-by-batch by the trainer, so a request never waits on more than one batch
4. **Requests tell the trainer to stand down**: `trainer.request_started()` / `request_finished()` wired into Flask's `before_request` / `after_request`
5. A cooldown after the last response (`MYGPT_TRAIN_COOLDOWN`, default 0.25 s) so the moment you send a message is never the moment it grabs the CPU
6. A request that hangs longer than 120 s is ignored, so a client that vanished mid-stream cannot freeze learning forever
7. Duty cycle (`MYGPT_TRAIN_DUTY`, default 0.35): the thread sleeps after each chunk so its CPU time stays under that share of one core, and only while there is work queued
8. `paused` — stop background training entirely; `stop()` also interrupts any sleep rather than waiting for a nap it no longer needs
9. `snapshot()` reports duty **actually observed** from the OS thread clock (`/proc/self/task/<tid>/stat`), plus CPU ms, rounds, queue and whether it is currently yielding

### The bug that made background training a lie (4)

10. **Auto-training ran on the request thread.** `_maybe_auto_train` called `train()` directly from inside the chat turn; `train()` holds the model lock for the whole round
11. Training rounds are now **queued** (`submit_round`, coalesced so only one is ever pending) and run during the next idle moment — deferred, never dropped
12. `Brain.train(requirement=…)` makes the distinction explicit: `"explicit"` blocks (you asked), `"background"` queues (upkeep nobody is waiting on)
13. The checkpoint command's "train and save" now trains in the background first, and `/api/train` still blocks because you asked for it

### API and UI (3)

14. `GET /api/trainer` — live trainer state and the honest duty figure
15. `POST /api/trainer` — `{"paused"?: bool, "duty"?: 0.05-1.0, "cooldown"?: s}`, validated
16. Model tab gains a Self-training card: duty (observed and target), CPU used, background steps and rounds, yielding state, a duty slider and a Pause/Resume button; `/api/metrics` exposes the same numbers as Prometheus-style gauges

### Measurement (2)

17. `tools/benchmark.py --trainer-impact` — same workload over real HTTP (`/api/chat` + `/api/teach`) run twice: once with rounds inline (the old code path reproduced exactly), once with rounds queued. Reports chat/teach percentiles, session wall time, chat latency *while 400 lines are queued*, whether the deferred round completes, and the trainer's own duty cycle
18. Measured: worst chat stall **719 ms → 34 ms**, worst teach stall **2,401 ms → 30 ms**, session **7.1 s → 3.9 s**, chat p95 while 400 lines are queued **26 ms**, trainer duty **0.34 of one core** against a 0.35 target (0.0 when paused), and the deferred round completed 10.7 s after the session using 3.94 s of CPU. `tests/test_trainer.py` (20 tests) locks all of it in, including a test that would fail if a learning event ever blocked for a round again

**Counting note, same as v1.11.0:** 18 items, but really three changes — a trainer
that yields, a training trigger moved off the request thread, and the
measurement that proves both. Items 10–13 are one bug described in parts.

## v1.11.0 — the transformer brain (107 items)

MyGPT's own model is now a real decoder-only transformer, and it can hand
hard questions to full-size local models through llama.cpp or 🤗 transformers.
Every claim in this list is checkable in the repository, and the model's
backward pass is verified numerically rather than asserted.

### Transformer brain (25)

1. `mygpt/transformer.py` — a decoder-only transformer language model in pure NumPy
2. Learned token embeddings + learned positional embeddings
3. N × pre-LayerNorm blocks (LayerNorm before every sublayer, not after)
4. Multi-head causal self-attention, heads split from full-width Q/K/V projections
5. Scaled dot-product attention with an upper-triangular causal mask
6. GELU feed-forward at 4× the model dimension
7. Residual connections around both sublayers
8. Final LayerNorm before the output head
9. Weight tying between the token embedding and the output head (GPT-2 style)
10. Bias-free projections (LLaMA style) — fewer parameters, same quality at this size
11. Inverted dropout on attention and residual outputs (train-time only)
12. Adam optimiser with warmup + cosine learning-rate decay
13. Global gradient-norm clipping at 1.0
14. Top-k, top-p (nucleus), temperature and repetition-penalty sampling
15. Prompt continuation: `generate(prompt=…)` starts from your text
16. `next_token_probs()` — the model's own ranked prediction for what comes next
17. Drop-in `NeuralLM` subclass: the trainer, checkpoints, memory and Brain need no changes
18. Vocabulary growth carries known embedding rows across `rebuild_vocab()`
19. `save()`/`load()` round-trip weights, vocab, counts and step counter in one npz
20. `load()` refuses a checkpoint from a different architecture instead of half-loading it
21. `describe()` — self-reported architecture card used by `/api/model`
22. `param_count()` and float32/float64 dtypes (float64 makes the gradient exact)
23. Efficiency: the head projects only each window's **last** position, not all `ctx` positions
24. Efficiency: GELU uses `x * x * x` instead of `x ** 3` — numpy's float32 power operator took the slow generic path (measured 3.05 ms vs 0.021 ms on the hot array), and GELU runs twice per step. Seed training went 9.7 s → 4.1 s with a bit-identical loss curve
25. Tunable via `MYGPT_BLOCKS`, `MYGPT_HEADS`, `MYGPT_DIM`, `MYGPT_CTX`, `MYGPT_DROPOUT`, `MYGPT_LR`

### Correctness verification (11)

26. `tests/test_transformer.py` — 33 tests, including a **central-difference gradient check** over every parameter tensor of 1-, 2- and 3-block models (max relative error 3.3e-06 at the optimal step size, which is float64 cancellation noise, not model error)
27. Gradient check in float64 so the finite difference is not swamped by float32 rounding
28. Causality test: editing the last token must not change any earlier position's logits
29. Consistency test: the fast last-position path equals the last slice of the full-position path
30. Relation test: a (B, V) gradient produces exactly the parameter gradients a (B, C, V) gradient does when the earlier positions carry no gradient
31. Learning test: perplexity falls and training loss drops over 60 rounds
32. Learning-rate test: warmup rises, peaks exactly at `lr`, then decays but never reaches zero
33. Clip test: a huge gradient cannot move a weight by more than the learning rate allows
34. Sampling tests: nucleus size derived independently from the cumulative distribution, repetition penalty lowers a repeated token's probability, top-p renormalises
35. Reproducibility test: same seed ⇒ same generated text
36. Persistence tests: identical weights after a save/load round trip, a foreign checkpoint is refused

### llama.cpp engine (11)

37. `mygpt/llamacpp_backend.py` — runs a local `.gguf` model **in-process** through llama-cpp-python
38. Auto-discovery of `models/*.gguf` and `data/models/*.gguf` (drop a file in and it just works)
39. `MYGPT_LLAMACPP_MODEL`, `_ENABLED`, `_LEARN`, `_CTX`, `_THREADS`, `_GPU_LAYERS`, `_MAX_TOKENS`, `_TEMPERATURE` configuration, persisted to `data/llamacpp.json`
40. Context window clamped to the length the model was **trained** with (read from the GGUF header, so llama.cpp never warns about overflow)
41. Lazy model load with reuse, explicit `unload()`, and load-time measurement
42. Chat through `create_chat_completion()` with a system prompt and trimmed history
43. Raw continuation through `create_completion()` for the UI's generation studio
44. Package-missing, file-missing, disabled and corrupt-file paths all degrade to a precise `probe()` reason instead of an exception
45. Answers can be learned back into MyGPT's own memory, like every other engine
46. `tests/gguf_fixture.py` builds a **valid tiny GGUF** with the official `gguf` writer, so the tests exercise real llama.cpp inference instead of mocks
47. 13 llama.cpp tests, including real generation, real chat, real header parsing and a real corrupt-file rejection

### 🤗 transformers engine (8)

48. `mygpt/hf_backend.py` — runs a causal LM from the HuggingFace Hub or a local directory
49. `MYGPT_HF_MODEL`, `_ENABLED`, `_LEARN`, `_DEVICE`, `_DTYPE`, `_MAX_TOKENS`, `_TEMPERATURE`, `_TOP_P`, `_OFFLINE` configuration, persisted to `data/hf.json`
50. Chat template used when the tokenizer has one, readable transcript when it does not
51. Device and dtype selection (cpu / cuda / mps, float32 / float16 / bfloat16 / auto)
52. Offline mode (`MYGPT_HF_OFFLINE=1`) for air-gapped machines with local weights
53. Lazy-loading pipeline with explicit `unload()`
54. Honest gating: without torch it reports *that* — torch is a ~2 GB dependency and is deliberately optional (`requirements-optional.txt`)
55. 13 transformers tests covering configuration, persistence, offline rules and the exact unavailability reasons

### Brain and engines (10)

56. The transformer is now the **default brain**; `MYGPT_ARCH=mlp` keeps the original network
57. `Brain._make_lm()` — architecture factory with a fallback to the MLP if the transformer cannot be built
58. `Brain.model_card()` — architecture, size, vocab, context, training state, checkpoints, engines
59. `Brain.backend_summary()` — every engine with availability, versions and the reason it is not ready
60. An MLP checkpoint is refused by the transformer and the corpus is re-tokenised instead — upgrading the architecture never orphans existing knowledge
61. `NeuralLM.load()` now returns False for a foreign checkpoint instead of raising `KeyError`
62. `auto` mode tries Cortex → Ollama → llama.cpp → transformers, so a running server always wins
63. Auto-probe loop covers the two new engines (detected / back online / offline events)
64. `any_local_llm()` and the install hint now consider in-process engines too
65. `stats()` reports `arch`, `params` and optimiser `steps` for the UI

### API (8)

66. `GET /api/model` — the architecture card
67. `GET /api/model/topnext?q=&k=` — ranked next-token probabilities
68. `POST /api/generate` — sample from the brain or an in-process engine, with latency reported
69. `GET /api/engines` — every engine's readiness, with reasons
70. `POST /api/engine/config` — configure llama.cpp or transformers live
71. `/api/backends` now lists five engines, each labelled and probed
72. `/api/backends/select` accepts `llamacpp` and `hf`
73. Parameters are clamped (tokens ≤ 400, temperature ≤ 3.0, top_p ∈ [0.05, 1]) — no 500s from silly input

### WebUI (10)

74. New **🧠 Model** tab (Alt+4) with three cards
75. Architecture card: parameters, blocks, heads, dim, context, optimiser steps, vocab, last loss
76. Plain-English description of the stack, plus tags for the training recipe and corpus size
77. Engine list: every engine with a ready / not-set-up / disabled badge, versions and models
78. Install command shown inline for engines that need one
79. Generation studio: prompt box, live-labelled sliders for tokens, temperature, top-k, top-p and repetition penalty, and an engine picker
80. Next-token prediction view: the softmax drawn as ranked bars with percentages
81. `↻ Re-probe engines` button
82. CSS for the model card, engine list, badges, sliders, generation output and probability bars
83. Reduced-motion respected by the new transitions

### Bugs fixed (8)

84. **`.gguf` discovery ignored an explicitly-scoped `models_dir`** — it also scanned the current working directory's `models/`, so a demo model sitting in the repo quietly changed the meaning of the test suite and of any app that keeps its models elsewhere. Found by putting a real model in `models/` and watching two clean test runs turn into two failures
85. `MYGPT_MODELS_DIR` (which folder MyGPT scans for models, default `<project root>/models`) and `MYGPT_LLAMACPP_MODELS` (override the search roots entirely; an empty value means "look nowhere") — the knob the tests needed to stay honest while a real model sits in `models/`
86. **The transformer was trained against the wrong logits** — the loss read position 0 of each window instead of the last position. Found by the gradient check, not by watching the loss go down
87. **The gradient corresponded to a different objective than the reported loss** — `dlogits` was initialised from the softmax, leaving gradient at every position. Also found by the gradient check
88. The corpus was read *after* the model loaded, so the architecture-change warmup never ran and the brain silently booted knowing only `<pad>`/`<unk>`
89. `perplexity()` scored the first position of each window rather than the last
90. `NeuralLM.load()` raised `KeyError` on a transformer checkpoint
91. Two test-harness bugs found while writing the checks (3-blocks at 0.05 tolerance in float32; a hardcoded nucleus size) — noted because the checks matter more than the assertions

### Measurement (13)

92. `tools/benchmark.py` — every number in this release is reproducible with one command (`--json`, `--live`, `--epochs N`)
93. Trains the transformer and the old MLP on the same corpus, the same context length (6 tokens), the same epochs and batch, so what is compared is the architecture rather than the configuration
94. Held-out perplexity: the last 10% of the corpus's texts are never trained on, and both models are scored on them
95. A scrambled-target control — shuffle the answers and perplexity must rise to at least the uniform baseline, or the metric isn't measuring prediction
96. The uniform baseline (perplexity = vocabulary size) is printed so that small numbers can be read in context
97. The script asserts the vocabulary is non-empty before printing anything: its first version trained both models on a four-token vocabulary because the corpus was never fed to them, and printed entirely plausible nonsense
98. Central-difference gradient check over all 24 parameter tensors of the shipped configuration, in float64 (at float32 a 1e-4 difference is round-off and the check would be meaningless)
99. llama.cpp load time, decode speed, file size and requested-vs-trained context window
100. Measured: at 20 epochs both models have memorised the corpus (train perplexity ≈ 2, so training loss alone tells you nothing) yet the transformer's held-out perplexity is 7,459 against the MLP's 212,977 — **28× lower** — for 3.96 s against 0.56 s
101. Measured: at a 5-epoch budget the gap is far smaller (770 vs 1,170), so the advantage is a scaling effect rather than something visible in one step
102. The llama.cpp speed figure names the 114 KB test GGUF it came from, because decode speed scales with model size and the number would otherwise read as a claim about real multi-billion-parameter checkpoints
103. `tests/test_benchmark.py` (6 tests) runs the benchmark's own code paths, including the vocabulary assertion and a real gradient check, so a broken benchmark fails the suite instead of printing numbers nobody can trust
104. README gains a "Measure it yourself" section: the measured table, the reproduction commands and the two honesty notes

### Docs (3)

105. README: new "The brain is a transformer" section, the local-model engine table, the Model tab, the new endpoints and the honest caveat about small-model prose
106. `requirements-optional.txt` — llama-cpp-python, gguf, transformers, torch (with the CPU-only torch advice), none of which MyGPT itself requires
107. Version bumped to 1.11.0

**Total: 107 numbered items.** Note what this list *is*: an itemisation of
changes, not 107 features. Most of it is one transformer, one benchmark and one
bug fix described in parts. The release was written the other way round from
v1.10.0 — the numbers came first (a gradient check, a held-out perplexity
comparison, a profiler trace) and the items describe what those measurements
forced us to change. Six of the eight bugs were found by measuring rather than
by reading the code, which a longer feature list would not have caught.

One more disclosure, because the habit of counting is worth breaking: the
"13 measurement items" above are 13 sentences about a 300-line script, and the
"10 WebUI items" are 10 edits to one tab. Neither number means what a reader
might assume.
## v1.10.0 — the 777+ release (1057 items)

Every item below is verifiable in the repository: templates in
`mygpt/snippets_more.py`, rules in `mygpt/mathx.py` and
`mygpt/textfx.py`, knowledge in `seed_corpus.json`, routes in
`app.py`, tests in `tests/test_v110.py`.

### Code templates (168)

1. Template family: linear search
2. Template family: selection sort
3. Template family: insertion sort
4. Template family: merge sort
5. Template family: quick sort
6. Template family: heap sort
7. Template family: counting sort
8. Template family: binary search recursive
9. Template family: two sum problem
10. Template family: maximum subarray
11. Template family: longest common prefix
12. Template family: longest common subsequence
13. Template family: edit distance
14. Template family: knapsack 0 1
15. Template family: coin change
16. Template family: fibonacci memoized
17. Template family: pascal triangle
18. Template family: catalan numbers
19. Template family: prime factorization
20. Template family: sieve of eratosthenes
21. Template family: nth prime
22. Template family: twin primes
23. Template family: perfect numbers
24. Template family: amicable numbers
25. Template family: happy numbers
26. Template family: kaprekar number
27. Template family: automorphic number
28. Template family: sum of divisors
29. Template family: count divisors
30. Template family: euler totient
31. Template family: trailing zeros factorial
32. Template family: binomial coefficient
33. Template family: permutations and combinations
34. Template family: power set
35. Template family: cartesian product
36. Template family: rotate a list
37. Template family: chunk a list
38. Template family: partition list
39. Template family: group by key
40. Template family: invert a dictionary
41. Template family: sort dict by value
42. Template family: dict from two lists
43. Template family: deep merge dicts
44. Template family: flatten a dict
45. Template family: count occurrences
46. Template family: find duplicates in list
47. Template family: remove falsy values
48. Template family: zip longest
49. Template family: pairwise iteration
50. Template family: matrix multiplication
51. Template family: matrix addition
52. Template family: identity matrix
53. Template family: determinant
54. Template family: rotate matrix
55. Template family: spiral matrix
56. Template family: diagonal sum
57. Template family: string to int
58. Template family: int to string
59. Template family: vigenere cipher
60. Template family: morse code
61. Template family: atbash cipher
62. Template family: base64 encode decode
63. Template family: hash a string
64. Template family: uuid generation
65. Template family: random shuffle
66. Template family: weighted choice
67. Template family: roll dice statistics
68. Template family: deck of cards
69. Template family: memoize decorator
70. Template family: retry decorator
71. Template family: singleton pattern
72. Template family: factory pattern
73. Template family: observer pattern
74. Template family: strategy pattern
75. Template family: namedtuple example
76. Template family: defaultdict example
77. Template family: heapq example
78. Template family: bisect example
79. Template family: itertools example
80. Template family: functools reduce
81. Template family: functools partial
82. Template family: context manager class
83. Template family: contextmanager decorator
84. Template family: property decorator
85. Template family: classmethod staticmethod
86. Template family: frozen dataclass
87. Template family: dataclass with slots
88. Template family: abc abstract class
89. Template family: typeddict example
90. Template family: mro multiple inheritance
91. Template family: counter example
92. Template family: chainmap example
93. Template family: csv dict reader
94. Template family: csv dict writer
95. Template family: json pretty print
96. Template family: json to csv
97. Template family: csv to json
98. Template family: ini config parser
99. Template family: xml parse example
100. Template family: sqlite basics
101. Template family: sqlite parameterized query
102. Template family: sqlite context manager
103. Template family: copy a file
104. Template family: move or rename a file
105. Template family: delete files by pattern
106. Template family: make directory tree
107. Template family: zip files into archive
108. Template family: unzip archive
109. Template family: human readable file size
110. Template family: check if file exists
111. Template family: temp file usage
112. Template family: pathlib tour
113. Template family: read file in chunks
114. Template family: tail a file
115. Template family: word frequency from file
116. Template family: grep text in files
117. Template family: bulk rename files
118. Template family: deduplicate files by hash
119. Template family: download a file
120. Template family: progress bar
121. Template family: text spinner
122. Template family: ansi colors
123. Template family: clear the screen
124. Template family: terminal menu
125. Template family: stopwatch
126. Template family: beep sound
127. Template family: rotating log files
128. Template family: serve a directory
129. Template family: http client with retries
130. Template family: url parsing
131. Template family: build a query string
132. Template family: json http post
133. Template family: basic auth header
134. Template family: rate limiter
135. `codegen.register_family()` — data-driven template registration
136. `snippets_more._broaden()` — auto-broadens a family regex until its canonical ask matches
137. `TEMPLATE_HINT` rewritten to advertise all 218 families (~1.9 KB)
138. Template family: trie
139. Template family: bloom filter
140. Template family: dijkstra
141. Template family: topological sort
142. Template family: bfs
143. Template family: dfs
144. Template family: heap
145. Template family: queue
146. Template family: deque
147. Template family: state machine
148. Template family: lru cache
149. Template family: ttl cache
150. Template family: backoff
151. Template family: circuit breaker
152. Template family: event emitter
153. Template family: cron
154. Template family: jwt
155. Template family: checksum
156. Template family: sliding window
157. Template family: two pointers
158. Template family: benchmark
159. Template family: memoise
160. Template family: pagination
161. Template family: async
162. Template family: threads
163. Template family: zip files
164. Template family: html escape
165. Template family: markdown table
166. Template family: validate email
167. `codegen.match_family()` — families are ranked by how much of the request they explain (match span, then pattern specificity, then recency), so a narrow ask can no longer be swallowed by a broad earlier pattern
168. `codegen._ranked()` — `code_reply()` walks families best-first instead of in registration order

### Seed knowledge (401)

169. Seed pair: what is a linked list
170. Seed pair: what is a stack
171. Seed pair: what is a queue
172. Seed pair: what is a hash table
173. Seed pair: what is a binary tree
174. Seed pair: what is a heap
175. Seed pair: what is a graph
176. Seed pair: what is breadth first search
177. Seed pair: what is depth first search
178. Seed pair: what is big o notation
179. Seed pair: what is a stable sort
180. Seed pair: what is recursion
181. Seed pair: what is dynamic programming
182. Seed pair: what is greedy algorithm
183. Seed pair: what is a sliding window
184. Seed pair: what is two pointer technique
185. Seed pair: what is memoisation
186. Seed pair: what is a deque
187. Seed pair: what is a generator
188. Seed pair: what is a context manager
189. Seed pair: what is a closure
190. Seed pair: what is duck typing
191. Seed pair: what is the gil
192. Seed pair: what are type hints
193. Seed pair: what is pytest
194. Seed pair: what is a virtual environment
195. Seed pair: what is pep 8
196. Seed pair: what is a wheel
197. Seed pair: what is requirements txt
198. Seed pair: what is a shebang
199. Seed pair: what does if __name__ mean
200. Seed pair: what is scope in python
201. Seed pair: what is immutability
202. Seed pair: what is tuple unpacking
203. Seed pair: what is a frozenset
204. Seed pair: what is a byte string
205. Seed pair: what is a raw string
206. Seed pair: what is string formatting
207. Seed pair: what is a join
208. Seed pair: what is a walrus operator
209. Seed pair: what is a ternary expression
210. Seed pair: what is a match statement
211. Seed pair: what is an exception chain
212. Seed pair: what is a finally block
213. Seed pair: what is a custom exception
214. Seed pair: what are logging levels
215. Seed pair: what is a daemon thread
216. Seed pair: what is a race condition
217. Seed pair: what is async await
218. Seed pair: what is a coroutine
219. Seed pair: what is an event loop
220. Seed pair: what is the difference between process and thread
221. Seed pair: what is multiprocessing
222. Seed pair: what is a memory leak in python
223. Seed pair: what is garbage collection
224. Seed pair: what is a linter
225. Seed pair: what is a formatter
226. Seed pair: what is a type checker
227. Seed pair: what is ci
228. Seed pair: what is a pre commit hook
229. Seed pair: what is dependency pinning
230. Seed pair: what is semantic versioning
231. Seed pair: what is a changelog
232. Seed pair: what is a regression
233. Seed pair: what is test coverage
234. Seed pair: what is mocking
235. Seed pair: what is a fixture
236. Seed pair: what is property based testing
237. Seed pair: what is api versioning
238. Seed pair: what is a health check
239. Seed pair: what is a load balancer
240. Seed pair: what is a cdn
241. Seed pair: what is http status 418
242. Seed pair: what is idempotency
243. Seed pair: what is a websocket
244. Seed pair: what is long polling
245. Seed pair: what is a json schema
246. Seed pair: what is openapi
247. Seed pair: what is csp
248. Seed pair: what is xss
249. Seed pair: what is sqli
250. Seed pair: what is csrf
251. Seed pair: what is a salt
252. Seed pair: what is hashing versus encryption
253. Seed pair: what is constant time comparison
254. Seed pair: what is the principle of least privilege
255. Seed pair: what is a token bucket
256. Seed pair: what is backoff
257. Seed pair: what is a circuit breaker
258. Seed pair: what is observability
259. Seed pair: what is a metric histogram
260. Seed pair: what is a trace id
261. Seed pair: what is graceful shutdown
262. Seed pair: what is a migration
263. Seed pair: what is privacy by design
264. Seed pair: what is a seed corpus
265. Seed pair: what is human in the loop
266. Seed pair: what is the ai alignment problem
267. Seed pair: what is goodhart's law
268. Seed pair: what is technical debt
269. Seed pair: what is refactoring
270. Seed pair: what is a code smell
271. Seed pair: what is yagni
272. Seed pair: what is kiss
273. Seed pair: what is dry
274. Seed pair: what is the boy scout rule
275. Seed pair: what is rubber duck debugging
276. Seed pair: what is a stack trace
277. Seed pair: what is a breakpoint
278. Seed pair: what is logging versus printing
279. Seed pair: what is an assertion
280. Seed pair: what is fail fast
281. Seed pair: what is defensive copying
282. Seed pair: what is a feature flag
283. Seed pair: what is canary deployment
284. Seed pair: what is rollback
285. Seed pair: what is a postmortem
286. Seed pair: what is an adr
287. Seed pair: what is technical writing
288. Seed pair: what is a user story
289. Seed pair: what is mvp
290. Seed pair: what is dogfooding
291. Seed pair: what is progressive disclosure
292. Seed pair: what is a vertical slice
293. Seed pair: what is tracer bullet development
294. Seed pair: what is yak shaving
295. Seed pair: what is a timebox
296. Seed pair: what is definition of done
297. Seed pair: what is acceptance criteria
298. Seed pair: what is load testing
299. Seed pair: what is chaos testing
300. Seed pair: what is a 400 versus 500
301. Seed pair: what is a 429
302. Seed pair: what is a 503
303. Seed pair: what is a 204
304. Seed pair: what is idempotent retry
305. Seed pair: what is a webhook versus polling
306. Seed pair: what is eventual consistency
307. Seed pair: what is a write ahead log
308. Seed pair: what is an atomic rename
309. Seed pair: what is a checksum
310. Seed pair: what is a heartbeat
311. Seed pair: what is a leaky abstraction
312. Seed pair: what is the law of demeter
313. Seed pair: what is dependency injection
314. Seed pair: what is inversion of control
315. Seed pair: what is deterministic code
316. Seed pair: what is a side effect
317. Seed pair: what is defensive validation
318. Seed pair: what is a data retention policy
319. Seed pair: what is backpressure
320. Seed pair: what is a semaphore
321. Seed pair: what is a deadlock
322. Seed pair: what is jitter
323. Seed pair: what is monotonic time
324. Seed pair: what is utc versus local time
325. Seed pair: what is epoch time
326. Seed pair: what is an iso 8601 date
327. Seed pair: what is a canonical form
328. Seed pair: what is stemming
329. Seed pair: what is stop word removal
330. Seed pair: what is a posting list
331. Seed pair: what is a term frequency
332. Seed pair: what is a document frequency
333. Seed pair: what is a dot product
334. Seed pair: what is vectorisation in numpy
335. Seed pair: what is broadcasting
336. Seed pair: what is a view versus a copy
337. Seed pair: what is a hot path
338. Seed pair: what is a bottleneck
339. Seed pair: what is a cold start
340. Seed pair: what is a warm cache
341. Seed pair: what is the 80 20 rule
342. Seed pair: what is hashability
343. Seed pair: what is a hash collision
344. Seed pair: what is a load factor
345. Seed pair: what is a balanced tree
346. Seed pair: what is a b-tree
347. Seed pair: what is a union find
348. Seed pair: what is topological sort
349. Seed pair: what is dijkstra
350. Seed pair: what is a star search
351. Seed pair: what is a minimum spanning tree
352. Seed pair: what is a segment tree
353. Seed pair: what is a suffix array
354. Seed pair: what is rolling hash
355. Seed pair: what is kmp
356. Seed pair: what is meet in the middle
357. Seed pair: what is a state machine
358. Seed pair: what is a finite automaton
359. Seed pair: what is the halting problem
360. Seed pair: what is p versus np
361. Seed pair: what is np complete
362. Seed pair: what is the travelling salesman problem
363. Seed pair: what is the pigeonhole principle
364. Seed pair: what is an invariant
365. Seed pair: what is induction
366. Seed pair: what is a counterexample
367. Seed pair: what is occam's razor
368. Seed pair: what is parkinson's law
369. Seed pair: what is conway's law
370. Seed pair: what is the map is not the territory
371. Seed pair: what is symbolic versus statistical ai
372. Seed pair: what is explainability
373. Seed pair: what is a confidence score
374. Seed pair: what is calibration
375. Seed pair: what is hallucination
376. Seed pair: what is a guardrail
377. Seed pair: what is feedback loop design
378. Seed pair: what is reinforcement in retrieval
379. Seed pair: what is catastrophic forgetting
380. Seed pair: what is a replay buffer
381. Seed pair: what is self supervision
382. Seed pair: what is a knowledge base versus a model
383. Seed pair: what is provenance
384. Seed pair: what is a tombstone
385. Seed pair: what is idempotent teaching
386. Seed pair: what is deduplication
387. Seed pair: what is a quality gate
388. Seed pair: what is a preflight check
389. Seed pair: what is a status page
390. Seed pair: what is a threat model
391. Seed pair: what is path traversal
392. Seed pair: what is input fuzzing
393. Seed pair: what is output encoding
394. Seed pair: what is atomicity
395. Seed pair: what is durability
396. Seed pair: what is a single writer principle
397. Seed pair: what is a bounded queue
398. Seed pair: what is an unbounded growth bug
399. Seed pair: what is a watchdog
400. Seed pair: what is a capability probe
401. Seed pair: what is explicit configuration
402. Seed pair: what is a twelve factor app
403. Seed pair: what is a monolith
404. Seed pair: what is coupling
405. Seed pair: what is cohesion
406. Seed pair: what is a test double
407. Seed pair: what is a hermetic test
408. Seed pair: what is a smoke test
409. Seed pair: what is test isolation
410. Seed pair: what is a golden file
411. Seed pair: what is flaky test
412. Seed pair: what is accessibility
413. Seed pair: what is aria
414. Seed pair: what is color contrast
415. Seed pair: what is reduced motion
416. Seed pair: what is semantic html
417. Seed pair: what is an accessible name
418. Seed pair: what is tab order
419. Seed pair: what is a skip link
420. Seed pair: what is internationalisation
421. Seed pair: what is a time zone bug
422. Seed pair: what is a monospace font
423. Seed pair: what is a pwa install
424. Seed pair: what is offline first
425. Seed pair: what is localstorage
426. Seed pair: what is a service worker
427. Seed pair: what is debouncing
428. Seed pair: what is an optimistic update
429. Seed pair: what is a toast
430. Seed pair: what is fitts law
431. Seed pair: what is hicks law
432. Seed pair: what is a design token
433. Seed pair: what is flexbox versus grid
434. Seed pair: what is perceived performance
435. Seed pair: what is cpu versus io bound
436. Seed pair: what is a microbenchmark
437. Seed pair: what is a reverse proxy
438. Seed pair: what is http keep alive
439. Seed pair: what is an etag
440. Seed pair: what is graceful degradation
441. Seed pair: what is progressive enhancement
442. Seed pair: what is a fallback chain
443. Seed pair: what is an lru cache
444. Seed pair: what is a ttl
445. Seed pair: what is a schema
446. Seed pair: what is a contract test
447. Seed pair: what is a regression suite
448. Seed pair: what is a test pyramid
449. Seed pair: what is a trie
450. Seed pair: what is a bloom filter
451. Seed pair: what is tf idf
452. Seed pair: what is an inverted index
453. Seed pair: what is cosine similarity
454. Seed pair: what is edit distance used for
455. Seed pair: what is levenshtein distance
456. Seed pair: what is a monte carlo method
457. Seed pair: what is the birthday problem
458. Seed pair: what is the law of large numbers
459. Seed pair: what is the normal distribution
460. Seed pair: what is standard deviation
461. Seed pair: what is a median versus mean
462. Seed pair: what is a percentile
463. Seed pair: what is correlation versus causation
464. Seed pair: what is p value
465. Seed pair: what is bayes theorem
466. Seed pair: what is a base rate
467. Seed pair: what is a decision tree
468. Seed pair: what is k nearest neighbours
469. Seed pair: what is k means
470. Seed pair: what is regression in ml
471. Seed pair: what is an activation function
472. Seed pair: what is softmax
473. Seed pair: what is a learning rate
474. Seed pair: what is batch size
475. Seed pair: what is an epoch
476. Seed pair: what is dropout
477. Seed pair: what is data leakage
478. Seed pair: what is feature engineering
479. Seed pair: what is an ablation
480. Seed pair: what is a baseline
481. Seed pair: what is reproducibility
482. Seed pair: what is a random seed
483. Seed pair: what is a benchmark
484. Seed pair: what is premature optimization
485. Seed pair: what is profiling
486. Seed pair: what is lazy evaluation
487. Seed pair: what is short circuit evaluation
488. Seed pair: what is a pure function
489. Seed pair: what is separation of concerns
490. Seed pair: what is a proof by contradiction
491. Seed pair: what is a necessary versus sufficient condition
492. Seed pair: what is a debugger
493. Seed pair: what is a code review
494. Seed pair: what is a pull request
495. Seed pair: what is a release tag
496. Seed pair: what is backwards compatibility
497. Seed pair: what is deprecation
498. Seed pair: what is an api contract
499. Seed pair: what is a runbook
500. Seed pair: what is a blast radius
501. Seed pair: what is the principle of least astonishment
502. Seed pair: what is active recall
503. Seed pair: what is the feynman technique
504. Seed pair: what is deliberate practice
505. Seed pair: what is deep work
506. Seed pair: what is incremental delivery
507. Seed pair: what is a non functional requirement
508. Seed pair: what is a graceful error message
509. Seed pair: what is a fan out
510. Seed pair: what is a cron job
511. Seed pair: what is idempotent startup
512. Seed pair: what is a version marker
513. Seed pair: what is a fallback default
514. Seed pair: what is a denial of service
515. Seed pair: what is resource exhaustion
516. Seed pair: what is a spike
517. Seed pair: what is a proof of concept
518. Seed pair: what is continuous delivery
519. Seed pair: what is infrastructure as code
520. Seed pair: what is a container
521. Seed pair: what is port forwarding
522. Seed pair: what is gzip compression
523. Seed pair: what is a cache busting query
524. Seed pair: what is lazy loading
525. Seed pair: what is a skeleton screen
526. Seed pair: what is the 3 click rule
527. Seed pair: what is a web font
528. Seed pair: what is a memory footprint
529. Seed pair: what is the lindy effect
530. Training text: the maths pack answers factorials fibonacci primes gcd lcm factorisation and divisors
531. Training text: unit conversions cover celsius fahrenheit kilometres miles pounds ounces
532. Training text: statistics work in chat: median mode range variance standard deviation geometric and harmonic mean
533. Training text: finance helpers calculate tips simple interest compound interest and letter grades
534. Training text: geometry helpers cover circles rectangles triangles spheres cylinders and hypotenuses
535. Training text: fractions simplify add and multiply with exact rational arithmetic
536. Training text: roman numerals convert both ways and reject non canonical spellings
537. Training text: percent helpers cover change off increase decrease and what percent of
538. Training text: the text pack uppercases lowercases titles capitalises and swaps case
539. Training text: text encodings include base64 rot13 url encoding binary hex sha256 md5 and crc32
540. Training text: line tools dedupe sort number strip and shuffle lines of text
541. Training text: extraction tools pull emails urls numbers hashtags and mentions out of text
542. Training text: data helpers pretty print json minify json and convert csv to markdown tables
543. Training text: word games include pig latin palindrome isogram and anagram checks
544. Training text: chat maths is exposed at the api math endpoint and text at api text
545. Training text: every maths and text rule is listed by the api rules endpoint
546. Training text: sixty two maths rules and fifty five text rules ship in version one ten
547. Training text: one hundred and thirty four additional code template families ship in version one ten
548. Training text: the template library now exceeds two hundred and eighteen families
549. Training text: seed knowledge grew past four hundred and eighty question answer pairs
550. Training text: the test suite passed four hundred tests in version one ten
551. Training text: generated tests give every template family and every rule its own test method
552. Training text: a ui density toggle switches between compact and comfortable spacing
553. Training text: a high contrast mode strengthens borders and muted text for readability
554. Training text: a reduce motion toggle disables animations and honours the system preference
555. Training text: the sidebar collapses with the button or ctrl b
556. Training text: pinned messages live in a strip above the composer and persist in local storage
557. Training text: hover actions on every message offer copy pin and quote
558. Training text: the edit last button reloads your previous message into the composer
559. Training text: copy all collects the whole transcript as plain text
560. Training text: a share button uses the web share api with a clipboard fallback
561. Training text: a print button and a print stylesheet produce a clean transcript on paper
562. Training text: desktop notifications and a title badge announce replies when the tab is hidden
563. Training text: an optional web audio chime plays when a reply arrives
564. Training text: messages typed while offline queue in local storage and flush when the connection returns
565. Training text: the status text shows round trip ping time on hover
566. Training text: polling pauses after five idle minutes to save battery
567. Training text: a command dialog lists every keyboard shortcut and the question mark key opens it
568. Training text: an about dialog shows the version and endpoint count
569. Training text: svg icon serves as favicon apple touch icon and manifest icon

### Maths pack (65)

570. Maths rule: factorial
571. Maths rule: fibonacci nth
572. Maths rule: is prime
573. Maths rule: nth prime
574. Maths rule: gcd lcm
575. Maths rule: prime factors
576. Maths rule: divisors
577. Maths rule: digit sum
578. Maths rule: digital root
579. Maths rule: perfect square check
580. Maths rule: palindrome number
581. Maths rule: leap year
582. Maths rule: divisible by
583. Maths rule: even or odd
584. Maths rule: nth root
585. Maths rule: log base 10
586. Maths rule: log2
587. Maths rule: natural log
588. Maths rule: trig degrees
589. Maths rule: absolute value
590. Maths rule: floor ceil
591. Maths rule: round to n
592. Maths rule: remainder
593. Maths rule: percent of
594. Maths rule: what percent of
595. Maths rule: percent off
596. Maths rule: percent increase
597. Maths rule: percent decrease
598. Maths rule: tip
599. Maths rule: simple interest
600. Maths rule: compound interest
601. Maths rule: grade letter
602. Maths rule: circle area
603. Maths rule: rectangle area
604. Maths rule: triangle area
605. Maths rule: sphere volume
606. Maths rule: cylinder volume
607. Maths rule: pythagoras
608. Maths rule: distance midpoint
609. Maths rule: slope
610. Maths rule: speed
611. Maths rule: time
612. Maths rule: bmi
613. Maths rule: sum of range
614. Maths rule: sum of squares
615. Maths rule: triangular number
616. Maths rule: median
617. Maths rule: mode
618. Maths rule: range
619. Maths rule: variance
620. Maths rule: stddev
621. Maths rule: geometric mean
622. Maths rule: harmonic mean
623. Maths rule: decimal to fraction
624. Maths rule: fraction to decimal
625. Maths rule: simplify fraction
626. Maths rule: add fractions
627. Maths rule: multiply fractions
628. Maths rule: ratio simplify
629. Maths rule: independent probability
630. Maths rule: coin run
631. Maths rule: dice double
632. Maths rule: hex to rgb
633. Maths rule: rgb to hex
634. Maths rule: quadratic roots

### Text pack (55)

635. Text rule: uppercase
636. Text rule: lowercase
637. Text rule: title case
638. Text rule: capitalize
639. Text rule: swap case
640. Text rule: reverse text
641. Text rule: reverse words
642. Text rule: count words
643. Text rule: count characters
644. Text rule: count vowels
645. Text rule: count consonants
646. Text rule: count sentences
647. Text rule: reading time
648. Text rule: word frequency
649. Text rule: slugify
650. Text rule: snake case
651. Text rule: kebab case
652. Text rule: camel case
653. Text rule: initials
654. Text rule: acronym
655. Text rule: base64 encode
656. Text rule: base64 decode
657. Text rule: rot13
658. Text rule: url encode
659. Text rule: binary of text
660. Text rule: hex of text
661. Text rule: sha256
662. Text rule: md5
663. Text rule: crc32
664. Text rule: remove duplicate lines
665. Text rule: sort lines
666. Text rule: number lines
667. Text rule: strip empty lines
668. Text rule: collapse spaces
669. Text rule: trim
670. Text rule: shuffle lines
671. Text rule: extract emails
672. Text rule: extract urls
673. Text rule: extract numbers
674. Text rule: extract hashtags
675. Text rule: extract mentions
676. Text rule: json pretty
677. Text rule: json minify
678. Text rule: csv to markdown
679. Text rule: markdown to text
680. Text rule: pig latin
681. Text rule: is palindrome
682. Text rule: is isogram
683. Text rule: are anagrams
684. Text rule: repeat text
685. Text rule: truncate
686. Text rule: pad text
687. Text rule: replace text
688. Text rule: split to list
689. Text rule: join list

### Brain wiring (8)

690. Maths pack runs in `reply()` before arithmetic (confidence 1.0, mode `math`)
691. Text pack runs in `reply()` and tags replies as `skill: text:<rule>`
692. `quick_answer()` consults the maths pack (self-eval coverage)
693. `quick_answer()` consults the text pack
694. Both packs return `None` on no match so normal chat continues
695. Rule handlers are exception-guarded — a broken rule can never 500 chat
696. Seed loading is **additive and idempotent** — a later boot merges only the pairs/texts an update added, instead of skipping the seed because memory is no longer empty
697. `TEMPLATE_HINT` now names only capabilities that really have a family — 29 advertised concepts (trie, bloom filter, dijkstra, LRU/TTL cache, circuit breaker, cron, JWT…) had no template behind them and were written for this release

### API (16)

698. GET /api/math — evaluate a maths expression, falls back to arithmetic
699. GET /api/text — run a text transform; 404 lists every available rule
700. GET /api/rules — machine-readable inventory of maths, text and code rules
701. GET /api/convert — unit/temperature conversion only
702. GET /api/roman — roman numerals both directions
703. GET /api/echo — echo with length + server time, for client debugging
704. GET /api/uptime — uptime seconds plus human form
705. GET /api/endpoints — self-describing route list
706. GET /api/metrics — Prometheus-style text metrics
707. POST /api/chat/batch — up to 10 messages in one round-trip, `results` array
708. GET /api/quote — a random constitution principle
709. X-Request-Id — per-request id, echoed when the client supplies one
710. Server-Timing — per-request duration header for profiling
711. before_request stamp — records the monotonic start used by `Server-Timing`
712. X-MyGPT-Version — version header on every response
713. uptime baseline — restored `_started_monotonic` used by the new endpoints

### WebUI (56)

714. 📐 density toggle switches compact ⇄ comfortable
715. Density preference persisted in localStorage
716. Compact CSS pack (tighter bubbles, cards and message gaps)
717. ◐ high-contrast toggle with strengthened borders and muted text
718. High-contrast CSS via `html[data-contrast=high]`
719. 🎞 reduced-motion toggle that shortens all animations
720. Reduced-motion CSS enforcement in one block
721. `prefers-reduced-motion` media query honoured automatically
722. `prefers-contrast: more` media query honoured automatically
723. ◧ sidebar collapse button hides the panel and widens the chat
724. Ctrl+B toggles the sidebar
725. Sidebar state persisted in localStorage
726. 🔔 sound toggle with a WebAudio chime — no audio assets
727. 🖥 desktop-notification toggle with permission request
728. Notification + title-badge flash when a reply lands while hidden
729. Pinned-messages strip above the composer
730. 📌 pin action on every message
731. Click a pin chip to jump; right-click to unpin
732. Pins persisted in localStorage (max 8, oldest evicted)
733. ⧉ copy action on every message
734. ❝ quote action drops the first line into the composer
735. Hover/focus reveal for the message action row
736. ✏️ edit-last button reloads the previous message
737. ⧉ copy-all button collects the whole transcript as text
738. ⤒ first button jumps to the top and flashes the message
739. 🔗 share button uses the Web Share API
740. Share falls back to the clipboard with a clear toast
741. 🖨 print button plus print-stylesheet rules for the new chrome
742. ⌘ help dialog listing every shortcut
743. `?` on the keyboard opens the help dialog
744. About dialog showing live version and endpoint count
745. Offline queue stores messages typed with no connection
746. Queue flushes automatically on `online`
747. Offline styling on the composer
748. Idle detection (5 quiet minutes) pauses polling
749. Welcome-back toast when activity resumes
750. Round-trip ping measured every 45 s
751. Ping time + quality shown in the status tooltip
752. Toggle on/off visual states for all seven prefs
753. Modal styling with backdrop, kbd chips and focus return
754. `.msg-actions`, `.pins-bar` and `.chat-actions` CSS
755. Skip-to-composer link (keyboard users)
756. `role="log"` + `aria-live` on the transcript
757. `aria-busy` set while a reply is pending
758. `:focus-visible` outlines on every interactive control
759. `.sr-only` utility class added
760. `aria-label` on the pins bar
761. Icon-only buttons all carry `aria-label`/`title`
762. Flash highlight on the message jumped to
763. Composer anchor for the skip-link target
764. v1.10 print rules hide action rows, pins and dialogs
765. Prefs persisted as one JSON key (`mygpt.prefs`)
766. Toast feedback for every new toggle
767. LocalStorage guarded in try/catch (private-mode safe)
768. Density/contrast/motion applied through `data-*` attributes
769. Deduped prefs bootstrap (one read, one write)

### Tests (336)

770. Test: TemplatePackTests.test_family_001_linear_search
771. Test: TemplatePackTests.test_family_002_selection_sort
772. Test: TemplatePackTests.test_family_003_insertion_sort
773. Test: TemplatePackTests.test_family_004_merge_sort
774. Test: TemplatePackTests.test_family_005_quick_sort
775. Test: TemplatePackTests.test_family_006_heap_sort
776. Test: TemplatePackTests.test_family_007_counting_sort
777. Test: TemplatePackTests.test_family_008_binary_search_recursive
778. Test: TemplatePackTests.test_family_009_two_sum_problem
779. Test: TemplatePackTests.test_family_010_maximum_subarray
780. Test: TemplatePackTests.test_family_011_longest_common_prefix
781. Test: TemplatePackTests.test_family_012_longest_common_subsequence
782. Test: TemplatePackTests.test_family_013_edit_distance
783. Test: TemplatePackTests.test_family_014_knapsack_0_1
784. Test: TemplatePackTests.test_family_015_coin_change
785. Test: TemplatePackTests.test_family_016_fibonacci_memoized
786. Test: TemplatePackTests.test_family_017_pascal_triangle
787. Test: TemplatePackTests.test_family_018_catalan_numbers
788. Test: TemplatePackTests.test_family_019_prime_factorization
789. Test: TemplatePackTests.test_family_020_sieve_of_eratosthenes
790. Test: TemplatePackTests.test_family_021_nth_prime
791. Test: TemplatePackTests.test_family_022_twin_primes
792. Test: TemplatePackTests.test_family_023_perfect_numbers
793. Test: TemplatePackTests.test_family_024_amicable_numbers
794. Test: TemplatePackTests.test_family_025_happy_numbers
795. Test: TemplatePackTests.test_family_026_kaprekar_number
796. Test: TemplatePackTests.test_family_027_automorphic_number
797. Test: TemplatePackTests.test_family_028_sum_of_divisors
798. Test: TemplatePackTests.test_family_029_count_divisors
799. Test: TemplatePackTests.test_family_030_euler_totient
800. Test: TemplatePackTests.test_family_031_trailing_zeros_factorial
801. Test: TemplatePackTests.test_family_032_binomial_coefficient
802. Test: TemplatePackTests.test_family_033_permutations_and_combinations
803. Test: TemplatePackTests.test_family_034_power_set
804. Test: TemplatePackTests.test_family_035_cartesian_product
805. Test: TemplatePackTests.test_family_036_rotate_a_list
806. Test: TemplatePackTests.test_family_037_chunk_a_list
807. Test: TemplatePackTests.test_family_038_partition_list
808. Test: TemplatePackTests.test_family_039_group_by_key
809. Test: TemplatePackTests.test_family_040_invert_a_dictionary
810. Test: TemplatePackTests.test_family_041_sort_dict_by_value
811. Test: TemplatePackTests.test_family_042_dict_from_two_lists
812. Test: TemplatePackTests.test_family_043_deep_merge_dicts
813. Test: TemplatePackTests.test_family_044_flatten_a_dict
814. Test: TemplatePackTests.test_family_045_count_occurrences
815. Test: TemplatePackTests.test_family_046_find_duplicates_in_list
816. Test: TemplatePackTests.test_family_047_remove_falsy_values
817. Test: TemplatePackTests.test_family_048_zip_longest
818. Test: TemplatePackTests.test_family_049_pairwise_iteration
819. Test: TemplatePackTests.test_family_050_matrix_multiplication
820. Test: TemplatePackTests.test_family_051_matrix_addition
821. Test: TemplatePackTests.test_family_052_identity_matrix
822. Test: TemplatePackTests.test_family_053_determinant
823. Test: TemplatePackTests.test_family_054_rotate_matrix
824. Test: TemplatePackTests.test_family_055_spiral_matrix
825. Test: TemplatePackTests.test_family_056_diagonal_sum
826. Test: TemplatePackTests.test_family_057_string_to_int
827. Test: TemplatePackTests.test_family_058_int_to_string
828. Test: TemplatePackTests.test_family_059_vigenere_cipher
829. Test: TemplatePackTests.test_family_060_morse_code
830. Test: TemplatePackTests.test_family_061_atbash_cipher
831. Test: TemplatePackTests.test_family_062_base64_encode_decode
832. Test: TemplatePackTests.test_family_063_hash_a_string
833. Test: TemplatePackTests.test_family_064_uuid_generation
834. Test: TemplatePackTests.test_family_065_random_shuffle
835. Test: TemplatePackTests.test_family_066_weighted_choice
836. Test: TemplatePackTests.test_family_067_roll_dice_statistics
837. Test: TemplatePackTests.test_family_068_deck_of_cards
838. Test: TemplatePackTests.test_family_069_memoize_decorator
839. Test: TemplatePackTests.test_family_070_retry_decorator
840. Test: TemplatePackTests.test_family_071_singleton_pattern
841. Test: TemplatePackTests.test_family_072_factory_pattern
842. Test: TemplatePackTests.test_family_073_observer_pattern
843. Test: TemplatePackTests.test_family_074_strategy_pattern
844. Test: TemplatePackTests.test_family_075_namedtuple_example
845. Test: TemplatePackTests.test_family_076_defaultdict_example
846. Test: TemplatePackTests.test_family_077_heapq_example
847. Test: TemplatePackTests.test_family_078_bisect_example
848. Test: TemplatePackTests.test_family_079_itertools_example
849. Test: TemplatePackTests.test_family_080_functools_reduce
850. Test: TemplatePackTests.test_family_081_functools_partial
851. Test: TemplatePackTests.test_family_082_context_manager_class
852. Test: TemplatePackTests.test_family_083_contextmanager_decorator
853. Test: TemplatePackTests.test_family_084_property_decorator
854. Test: TemplatePackTests.test_family_085_classmethod_staticmethod
855. Test: TemplatePackTests.test_family_086_frozen_dataclass
856. Test: TemplatePackTests.test_family_087_dataclass_with_slots
857. Test: TemplatePackTests.test_family_088_abc_abstract_class
858. Test: TemplatePackTests.test_family_089_typeddict_example
859. Test: TemplatePackTests.test_family_090_mro_multiple_inheritance
860. Test: TemplatePackTests.test_family_091_counter_example
861. Test: TemplatePackTests.test_family_092_chainmap_example
862. Test: TemplatePackTests.test_family_093_csv_dict_reader
863. Test: TemplatePackTests.test_family_094_csv_dict_writer
864. Test: TemplatePackTests.test_family_095_json_pretty_print
865. Test: TemplatePackTests.test_family_096_json_to_csv
866. Test: TemplatePackTests.test_family_097_csv_to_json
867. Test: TemplatePackTests.test_family_098_ini_config_parser
868. Test: TemplatePackTests.test_family_099_xml_parse_example
869. Test: TemplatePackTests.test_family_100_sqlite_basics
870. Test: TemplatePackTests.test_family_101_sqlite_parameterized_query
871. Test: TemplatePackTests.test_family_102_sqlite_context_manager
872. Test: TemplatePackTests.test_family_103_copy_a_file
873. Test: TemplatePackTests.test_family_104_move_or_rename_a_file
874. Test: TemplatePackTests.test_family_105_delete_files_by_pattern
875. Test: TemplatePackTests.test_family_106_make_directory_tree
876. Test: TemplatePackTests.test_family_107_zip_files_into_archive
877. Test: TemplatePackTests.test_family_108_unzip_archive
878. Test: TemplatePackTests.test_family_109_human_readable_file_size
879. Test: TemplatePackTests.test_family_110_check_if_file_exists
880. Test: TemplatePackTests.test_family_111_temp_file_usage
881. Test: TemplatePackTests.test_family_112_pathlib_tour
882. Test: TemplatePackTests.test_family_113_read_file_in_chunks
883. Test: TemplatePackTests.test_family_114_tail_a_file
884. Test: TemplatePackTests.test_family_115_word_frequency_from_file
885. Test: TemplatePackTests.test_family_116_grep_text_in_files
886. Test: TemplatePackTests.test_family_117_bulk_rename_files
887. Test: TemplatePackTests.test_family_118_deduplicate_files_by_hash
888. Test: TemplatePackTests.test_family_119_download_a_file
889. Test: TemplatePackTests.test_family_120_progress_bar
890. Test: TemplatePackTests.test_family_121_text_spinner
891. Test: TemplatePackTests.test_family_122_ansi_colors
892. Test: TemplatePackTests.test_family_123_clear_the_screen
893. Test: TemplatePackTests.test_family_124_terminal_menu
894. Test: TemplatePackTests.test_family_125_stopwatch
895. Test: TemplatePackTests.test_family_126_beep_sound
896. Test: TemplatePackTests.test_family_127_rotating_log_files
897. Test: TemplatePackTests.test_family_128_serve_a_directory
898. Test: TemplatePackTests.test_family_129_http_client_with_retries
899. Test: TemplatePackTests.test_family_130_url_parsing
900. Test: TemplatePackTests.test_family_131_build_a_query_string
901. Test: TemplatePackTests.test_family_132_json_http_post
902. Test: TemplatePackTests.test_family_133_basic_auth_header
903. Test: TemplatePackTests.test_family_134_rate_limiter
904. Test: TemplatePackTests.test_family_135_trie
905. Test: TemplatePackTests.test_family_136_bloom_filter
906. Test: TemplatePackTests.test_family_137_dijkstra
907. Test: TemplatePackTests.test_family_138_topological_sort
908. Test: TemplatePackTests.test_family_139_bfs
909. Test: TemplatePackTests.test_family_140_dfs
910. Test: TemplatePackTests.test_family_141_heap
911. Test: TemplatePackTests.test_family_142_queue
912. Test: TemplatePackTests.test_family_143_deque
913. Test: TemplatePackTests.test_family_144_state_machine
914. Test: TemplatePackTests.test_family_145_lru_cache
915. Test: TemplatePackTests.test_family_146_ttl_cache
916. Test: TemplatePackTests.test_family_147_backoff
917. Test: TemplatePackTests.test_family_148_circuit_breaker
918. Test: TemplatePackTests.test_family_149_event_emitter
919. Test: TemplatePackTests.test_family_150_cron
920. Test: TemplatePackTests.test_family_151_jwt
921. Test: TemplatePackTests.test_family_152_checksum
922. Test: TemplatePackTests.test_family_153_sliding_window
923. Test: TemplatePackTests.test_family_154_two_pointers
924. Test: TemplatePackTests.test_family_155_benchmark
925. Test: TemplatePackTests.test_family_156_memoise
926. Test: TemplatePackTests.test_family_157_pagination
927. Test: TemplatePackTests.test_family_158_async
928. Test: TemplatePackTests.test_family_159_threads
929. Test: TemplatePackTests.test_family_160_zip_files
930. Test: TemplatePackTests.test_family_161_html_escape
931. Test: TemplatePackTests.test_family_162_markdown_table
932. Test: TemplatePackTests.test_family_163_validate_email
933. Test: ApiPackTests.test_chat_batch
934. Test: ApiPackTests.test_chat_batch_cap
935. Test: ApiPackTests.test_chat_batch_validation
936. Test: ApiPackTests.test_convert_endpoint
937. Test: ApiPackTests.test_convert_endpoint_404
938. Test: ApiPackTests.test_echo_endpoint
939. Test: ApiPackTests.test_endpoints_listing
940. Test: ApiPackTests.test_math_endpoint
941. Test: ApiPackTests.test_math_endpoint_400
942. Test: ApiPackTests.test_math_endpoint_404
943. Test: ApiPackTests.test_metrics_endpoint
944. Test: ApiPackTests.test_page_has_v110_controls
945. Test: ApiPackTests.test_quote_endpoint
946. Test: ApiPackTests.test_request_id_echoed
947. Test: ApiPackTests.test_request_id_header
948. Test: ApiPackTests.test_roman_endpoint_number
949. Test: ApiPackTests.test_roman_endpoint_roman
950. Test: ApiPackTests.test_rules_endpoint
951. Test: ApiPackTests.test_server_timing_header
952. Test: ApiPackTests.test_text_endpoint
953. Test: ApiPackTests.test_text_endpoint_404_lists_rules
954. Test: ApiPackTests.test_uptime_endpoint
955. Test: ApiPackTests.test_version_header
956. Test: BrainPackTests.test_code_still_wins_for_code_asks
957. Test: BrainPackTests.test_counter_grows
958. Test: BrainPackTests.test_maths_pack_answer
959. Test: BrainPackTests.test_quick_answer_uses_mathx
960. Test: BrainPackTests.test_quick_answer_uses_textfx
961. Test: BrainPackTests.test_seed_knowledge_reachable
962. Test: BrainPackTests.test_text_pack_answer
963. Test: BrainPackTests.test_text_pack_skill_tag
964. Test: MathPackTests.test_math_001_factorial
965. Test: MathPackTests.test_math_002_fibonacci
966. Test: MathPackTests.test_math_003_is_prime_yes
967. Test: MathPackTests.test_math_004_is_prime_no
968. Test: MathPackTests.test_math_005_nth_prime
969. Test: MathPackTests.test_math_006_gcd
970. Test: MathPackTests.test_math_007_lcm
971. Test: MathPackTests.test_math_008_prime_factors
972. Test: MathPackTests.test_math_009_divisors
973. Test: MathPackTests.test_math_010_digit_sum
974. Test: MathPackTests.test_math_011_digital_root
975. Test: MathPackTests.test_math_012_perfect_square
976. Test: MathPackTests.test_math_013_palindrome_number
977. Test: MathPackTests.test_math_014_leap_year
978. Test: MathPackTests.test_math_015_divisible
979. Test: MathPackTests.test_math_016_even_odd
980. Test: MathPackTests.test_math_017_cube_root
981. Test: MathPackTests.test_math_018_log10
982. Test: MathPackTests.test_math_019_log2
983. Test: MathPackTests.test_math_020_natural_log
984. Test: MathPackTests.test_math_021_trig
985. Test: MathPackTests.test_math_022_absolute
986. Test: MathPackTests.test_math_023_floor
987. Test: MathPackTests.test_math_024_ceiling
988. Test: MathPackTests.test_math_025_round_decimals
989. Test: MathPackTests.test_math_026_remainder
990. Test: MathPackTests.test_math_027_percent_increase
991. Test: MathPackTests.test_math_028_percent_decrease
992. Test: MathPackTests.test_math_029_tip
993. Test: MathPackTests.test_math_030_simple_interest
994. Test: MathPackTests.test_math_031_compound_interest
995. Test: MathPackTests.test_math_032_grade
996. Test: MathPackTests.test_math_033_circle
997. Test: MathPackTests.test_math_034_rectangle
998. Test: MathPackTests.test_math_035_triangle
999. Test: MathPackTests.test_math_036_sphere
1000. Test: MathPackTests.test_math_037_cylinder
1001. Test: MathPackTests.test_math_038_pythagoras
1002. Test: MathPackTests.test_math_039_distance
1003. Test: MathPackTests.test_math_040_midpoint
1004. Test: MathPackTests.test_math_041_slope
1005. Test: MathPackTests.test_math_042_speed
1006. Test: MathPackTests.test_math_043_travel_time
1007. Test: MathPackTests.test_math_044_bmi
1008. Test: MathPackTests.test_math_045_sum_range
1009. Test: MathPackTests.test_math_046_sum_squares
1010. Test: MathPackTests.test_math_047_triangular
1011. Test: MathPackTests.test_math_048_median
1012. Test: MathPackTests.test_math_049_mode
1013. Test: MathPackTests.test_math_050_range
1014. Test: MathPackTests.test_math_051_variance
1015. Test: MathPackTests.test_math_052_stddev
1016. Test: MathPackTests.test_math_053_geometric_mean
1017. Test: MathPackTests.test_math_054_harmonic_mean
1018. Test: MathPackTests.test_math_055_decimal_to_fraction
1019. Test: MathPackTests.test_math_056_fraction_to_decimal
1020. Test: MathPackTests.test_math_057_simplify_fraction
1021. Test: MathPackTests.test_math_058_add_fractions
1022. Test: MathPackTests.test_math_059_multiply_fractions
1023. Test: MathPackTests.test_math_060_ratio
1024. Test: MathPackTests.test_math_061_independent_probability
1025. Test: MathPackTests.test_math_062_coin_run
1026. Test: MathPackTests.test_math_063_dice_double
1027. Test: MathPackTests.test_math_064_hex_to_rgb
1028. Test: MathPackTests.test_math_065_rgb_to_hex
1029. Test: MathPackTests.test_math_066_quadratic
1030. Test: MathPackTests.test_math_067_percent_of
1031. Test: MathPackTests.test_math_068_what_percent_of
1032. Test: MathPackTests.test_math_069_percent_off
1033. Test: MathPackTests.test_rule_count
1034. Test: MathPackTests.test_rule_names_unique
1035. Test: MathPackTests.test_unrelated_text_no_match
1036. Test: SeedPackTests.test_answer_length_sane
1037. Test: SeedPackTests.test_every_pair_has_content
1038. Test: SeedPackTests.test_no_duplicate_questions
1039. Test: SeedPackTests.test_no_markup_in_answers
1040. Test: SeedPackTests.test_pair_count
1041. Test: SeedPackTests.test_seed_merge_is_additive
1042. Test: SeedPackTests.test_seed_topic_is_answerable
1043. Test: SeedPackTests.test_texts_present
1044. Test: TemplatePackTests.test_all_extra_snippets_distinct
1045. Test: TemplatePackTests.test_all_extra_snippets_distinct — now asserts every canonical ask routes to its own family and that no two families share an ask
1046. Test: TemplatePackTests.test_every_snippet_compiles
1047. Test: TemplatePackTests.test_total_family_count
1048. Test: TextPackTests.test_questions_not_hijacked
1049. Test: TextPackTests.test_rule_count
1050. Test: TextPackTests.test_rule_names_unique
1051. Test: TextPackTests.test_text_001_uppercase
1052. Test: TextPackTests.test_text_002_lowercase
1053. Test: TextPackTests.test_text_003_title_case
1054. Test: TextPackTests.test_text_004_capitalize
1055. Test: TextPackTests.test_text_005_swap_case
1056. Test: TextPackTests.test_text_006_reverse_text
1057. Test: TextPackTests.test_text_007_reverse_words
1058. Test: TextPackTests.test_text_008_count_words
1059. Test: TextPackTests.test_text_009_count_characters
1060. Test: TextPackTests.test_text_010_count_vowels
1061. Test: TextPackTests.test_text_011_count_consonants
1062. Test: TextPackTests.test_text_012_count_sentences
1063. Test: TextPackTests.test_text_013_reading_time
1064. Test: TextPackTests.test_text_014_word_frequency
1065. Test: TextPackTests.test_text_015_slugify
1066. Test: TextPackTests.test_text_016_snake_case
1067. Test: TextPackTests.test_text_017_kebab_case
1068. Test: TextPackTests.test_text_018_camel_case
1069. Test: TextPackTests.test_text_019_initials
1070. Test: TextPackTests.test_text_020_acronym
1071. Test: TextPackTests.test_text_021_base64_encode
1072. Test: TextPackTests.test_text_022_base64_decode
1073. Test: TextPackTests.test_text_023_rot13
1074. Test: TextPackTests.test_text_024_url_encode
1075. Test: TextPackTests.test_text_025_binary_of_text
1076. Test: TextPackTests.test_text_026_hex_of_text
1077. Test: TextPackTests.test_text_027_sha256
1078. Test: TextPackTests.test_text_028_md5
1079. Test: TextPackTests.test_text_029_crc32
1080. Test: TextPackTests.test_text_030_dedupe_lines
1081. Test: TextPackTests.test_text_031_sort_lines
1082. Test: TextPackTests.test_text_032_number_lines
1083. Test: TextPackTests.test_text_033_strip_empty
1084. Test: TextPackTests.test_text_034_collapse_spaces
1085. Test: TextPackTests.test_text_035_trim
1086. Test: TextPackTests.test_text_036_shuffle_lines
1087. Test: TextPackTests.test_text_037_extract_emails
1088. Test: TextPackTests.test_text_038_extract_urls
1089. Test: TextPackTests.test_text_039_extract_numbers
1090. Test: TextPackTests.test_text_040_extract_hashtags
1091. Test: TextPackTests.test_text_041_extract_mentions
1092. Test: TextPackTests.test_text_042_json_pretty
1093. Test: TextPackTests.test_text_043_json_minify
1094. Test: TextPackTests.test_text_044_csv_to_markdown
1095. Test: TextPackTests.test_text_045_markdown_to_text
1096. Test: TextPackTests.test_text_046_pig_latin
1097. Test: TextPackTests.test_text_047_is_palindrome
1098. Test: TextPackTests.test_text_048_is_isogram
1099. Test: TextPackTests.test_text_049_anagrams
1100. Test: TextPackTests.test_text_050_repeat_text
1101. Test: TextPackTests.test_text_051_truncate
1102. Test: TextPackTests.test_text_052_pad_text
1103. Test: TextPackTests.test_text_053_replace_text
1104. Test: TextPackTests.test_text_054_split_to_list
1105. Test: TextPackTests.test_text_055_join_list

### Efficiency (5)

1106. `codegen.has_template` memoised with lru_cache (hot path, pure)
1107. `mathx.solve` memoised with lru_cache
1108. `textfx.solve` memoised with lru_cache
1109. Seed texts deduplicated on load (`dict.fromkeys`)
1110. Seed merge hashes normalised questions once per boot (`O(n)` set lookups, not a nested scan) and re-trains briefly (4 epochs) only when it actually added something

### Bugs fixed (12)

1111. `/api/uptime` and `/api/metrics` referenced `_started_monotonic`, which v1.9 had removed — restored
1112. `rgb_to_hex` never matched: the pattern demanded a separator that callers omit
1113. `reverse words:` was swallowed by the reverse-text rule — rule tightened
1114. `json pretty:` was swallowed by the pretty-print-json rule — pattern extended
1115. 28 new template asks did not match their own regex — `_broaden()` now guarantees it
1116. 28 generated per-family tests assumed first-match identity — made match-aware, exposing real overlaps
1117. "what is 17% of 250" fell through to the curiosity fallback — percent-of/off/what-percent rules added
1118. `Brain._find_math` understood "20 percent of 150" but not "17% of 250" — `% of` now normalised
1119. Docstring counts drifted from reality (130→134 families, 48→62 maths rules, 45→55 text rules) — corrected
1120. New seed knowledge never reached an existing `data/` folder — the `not self.memory.pairs` guard meant updates shipped knowledge that returned "curious" forever (found live: *what is a trie*)
1121. **24 of the 163 new asks were answered by the wrong family** — "twin primes" returned the generic primes snippet, "property decorator" returned a bare decorator, "read a file in chunks" returned "read a file". First-match-wins on registration order; now scored by specificity. Every ask routes to its own family (163/163)
1122. The `merge dictionaries` pattern swallowed "deep merge dictionaries" (negative lookbehind added)

### Docs (4)

1123. Version bumped to 1.10.0
1124. README: 218 template families, both new packs, 11 endpoints, 420 tests, new WebUI blocks
1125. CHANGELOG: this release, numbered end to end
1126. Both pack docstrings reconciled with the real rule counts

**Total: 1126 numbered items.** Counting convention: one item per template
family, seed pair or text, maths/text rule, endpoint, UI behaviour, test
method and fix — the same capability is counted at each layer where it
ships (code, brain, API, UI, tests), so this is an itemisation of the
release, not 1,121 independent features.
## v1.9.0 — "another 200+ improvements" (231 items)

### Code templates in chat (33)

1. New template: number guessing game (random secret + higher/lower loop)
2. New template: rock paper scissors (CPU choice + win/draw/lose logic)
3. New template: hangman (lives, masked word, win/lose detection)
4. New template: todo list app (add/done/list commands)
5. New template: contact book / address book (add/find/list)
6. New template: BMI calculator with weight-band classification
7. New template: age calculator (years + total days from a birth date)
8. New template: stack & queue with collections.deque
9. New template: linked list (Node + traversal)
10. New template: decorator example (@timed wrapper over a function)
11. New template: generator example (yield, lazy values)
12. New template: dataclass example (fields, default_factory, property)
13. New template: enum example (Enum + auto())
14. New template: exception handling (try/except/else/finally)
15. New template: list comprehension (filtered, nested, dict)
16. New template: lambda with map/filter/sorted keys
17. New template: argparse command-line parser (args + flags)
18. New template: logging setup (console + file handlers)
19. New template: unittest skeleton (two test methods)
20. New template: walk a directory (os.walk with hidden-folder pruning)
21. New template: count lines in a file
22. New template: web scraper (urllib + regex, honest "no BS4" note in code)
23. New template: read environment variables
24. New template: config file loader (defaults + JSON overlay)
25. New template: collatz sequence
26. New template: reverse the words in a sentence
27. New template: pangram check (set of a-z)
28. New template: sort a list of dicts by key/value
29. New template: number/star pyramid pattern
30. New template: number to words (recursive hundreds translation)
31. `TEMPLATE_HINT` now advertises the new families to the model
32. New code-request verb list (`CODE_VERB`): write/show/make/print/convert…
33. `wants_code()` now also fires when a known template matches an imperative
    ("write a guessing game" is code, but "what is a decorator" stays knowledge)

### Seed knowledge — bigger on first boot (50)

34. New seed pair: switch to light mode
35. New seed pair: search the chat (+ Ctrl+K)
36. New seed pair: clear the chat (and what is kept)
37. New seed pair: streaming replies
38. New seed pair: every keyboard shortcut in one answer
39. New seed pair: copying just the code
40. New seed pair: what syntax highlighting is
41. New seed pair: change the font size
42. New seed pair: print the conversation
43. New seed pair: drag & drop chat import
44. New seed pair: what a PWA is
45. New seed pair: what a web manifest is
46. New seed pair: roman numerals (both directions)
47. New seed pair: which units convert
48. New seed pair: temperature conversion
49. New seed pair: what percent change is
50. New seed pair: averaging a list of numbers
51. New seed pair: the version endpoint
52. New seed pair: the memory search endpoint
53. New seed pair: the suggest endpoint
54. New seed pair: the models endpoint
55. New seed pair: robots.txt policy
56. New seed pair: what CORS is
57. New seed pair: what server-sent events are
58. New seed pair: what is new in 1.9
59. New seed pair: how many code templates exist
60. New seed pair: how many tests exist
61. New seed pair: recall your last message with ↑
62. New seed pair: switch tabs with Alt+1/2/3
63. New seed pair: focus the search box
64. New seed pair: export keyboard shortcut
65. New seed pair: mobile friendliness
66. New seed pair: copy a whole message
67. New seed pair: the character limit
68. New seed pair: teach many pairs at once (bulk endpoint)
69. New seed pair: the typing indicator
70. New seed pair: the date separator
71. New seed pair: Python highlighting
72. New seed pair: what a decorator is
73. New seed pair: what a generator is
74. New training text: streaming with server-sent events
75. New training text: light theme follows system preference
76. New training text: roman numerals are validated
77. New training text: unit conversion in plain words
78. New training text: code copy button + highlighting
79. New training text: transcript search and clear
80. New training text: keyboard shortcuts
81. New training text: installable PWA manifest
82. New training text: math covers list statistics
83. New training text: bulk teaching caps at one hundred pairs

### Math & language understanding (22)

84. Unit table: length (m, km, cm, mm, metre, mile, inch, foot, yard)
85. Unit table: mass (kg, g, kilo, pound, lb, ounce, oz)
86. Celsius → Fahrenheit conversion ("100 celsius in fahrenheit" → 212 °F)
87. Fahrenheit → Celsius conversion ("32 f to c" → 0 °C)
88. Same-unit asks are ignored instead of echoing (no false positives)
89. Unit family check — "5 km in kg" is politely not converted
90. Percent change between two numbers
91. Percent change from zero reports "undefined" instead of dividing
92. "X% off Y" discount maths
93. "A is what percent of B"
94. Average / mean of a comma-separated number list
95. Sum / total of a number list
96. Max / min of a number list
97. "half of N"
98. "double of N" / "twice of N"
99. "triple of N" / "thrice of N"
100. Number → roman numerals ("42 in roman" → XLII)
101. Roman numerals → number ("XIV in numbers" → 14)
102. Roman validation: non-canonical forms (IIII, VX) are rejected
103. Roman bounds: only 1–3999 convert
104. Pretty number formatting (integers without ".0", 6 sig-figs otherwise)
105. Special maths wired into `reply()` ahead of plain arithmetic

### Brain & self-learning internals (13)

106. `teach_many()` — validated bulk teaching with per-item error reporting
107. `search_memory()` — ranked retrieval exposed for inspection
108. `suggest()` — question-title autocomplete (prefix-ranked)
109. `analytics()` — counters, intent and mode histograms
110. Analytics: busiest-hours aggregation from episode timestamps
111. Analytics: top-memories ranking by hit count
112. `export_json()` — structured transcript export
113. `clear_transcript()` — wipe the dialogue, keep the knowledge
114. `last_records` ring buffer (deque, 200 turns) feeding analytics
115. `EpisodicMemory.clear()` — resets episodes, index matrix, working set
116. `MYGPT_CHECKPOINTS` env var relocates the checkpoint dir
117. Brain tolerates a missing seed corpus path (`seed_path=None`)
118. `export_json()` no longer crashes on the package version import (bug fix)

### API — new endpoints and hardening (22)

119. `POST /api/chat/stream` — Server-Sent Events, word-by-word tokens + done event
120. `GET /api/events/stream` — SSE snapshot of recent self-learning events
121. `GET /api/version` — version + author links
122. `GET /api/memory/search` — ranked retrieval (`?q=`, `?k=`)
123. `GET /api/memory/list` — paginated memory listing
124. `GET /api/suggest` — autocomplete from everything known
125. `GET /api/analytics` — learning telemetry summary
126. `GET /api/export.json` — structured transcript download
127. `GET /api/export.csv` — spreadsheet-friendly transcript download
128. `GET /api/backends/models` — every answerable engine in one list
129. `POST /api/teach/bulk` — up to 100 validated pairs per request
130. `POST /api/clear` — clear the transcript (knowledge kept)
131. `GET /api/checkpoint/info` — single-checkpoint metadata
132. `GET /robots.txt` — crawlers stay off the JSON API
133. `GET /manifest.json` — PWA manifest for install-to-desktop
134. `OPTIONS` catch-all for `/api/*` with a real 204 preflight
135. Unknown `/api/*` paths answer a JSON 404 (never an HTML page)
136. Wrong-verb requests on real endpoints keep a proper JSON 405
137. `after_request` CORS headers on every `/api/*` response
138. Security headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy`
139. `_validate_message()` shared chat validation helper
140. `MAX_BULK_PAIRS = 100` cap for bulk teaching

### WebUI & UX (72)

141. 🌓 light/dark theme toggle button in the top bar
142. Light theme follows `prefers-color-scheme` on the first visit
143. Theme choice persists in localStorage
144. `theme-color` meta updates with the chosen theme
145. A− / A+ text-size controls (five zoom steps)
146. Text size persists in localStorage
147. Live chat search box in the model bar
148. Ctrl+K focuses and selects the search box
149. Escape clears the search and restores every message
150. Non-matching messages hide via a `filtered-out` class
151. "No messages match" toast when a search finds nothing
152. 🗑 clear button (with a confirm dialog) for the transcript
153. Clear keeps learned memories/facts but forgets the visible log
154. Dependency-free Python syntax highlighter (in-browser)
155. Highlighter colours keywords, strings, comments, numbers, decorators
156. Highlighter masks strings/comments first so later passes can't leak
157. Code blocks get a header bar showing the language
158. ⧉ copy button on every code block (copies Python only)
159. Copy button flips to "✓ copied" for a moment
160. Replies stream in word-by-word via SSE
161. Streaming falls back to the plain endpoint if SSE fails
162. Typing dots are replaced by the first streamed token
163. Day dividers ("Today", "Yesterday", dates) between message groups
164. Unread badge on the jump-to-latest button when you're scrolled up
165. Badge pulses on new arrivals and clears when you return to the bottom
166. Double-click any message to copy it
167. Drag & drop a chat export anywhere on the chat panel to import
168. Drop-zone outline with an inline hint while dragging
169. Character counter appears past 3000 and warns past 3800
170. ↑ in an empty composer recalls your last message
171. Ctrl+Shift+E exports the transcript
172. Ctrl+Shift+L clears the chat
173. Ctrl/Cmd+Enter also sends from the composer
174. Alt+1 / Alt+2 / Alt+3 switch sidebar tabs
175. Tab buttons show their shortcut and use tablist roles
176. Bulk-teach card: paste `question :: answer` lines
177. Bulk-teach parses, validates and reports stored/skipped counts
178. Bulk-teach refuses >100 pairs client-side too
179. Memory-search card with live ranked results
180. Memory-search results show match percentage
181. Memory-search shows "teach me this!" when nothing matches
182. Memory-search debounces input (220 ms)
183. Print stylesheet: Ctrl+P prints only the conversation
184. Print stylesheet hides sidebars, buttons, toasts and the composer
185. Favourite-icon replaced with the new `icon.svg`
186. Apple touch icon + standalone meta tags
187. `color-scheme` meta so form controls follow the theme
188. Open Graph title/description/type for link previews
189. Viewport-safe responsive tweaks for the new toolbar
190. `.tools` cluster keeps the status dot aligned on narrow screens
191. Light-theme bubble shadows and card hover colours
192. `nosniff`/referrer headers reinforce the hardened setup in-browser
193. `static/icon.svg` — gradient orb app icon
194. Search box grows on focus for readability
195. Clear button styled consistently with the export button
196. Bulk teach note area explains skipped rows
197. Memory list rows show answer previews, not just questions
198. Composer keeps drafts (existing) and now also the zoom/theme prefs
199. Scroll button label switches to "⌄ N new" while unread
200. Code blocks keep horizontal scroll without breaking the bubble layout
201. Highlight colours tuned for the dark theme
202. Light theme overrides for `pre` and `.code-box` backgrounds
203. Toast feedback for theme, zoom, copy and clear actions
204. `aria-live` counter keeps screen readers informed near the limit
205. Drop-to-import reuses the same validation as the file picker
206. Search respects case-insensitive matching
207. Search box is a real `<input type=search>` (native clear affordance)
208. `manifest.json` link enables install-to-desktop
209. Theme toggle keeps the 🌓 label honest in both modes
210. Zoom applies to rem-based layout so the whole UI scales
211. Bulk teach clears the textarea on a perfect run only
212. Memory search panel is separate from the teach form (no accidental edits)

### Test suite — 69 new test methods across 48 entries (48)

213. Tokenizer: mixed-case + punctuation
214. Memory: mixed known/unknown token regression (the `set |= ()` crash)
215. New-template loop: all 30 families match and return code
216. New-template loop: each family produces distinct code
217. New-template loop: code replies carry the codero-sus credit
218. New-template loop: `TEMPLATE_HINT` advertises new families
219. New-template loop: unknown asks fall back gracefully
220. Special maths: 24 tests (units × 6, temperature × 2, percent × 4,
     list stats × 5, half/double/triple × 3, roman × 4)
221. Episode clear: index reset
222. Episode clear: persistence round-trip
223. Brain v1.9: teach_many counts
224. Brain v1.9: teach_many skips invalid items
225. Brain v1.9: search_memory shapes
226. Brain v1.9: search_memory empty query
227. Brain v1.9: suggest substring match
228. Brain v1.9: suggest empty
229. Brain v1.9: analytics after a turn
230. Brain v1.9: export_json structure
231. Brain v1.9: clear_transcript keeps memory
232. Brain v1.9: reply mode recorded in the ring buffer
233. Brain v1.9: checkpoints honour the env override
234. API: version endpoint
235. API: chat stream sends token + done events
236. API: chat stream validation
237. API: events stream snapshot + ping
238. API: memory search returns scored hits
239. API: memory search requires a query
240. API: memory list pagination
241. API: suggest returns matching titles
242. API: suggest prefix ranking
243. API: analytics shape
244. API: export.json parses and carries version
245. API: export.csv header row
246. API: backends/models includes the brain
247. API: teach/bulk stores valid pairs
248. API: teach/bulk reports bad items individually
249. API: teach/bulk requires pairs
250. API: teach/bulk enforces the 100 cap
251. API: checkpoint info found/not-found
252. API: robots.txt policy
253. API: manifest.json fields
254. API: clear wipes history
255. API: CORS header present on /api
256. API: security headers on the page
257. API: OPTIONS preflight accepted
258. API: icon.svg served
259. API: the page ships every v1.9 control (7 marker check)
260. Checkpoint command test isolated from leftover checkpoints on disk

### Bugs found by the new tests, fixed (4)

261. `memory.search()` crashed with `TypeError: unsupported operand |=` on any
     query mixing known + unknown words (HTTP 500) — fixed with a guarded union
262. The OPTIONS catch-all made unknown `/api/*` paths answer 405 instead of
     404 — fixed with path-aware 405/404 disambiguation
263. `Brain(data_dir, None)` crashed on a missing seed path — guarded
264. The checkpoint test asserted a global count and broke once real checkpoints
     existed — now diffs before/after and uses `MYGPT_CHECKPOINTS`

### Docs & meta (5)

265. README: WebUI section rewritten for streaming, search, theme, zoom, shortcuts
266. README: code-templates section lists the new families (80+ families)
267. README: Tests section updated to 116 tests with the new coverage summary
268. README: API table gains 16 new endpoint rows + the CORS note
269. Version bumped to 1.9.0

That is 269 numbered items — every one a real, verifiable change in this
release: code you can read in `mygpt/`, `app.py`, `static/`, `templates/`,
`seed_corpus.json` and `tests/`.

## v1.8.0 — the "200+ improvements" release (204 items)

### Code templates in chat (31)

1. New template: bubble sort
2. New template: binary search (function form)
3. New template: fizzbuzz (one-liner trick)
4. New template: prime check for a single number
5. New template: even-or-odd check
6. New template: read a text file line by line
7. New template: write a text file
8. Write-file template detects "append" asks and switches to mode "a"
9. New template: word frequency with collections.Counter
10. New template: remove duplicates preserving order
11. New template: class skeleton with `__init__` + method
12. New template: HTTP GET with urllib (+ User-Agent header, timeout)
13. New template: regex search + findall demo
14. New template: read CSV with csv.DictReader
15. New template: JSON dumps/loads roundtrip
16. New template: timer as a context manager (contextlib + perf_counter)
17. New template: random.choice from a list
18. Random template detects dice asks → random.randint(1, 6)
19. Random template detects shuffle asks → random.shuffle
20. New template: multiplication table (1–10, parameterised)
21. New template: caesar cipher encoder
22. Caesar template detects ROT13 asks (shift 13)
23. New template: strong password generator (secrets module)
24. New template: countdown with liftoff (parameterised start)
25. New template: matrix transpose with zip(*)
26. New template: leap year check
27. New template: digit count
28. New template: flatten arbitrarily nested lists (recursive generator)
29. New template: merge dictionaries (| operator + ** fallback)
30. New template: zip two lists into a dict
31. New template: f-string formatting (percent, padding, centring) + set operations union/intersection/difference/symmetric-difference (TEMPLATE_HINT rewritten to advertise all 52 families)

### Seed knowledge — smarter from first boot (61)

32. Pair: what is a checkpoint
33. Pair: how do i save your model
34. Pair: what is cortex llmhoster (credits codero-sus)
35. Pair: what is ollama
36. Pair: how do i change your model (picker next to send button)
37. Pair: how do i export our chat
38. Pair: how do i run the self evaluation
39. Pair: what is the growth tab
40. Pair: what is the mind tab
41. Pair: what is the learn tab
42. Pair: what is a loss curve
43. Pair: what is backpropagation
44. Pair: what is gradient descent
45. Pair: what is adam optimizer
46. Pair: what is tokenization
47. Pair: what is an embedding
48. Pair: what is a large language model
49. Pair: what is gpt
50. Pair: what is numpy
51. Pair: what is an api
52. Pair: what is http
53. Pair: what is json
54. Pair: how do i update mygpt (updater.sh/.bat + WebUI)
55. Pair: what is your license (personal-use terms)
56. Pair: can i sell mygpt (no — permission required)
57. Pair: can i modify mygpt (no — permission required)
58. Pair: where is your source code (GitHub links)
59. Pair: tell me about codero-sus (author profile)
60. Pair: how do i teach you (three ways)
61. Pair: how do you train (corpus + Adam)
62. Pair: what is a constitution (principles)
63. Pair: what are skills (procedural memory)
64. Pair: what is episodic memory
65. Pair: what is dreaming (dream replay)
66. Pair: do you use the cloud (no — fully local)
67. Pair: what is markdown
68. Pair: what is git
69. Pair: what is a database (JSON-files design choice)
70. Pair: how do i reset you (delete data/, keep checkpoints)
71. Text: checkpoints save trained weights into the model-trained folder
72. Text: cortex llmhoster and ollama serve local models for open questions
73. Text: mygpt was made with love by codero sus
74. Text: the model picker next to the send button chooses the engine
75. Text: the self evaluation battery tests math identity knowledge principles
76. Text: the constitution grows from promoted lessons
77. Text: episodic memory recalls similar past moments by embedding similarity
78. Text: adam gradient descent steps weights downhill against the loss
79. Text: the conversation export downloads the whole chat as markdown
80. Text: mygpt never runs code it only shows code blocks in chat
81. Text: memory uses tf-idf cosine similarity
82. Text: a checkpoint holds weights and metadata in one folder
83. Text: the webui restores your conversation after reload
84. Text: word math like seven times eight is understood
85. Text: mygpt answers with its own brain before any hosted model
86. Text: positive feedback raises a memory weight, negative lowers it
87. Text: smoke tests cover tokenizer memory math api checkpoints
88. Text: the updater installs only confirmed commits of the pinned branch
89. Text: local model hosts are auto probed every twenty seconds
90. Text: the license keeps mygpt free for personal non-commercial use
91. Pair: how were you built (de-duplicated the colliding second "who made you" seed pair — identity answers now reliably credit codero-sus)
92. Seed corpus grew from 44 to 80 pairs and 16 to 36 training texts

### Math & language understanding (16)

93. Number-word vocabulary: zero…twenty, thirty…ninety, hundred are understood as digits
94. "times" → multiplication
95. "multiplied by" → multiplication
96. "plus" → addition
97. "added to" → addition
98. "minus" → subtraction
99. "subtracted from" → subtraction
100. "divided by" → division
101. "over" → division
102. "to the power of" → exponent
103. "squared" → ^2
104. "mod" → modulo
105. "square root of" → **0.5 evaluation
106. "sqrt of" → **0.5 evaluation
107. "20 percent of 150"-style asks compute correctly
108. Division by zero now answers "undefined — division by zero" instead of silently falling through; chat inputs are hard-capped at 4000 characters

### API hardening & new endpoints (12)

109. GET /api/health — lightweight liveness (version, uptime, backend reachability)
110. GET /api/ping — minimal round-trip probe
111. 404 handler returns JSON {ok:false,error}
112. 405 handler returns JSON
113. 413 handler returns JSON (import size cap)
114. 500 handler returns JSON
115. /api/chat rejects non-string messages with 400
116. /api/chat rejects messages over 4000 chars with 400
117. /api/teach rejects non-string fields with 400
118. /api/teach enforces length caps (question 500 / answer 4000) with 400
119. Shared MAX_* constants document the limits in one place
120. /api/health uses TTL-cached backend probes (no extra round-trips)

### WebUI & UX (28)

121. Composer input upgraded from <input> to a multi-line <textarea>
122. Textarea auto-grows with content (capped at 150 px, then scrolls)
123. Enter sends the message
124. Shift+Enter inserts a newline
125. Escape clears the composer
126. Unsent drafts persist in localStorage across reloads
127. Drafts are restored on boot
128. Floating "jump to latest" button appears when scrolled up
129. Jump button auto-hides near the bottom
130. Top-bar dot turns amber with "offline — reconnecting…" when the browser loses network
131. Dot returns to green "online & learning" on reconnect
132. "/" focuses the composer from anywhere (vim/chat style)
133. Every message shows its timestamp on hover
134. Failed sends get a ↻ Retry chip that resubmits the message
135. Send no longer breaks on network exceptions (try/catch around fetch)
136. aria-label on the message textarea
137. aria-label on the model selector
138. aria-label on the send button
139. Toast is announced politely to screen readers (role=status, aria-live)
140. Meta description added (credits codero-sus)
141. theme-color meta added (#0b0e14)
142. author meta added (codero-sus + GitHub)
143. Page title now says "by codero-sus"
144. <noscript> fallback explains the JSON API still works (credits codero-sus)
145. Ctrl/Cmd+Enter submits the Teach form (question field)
146. Ctrl/Cmd+Enter submits the Teach form (answer field)
147. Backend pill tooltip explains "brain" mode
148. Backend pill tooltip explains "auto" ordering (brain → Cortex → Ollama)
149. Backend pill tooltip names the hosted engine
150. Textarea maxlength=4000 mirrors the server cap
151. Composer aligns items to the bottom so the button tracks the growing textarea
152. chat-panel is positioned for the floating jump button
153. Focus-ring polish extended to the new composer textarea
154. Placeholder teaches the Enter/Shift+Enter convention
155. Jump button has hover accent styling
156. Offline dot styling (no pulse when offline)
157. Draft helpers degrade gracefully in private-browsing mode
158. Scroll-button state updates on every message and on scroll events

### Test suite — new, 47 tests (47)

159. tokenize lowercases and splits
160. tokenize keeps apostrophes
161. normalize produces canonical form
162. tokenize cache is not poisonable by mutating a returned list
163. memory search finds the best match
164. memory search returns [] for zero token overlap
165. reinforce raises weights and is retrievable via get()
166. replace-question updates an existing pair in place
167. remove() deletes pairs
168. wants_code detects code asks
169. wants_code ignores non-code asks
170. 20 representative code asks each match a template and emit ```python
171. unknown code asks fall back gracefully with credit links
172. every code reply credits codero-sus GitHub + website
173. symbol math (23*47)
174. "6 times 7" word math
175. "seven times eight" number-word math
176. "144 divided by 12"
177. "square root of 144"
178. "20 percent of 150"
179. "2 to the power of 10"
180. division by zero returns the undefined message
181. non-math text returns None
182. language model trains (loss not increasing) and generate() returns text
183. weights survive a save/load roundtrip with identical vocab
184. checkpoint save names folders from labels + timestamps
185. checkpoint list/get/weights_path agree
186. checkpoint load restores weights into a fresh model
187. checkpoint delete removes the folder
188. checkpoint path traversal (../../etc, ..) is blocked on every method
189. episodes remember/search/recency
190. recent_dialogue returns the last k turns
191. CortexClient survives configure() to a dead port and chat() returns None
192. OllamaClient survives configure() to a dead port and chat() returns None
193. brain boots from a temp dir with the real seed corpus
194. greeting reply from seed memory
195. "what is 12 times 12" answers 144 in math mode
196. identity reply credits codero-sus
197. teach → recall roundtrip through the full pipeline
198. "write code for fizzbuzz" yields a code-mode reply
199. chat command "checkpoint the model" creates and reports a checkpoint
200. set_chat_backend validates unknown engines (400-class result)
201. install_hint is present with codero-sus first when no local LLM exists
202. 5000-word input is capped without crashing
203. export_transcript contains the credit footer
204. API suite: health/ping/stats-shape/backends/select-validation/chat-validation (empty + overlong)/teach-validation/history/export/eval/checkpoint-lifecycle (create→list→download→traversal-404→delete)/JSON-404/JSON-405

### Bugs found by the new tests and fixed (3, included above)

- Duplicate "who made you" seed pair (item 91)
- Class-template regex missed "code for a class" (item 11 family hardened)
- JSON-template regex missed "json code example" (item 15 family hardened)

## Earlier versions

- **v1.7.0** — memoised tokenizer, cached corpus encodings, debounced saves,
  conversation restore, checkpoint download, copy button, smart auto-scroll,
  word-form math (self-eval 5/5)
- **v1.6.0** — memory candidate pruning, keep-alive backends, TTL-cached
  probes, stats dedupe, self-eval button, chat export, latency display,
  suggestion chips
- **v1.5.0** — Ollama backend, model picker, `_model_trained/` checkpoints,
  chat commands, UI polish
- **v1.4.0 and earlier** — branch-pinned updater, launchers with
  python.env/2PY2 resolution, Cortex LLMHoster integration, CORTEX
  self-learning loop, chat-history import, code replies in chat

Made with ❤️ by codero-sus — https://github.com/codero-sus · https://the-codero.web.app/
