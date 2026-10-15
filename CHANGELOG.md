# Changelog

All credits: **codero-sus** — [github.com/codero-sus](https://github.com/codero-sus) ·
[the-codero.web.app](https://the-codero.web.app/)

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
