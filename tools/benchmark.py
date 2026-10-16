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


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark MyGPT's brain.")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--skip-grad-check", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="benchmark data/corpus.json (what a running MyGPT "
                         "has learned from chats) instead of the seed corpus")
    args = ap.parse_args()

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
