# Changelog

All credits: **codero-sus** — [github.com/codero-sus](https://github.com/codero-sus) ·
[the-codero.web.app](https://the-codero.web.app/)

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
