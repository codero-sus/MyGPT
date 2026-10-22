"""Background trainer: the request path never waits on gradient steps.

Ported from CORTEX (github.com/codero-sus/agi): a queue-fed worker thread runs
Adam steps, debounces checkpoints, and — when idle — replays distilled mind
state as "dream" training.

Two guarantees make that safe to run while you are using the app:

1. **It yields to requests.** Every HTTP request marks itself in flight, and
   the worker waits for the app to go quiet before it touches the model. It
   also stays quiet for a short cooldown after the last response, so the moment
   you send a message is never the moment it grabs the CPU.
2. **No step holds the model for long.** A full training round is run one batch
   at a time against ``NeuralLM.step_batch``, which takes the model lock for the
   step alone. A chat request only ever waits for one batch, not for a round.

On top of that it duty-cycles: after each chunk of work it sleeps so that the
thread's CPU time stays at or below ``duty`` of wall-clock time. The default is
0.35 — the trainer uses at most about a third of one core, and only when there
is something queued to learn. Idle costs nothing; there is no polling loop, the
worker blocks on its queue for a second at a time.

Everything here is measured, not asserted: ``snapshot()`` reports the thread's
own CPU time (read from the OS thread clock), the duty actually achieved, and
how long it has been waiting for requests. ``tools/benchmark.py --trainer-impact``
turns those numbers into a before/after report.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable

import numpy as np

CHECKPOINT_EVERY = 12      # dirty steps between weight saves
DREAM_IDLE_SEC = 20.0      # idle seconds before a dream replay
SAVE_IDLE_SEC = 15.0       # idle seconds before flushing a dirty checkpoint
DREAM_STEPS = 3            # training steps per dream replay
ROUND_BATCH = 32           # windows per step when a full round is run in chunks

DUTY = 0.35                # background training: CPU time / wall time, max
COOLDOWN = 0.25            # stay quiet this long after the last response
MAX_SLEEP = 0.5            # cap on any single duty-cycle nap, seconds
STUCK_REQUEST_SEC = 120.0  # ignore a request counter left hanging longer than this
YIELD_MAX_WAIT = 2.0       # longest single wait for requests to clear


def thread_cpu_seconds(tid: int | None = None) -> float | None:
    """CPU seconds burned by one OS thread, or None if we cannot tell.

    Linux exposes this in ``/proc/self/task/<tid>/stat``; elsewhere we return
    None and the caller falls back to process-wide CPU time. Measured this way
    the number is attributable to the trainer alone, so "how much CPU does it
    use" is answerable even while the app is serving requests.
    """
    if tid is None:
        tid = threading.get_native_id()
    try:
        with open(f"/proc/self/task/{tid}/stat", encoding="utf-8") as handle:
            fields = handle.read().rsplit(")", 1)[1].split()
        ticks = float(fields[11]) + float(fields[12])       # utime + stime
        return ticks / os.sysconf("SC_CLK_TCK")
    except Exception:
        return None


def _num(value, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:                                     # NaN
        return default
    return max(low, min(high, number))


class BackgroundTrainer:
    def __init__(self, lm, save_fn: Callable[[], None]):
        self.lm = lm
        self.save_fn = save_fn
        # jobs: ("steps", text, n) or ("round", texts, epochs, reason)
        self.jobs: queue.Queue[tuple] = queue.Queue(maxsize=256)
        self.dream_source: Callable[[], str] | None = None
        self.on_round: Callable[[dict], None] | None = None
        self.busy = False
        self.queued = 0
        self.done_steps = 0
        self.rounds = 0
        self.last_loss = 0.0
        self.last_round: dict | None = None
        self.last_save = time.time()
        self._dirty = 0
        self._round_pending = False

        self.duty = _num(os.environ.get("MYGPT_TRAIN_DUTY"), DUTY, 0.05, 1.0)
        self.cooldown = _num(os.environ.get("MYGPT_TRAIN_COOLDOWN"), COOLDOWN,
                             0.0, 60.0)
        self.paused = False

        self._inflight = 0
        self._inflight_since = 0.0
        self._last_request_end = 0.0
        self._state_lock = threading.Lock()
        self._rng = np.random.default_rng()
        self._started = time.time()
        self._cpu_start = thread_cpu_seconds()
        self.cpu_seconds = 0.0            # CPU spent *by this thread*, seconds
        self._stop = threading.Event()
        self._native_id: int | None = None
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="mygpt-trainer")
        self._thread.start()

    # ------------------------------------------------------------ request path
    def request_started(self) -> None:
        """Mark an HTTP request as in flight (called from the web layer)."""
        with self._state_lock:
            if self._inflight == 0:
                self._inflight_since = time.time()
            self._inflight += 1

    def request_finished(self) -> None:
        with self._state_lock:
            self._inflight = max(0, self._inflight - 1)
            self._last_request_end = time.time()

    def should_yield(self) -> bool:
        """True while the app is serving, i.e. the trainer should stay quiet."""
        if self.paused:
            return True
        now = time.time()
        with self._state_lock:
            inflight = self._inflight
            since = self._inflight_since
            last_end = self._last_request_end
        if inflight:
            # A client that vanished mid-stream must not freeze learning forever.
            return (now - since) <= STUCK_REQUEST_SEC
        return (now - last_end) < self.cooldown

    def _yield_to_requests(self, max_wait: float = YIELD_MAX_WAIT) -> None:
        """Wait for the app to go quiet, but never longer than ``max_wait``.

        The cap matters: lock holds are a single batch (milliseconds), so after
        a bounded wait it is better to make slow progress than to stall a round
        indefinitely behind a long-lived stream.
        """
        deadline = time.time() + max_wait
        while not self._stop.is_set() and time.time() < deadline:
            if not self.should_yield():
                return
            self._stop.wait(0.05)

    # ------------------------------------------------------------------ submit
    def submit(self, text: str, steps: int = 2) -> bool:
        if not text or len(text) < 8:
            return False
        try:
            self.jobs.put_nowait(("steps", text, max(1, steps)))
            self.queued += 1
            return True
        except queue.Full:
            return False

    def submit_round(self, texts: list[str], epochs: int = 6,
                     reason: str = "auto", max_windows: int = 20000) -> bool:
        """Ask for a full training round. Coalesced: one round is ever queued.

        ``max_windows`` bounds the round's window sample — upkeep rounds on a
        grown corpus stay cheap, while an explicit train may ask for more.
        """
        if not texts:
            return False
        if self._round_pending:
            return False
        try:
            self.jobs.put_nowait(("round", list(texts), max(1, int(epochs)),
                                  reason, max(1, int(max_windows))))
            self._round_pending = True
            return True
        except queue.Full:
            return False

    # ------------------------------------------------------------------- state
    def configure(self, **kwargs) -> dict:
        """Adjust the knobs the UI/API may change: ``paused``, ``duty``."""
        if "paused" in kwargs and kwargs["paused"] is not None:
            self.paused = bool(kwargs["paused"])
        if kwargs.get("duty") is not None:
            self.duty = _num(kwargs["duty"], self.duty, 0.05, 1.0)
        if kwargs.get("cooldown") is not None:
            self.cooldown = _num(kwargs["cooldown"], self.cooldown, 0.0, 60.0)
        return self.snapshot()

    def cpu_now(self) -> float:
        """CPU seconds burned by the *trainer* thread (falls back to process CPU).

        The id has to be captured rather than looked up: when this runs on the
        request thread, ``threading.get_native_id()`` is the request thread, and
        the answer would silently be "how much CPU the caller used".
        """
        if self._native_id is None:
            return time.process_time()
        measured = thread_cpu_seconds(self._native_id)
        if measured is None:
            return time.process_time()
        return measured

    def snapshot(self) -> dict:
        wall = max(1e-9, time.time() - self._started)
        with self._state_lock:
            inflight = self._inflight
        return {"busy": self.busy, "queue": self.jobs.qsize(),
                "queued": self.queued, "done_steps": self.done_steps,
                "last_loss": round(self.last_loss, 4),
                "rounds": self.rounds, "round_pending": self._round_pending,
                "paused": self.paused, "inflight": inflight,
                "waiting_for_requests": self.should_yield(),
                "duty_target": round(self.duty, 3),
                "duty_observed": round(self.cpu_seconds / wall, 3),
                "cpu_ms": int(self.cpu_seconds * 1000),
                "last_round": self.last_round}

    def flush_save(self) -> None:
        try:
            self.save_fn()
            self.last_save = time.time()
            self._dirty = 0
        except Exception:
            pass

    # ---------------------------------------------------------------- the loop
    def _run(self) -> None:
        self._native_id = threading.get_native_id()
        last_dream = time.time()
        while not self._stop.is_set():
            try:
                job = self.jobs.get(timeout=1.0)
            except queue.Empty:
                now = time.time()
                if (now - last_dream >= DREAM_IDLE_SEC
                        and not self.should_yield()):
                    last_dream = now
                    self._dream()
                if self._dirty and now - self.last_save > SAVE_IDLE_SEC:
                    self.flush_save()
                continue
            if job[0] == "stop":
                break
            self.busy = True
            try:
                if job[0] == "round":
                    self._run_round(*job[1:])
                else:
                    self._run_steps(*job[1:])
            except Exception:
                pass
            finally:
                self.busy = False

    def _run_steps(self, text: str, steps: int) -> None:
        loss_acc, n = 0.0, 0
        for _ in range(steps):
            if self._stop.is_set():
                break
            self._yield_to_requests()
            cpu0 = self.cpu_now()
            try:
                loss_acc += self.lm.train_step(text)
            except Exception:
                break
            n += 1
            self.done_steps += 1
            self._dirty += 1
            self._spend(cpu0)
            if self._dirty >= CHECKPOINT_EVERY:
                self.flush_save()
        if n:
            self.last_loss = loss_acc / n

    def _run_round(self, texts: list[str], epochs: int, reason: str,
                   max_windows: int = 20000) -> None:
        """A full round, one batch at a time, yielding and duty-cycling as it goes."""
        started, cpu_start = time.time(), self.cpu_now()
        result: dict = {"reason": reason, "epochs": epochs, "windows": 0,
                        "loss_first": None, "loss_last": None,
                        "steps": 0, "stopped": False}
        try:
            windows = self.lm.all_windows(list(texts), max_windows=max_windows)
            result["windows"] = len(windows)
            if windows:
                first, last, steps = None, None, 0
                for _ in range(max(1, int(epochs))):
                    if self._stop.is_set():
                        result["stopped"] = True
                        break
                    self._yield_to_requests()
                    self._rng.shuffle(windows)
                    for b in range(0, len(windows), ROUND_BATCH):
                        if self._stop.is_set():
                            result["stopped"] = True
                            break
                        cpu0 = self.cpu_now()
                        loss = self.lm.step_batch(windows[b:b + ROUND_BATCH])
                        if first is None:
                            first = loss
                        last = loss
                        steps += 1
                        self.done_steps += 1
                        self._dirty += 1
                        self.last_loss = loss
                        self._spend(cpu0)
                        if self._dirty >= CHECKPOINT_EVERY:
                            self.flush_save()
                        if b % (ROUND_BATCH * 4) == 0:
                            self._yield_to_requests()
                result.update(loss_first=(float(first) if first is not None
                                          else None),
                              loss_last=(float(last) if last is not None else None),
                              steps=steps)
        finally:
            result["took_ms"] = int((time.time() - started) * 1000)
            result["cpu_ms"] = int(max(0.0, self.cpu_now() - cpu_start) * 1000)
            self.rounds += 1
            self._round_pending = False
            self.last_round = result
            callback = self.on_round
            if callback is not None:
                try:
                    callback(result)
                except Exception:
                    pass

    def _spend(self, cpu_before: float) -> None:
        """Account the CPU just used, then sleep to stay under the duty cycle."""
        used = max(0.0, self.cpu_now() - cpu_before)
        self.cpu_seconds += used
        if used > 0.0 and self.duty < 1.0:
            # Event.wait rather than time.sleep: stop() has to be able to cut a
            # duty-cycle nap short, otherwise shutdown (and the test suite) waits
            # for a nap it no longer needs.
            self._stop.wait(min(used * (1.0 / self.duty - 1.0), MAX_SLEEP))

    def _dream(self) -> None:
        """Idle replay: retrain on a distilled snapshot of the mind."""
        src = self.dream_source
        if src is None:
            return
        try:
            text = src()
        except Exception:
            return
        if not text:
            return
        self.busy = True
        try:
            for _ in range(DREAM_STEPS):
                if self._stop.is_set():
                    break
                cpu0 = self.cpu_now()
                self.last_loss = self.lm.train_step(text)
                self.done_steps += 1
                self._dirty += 1
                self._spend(cpu0)
        except Exception:
            pass
        finally:
            self.busy = False

    def stop(self) -> None:
        """Ask the worker to finish. Wakes it out of any sleep it is in."""
        self._stop.set()
        try:
            self.jobs.put_nowait(("stop",))          # unblock a queue.get
        except queue.Full:
            pass
