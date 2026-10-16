"""The background trainer: idle-only, duty-cycled, and never in your way.

These are the tests behind the v1.11.0 claim that self-training has "very little
impact". They check the three properties the claim rests on:

1. **It yields.** With a request in flight, the trainer does not touch the model.
2. **It is capped.** Its own CPU time stays under the configured duty cycle.
3. **It can be stopped.** ``paused=True`` means it does nothing at all.

and one about the bug this replaced: a learning event must not run a training
round on the request thread. That is the difference between "training happens in
the background" and "training happens in the background, except every fifth
teach, when it happens in front of you".
"""

from __future__ import annotations

import os
import json
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np                                            # noqa: E402

from mygpt.trainer import BackgroundTrainer                   # noqa: E402


class StubLM:
    """A language model whose step cost is predictable (a real matmul)."""

    def __init__(self, step_seconds: float = 0.01):
        self.step_seconds = step_seconds
        self.steps = 0
        self.lock_holder = None

    def train_step(self, text: str, max_windows: int = 64) -> float:
        deadline = time.perf_counter() + self.step_seconds
        a = np.random.rand(96, 96)
        while time.perf_counter() < deadline:
            a = a @ np.random.rand(96, 96)
        self.steps += 1
        return float(a.sum() % 1.0)

    def all_windows(self, texts):
        return [(np.zeros(4, dtype=np.int64), 1) for _ in texts[:20]]

    def step_batch(self, windows):
        time.sleep(self.step_seconds)
        self.steps += 1
        return 1.234


class TrainerTests(unittest.TestCase):

    def setUp(self):
        self.lm = StubLM()
        self.trainer = BackgroundTrainer(self.lm, lambda: None)

    def tearDown(self):
        self.trainer.stop()

    # ------------------------------------------------------------------ basics
    def test_short_text_is_not_queued(self):
        self.assertFalse(self.trainer.submit("tiny"))
        self.assertTrue(self.trainer.submit("a long enough sentence to learn"))

    def test_queue_has_a_ceiling(self):
        accepted = sum(1 for i in range(400)
                       if self.trainer.submit(f"queued sentence number {i}"))
        self.assertLess(accepted, 400, "the queue must refuse work eventually")
        self.assertGreater(accepted, 0)

    # ------------------------------------------------------------------- pause
    def test_paused_means_no_steps_at_all(self):
        self.trainer.configure(paused=True)
        for i in range(20):
            self.trainer.submit(f"paused sentence number {i}", steps=1)
        time.sleep(1.5)
        self.assertEqual(self.lm.steps, 0, "paused trainer must not train")
        self.assertTrue(self.trainer.should_yield())
        self.trainer.configure(paused=False)
        self.assertFalse(self.trainer.paused)

    # -------------------------------------------------------------------- yield
    def test_a_request_in_flight_stops_the_trainer(self):
        self.trainer.request_started()
        for i in range(20):
            self.trainer.submit(f"yield sentence number {i}", steps=1)
        time.sleep(1.0)
        self.assertEqual(self.lm.steps, 0,
                         "the trainer answered while a request was in flight")
        self.trainer.request_finished()
        deadline = time.time() + 5.0
        while time.time() < deadline and self.lm.steps == 0:
            time.sleep(0.05)
        self.assertGreater(self.lm.steps, 0, "work resumes once the app is idle")

    def test_cooldown_after_the_last_response(self):
        self.trainer.cooldown = 0.6
        self.trainer.request_started()
        self.trainer.request_finished()
        time.sleep(0.2)
        self.assertTrue(self.trainer.should_yield(),
                        "the gap right after a reply is still the user's")
        time.sleep(0.6)
        self.assertFalse(self.trainer.should_yield())

    def test_a_hung_request_does_not_freeze_learning_forever(self):
        import mygpt.trainer as trainer_module
        saved = trainer_module.STUCK_REQUEST_SEC
        trainer_module.STUCK_REQUEST_SEC = 0.3
        try:
            self.trainer.request_started()          # client vanished, never ends
            time.sleep(0.5)
            self.assertFalse(self.trainer.should_yield(),
                             "a request older than the stuck limit is ignored")
        finally:
            trainer_module.STUCK_REQUEST_SEC = saved

    # ---------------------------------------------------------------- duty cycle
    def test_duty_cycle_caps_its_share_of_one_core(self):
        self.trainer.duty = 0.25
        for i in range(200):
            self.trainer.submit(f"duty sentence number {i}", steps=1)
        cpu_before = self.trainer.cpu_now()
        wall = time.perf_counter()
        time.sleep(3.0)
        elapsed = time.perf_counter() - wall
        cpu = max(0.0, self.trainer.cpu_now() - cpu_before)
        duty = cpu / elapsed if elapsed else 0.0
        self.assertLess(duty, 0.6, f"trainer used {duty:.2f} of a core, "
                                   f"target 0.25")
        self.assertGreater(self.lm.steps, 0, "and it does keep working")

    def test_cpu_accounting_is_the_trainer_thread_not_the_caller(self):
        """cpu_now() must not report the *calling* thread's CPU.

        The first version of this used ``threading.get_native_id()``, which
        silently returns whoever called it — so the reported duty was the web
        thread's, and the trainer looked free while it was in fact working.
        """
        for i in range(60):
            self.trainer.submit(f"accounting sentence {i}", steps=1)
        deadline = time.time() + 5.0
        while time.time() < deadline and self.trainer.cpu_seconds == 0:
            time.sleep(0.05)
        self.assertGreater(self.trainer.cpu_seconds, 0.0,
                           "the trainer's own CPU time must be visible")
        self.assertGreater(self.trainer.cpu_now(), 0.0)

    # --------------------------------------------------------------- full rounds
    def test_submit_round_runs_a_round_and_reports_back(self):
        results = []
        self.trainer.on_round = results.append
        self.trainer.duty = 1.0
        self.assertTrue(self.trainer.submit_round(["alpha beta gamma"],
                                                  epochs=2, reason="test"))
        deadline = time.time() + 10.0
        while time.time() < deadline and not results:
            time.sleep(0.05)
        self.assertTrue(results, "a queued round must actually run")
        report = results[0]
        self.assertEqual(report["reason"], "test")
        self.assertEqual(report["epochs"], 2)
        self.assertIsNotNone(report["loss_last"])
        self.assertGreater(report["steps"], 0)
        self.assertEqual(self.trainer.rounds, 1)
        self.assertFalse(self.trainer.snapshot()["round_pending"])

    def test_rounds_are_coalesced(self):
        self.assertTrue(self.trainer.submit_round(["one two three"], epochs=1))
        self.assertFalse(self.trainer.submit_round(["one two three"], epochs=1),
                         "only one round should ever be queued at a time")
        self.trainer.configure(paused=True)     # so the first one waits
        self.trainer.stop()

    def test_round_stops_promptly_when_asked(self):
        self.trainer.duty = 0.1
        self.trainer.submit_round(["line " * 40] * 40, epochs=50)
        time.sleep(0.6)
        self.trainer.stop()
        time.sleep(0.4)
        self.assertFalse(self.trainer._thread.is_alive(),
                         "stop() must not wait for a 50-epoch round")


class BrainAutoTrainTests(unittest.TestCase):
    """A learning event must not train on the request thread."""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls._saved_env = {k: v for k, v in os.environ.items()
                          if k.startswith("MYGPT_")}
        for key in list(os.environ):
            if key.startswith("MYGPT_"):
                os.environ.pop(key)
        os.environ.update({
            "MYGPT_DATA": cls._td.name,
            "MYGPT_CHECKPOINTS": os.path.join(cls._td.name, "ckpts"),
            "MYGPT_MODELS_DIR": "",
            "MYGPT_LLAMACPP_MODELS": "",
            "MYGPT_CORTEX_ENABLED": "0",
            "MYGPT_OLLAMA_ENABLED": "0",
            "MYGPT_CORTEX_URL": "http://127.0.0.1:1",
            "MYGPT_OLLAMA_URL": "http://127.0.0.1:1",
            "MYGPT_BLOCKS": "1", "MYGPT_DIM": "32", "MYGPT_HEADS": "2",
        })
        seed = os.path.join(cls._td.name, "seed.json")
        with open(os.path.join(ROOT, "seed_corpus.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        with open(seed, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        from mygpt.brain import Brain, AUTO_TRAIN_EVERY
        cls.AUTO_TRAIN_EVERY = AUTO_TRAIN_EVERY
        cls.brain = Brain(cls._td.name, seed)
        # stop the boot work so tests start from a quiet trainer
        cls.brain.trainer.configure(paused=True)

    @classmethod
    def tearDownClass(cls):
        cls.brain.trainer.stop()
        cls._td.cleanup()
        for key in [k for k in os.environ if k.startswith("MYGPT_")]:
            os.environ.pop(key, None)
        os.environ.update(cls._saved_env)

    def test_teaching_returns_immediately_and_queues_a_round(self):
        brain = self.brain
        brain.trainer.configure(paused=False)
        brain.counters["events_since_train"] = 0
        before_rounds = brain.counters["train_rounds"]
        slowest = 0.0
        for i in range(self.AUTO_TRAIN_EVERY):
            t0 = time.perf_counter()
            result = brain.teach(f"auto bench question {i}",
                                 "auto bench answer with enough words in it.")
            slowest = max(slowest, time.perf_counter() - t0)
            self.assertTrue(result.get("ok"))
        # teaching used to block for a whole round (seconds). It must now be a
        # queue insert: the round is deferred, not dropped and not inline.
        self.assertLess(slowest, 0.5,
                        f"a learning event waited {slowest:.2f}s — the round "
                        f"is being run on the request thread again")
        snap = brain.trainer.snapshot()
        self.assertTrue(snap["round_pending"] or snap["rounds"] > 0,
                        "the round must be queued for the background trainer")
        self.assertEqual(brain.counters["train_rounds"], before_rounds,
                         "no round may complete inline during the teach call")

    def test_explicit_training_still_blocks_and_reports(self):
        brain = self.brain
        result = brain.train(epochs=1, reason="test explicit",
                             requirement="explicit")
        self.assertTrue(result.get("ok"))
        self.assertIn("loss", result)
        self.assertNotIn("deferred", result)

    def test_trainer_snapshot_reports_duty_and_waiting(self):
        snap = self.brain.trainer.snapshot()
        for key in ("duty_target", "duty_observed", "cpu_ms", "paused",
                    "waiting_for_requests", "rounds", "last_round"):
            self.assertIn(key, snap)


class TrainerApiTests(unittest.TestCase):
    """GET/POST /api/trainer, over the real app."""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls._saved_env = {k: v for k, v in os.environ.items()
                          if k.startswith("MYGPT_")}
        for key in list(os.environ):
            if key.startswith("MYGPT_"):
                os.environ.pop(key)
        os.environ.update({
            "MYGPT_DATA": cls._td.name,
            "MYGPT_CHECKPOINTS": os.path.join(cls._td.name, "ckpts"),
            "MYGPT_MODELS_DIR": "",
            "MYGPT_LLAMACPP_MODELS": "",
            "MYGPT_CORTEX_ENABLED": "0",
            "MYGPT_OLLAMA_ENABLED": "0",
            "MYGPT_CORTEX_URL": "http://127.0.0.1:1",
            "MYGPT_OLLAMA_URL": "http://127.0.0.1:1",
            "MYGPT_BLOCKS": "1", "MYGPT_DIM": "32", "MYGPT_HEADS": "2",
        })
        # Reload rather than import: another test module may have imported
        # ``app`` already, which would hand us that module's Brain — bound to a
        # temp dir its own tearDown has since deleted.
        import importlib
        import app as app_module
        try:
            app_module.brain.trainer.stop()
        except Exception:
            pass
        app_module = importlib.reload(app_module)
        cls.app_module = app_module
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app_module.brain.trainer.stop()
        except Exception:
            pass
        cls._td.cleanup()
        for key in [k for k in os.environ if k.startswith("MYGPT_")]:
            os.environ.pop(key, None)
        os.environ.update(cls._saved_env)

    def test_status_endpoint_reports_the_trainer(self):
        resp = self.client.get("/api/trainer")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("duty_target", body)
        self.assertIn("note", body)

    def test_requests_are_counted_and_released(self):
        trainer = self.app_module.brain.trainer
        self.client.get("/api/ping")
        self.assertEqual(trainer.snapshot()["inflight"], 0,
                         "every request must be released in after_request")

    def test_during_a_request_the_trainer_yields(self):
        trainer = self.app_module.brain.trainer
        trainer.request_started()
        try:
            self.assertTrue(trainer.should_yield())
        finally:
            trainer.request_finished()
        self.assertFalse(trainer.snapshot()["inflight"])

    def test_pause_and_resume_through_the_api(self):
        resp = self.client.post("/api/trainer", json={"paused": True})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["paused"])
        resp = self.client.post("/api/trainer", json={"paused": False})
        self.assertFalse(resp.get_json()["paused"])

    def test_duty_can_be_tuned_and_is_validated(self):
        resp = self.client.post("/api/trainer", json={"duty": 0.1})
        self.assertAlmostEqual(resp.get_json()["duty_target"], 0.1)
        resp = self.client.post("/api/trainer", json={"duty": "lots"})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post("/api/trainer", json={"duty": 0.35})

    def test_train_endpoint_is_still_explicit(self):
        resp = self.client.post("/api/train", json={"epochs": 1})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertNotIn("deferred", body)


if __name__ == "__main__":
    unittest.main()
