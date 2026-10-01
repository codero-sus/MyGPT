"""Background trainer: the request path never waits on gradient steps.

Ported from CORTEX (github.com/codero-sus/agi): a queue-fed worker thread
runs Adam steps, debounces checkpoints, and — when idle — replays distilled
mind state as "dream" training.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable

CHECKPOINT_EVERY = 12      # dirty steps between weight saves
DREAM_IDLE_SEC = 20.0      # idle seconds before a dream replay
SAVE_IDLE_SEC = 15.0       # idle seconds before flushing a dirty checkpoint


class BackgroundTrainer:
    def __init__(self, lm, save_fn: Callable[[], None]):
        self.lm = lm
        self.save_fn = save_fn
        self.q: queue.Queue[tuple[str, int]] = queue.Queue(maxsize=128)
        self.dream_source: Callable[[], str] | None = None
        self.busy = False
        self.queued = 0
        self.done_steps = 0
        self.last_loss = 0.0
        self.last_save = time.time()
        self._dirty = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="mygpt-trainer")
        self._thread.start()

    def submit(self, text: str, steps: int = 2) -> bool:
        if not text or len(text) < 8:
            return False
        try:
            self.q.put_nowait((text, max(1, steps)))
            self.queued += 1
            return True
        except queue.Full:
            return False

    def snapshot(self) -> dict:
        return {"busy": self.busy, "queue": self.q.qsize(),
                "queued": self.queued, "done_steps": self.done_steps,
                "last_loss": round(self.last_loss, 4)}

    def flush_save(self) -> None:
        try:
            self.save_fn()
            self.last_save = time.time()
            self._dirty = 0
        except Exception:
            pass

    def _run(self) -> None:
        last_dream = time.time()
        while not self._stop.is_set():
            try:
                text, steps = self.q.get(timeout=1.0)
            except queue.Empty:
                now = time.time()
                if now - last_dream >= DREAM_IDLE_SEC:
                    last_dream = now
                    self._dream()
                if self._dirty and now - self.last_save > SAVE_IDLE_SEC:
                    self.flush_save()
                continue
            self.busy = True
            try:
                loss_acc, n = 0.0, 0
                for _ in range(steps):
                    loss_acc += self.lm.train_step(text)
                    n += 1
                    self.done_steps += 1
                    self._dirty += 1
                if n:
                    self.last_loss = loss_acc / n
                if self._dirty >= CHECKPOINT_EVERY:
                    self.flush_save()
            except Exception:
                pass
            finally:
                self.busy = False

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
            for _ in range(3):
                self.last_loss = self.lm.train_step(text)
                self.done_steps += 1
                self._dirty += 1
        except Exception:
            pass
        finally:
            self.busy = False

    def stop(self) -> None:
        self._stop.set()
