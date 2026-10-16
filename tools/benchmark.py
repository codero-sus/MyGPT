#!/usr/bin/env python3
"""Measure MyGPT's own brain, honestly.

Run it yourself:

    .venv/bin/python tools/benchmark.py            # table
    .venv/bin/python tools/benchmark.py --json     # machine-readable

What it reports, and why each number is trustworthy:

* **Training time** — wall clock around ``NeuralLM.train`` on the real seed
  corpus, same epochs and batch size for both architectures, first run only
  (no warm caches being timed).
* **Loss first -> last** — the model's own reported loss, and
  **perplexity** on the same held-out slice for both architectures, so the two
  are compared on one scale (perplexity = exp(mean NLL)).
* **Held-out perplexity** — the last 10% of windows are never trained on; both
  models are scored on exactly those windows. A model that overfits scores
  well on train and badly here.
* **Gradient check** — central-difference check of every parameter tensor
  (float64, dropout off). This is the one that says the hand-written backward
  pass is actually correct, not just that the loss goes down.
* **Generation speed** — tokens/second sampled from the trained brain, plus
  llama.cpp throughput on a real GGUF when one is available.

Every number printed here comes from a measurement in this process. Nothing is
estimated, rounded up, or copied from a datasheet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np                                        # noqa: E402

from mygpt.langmodel import SPECIALS, NeuralLM            # noqa: E402
from mygpt.transformer import TransformerLM               # noqa: E402


def _corpus(live: bool = False) -> list[str]:
    """The lines the brain's language model actually trains on.

    At first boot that is exactly ``seed_corpus.json["texts"]`` — the 481 seeded
    Q→A *pairs* only go into memory retrieval, they never enter the LM corpus.
    With ``live=True`` we read ``data/corpus.json`` instead, i.e. the corpus a
    running MyGPT has accumulated from chats and teaching.
    """
    import json as _json
    if live:
        path = os.path.join(ROOT, "data", "corpus.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                lines = _json.load(fh)
            if lines:
                return [t for t in lines if isinstance(t, str) and t.strip()]
    with open(os.path.join(ROOT, "seed_corpus.json"), encoding="utf-8") as fh:
        data = _json.load(fh)
    return [t for t in data.get("texts", [])
            if isinstance(t, str) and t.strip()]


def _split(texts: list[str], holdout: float = 0.1):
    """Train/held-out split of the corpus's texts (deterministic)."""
    cut = max(1, int(len(texts) * (1.0 - holdout)))
    return texts[:cut], texts[cut:]


def _train(model, texts, epochs: int, batch: int):
    start = time.perf_counter()
    stats = model.train(texts, epochs=epochs, batch_size=batch)
    return time.perf_counter() - start, stats


def _generation_tokens_per_second(model, tokens: int = 40) -> float:
    model.generate(2, temperature=0.9)          # warm up any lazy path
    start = time.perf_counter()
    model.generate(tokens, temperature=0.9)
    elapsed = time.perf_counter() - start
    return tokens / elapsed if elapsed > 0 else float("nan")


def _perplexity(model, texts) -> float | None:
    try:
        value = model.perplexity(texts)
    except Exception:                                       # pragma: no cover
        return None
    return float(value) if value and np.isfinite(value) else None


def _window_perplexity(model, texts, shuffle_targets: bool = False,
                       seed: int = 17) -> float | None:
    """Perplexity over a text's windows, optionally with scrambled targets.

    The scrambled variant is the control: if a model is genuinely predicting
    (rather than the number being small for some arithmetic reason), scrambling
    the answer should push perplexity up towards the vocabulary size.
    """
    windows = list(model._windows(texts))
    if not windows:
        return None
    rng = np.random.default_rng(seed)
    targets = [int(w[1]) for w in windows]
    if shuffle_targets:
        targets = list(rng.permutation(targets))
    total = 0.0
    for (context, _), target in zip(windows, targets):
        logits, _ = model._forward(np.asarray(context)[None, :])
        row = logits[0]
        probs = np.exp(row - row.max())
        probs /= probs.sum()
        total += -np.log(float(probs[target]) + 1e-12)
    return float(np.exp(total / len(windows)))


def benchmark_architectures(epochs: int, batch: int, live: bool = False) -> dict:
    texts = _corpus(live=live)
    train_texts, held_out = _split(texts)
    out: dict = {
        "corpus": {"texts": len(texts), "train_texts": len(train_texts),
                   "held_out_texts": len(held_out)},
        "config": {"epochs": epochs, "batch_size": batch},
        "models": {},
    }
    # Same width and the *same context length*, so the comparison is about the
    # architecture (attention vs mean-pooled bag of words), not about one model
    # simply being shown more history.
    specs = [("transformer", TransformerLM,
              dict(dim=48, heads=4, blocks=2, ctx=6)),
             ("mlp", NeuralLM, dict(dim=48, hidden=128, ctx=6))]
    for name, cls, kwargs in specs:
        model = cls(**kwargs)
        for text in train_texts:                  # vocabulary comes from the data
            model.observe(text)
        model.rebuild_vocab()
        assert model.vocab_size > len(SPECIALS) + 1, (
            "vocabulary is empty — the corpus was never observed, so every "
            "token would be <unk> and every number below would be nonsense")
        if not hasattr(model, "param_count"):     # the MLP predates it
            model.param_count = lambda m=model: int(
                sum(a.size for a in (m.E, m.W1, m.b1, m.W_out, m.b_out)
                    if a is not None))
        windows = len(list(model._windows(train_texts)))
        if windows == 0:
            continue
        seconds, stats = _train(model, train_texts, epochs, batch)
        out["models"][name] = {
            "params": int(model.param_count()),
            "vocab": int(model.vocab_size),
            "windows": windows,
            "train_seconds": round(seconds, 3),
            "ms_per_epoch": round(1000.0 * seconds / max(1, epochs), 1),
            "loss_first": (round(stats["loss_first"], 4)
                           if stats.get("loss_first") is not None else None),
            "loss_last": (round(stats["loss_last"], 4)
                          if stats.get("loss_last") is not None else None),
            "perplexity_train": _window_perplexity(model, train_texts),
            "perplexity_held_out": _window_perplexity(model, held_out),
            "perplexity_held_out_control": _window_perplexity(
                model, held_out, shuffle_targets=True),
            "perplexity_uniform_baseline": int(model.vocab_size),
            "generation_tokens_per_sec": round(
                _generation_tokens_per_second(model), 1),
        }
    return out


def grad_check(samples: int = 25, eps: float = 1e-4) -> dict:
    """Central-difference check of the transformer's backward pass.

    Uses the *shipped* brain configuration (MYGPT_DIM/BLOCKS/HEADS defaults)
    in float64 with dropout off — at float32 a 1e-4 central difference is pure
    round-off and the check would be meaningless. Every tensor gets checked;
    tensors with more than ``samples`` entries are sampled, uniformly over the
    flat index space, and the worst relative error is reported with the tensor
    it came from.
    """
    from mygpt.brain import Brain                        # noqa: F401 (defaults)

    kwargs = dict(ffn_mult=4, dropout=0.0, dtype=np.float64)
    for env, key, default in (("MYGPT_DIM", "dim", 64),
                              ("MYGPT_BLOCKS", "blocks", 2),
                              ("MYGPT_HEADS", "heads", 4),
                              ("MYGPT_CTX", "ctx", 6)):
        kwargs[key] = int(os.environ.get(env, default))
    model = TransformerLM(**kwargs)
    for text in _corpus():                        # the shipped vocabulary, not a toy one
        model.observe(text)
    model.rebuild_vocab()

    rng = np.random.default_rng(3)
    B = 2
    ctx = rng.integers(0, model.vocab_size, (B, model.ctx)).astype(np.int64)
    tgt = rng.integers(0, model.vocab_size, B).astype(np.int64)

    logits, caches = model._forward(ctx)
    probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs /= probs.sum(axis=-1, keepdims=True)
    rows = np.arange(B)
    dlogits = probs.copy()
    dlogits[rows, tgt] -= 1.0
    dlogits /= B
    analytic = model._backward(dlogits, caches)

    def loss() -> float:
        lg, _ = model._forward(ctx)
        pr = np.exp(lg - lg.max(axis=-1, keepdims=True))
        pr /= pr.sum(axis=-1, keepdims=True)
        return float(-np.log(pr[rows, tgt] + 1e-12).mean())

    worst, worst_name, checked, coordinates = 0.0, "", 0, 0
    for name, param in model.params.items():
        flat = param.reshape(-1)
        n = flat.size
        picks = (range(n) if n <= samples
                 else rng.choice(n, samples, replace=False))
        for i in picks:
            i = int(i)
            old = float(flat[i])
            flat[i] = old + eps
            up = loss()
            flat[i] = old - eps
            down = loss()
            flat[i] = old
            numeric = (up - down) / (2 * eps)
            got = float(analytic[name].reshape(-1)[i])
            err = abs(numeric - got) / max(1e-6, abs(numeric) + abs(got))
            coordinates += 1
            if err > worst:
                worst, worst_name = err, name
        checked += 1
    return {"worst_relative_error": worst, "worst_tensor": worst_name,
            "parameter_tensors": checked, "coordinates_checked": coordinates,
            "eps": eps, "dtype": "float64",
            "config": {k: kwargs[k] for k in ("dim", "blocks", "heads", "ctx")}}


def benchmark_llamacpp() -> dict | None:
    """Real llama.cpp throughput, if a GGUF and the package are available."""
    try:
        from mygpt.llamacpp_backend import LlamaCppClient
    except Exception:
        return None
    client = LlamaCppClient()
    if not client.available():
        return None
    start = time.perf_counter()
    try:
        client.load()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    load_seconds = time.perf_counter() - start
    prompt = "hello"
    t0 = time.perf_counter()
    text = client.generate(prompt, max_tokens=48)
    generation_seconds = time.perf_counter() - t0
    n_ctx = client.effective_n_ctx
    return {
        "model": os.path.basename(client.loaded_model or ""),
        "model_size_bytes": os.path.getsize(client.loaded_model or "") or None,
        "requested_n_ctx": client.n_ctx,
        "trained_context": client.model_context_length(client.loaded_model),
        "effective_n_ctx": n_ctx,
        "load_seconds": round(load_seconds, 3),
        "generation_seconds": round(generation_seconds, 3),
        "generation_tokens_per_sec": (round(48 / generation_seconds, 1)
                                      if generation_seconds else None),
        "produced_text": bool(text),
    }


def _isolated_app(tmp: str):
    """The real Flask app, booted against a temp data dir, engines off.

    Driving the HTTP path (rather than calling ``brain.reply`` directly) is the
    point: the request hooks that tell the trainer to stand down are part of the
    app, so a benchmark that bypasses them would be measuring the wrong thing.
    """
    import importlib
    import shutil
    for key, value in (("MYGPT_CHECKPOINTS", os.path.join(tmp, "ckpts")),
                       ("MYGPT_DATA", tmp),
                       ("MYGPT_MODELS_DIR", ""),
                       ("MYGPT_LLAMACPP_MODELS", ""),
                       ("MYGPT_CORTEX_ENABLED", "0"),
                       ("MYGPT_OLLAMA_ENABLED", "0"),
                       ("MYGPT_CORTEX_URL", "http://127.0.0.1:1"),
                       ("MYGPT_OLLAMA_URL", "http://127.0.0.1:1")):
        os.environ[key] = value
    if not os.path.exists(os.path.join(tmp, "seed.json")):
        shutil.copyfile(os.path.join(ROOT, "seed_corpus.json"),
                        os.path.join(tmp, "seed.json"))
    import app as app_module
    app_module = importlib.reload(app_module)           # fresh Brain per run
    return app_module


def _stop_trainer(module) -> None:
    try:
        module.brain.trainer.stop()
    except Exception:
        pass


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _workload(client, brain, turns: int = 24, gap: float = 0.15) -> dict:
    """A realistic session over HTTP: chat every turn, teach every third turn.

    Teaching is what marks a learning event (``_ingest`` → ``_maybe_auto_train``);
    a plain chat turn does not, so a workload of only chats would never reach the
    auto-training path this benchmark is about.
    """
    chat_ms, teach_ms = [], []
    started = time.perf_counter()
    for i in range(turns):
        t0 = time.perf_counter()
        client.post("/api/chat", json={
            "message": ("what is the time complexity of a hash map lookup"
                        if i % 2 else "hello, how are you?")})
        chat_ms.append((time.perf_counter() - t0) * 1000)
        if i % 3 == 0:
            t0 = time.perf_counter()
            client.post("/api/teach", json={
                "question": f"bench question {i}",
                "answer": (f"bench answer {i} - a fixed sentence used to "
                           f"measure how long a learning event takes.")})
            teach_ms.append((time.perf_counter() - t0) * 1000)
        time.sleep(gap)
    return {"wall_seconds": round(time.perf_counter() - started, 2),
            "chat_ms": chat_ms, "teach_ms": teach_ms,
            "rounds": brain.counters.get("train_rounds", 0),
            "trainer_rounds": brain.trainer.rounds,
            "learned_pairs": len(brain.memory.pairs)}


def _chat_under_load(client, brain, queued: int = 400,
                     turns: int = 8) -> dict:
    """Chat latency while the trainer has a large queue to get through."""
    for i in range(queued):
        brain.trainer.submit(f"load line {i} pushed into the trainer queue",
                             steps=1)
    latencies = []
    for i in range(turns):
        t0 = time.perf_counter()
        resp = client.post("/api/chat", json={"message": f"load test turn {i}"})
        latencies.append((time.perf_counter() - t0) * 1000)
        assert resp.status_code == 200, resp.status_code
        time.sleep(0.1)
    return {"chat_p50_ms": round(_percentile(latencies, 50), 1),
            "chat_p95_ms": round(_percentile(latencies, 95), 1),
            "chat_max_ms": round(max(latencies), 1),
            "queue_remaining": brain.trainer.jobs.qsize()}


def _wait_for_round(brain, timeout: float = 25.0) -> dict:
    """Let a queued round finish while nothing else is happening.

    This is the honest counterweight to the stall measurement: the round is not
    skipped, it is *deferred* to the next quiet moment. Without this, the
    "after" scenario would look faster simply because we stopped counting.
    """
    if not brain.trainer.snapshot().get("round_pending") and brain.trainer.rounds == 0:
        return {"queued": False, "completed": False}
    start_rounds = brain.trainer.rounds
    cpu_before = brain.trainer.cpu_now()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if brain.trainer.rounds > start_rounds:
            return {"queued": True, "completed": True,
                    "seconds": round(time.perf_counter() - t0, 2),
                    "cpu_seconds": round(max(0.0, brain.trainer.cpu_now()
                                             - cpu_before), 3),
                    "loss_last": brain.trainer.last_loss}
        time.sleep(0.1)
    return {"queued": True, "completed": False,
            "seconds": round(time.perf_counter() - t0, 2),
            "cpu_seconds": round(max(0.0, brain.trainer.cpu_now()
                                     - cpu_before), 3)}


def _idle_duty(brain, queued: int, seconds: float) -> dict:
    """Queue work, sit idle, and watch the trainer thread's own CPU clock."""
    for i in range(queued):
        brain.trainer.submit(f"duty line {i} for the background trainer",
                             steps=1)
    cpu_before = brain.trainer.cpu_now()
    wall = time.perf_counter()
    time.sleep(seconds)
    elapsed = time.perf_counter() - wall
    cpu = max(0.0, brain.trainer.cpu_now() - cpu_before)
    return {"seconds": round(elapsed, 2), "cpu_seconds": round(cpu, 3),
            "duty_observed": round(cpu / elapsed, 3) if elapsed else None,
            "duty_target": brain.trainer.duty,
            "queue_left": brain.trainer.jobs.qsize(),
            "steps_left_running": brain.trainer.busy}


def benchmark_trainer_impact(turns: int = 24, duty_window: float = 6.0) -> dict:
    """Measure what background self-training costs a session, old vs new.

    ``before_inline_rounds`` reproduces the pre-v1.11 code path exactly: the
    auto-training trigger runs its round inline, on the request thread, with the
    model locked for the whole round. ``after_queued_rounds`` is the shipped
    path, which hands the round to the trainer. Both use today's constants and
    the same workload over the same HTTP endpoints, so the only difference is
    where the round runs.
    """
    import shutil
    import tempfile

    from mygpt.brain import AUTO_TRAIN_EPOCHS, AUTO_TRAIN_EVERY

    out: dict = {"workload": {"turns": turns,
                              "chat_every_turn": True,
                              "teach_every": 3},
                 "auto_train_every": AUTO_TRAIN_EVERY,
                 "auto_train_epochs": AUTO_TRAIN_EPOCHS}
    module = None
    for label, legacy in (("before_inline_rounds", True),
                          ("after_queued_rounds", False)):
        if module is not None:                       # stop the previous brain
            _stop_trainer(module)
        tmp = tempfile.mkdtemp(prefix=f"mygpt-bench-{label}-")
        boot = time.perf_counter()
        module = _isolated_app(tmp)
        brain = module.brain
        client = module.app.test_client()
        boot_seconds = time.perf_counter() - boot
        if legacy:
            def _legacy_auto(b=brain):
                b.counters["events_since_train"] += 1
                if b.counters["events_since_train"] >= AUTO_TRAIN_EVERY:
                    b.train(epochs=AUTO_TRAIN_EPOCHS, reason="auto training",
                            requirement="explicit")     # the old inline path
            brain._maybe_auto_train = _legacy_auto
        try:
            run = _workload(client, brain, turns=turns)
            deferred = _wait_for_round(brain)
            load = _chat_under_load(client, brain)
            idle = _idle_duty(brain, 400, duty_window)
            brain.trainer.configure(paused=True)
            paused = _idle_duty(brain, 60, 2.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        out[label] = {
            "boot_seconds": round(boot_seconds, 2),
            "wall_seconds": run["wall_seconds"],
            "chat_p50_ms": round(_percentile(run["chat_ms"], 50), 1),
            "chat_p95_ms": round(_percentile(run["chat_ms"], 95), 1),
            "chat_max_ms": round(max(run["chat_ms"]), 1),
            "teach_p50_ms": round(_percentile(run["teach_ms"], 50), 1),
            "teach_max_ms": round(max(run["teach_ms"]), 1),
            "rounds": run["rounds"],
            "trainer_rounds": run["trainer_rounds"],
            "deferred_round": deferred,
            "chat_under_load_p95_ms": load["chat_p95_ms"],
            "chat_under_load_max_ms": load["chat_max_ms"],
            "chat_under_load_queue_left": load["queue_remaining"],
            "idle_duty": idle["duty_observed"],
            "idle_cpu_seconds": idle["cpu_seconds"],
            "idle_duty_target": idle["duty_target"],
            "paused_duty": paused["duty_observed"],
            "paused_cpu_seconds": paused["cpu_seconds"],
        }
    before = out["before_inline_rounds"]
    after = out["after_queued_rounds"]
    out["verdict"] = {
        "chat_max_before_ms": before["chat_max_ms"],
        "chat_max_after_ms": after["chat_max_ms"],
        "chat_max_ratio": (round(before["chat_max_ms"] / after["chat_max_ms"], 1)
                           if after["chat_max_ms"] else None),
        "teach_max_before_ms": before["teach_max_ms"],
        "teach_max_after_ms": after["teach_max_ms"],
        "rounds_before": before["rounds"], "rounds_after": after["rounds"],
        "rounds_queued_instead": after["trainer_rounds"],
        "deferred_round_completed": bool(
            after["deferred_round"].get("completed")),
        "deferred_round_seconds": after["deferred_round"].get("seconds"),
        "deferred_round_cpu_seconds": after["deferred_round"].get("cpu_seconds"),
    }
    return out


def _print_trainer_impact(impact: dict) -> None:
    before = impact["before_inline_rounds"]
    after = impact["after_queued_rounds"]
    print("Background self-training: what it costs a session")
    print(f"  workload: {impact['workload']['turns']} turns over /api/chat and "
          f"/api/teach (a teaching event every third turn)")
    print(f"  auto-training: every {impact['auto_train_every']} learning events, "
          f"{impact['auto_train_epochs']} epochs")
    print()
    head = (f"{'':24} {'chat p50':>9} {'chat p95':>9} {'chat max':>9} "
            f"{'teach max':>10} {'session':>8} {'rounds':>7}")
    print(head)
    print("-" * len(head))
    for label, name in ((before, "before (inline round)"),
                        (after, "after (queued round)")):
        print(f"{name:24} {label['chat_p50_ms']:>7.0f}ms "
              f"{label['chat_p95_ms']:>7.0f}ms {label['chat_max_ms']:>7.0f}ms "
              f"{label['teach_max_ms']:>8.0f}ms "
              f"{label['wall_seconds']:>6.1f}s {label['rounds']:>7}")
    verdict = impact["verdict"]
    print()
    print(f"  worst case before: {verdict['chat_max_before_ms']:.0f}ms chat, "
          f"{verdict['teach_max_before_ms']:.0f}ms teach (round ran on the "
          f"request thread)")
    print(f"  worst case after:  {verdict['chat_max_after_ms']:.0f}ms chat, "
          f"{verdict['teach_max_after_ms']:.0f}ms teach "
          f"({verdict['rounds_before']} rounds ran inline before; after, "
          f"{verdict['rounds_queued_instead']} ran on a request thread)")
    if verdict.get("deferred_round_completed"):
        print(f"  the deferred round did run: finished "
              f"{verdict['deferred_round_seconds']}s of wall time after the "
              f"session ended, {verdict['deferred_round_cpu_seconds']}s of CPU "
              f"— deferred, never dropped")
    print()
    print("  chat while the trainer has 400 lines queued:")
    for label, name in ((before, "before"), (after, "after")):
        print(f"    {name:6} p95 {label['chat_under_load_p95_ms']}ms, "
              f"max {label['chat_under_load_max_ms']}ms")
    print()
    print("Cost while you are not using the app (trainer thread's own CPU clock):")
    for label, name in ((before, "before"), (after, "after")):
        print(f"  {name:6} duty {label['idle_duty']} of one core "
              f"({label['idle_cpu_seconds']}s CPU, target "
              f"{label['idle_duty_target']}) · paused "
              f"{label['paused_duty']}")
    print("  duty = trainer CPU seconds / wall seconds, measured on that thread, "
          "so 0.35 means at most about a third of one core, and only while there "
          "is something queued")


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark MyGPT's brain.")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--skip-grad-check", action="store_true")
    ap.add_argument("--trainer-impact", action="store_true",
                    help="measure what background self-training costs a chat "
                         "session, before vs after v1.11.0")
    ap.add_argument("--live", action="store_true",
                    help="benchmark data/corpus.json (what a running MyGPT "
                         "has learned from chats) instead of the seed corpus")
    args = ap.parse_args()

    if args.trainer_impact:
        impact = benchmark_trainer_impact()
        if args.json:
            print(json.dumps(impact, indent=2))
            return 0
        _print_trainer_impact(impact)
        return 0

    result = benchmark_architectures(args.epochs, args.batch,
                                     live=args.live)
    if not args.skip_grad_check:
        result["gradient_check"] = grad_check()
    llama = benchmark_llamacpp()
    if llama:
        result["llamacpp"] = llama

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    corpus = result["corpus"]
    print(f"MyGPT brain benchmark — {corpus['texts']} texts "
          f"({corpus['train_texts']} train / {corpus['held_out_texts']} held "
          f"out), epochs={args.epochs}, batch={args.batch}")
    print()
    head = f"{'model':12} {'params':>8} {'windows':>8} {'train s':>8} " \
           f"{'loss':>13} {'ppl train':>10} {'ppl held':>9} {'tok/s':>7} " \
           f"{'ppl scrambled':>13}"
    print(head)
    print("-" * len(head))
    for name, m in result["models"].items():
        ppl_t = f"{m['perplexity_train']:.1f}" if m['perplexity_train'] else "n/a"
        ppl_h = (f"{m['perplexity_held_out']:.1f}"
                 if m["perplexity_held_out"] else "n/a")
        loss = f"{m['loss_first']} -> {m['loss_last']}"
        ctrl = m.get("perplexity_held_out_control")
        ctrl_s = f"{ctrl:.1f}" if ctrl else "n/a"
        print(f"{name:12} {m['params']:>8,} {m['windows']:>8} "
              f"{m['train_seconds']:>8.2f} {loss:>13} {ppl_t:>10} {ppl_h:>9} "
              f"{m['generation_tokens_per_sec']:>7.1f} {ctrl_s:>11}")
    vocab = next(iter(result["models"].values()), {}).get(
        "perplexity_uniform_baseline")
    if vocab:
        print()
        print(f"scale: a model that knew nothing would score perplexity = "
              f"vocabulary size = {vocab} on these windows. The scrambled-"
              f"target control sits at or above that: a model that has learned "
              f"something is confidently wrong when the answers are shuffled, "
              f"which costs more than staying flat.")
    gc = result.get("gradient_check")
    if gc:
        print()
        print(f"gradient check: worst relative error "
              f"{gc['worst_relative_error']:.2e} over "
              f"{gc['parameter_tensors']} tensors (eps={gc['eps']}, "
              f"{gc['dtype']}) -> {'PASS' if gc['worst_relative_error'] < 1e-3 else 'FAIL'}")
    if llama := result.get("llamacpp"):
        print(f"llama.cpp: {llama.get('model')} "
              f"({llama.get('model_size_bytes')} bytes) — load "
              f"{llama.get('load_seconds')}s, "
              f"{llama.get('generation_tokens_per_sec')} tok/s, n_ctx "
              f"{llama.get('effective_n_ctx')} "
              f"(requested {llama.get('requested_n_ctx')}, trained window "
              f"{llama.get('trained_context')})")
        print("note: decode speed scales with the model — this measures the "
              "tiny test GGUF shipped by tests/gguf_fixture.py, not a real "
              "multi-billion-parameter checkpoint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
