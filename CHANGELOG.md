# Changelog

All credits: **codero-sus** — [github.com/codero-sus](https://github.com/codero-sus) ·
[the-codero.web.app](https://the-codero.web.app/)

## v1.10.0 — the 777+ release (1057 items)

Every item below is verifiable in the repository: templates in
`mygpt/snippets_more.py`, rules in `mygpt/mathx.py` and
`mygpt/textfx.py`, knowledge in `seed_corpus.json`, routes in
`app.py`, tests in `tests/test_v110.py`.

### Code templates (137)

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

### Seed knowledge (401)

138. Seed pair: what is a linked list
139. Seed pair: what is a stack
140. Seed pair: what is a queue
141. Seed pair: what is a hash table
142. Seed pair: what is a binary tree
143. Seed pair: what is a heap
144. Seed pair: what is a graph
145. Seed pair: what is breadth first search
146. Seed pair: what is depth first search
147. Seed pair: what is big o notation
148. Seed pair: what is a stable sort
149. Seed pair: what is recursion
150. Seed pair: what is dynamic programming
151. Seed pair: what is greedy algorithm
152. Seed pair: what is a sliding window
153. Seed pair: what is two pointer technique
154. Seed pair: what is memoisation
155. Seed pair: what is a deque
156. Seed pair: what is a generator
157. Seed pair: what is a context manager
158. Seed pair: what is a closure
159. Seed pair: what is duck typing
160. Seed pair: what is the gil
161. Seed pair: what are type hints
162. Seed pair: what is pytest
163. Seed pair: what is a virtual environment
164. Seed pair: what is pep 8
165. Seed pair: what is a wheel
166. Seed pair: what is requirements txt
167. Seed pair: what is a shebang
168. Seed pair: what does if __name__ mean
169. Seed pair: what is scope in python
170. Seed pair: what is immutability
171. Seed pair: what is tuple unpacking
172. Seed pair: what is a frozenset
173. Seed pair: what is a byte string
174. Seed pair: what is a raw string
175. Seed pair: what is string formatting
176. Seed pair: what is a join
177. Seed pair: what is a walrus operator
178. Seed pair: what is a ternary expression
179. Seed pair: what is a match statement
180. Seed pair: what is an exception chain
181. Seed pair: what is a finally block
182. Seed pair: what is a custom exception
183. Seed pair: what are logging levels
184. Seed pair: what is a daemon thread
185. Seed pair: what is a race condition
186. Seed pair: what is async await
187. Seed pair: what is a coroutine
188. Seed pair: what is an event loop
189. Seed pair: what is the difference between process and thread
190. Seed pair: what is multiprocessing
191. Seed pair: what is a memory leak in python
192. Seed pair: what is garbage collection
193. Seed pair: what is a linter
194. Seed pair: what is a formatter
195. Seed pair: what is a type checker
196. Seed pair: what is ci
197. Seed pair: what is a pre commit hook
198. Seed pair: what is dependency pinning
199. Seed pair: what is semantic versioning
200. Seed pair: what is a changelog
201. Seed pair: what is a regression
202. Seed pair: what is test coverage
203. Seed pair: what is mocking
204. Seed pair: what is a fixture
205. Seed pair: what is property based testing
206. Seed pair: what is api versioning
207. Seed pair: what is a health check
208. Seed pair: what is a load balancer
209. Seed pair: what is a cdn
210. Seed pair: what is http status 418
211. Seed pair: what is idempotency
212. Seed pair: what is a websocket
213. Seed pair: what is long polling
214. Seed pair: what is a json schema
215. Seed pair: what is openapi
216. Seed pair: what is csp
217. Seed pair: what is xss
218. Seed pair: what is sqli
219. Seed pair: what is csrf
220. Seed pair: what is a salt
221. Seed pair: what is hashing versus encryption
222. Seed pair: what is constant time comparison
223. Seed pair: what is the principle of least privilege
224. Seed pair: what is a token bucket
225. Seed pair: what is backoff
226. Seed pair: what is a circuit breaker
227. Seed pair: what is observability
228. Seed pair: what is a metric histogram
229. Seed pair: what is a trace id
230. Seed pair: what is graceful shutdown
231. Seed pair: what is a migration
232. Seed pair: what is privacy by design
233. Seed pair: what is a seed corpus
234. Seed pair: what is human in the loop
235. Seed pair: what is the ai alignment problem
236. Seed pair: what is goodhart's law
237. Seed pair: what is technical debt
238. Seed pair: what is refactoring
239. Seed pair: what is a code smell
240. Seed pair: what is yagni
241. Seed pair: what is kiss
242. Seed pair: what is dry
243. Seed pair: what is the boy scout rule
244. Seed pair: what is rubber duck debugging
245. Seed pair: what is a stack trace
246. Seed pair: what is a breakpoint
247. Seed pair: what is logging versus printing
248. Seed pair: what is an assertion
249. Seed pair: what is fail fast
250. Seed pair: what is defensive copying
251. Seed pair: what is a feature flag
252. Seed pair: what is canary deployment
253. Seed pair: what is rollback
254. Seed pair: what is a postmortem
255. Seed pair: what is an adr
256. Seed pair: what is technical writing
257. Seed pair: what is a user story
258. Seed pair: what is mvp
259. Seed pair: what is dogfooding
260. Seed pair: what is progressive disclosure
261. Seed pair: what is a vertical slice
262. Seed pair: what is tracer bullet development
263. Seed pair: what is yak shaving
264. Seed pair: what is a timebox
265. Seed pair: what is definition of done
266. Seed pair: what is acceptance criteria
267. Seed pair: what is load testing
268. Seed pair: what is chaos testing
269. Seed pair: what is a 400 versus 500
270. Seed pair: what is a 429
271. Seed pair: what is a 503
272. Seed pair: what is a 204
273. Seed pair: what is idempotent retry
274. Seed pair: what is a webhook versus polling
275. Seed pair: what is eventual consistency
276. Seed pair: what is a write ahead log
277. Seed pair: what is an atomic rename
278. Seed pair: what is a checksum
279. Seed pair: what is a heartbeat
280. Seed pair: what is a leaky abstraction
281. Seed pair: what is the law of demeter
282. Seed pair: what is dependency injection
283. Seed pair: what is inversion of control
284. Seed pair: what is deterministic code
285. Seed pair: what is a side effect
286. Seed pair: what is defensive validation
287. Seed pair: what is a data retention policy
288. Seed pair: what is backpressure
289. Seed pair: what is a semaphore
290. Seed pair: what is a deadlock
291. Seed pair: what is jitter
292. Seed pair: what is monotonic time
293. Seed pair: what is utc versus local time
294. Seed pair: what is epoch time
295. Seed pair: what is an iso 8601 date
296. Seed pair: what is a canonical form
297. Seed pair: what is stemming
298. Seed pair: what is stop word removal
299. Seed pair: what is a posting list
300. Seed pair: what is a term frequency
301. Seed pair: what is a document frequency
302. Seed pair: what is a dot product
303. Seed pair: what is vectorisation in numpy
304. Seed pair: what is broadcasting
305. Seed pair: what is a view versus a copy
306. Seed pair: what is a hot path
307. Seed pair: what is a bottleneck
308. Seed pair: what is a cold start
309. Seed pair: what is a warm cache
310. Seed pair: what is the 80 20 rule
311. Seed pair: what is hashability
312. Seed pair: what is a hash collision
313. Seed pair: what is a load factor
314. Seed pair: what is a balanced tree
315. Seed pair: what is a b-tree
316. Seed pair: what is a union find
317. Seed pair: what is topological sort
318. Seed pair: what is dijkstra
319. Seed pair: what is a star search
320. Seed pair: what is a minimum spanning tree
321. Seed pair: what is a segment tree
322. Seed pair: what is a suffix array
323. Seed pair: what is rolling hash
324. Seed pair: what is kmp
325. Seed pair: what is meet in the middle
326. Seed pair: what is a state machine
327. Seed pair: what is a finite automaton
328. Seed pair: what is the halting problem
329. Seed pair: what is p versus np
330. Seed pair: what is np complete
331. Seed pair: what is the travelling salesman problem
332. Seed pair: what is the pigeonhole principle
333. Seed pair: what is an invariant
334. Seed pair: what is induction
335. Seed pair: what is a counterexample
336. Seed pair: what is occam's razor
337. Seed pair: what is parkinson's law
338. Seed pair: what is conway's law
339. Seed pair: what is the map is not the territory
340. Seed pair: what is symbolic versus statistical ai
341. Seed pair: what is explainability
342. Seed pair: what is a confidence score
343. Seed pair: what is calibration
344. Seed pair: what is hallucination
345. Seed pair: what is a guardrail
346. Seed pair: what is feedback loop design
347. Seed pair: what is reinforcement in retrieval
348. Seed pair: what is catastrophic forgetting
349. Seed pair: what is a replay buffer
350. Seed pair: what is self supervision
351. Seed pair: what is a knowledge base versus a model
352. Seed pair: what is provenance
353. Seed pair: what is a tombstone
354. Seed pair: what is idempotent teaching
355. Seed pair: what is deduplication
356. Seed pair: what is a quality gate
357. Seed pair: what is a preflight check
358. Seed pair: what is a status page
359. Seed pair: what is a threat model
360. Seed pair: what is path traversal
361. Seed pair: what is input fuzzing
362. Seed pair: what is output encoding
363. Seed pair: what is atomicity
364. Seed pair: what is durability
365. Seed pair: what is a single writer principle
366. Seed pair: what is a bounded queue
367. Seed pair: what is an unbounded growth bug
368. Seed pair: what is a watchdog
369. Seed pair: what is a capability probe
370. Seed pair: what is explicit configuration
371. Seed pair: what is a twelve factor app
372. Seed pair: what is a monolith
373. Seed pair: what is coupling
374. Seed pair: what is cohesion
375. Seed pair: what is a test double
376. Seed pair: what is a hermetic test
377. Seed pair: what is a smoke test
378. Seed pair: what is test isolation
379. Seed pair: what is a golden file
380. Seed pair: what is flaky test
381. Seed pair: what is accessibility
382. Seed pair: what is aria
383. Seed pair: what is color contrast
384. Seed pair: what is reduced motion
385. Seed pair: what is semantic html
386. Seed pair: what is an accessible name
387. Seed pair: what is tab order
388. Seed pair: what is a skip link
389. Seed pair: what is internationalisation
390. Seed pair: what is a time zone bug
391. Seed pair: what is a monospace font
392. Seed pair: what is a pwa install
393. Seed pair: what is offline first
394. Seed pair: what is localstorage
395. Seed pair: what is a service worker
396. Seed pair: what is debouncing
397. Seed pair: what is an optimistic update
398. Seed pair: what is a toast
399. Seed pair: what is fitts law
400. Seed pair: what is hicks law
401. Seed pair: what is a design token
402. Seed pair: what is flexbox versus grid
403. Seed pair: what is perceived performance
404. Seed pair: what is cpu versus io bound
405. Seed pair: what is a microbenchmark
406. Seed pair: what is a reverse proxy
407. Seed pair: what is http keep alive
408. Seed pair: what is an etag
409. Seed pair: what is graceful degradation
410. Seed pair: what is progressive enhancement
411. Seed pair: what is a fallback chain
412. Seed pair: what is an lru cache
413. Seed pair: what is a ttl
414. Seed pair: what is a schema
415. Seed pair: what is a contract test
416. Seed pair: what is a regression suite
417. Seed pair: what is a test pyramid
418. Seed pair: what is a trie
419. Seed pair: what is a bloom filter
420. Seed pair: what is tf idf
421. Seed pair: what is an inverted index
422. Seed pair: what is cosine similarity
423. Seed pair: what is edit distance used for
424. Seed pair: what is levenshtein distance
425. Seed pair: what is a monte carlo method
426. Seed pair: what is the birthday problem
427. Seed pair: what is the law of large numbers
428. Seed pair: what is the normal distribution
429. Seed pair: what is standard deviation
430. Seed pair: what is a median versus mean
431. Seed pair: what is a percentile
432. Seed pair: what is correlation versus causation
433. Seed pair: what is p value
434. Seed pair: what is bayes theorem
435. Seed pair: what is a base rate
436. Seed pair: what is a decision tree
437. Seed pair: what is k nearest neighbours
438. Seed pair: what is k means
439. Seed pair: what is regression in ml
440. Seed pair: what is an activation function
441. Seed pair: what is softmax
442. Seed pair: what is a learning rate
443. Seed pair: what is batch size
444. Seed pair: what is an epoch
445. Seed pair: what is dropout
446. Seed pair: what is data leakage
447. Seed pair: what is feature engineering
448. Seed pair: what is an ablation
449. Seed pair: what is a baseline
450. Seed pair: what is reproducibility
451. Seed pair: what is a random seed
452. Seed pair: what is a benchmark
453. Seed pair: what is premature optimization
454. Seed pair: what is profiling
455. Seed pair: what is lazy evaluation
456. Seed pair: what is short circuit evaluation
457. Seed pair: what is a pure function
458. Seed pair: what is separation of concerns
459. Seed pair: what is a proof by contradiction
460. Seed pair: what is a necessary versus sufficient condition
461. Seed pair: what is a debugger
462. Seed pair: what is a code review
463. Seed pair: what is a pull request
464. Seed pair: what is a release tag
465. Seed pair: what is backwards compatibility
466. Seed pair: what is deprecation
467. Seed pair: what is an api contract
468. Seed pair: what is a runbook
469. Seed pair: what is a blast radius
470. Seed pair: what is the principle of least astonishment
471. Seed pair: what is active recall
472. Seed pair: what is the feynman technique
473. Seed pair: what is deliberate practice
474. Seed pair: what is deep work
475. Seed pair: what is incremental delivery
476. Seed pair: what is a non functional requirement
477. Seed pair: what is a graceful error message
478. Seed pair: what is a fan out
479. Seed pair: what is a cron job
480. Seed pair: what is idempotent startup
481. Seed pair: what is a version marker
482. Seed pair: what is a fallback default
483. Seed pair: what is a denial of service
484. Seed pair: what is resource exhaustion
485. Seed pair: what is a spike
486. Seed pair: what is a proof of concept
487. Seed pair: what is continuous delivery
488. Seed pair: what is infrastructure as code
489. Seed pair: what is a container
490. Seed pair: what is port forwarding
491. Seed pair: what is gzip compression
492. Seed pair: what is a cache busting query
493. Seed pair: what is lazy loading
494. Seed pair: what is a skeleton screen
495. Seed pair: what is the 3 click rule
496. Seed pair: what is a web font
497. Seed pair: what is a memory footprint
498. Seed pair: what is the lindy effect
499. Training text: the maths pack answers factorials fibonacci primes gcd lcm factorisation and divisors
500. Training text: unit conversions cover celsius fahrenheit kilometres miles pounds ounces
501. Training text: statistics work in chat: median mode range variance standard deviation geometric and harmonic mean
502. Training text: finance helpers calculate tips simple interest compound interest and letter grades
503. Training text: geometry helpers cover circles rectangles triangles spheres cylinders and hypotenuses
504. Training text: fractions simplify add and multiply with exact rational arithmetic
505. Training text: roman numerals convert both ways and reject non canonical spellings
506. Training text: percent helpers cover change off increase decrease and what percent of
507. Training text: the text pack uppercases lowercases titles capitalises and swaps case
508. Training text: text encodings include base64 rot13 url encoding binary hex sha256 md5 and crc32
509. Training text: line tools dedupe sort number strip and shuffle lines of text
510. Training text: extraction tools pull emails urls numbers hashtags and mentions out of text
511. Training text: data helpers pretty print json minify json and convert csv to markdown tables
512. Training text: word games include pig latin palindrome isogram and anagram checks
513. Training text: chat maths is exposed at the api math endpoint and text at api text
514. Training text: every maths and text rule is listed by the api rules endpoint
515. Training text: sixty two maths rules and fifty five text rules ship in version one ten
516. Training text: one hundred and thirty four additional code template families ship in version one ten
517. Training text: the template library now exceeds two hundred and eighteen families
518. Training text: seed knowledge grew past four hundred and eighty question answer pairs
519. Training text: the test suite passed four hundred tests in version one ten
520. Training text: generated tests give every template family and every rule its own test method
521. Training text: a ui density toggle switches between compact and comfortable spacing
522. Training text: a high contrast mode strengthens borders and muted text for readability
523. Training text: a reduce motion toggle disables animations and honours the system preference
524. Training text: the sidebar collapses with the button or ctrl b
525. Training text: pinned messages live in a strip above the composer and persist in local storage
526. Training text: hover actions on every message offer copy pin and quote
527. Training text: the edit last button reloads your previous message into the composer
528. Training text: copy all collects the whole transcript as plain text
529. Training text: a share button uses the web share api with a clipboard fallback
530. Training text: a print button and a print stylesheet produce a clean transcript on paper
531. Training text: desktop notifications and a title badge announce replies when the tab is hidden
532. Training text: an optional web audio chime plays when a reply arrives
533. Training text: messages typed while offline queue in local storage and flush when the connection returns
534. Training text: the status text shows round trip ping time on hover
535. Training text: polling pauses after five idle minutes to save battery
536. Training text: a command dialog lists every keyboard shortcut and the question mark key opens it
537. Training text: an about dialog shows the version and endpoint count
538. Training text: svg icon serves as favicon apple touch icon and manifest icon

### Maths pack (65)

539. Maths rule: factorial
540. Maths rule: fibonacci nth
541. Maths rule: is prime
542. Maths rule: nth prime
543. Maths rule: gcd lcm
544. Maths rule: prime factors
545. Maths rule: divisors
546. Maths rule: digit sum
547. Maths rule: digital root
548. Maths rule: perfect square check
549. Maths rule: palindrome number
550. Maths rule: leap year
551. Maths rule: divisible by
552. Maths rule: even or odd
553. Maths rule: nth root
554. Maths rule: log base 10
555. Maths rule: log2
556. Maths rule: natural log
557. Maths rule: trig degrees
558. Maths rule: absolute value
559. Maths rule: floor ceil
560. Maths rule: round to n
561. Maths rule: remainder
562. Maths rule: percent of
563. Maths rule: what percent of
564. Maths rule: percent off
565. Maths rule: percent increase
566. Maths rule: percent decrease
567. Maths rule: tip
568. Maths rule: simple interest
569. Maths rule: compound interest
570. Maths rule: grade letter
571. Maths rule: circle area
572. Maths rule: rectangle area
573. Maths rule: triangle area
574. Maths rule: sphere volume
575. Maths rule: cylinder volume
576. Maths rule: pythagoras
577. Maths rule: distance midpoint
578. Maths rule: slope
579. Maths rule: speed
580. Maths rule: time
581. Maths rule: bmi
582. Maths rule: sum of range
583. Maths rule: sum of squares
584. Maths rule: triangular number
585. Maths rule: median
586. Maths rule: mode
587. Maths rule: range
588. Maths rule: variance
589. Maths rule: stddev
590. Maths rule: geometric mean
591. Maths rule: harmonic mean
592. Maths rule: decimal to fraction
593. Maths rule: fraction to decimal
594. Maths rule: simplify fraction
595. Maths rule: add fractions
596. Maths rule: multiply fractions
597. Maths rule: ratio simplify
598. Maths rule: independent probability
599. Maths rule: coin run
600. Maths rule: dice double
601. Maths rule: hex to rgb
602. Maths rule: rgb to hex
603. Maths rule: quadratic roots

### Text pack (55)

604. Text rule: uppercase
605. Text rule: lowercase
606. Text rule: title case
607. Text rule: capitalize
608. Text rule: swap case
609. Text rule: reverse text
610. Text rule: reverse words
611. Text rule: count words
612. Text rule: count characters
613. Text rule: count vowels
614. Text rule: count consonants
615. Text rule: count sentences
616. Text rule: reading time
617. Text rule: word frequency
618. Text rule: slugify
619. Text rule: snake case
620. Text rule: kebab case
621. Text rule: camel case
622. Text rule: initials
623. Text rule: acronym
624. Text rule: base64 encode
625. Text rule: base64 decode
626. Text rule: rot13
627. Text rule: url encode
628. Text rule: binary of text
629. Text rule: hex of text
630. Text rule: sha256
631. Text rule: md5
632. Text rule: crc32
633. Text rule: remove duplicate lines
634. Text rule: sort lines
635. Text rule: number lines
636. Text rule: strip empty lines
637. Text rule: collapse spaces
638. Text rule: trim
639. Text rule: shuffle lines
640. Text rule: extract emails
641. Text rule: extract urls
642. Text rule: extract numbers
643. Text rule: extract hashtags
644. Text rule: extract mentions
645. Text rule: json pretty
646. Text rule: json minify
647. Text rule: csv to markdown
648. Text rule: markdown to text
649. Text rule: pig latin
650. Text rule: is palindrome
651. Text rule: is isogram
652. Text rule: are anagrams
653. Text rule: repeat text
654. Text rule: truncate
655. Text rule: pad text
656. Text rule: replace text
657. Text rule: split to list
658. Text rule: join list

### Brain wiring (7)

659. Maths pack runs in `reply()` before arithmetic (confidence 1.0, mode `math`)
660. Text pack runs in `reply()` and tags replies as `skill: text:<rule>`
661. `quick_answer()` consults the maths pack (self-eval coverage)
662. `quick_answer()` consults the text pack
663. Both packs return `None` on no match so normal chat continues
664. Rule handlers are exception-guarded — a broken rule can never 500 chat
665. Seed loading is **additive and idempotent** — a later boot merges only the pairs/texts an update added, instead of skipping the seed because memory is no longer empty

### API (16)

666. GET /api/math — evaluate a maths expression, falls back to arithmetic
667. GET /api/text — run a text transform; 404 lists every available rule
668. GET /api/rules — machine-readable inventory of maths, text and code rules
669. GET /api/convert — unit/temperature conversion only
670. GET /api/roman — roman numerals both directions
671. GET /api/echo — echo with length + server time, for client debugging
672. GET /api/uptime — uptime seconds plus human form
673. GET /api/endpoints — self-describing route list
674. GET /api/metrics — Prometheus-style text metrics
675. POST /api/chat/batch — up to 10 messages in one round-trip, `results` array
676. GET /api/quote — a random constitution principle
677. X-Request-Id — per-request id, echoed when the client supplies one
678. Server-Timing — per-request duration header for profiling
679. before_request stamp — records the monotonic start used by `Server-Timing`
680. X-MyGPT-Version — version header on every response
681. uptime baseline — restored `_started_monotonic` used by the new endpoints

### WebUI (56)

682. 📐 density toggle switches compact ⇄ comfortable
683. Density preference persisted in localStorage
684. Compact CSS pack (tighter bubbles, cards and message gaps)
685. ◐ high-contrast toggle with strengthened borders and muted text
686. High-contrast CSS via `html[data-contrast=high]`
687. 🎞 reduced-motion toggle that shortens all animations
688. Reduced-motion CSS enforcement in one block
689. `prefers-reduced-motion` media query honoured automatically
690. `prefers-contrast: more` media query honoured automatically
691. ◧ sidebar collapse button hides the panel and widens the chat
692. Ctrl+B toggles the sidebar
693. Sidebar state persisted in localStorage
694. 🔔 sound toggle with a WebAudio chime — no audio assets
695. 🖥 desktop-notification toggle with permission request
696. Notification + title-badge flash when a reply lands while hidden
697. Pinned-messages strip above the composer
698. 📌 pin action on every message
699. Click a pin chip to jump; right-click to unpin
700. Pins persisted in localStorage (max 8, oldest evicted)
701. ⧉ copy action on every message
702. ❝ quote action drops the first line into the composer
703. Hover/focus reveal for the message action row
704. ✏️ edit-last button reloads the previous message
705. ⧉ copy-all button collects the whole transcript as text
706. ⤒ first button jumps to the top and flashes the message
707. 🔗 share button uses the Web Share API
708. Share falls back to the clipboard with a clear toast
709. 🖨 print button plus print-stylesheet rules for the new chrome
710. ⌘ help dialog listing every shortcut
711. `?` on the keyboard opens the help dialog
712. About dialog showing live version and endpoint count
713. Offline queue stores messages typed with no connection
714. Queue flushes automatically on `online`
715. Offline styling on the composer
716. Idle detection (5 quiet minutes) pauses polling
717. Welcome-back toast when activity resumes
718. Round-trip ping measured every 45 s
719. Ping time + quality shown in the status tooltip
720. Toggle on/off visual states for all seven prefs
721. Modal styling with backdrop, kbd chips and focus return
722. `.msg-actions`, `.pins-bar` and `.chat-actions` CSS
723. Skip-to-composer link (keyboard users)
724. `role="log"` + `aria-live` on the transcript
725. `aria-busy` set while a reply is pending
726. `:focus-visible` outlines on every interactive control
727. `.sr-only` utility class added
728. `aria-label` on the pins bar
729. Icon-only buttons all carry `aria-label`/`title`
730. Flash highlight on the message jumped to
731. Composer anchor for the skip-link target
732. v1.10 print rules hide action rows, pins and dialogs
733. Prefs persisted as one JSON key (`mygpt.prefs`)
734. Toast feedback for every new toggle
735. LocalStorage guarded in try/catch (private-mode safe)
736. Density/contrast/motion applied through `data-*` attributes
737. Deduped prefs bootstrap (one read, one write)

### Tests (306)

738. Test: TemplatePackTests.test_all_extra_snippets_distinct
739. Test: SeedPackTests.test_answer_length_sane
740. Test: ApiPackTests.test_chat_batch
741. Test: ApiPackTests.test_chat_batch_cap
742. Test: ApiPackTests.test_chat_batch_validation
743. Test: BrainPackTests.test_code_still_wins_for_code_asks
744. Test: ApiPackTests.test_convert_endpoint
745. Test: ApiPackTests.test_convert_endpoint_404
746. Test: BrainPackTests.test_counter_grows
747. Test: ApiPackTests.test_echo_endpoint
748. Test: ApiPackTests.test_endpoints_listing
749. Test: SeedPackTests.test_every_pair_has_content
750. Test: TemplatePackTests.test_every_snippet_compiles
751. Test: TemplatePackTests.test_family_001_linear_search
752. Test: TemplatePackTests.test_family_002_selection_sort
753. Test: TemplatePackTests.test_family_003_insertion_sort
754. Test: TemplatePackTests.test_family_004_merge_sort
755. Test: TemplatePackTests.test_family_005_quick_sort
756. Test: TemplatePackTests.test_family_006_heap_sort
757. Test: TemplatePackTests.test_family_007_counting_sort
758. Test: TemplatePackTests.test_family_008_binary_search_recursive
759. Test: TemplatePackTests.test_family_009_two_sum_problem
760. Test: TemplatePackTests.test_family_010_maximum_subarray
761. Test: TemplatePackTests.test_family_011_longest_common_prefix
762. Test: TemplatePackTests.test_family_012_longest_common_subsequence
763. Test: TemplatePackTests.test_family_013_edit_distance
764. Test: TemplatePackTests.test_family_014_knapsack_0_1
765. Test: TemplatePackTests.test_family_015_coin_change
766. Test: TemplatePackTests.test_family_016_fibonacci_memoized
767. Test: TemplatePackTests.test_family_017_pascal_triangle
768. Test: TemplatePackTests.test_family_018_catalan_numbers
769. Test: TemplatePackTests.test_family_019_prime_factorization
770. Test: TemplatePackTests.test_family_020_sieve_of_eratosthenes
771. Test: TemplatePackTests.test_family_021_nth_prime
772. Test: TemplatePackTests.test_family_022_twin_primes
773. Test: TemplatePackTests.test_family_023_perfect_numbers
774. Test: TemplatePackTests.test_family_024_amicable_numbers
775. Test: TemplatePackTests.test_family_025_happy_numbers
776. Test: TemplatePackTests.test_family_026_kaprekar_number
777. Test: TemplatePackTests.test_family_027_automorphic_number
778. Test: TemplatePackTests.test_family_028_sum_of_divisors
779. Test: TemplatePackTests.test_family_029_count_divisors
780. Test: TemplatePackTests.test_family_030_euler_totient
781. Test: TemplatePackTests.test_family_031_trailing_zeros_factorial
782. Test: TemplatePackTests.test_family_032_binomial_coefficient
783. Test: TemplatePackTests.test_family_033_permutations_and_combinations
784. Test: TemplatePackTests.test_family_034_power_set
785. Test: TemplatePackTests.test_family_035_cartesian_product
786. Test: TemplatePackTests.test_family_036_rotate_a_list
787. Test: TemplatePackTests.test_family_037_chunk_a_list
788. Test: TemplatePackTests.test_family_038_partition_list
789. Test: TemplatePackTests.test_family_039_group_by_key
790. Test: TemplatePackTests.test_family_040_invert_a_dictionary
791. Test: TemplatePackTests.test_family_041_sort_dict_by_value
792. Test: TemplatePackTests.test_family_042_dict_from_two_lists
793. Test: TemplatePackTests.test_family_043_deep_merge_dicts
794. Test: TemplatePackTests.test_family_044_flatten_a_dict
795. Test: TemplatePackTests.test_family_045_count_occurrences
796. Test: TemplatePackTests.test_family_046_find_duplicates_in_list
797. Test: TemplatePackTests.test_family_047_remove_falsy_values
798. Test: TemplatePackTests.test_family_048_zip_longest
799. Test: TemplatePackTests.test_family_049_pairwise_iteration
800. Test: TemplatePackTests.test_family_050_matrix_multiplication
801. Test: TemplatePackTests.test_family_051_matrix_addition
802. Test: TemplatePackTests.test_family_052_identity_matrix
803. Test: TemplatePackTests.test_family_053_determinant
804. Test: TemplatePackTests.test_family_054_rotate_matrix
805. Test: TemplatePackTests.test_family_055_spiral_matrix
806. Test: TemplatePackTests.test_family_056_diagonal_sum
807. Test: TemplatePackTests.test_family_057_string_to_int
808. Test: TemplatePackTests.test_family_058_int_to_string
809. Test: TemplatePackTests.test_family_059_vigenere_cipher
810. Test: TemplatePackTests.test_family_060_morse_code
811. Test: TemplatePackTests.test_family_061_atbash_cipher
812. Test: TemplatePackTests.test_family_062_base64_encode_decode
813. Test: TemplatePackTests.test_family_063_hash_a_string
814. Test: TemplatePackTests.test_family_064_uuid_generation
815. Test: TemplatePackTests.test_family_065_random_shuffle
816. Test: TemplatePackTests.test_family_066_weighted_choice
817. Test: TemplatePackTests.test_family_067_roll_dice_statistics
818. Test: TemplatePackTests.test_family_068_deck_of_cards
819. Test: TemplatePackTests.test_family_069_memoize_decorator
820. Test: TemplatePackTests.test_family_070_retry_decorator
821. Test: TemplatePackTests.test_family_071_singleton_pattern
822. Test: TemplatePackTests.test_family_072_factory_pattern
823. Test: TemplatePackTests.test_family_073_observer_pattern
824. Test: TemplatePackTests.test_family_074_strategy_pattern
825. Test: TemplatePackTests.test_family_075_namedtuple_example
826. Test: TemplatePackTests.test_family_076_defaultdict_example
827. Test: TemplatePackTests.test_family_077_heapq_example
828. Test: TemplatePackTests.test_family_078_bisect_example
829. Test: TemplatePackTests.test_family_079_itertools_example
830. Test: TemplatePackTests.test_family_080_functools_reduce
831. Test: TemplatePackTests.test_family_081_functools_partial
832. Test: TemplatePackTests.test_family_082_context_manager_class
833. Test: TemplatePackTests.test_family_083_contextmanager_decorator
834. Test: TemplatePackTests.test_family_084_property_decorator
835. Test: TemplatePackTests.test_family_085_classmethod_staticmethod
836. Test: TemplatePackTests.test_family_086_frozen_dataclass
837. Test: TemplatePackTests.test_family_087_dataclass_with_slots
838. Test: TemplatePackTests.test_family_088_abc_abstract_class
839. Test: TemplatePackTests.test_family_089_typeddict_example
840. Test: TemplatePackTests.test_family_090_mro_multiple_inheritance
841. Test: TemplatePackTests.test_family_091_counter_example
842. Test: TemplatePackTests.test_family_092_chainmap_example
843. Test: TemplatePackTests.test_family_093_csv_dict_reader
844. Test: TemplatePackTests.test_family_094_csv_dict_writer
845. Test: TemplatePackTests.test_family_095_json_pretty_print
846. Test: TemplatePackTests.test_family_096_json_to_csv
847. Test: TemplatePackTests.test_family_097_csv_to_json
848. Test: TemplatePackTests.test_family_098_ini_config_parser
849. Test: TemplatePackTests.test_family_099_xml_parse_example
850. Test: TemplatePackTests.test_family_100_sqlite_basics
851. Test: TemplatePackTests.test_family_101_sqlite_parameterized_query
852. Test: TemplatePackTests.test_family_102_sqlite_context_manager
853. Test: TemplatePackTests.test_family_103_copy_a_file
854. Test: TemplatePackTests.test_family_104_move_or_rename_a_file
855. Test: TemplatePackTests.test_family_105_delete_files_by_pattern
856. Test: TemplatePackTests.test_family_106_make_directory_tree
857. Test: TemplatePackTests.test_family_107_zip_files_into_archive
858. Test: TemplatePackTests.test_family_108_unzip_archive
859. Test: TemplatePackTests.test_family_109_human_readable_file_size
860. Test: TemplatePackTests.test_family_110_check_if_file_exists
861. Test: TemplatePackTests.test_family_111_temp_file_usage
862. Test: TemplatePackTests.test_family_112_pathlib_tour
863. Test: TemplatePackTests.test_family_113_read_file_in_chunks
864. Test: TemplatePackTests.test_family_114_tail_a_file
865. Test: TemplatePackTests.test_family_115_word_frequency_from_file
866. Test: TemplatePackTests.test_family_116_grep_text_in_files
867. Test: TemplatePackTests.test_family_117_bulk_rename_files
868. Test: TemplatePackTests.test_family_118_deduplicate_files_by_hash
869. Test: TemplatePackTests.test_family_119_download_a_file
870. Test: TemplatePackTests.test_family_120_progress_bar
871. Test: TemplatePackTests.test_family_121_text_spinner
872. Test: TemplatePackTests.test_family_122_ansi_colors
873. Test: TemplatePackTests.test_family_123_clear_the_screen
874. Test: TemplatePackTests.test_family_124_terminal_menu
875. Test: TemplatePackTests.test_family_125_stopwatch
876. Test: TemplatePackTests.test_family_126_beep_sound
877. Test: TemplatePackTests.test_family_127_rotating_log_files
878. Test: TemplatePackTests.test_family_128_serve_a_directory
879. Test: TemplatePackTests.test_family_129_http_client_with_retries
880. Test: TemplatePackTests.test_family_130_url_parsing
881. Test: TemplatePackTests.test_family_131_build_a_query_string
882. Test: TemplatePackTests.test_family_132_json_http_post
883. Test: TemplatePackTests.test_family_133_basic_auth_header
884. Test: TemplatePackTests.test_family_134_rate_limiter
885. Test: MathPackTests.test_math_001_factorial
886. Test: MathPackTests.test_math_002_fibonacci
887. Test: MathPackTests.test_math_003_is_prime_yes
888. Test: MathPackTests.test_math_004_is_prime_no
889. Test: MathPackTests.test_math_005_nth_prime
890. Test: MathPackTests.test_math_006_gcd
891. Test: MathPackTests.test_math_007_lcm
892. Test: MathPackTests.test_math_008_prime_factors
893. Test: MathPackTests.test_math_009_divisors
894. Test: MathPackTests.test_math_010_digit_sum
895. Test: MathPackTests.test_math_011_digital_root
896. Test: MathPackTests.test_math_012_perfect_square
897. Test: MathPackTests.test_math_013_palindrome_number
898. Test: MathPackTests.test_math_014_leap_year
899. Test: MathPackTests.test_math_015_divisible
900. Test: MathPackTests.test_math_016_even_odd
901. Test: MathPackTests.test_math_017_cube_root
902. Test: MathPackTests.test_math_018_log10
903. Test: MathPackTests.test_math_019_log2
904. Test: MathPackTests.test_math_020_natural_log
905. Test: MathPackTests.test_math_021_trig
906. Test: MathPackTests.test_math_022_absolute
907. Test: MathPackTests.test_math_023_floor
908. Test: MathPackTests.test_math_024_ceiling
909. Test: MathPackTests.test_math_025_round_decimals
910. Test: MathPackTests.test_math_026_remainder
911. Test: MathPackTests.test_math_027_percent_increase
912. Test: MathPackTests.test_math_028_percent_decrease
913. Test: MathPackTests.test_math_029_tip
914. Test: MathPackTests.test_math_030_simple_interest
915. Test: MathPackTests.test_math_031_compound_interest
916. Test: MathPackTests.test_math_032_grade
917. Test: MathPackTests.test_math_033_circle
918. Test: MathPackTests.test_math_034_rectangle
919. Test: MathPackTests.test_math_035_triangle
920. Test: MathPackTests.test_math_036_sphere
921. Test: MathPackTests.test_math_037_cylinder
922. Test: MathPackTests.test_math_038_pythagoras
923. Test: MathPackTests.test_math_039_distance
924. Test: MathPackTests.test_math_040_midpoint
925. Test: MathPackTests.test_math_041_slope
926. Test: MathPackTests.test_math_042_speed
927. Test: MathPackTests.test_math_043_travel_time
928. Test: MathPackTests.test_math_044_bmi
929. Test: MathPackTests.test_math_045_sum_range
930. Test: MathPackTests.test_math_046_sum_squares
931. Test: MathPackTests.test_math_047_triangular
932. Test: MathPackTests.test_math_048_median
933. Test: MathPackTests.test_math_049_mode
934. Test: MathPackTests.test_math_050_range
935. Test: MathPackTests.test_math_051_variance
936. Test: MathPackTests.test_math_052_stddev
937. Test: MathPackTests.test_math_053_geometric_mean
938. Test: MathPackTests.test_math_054_harmonic_mean
939. Test: MathPackTests.test_math_055_decimal_to_fraction
940. Test: MathPackTests.test_math_056_fraction_to_decimal
941. Test: MathPackTests.test_math_057_simplify_fraction
942. Test: MathPackTests.test_math_058_add_fractions
943. Test: MathPackTests.test_math_059_multiply_fractions
944. Test: MathPackTests.test_math_060_ratio
945. Test: MathPackTests.test_math_061_independent_probability
946. Test: MathPackTests.test_math_062_coin_run
947. Test: MathPackTests.test_math_063_dice_double
948. Test: MathPackTests.test_math_064_hex_to_rgb
949. Test: MathPackTests.test_math_065_rgb_to_hex
950. Test: MathPackTests.test_math_066_quadratic
951. Test: MathPackTests.test_math_067_percent_of
952. Test: MathPackTests.test_math_068_what_percent_of
953. Test: MathPackTests.test_math_069_percent_off
954. Test: ApiPackTests.test_math_endpoint
955. Test: ApiPackTests.test_math_endpoint_400
956. Test: ApiPackTests.test_math_endpoint_404
957. Test: BrainPackTests.test_maths_pack_answer
958. Test: ApiPackTests.test_metrics_endpoint
959. Test: SeedPackTests.test_no_duplicate_questions
960. Test: SeedPackTests.test_no_markup_in_answers
961. Test: ApiPackTests.test_page_has_v110_controls
962. Test: SeedPackTests.test_pair_count
963. Test: TextPackTests.test_questions_not_hijacked
964. Test: BrainPackTests.test_quick_answer_uses_mathx
965. Test: BrainPackTests.test_quick_answer_uses_textfx
966. Test: ApiPackTests.test_quote_endpoint
967. Test: ApiPackTests.test_request_id_echoed
968. Test: ApiPackTests.test_request_id_header
969. Test: ApiPackTests.test_roman_endpoint_number
970. Test: ApiPackTests.test_roman_endpoint_roman
971. Test: MathPackTests.test_rule_count
972. Test: TextPackTests.test_rule_count
973. Test: MathPackTests.test_rule_names_unique
974. Test: TextPackTests.test_rule_names_unique
975. Test: ApiPackTests.test_rules_endpoint
976. Test: BrainPackTests.test_seed_knowledge_reachable
977. Test: SeedPackTests.test_seed_merge_is_additive
978. Test: SeedPackTests.test_seed_topic_is_answerable
979. Test: ApiPackTests.test_server_timing_header
980. Test: TextPackTests.test_text_001_uppercase
981. Test: TextPackTests.test_text_002_lowercase
982. Test: TextPackTests.test_text_003_title_case
983. Test: TextPackTests.test_text_004_capitalize
984. Test: TextPackTests.test_text_005_swap_case
985. Test: TextPackTests.test_text_006_reverse_text
986. Test: TextPackTests.test_text_007_reverse_words
987. Test: TextPackTests.test_text_008_count_words
988. Test: TextPackTests.test_text_009_count_characters
989. Test: TextPackTests.test_text_010_count_vowels
990. Test: TextPackTests.test_text_011_count_consonants
991. Test: TextPackTests.test_text_012_count_sentences
992. Test: TextPackTests.test_text_013_reading_time
993. Test: TextPackTests.test_text_014_word_frequency
994. Test: TextPackTests.test_text_015_slugify
995. Test: TextPackTests.test_text_016_snake_case
996. Test: TextPackTests.test_text_017_kebab_case
997. Test: TextPackTests.test_text_018_camel_case
998. Test: TextPackTests.test_text_019_initials
999. Test: TextPackTests.test_text_020_acronym
1000. Test: TextPackTests.test_text_021_base64_encode
1001. Test: TextPackTests.test_text_022_base64_decode
1002. Test: TextPackTests.test_text_023_rot13
1003. Test: TextPackTests.test_text_024_url_encode
1004. Test: TextPackTests.test_text_025_binary_of_text
1005. Test: TextPackTests.test_text_026_hex_of_text
1006. Test: TextPackTests.test_text_027_sha256
1007. Test: TextPackTests.test_text_028_md5
1008. Test: TextPackTests.test_text_029_crc32
1009. Test: TextPackTests.test_text_030_dedupe_lines
1010. Test: TextPackTests.test_text_031_sort_lines
1011. Test: TextPackTests.test_text_032_number_lines
1012. Test: TextPackTests.test_text_033_strip_empty
1013. Test: TextPackTests.test_text_034_collapse_spaces
1014. Test: TextPackTests.test_text_035_trim
1015. Test: TextPackTests.test_text_036_shuffle_lines
1016. Test: TextPackTests.test_text_037_extract_emails
1017. Test: TextPackTests.test_text_038_extract_urls
1018. Test: TextPackTests.test_text_039_extract_numbers
1019. Test: TextPackTests.test_text_040_extract_hashtags
1020. Test: TextPackTests.test_text_041_extract_mentions
1021. Test: TextPackTests.test_text_042_json_pretty
1022. Test: TextPackTests.test_text_043_json_minify
1023. Test: TextPackTests.test_text_044_csv_to_markdown
1024. Test: TextPackTests.test_text_045_markdown_to_text
1025. Test: TextPackTests.test_text_046_pig_latin
1026. Test: TextPackTests.test_text_047_is_palindrome
1027. Test: TextPackTests.test_text_048_is_isogram
1028. Test: TextPackTests.test_text_049_anagrams
1029. Test: TextPackTests.test_text_050_repeat_text
1030. Test: TextPackTests.test_text_051_truncate
1031. Test: TextPackTests.test_text_052_pad_text
1032. Test: TextPackTests.test_text_053_replace_text
1033. Test: TextPackTests.test_text_054_split_to_list
1034. Test: TextPackTests.test_text_055_join_list
1035. Test: ApiPackTests.test_text_endpoint
1036. Test: ApiPackTests.test_text_endpoint_404_lists_rules
1037. Test: BrainPackTests.test_text_pack_answer
1038. Test: BrainPackTests.test_text_pack_skill_tag
1039. Test: SeedPackTests.test_texts_present
1040. Test: TemplatePackTests.test_total_family_count
1041. Test: MathPackTests.test_unrelated_text_no_match
1042. Test: ApiPackTests.test_uptime_endpoint
1043. Test: ApiPackTests.test_version_header

### Efficiency (5)

1044. `codegen.has_template` memoised with lru_cache (hot path, pure)
1045. `mathx.solve` memoised with lru_cache
1046. `textfx.solve` memoised with lru_cache
1047. Seed texts deduplicated on load (`dict.fromkeys`)
1048. Seed merge hashes normalised questions once per boot (`O(n)` set lookups, not a nested scan) and re-trains briefly (4 epochs) only when it actually added something

### Bugs fixed (10)

1049. `/api/uptime` and `/api/metrics` referenced `_started_monotonic`, which v1.9 had removed — restored
1050. `rgb_to_hex` never matched: the pattern demanded a separator that callers omit
1051. `reverse words:` was swallowed by the reverse-text rule — rule tightened
1052. `json pretty:` was swallowed by the pretty-print-json rule — pattern extended
1053. 28 new template asks did not match their own regex — `_broaden()` now guarantees it
1054. 28 generated per-family tests assumed first-match identity — made match-aware, exposing real overlaps
1055. "what is 17% of 250" fell through to the curiosity fallback — percent-of/off/what-percent rules added
1056. `Brain._find_math` understood "20 percent of 150" but not "17% of 250" — `% of` now normalised
1057. Docstring counts drifted from reality (130→134 families, 48→62 maths rules, 45→55 text rules) — corrected
1058. New seed knowledge never reached an existing `data/` folder — the `not self.memory.pairs` guard meant updates shipped knowledge that returned "curious" forever (found live: *what is a trie*)

### Docs (4)

1059. Version bumped to 1.10.0
1060. README: 218 template families, both new packs, 11 endpoints, 420 tests, new WebUI blocks
1061. CHANGELOG: this release, numbered end to end
1062. Both pack docstrings reconciled with the real rule counts

**Total: 1062 numbered items.** Counting convention matches v1.8/v1.9:
one item per template family, seed pair or text, maths/text rule,
endpoint, UI behaviour, test method and fix — so the same underlying
capability is counted at each layer where it ships (code, brain, API,
UI, tests).
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
