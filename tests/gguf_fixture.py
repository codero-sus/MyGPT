"""Build a tiny but *valid* GGUF model, so llama.cpp can be tested for real.

Downloading a model is not possible in a sandbox (huggingface.co is blocked and
real GGUFs are gigabytes), so instead we synthesise one: the official ``gguf``
writer emits a Llama-architecture model with the real metadata keys llama.cpp
requires, and llama.cpp then loads and runs it like any other GGUF.

The weights are random, so the text it produces is gibberish — that is the
point. The tests here verify *plumbing and inference*, not model quality: the
file parses, the engine loads it, tokens go in, tokens come out, and MyGPT's
backend handles both success and failure. Dropping a real GGUF into ``models/``
exercises exactly the same code path.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np

# tiny but structurally complete
DIM = 32
FFN = 64
BLOCKS = 1
CTX = 512
HEADS = 4
_CACHE: str | None = None


def build_tiny_gguf(path: str | None = None) -> str:
    """Write a minimal Llama-architecture GGUF and return its path."""
    import gguf

    tokens = ["<unk>", "<s>", "</s>"] + [f"<0x{i:02X}>" for i in range(256)]
    types = ([gguf.TokenType.UNKNOWN, gguf.TokenType.CONTROL,
              gguf.TokenType.CONTROL] + [gguf.TokenType.BYTE] * 256)
    vocab = len(tokens)

    if path is None:
        handle, path = tempfile.mkstemp(suffix=".gguf", prefix="mygpt-tiny-")
        os.close(handle)

    rng = np.random.default_rng(0)
    writer = gguf.GGUFWriter(path, "llama")
    writer.add_name("mygpt-tiny-gguf-test")
    writer.add_block_count(BLOCKS)
    writer.add_context_length(CTX)
    writer.add_embedding_length(DIM)
    writer.add_feed_forward_length(FFN)
    writer.add_head_count(HEADS)
    writer.add_head_count_kv(HEADS)
    writer.add_layer_norm_rms_eps(1e-5)
    writer.add_rope_dimension_count(DIM // HEADS)
    writer.add_tokenizer_model("llama")
    writer.add_token_list(tokens)
    writer.add_token_scores([0.0] * vocab)
    writer.add_token_types(types)
    writer.add_bos_token_id(1)
    writer.add_eos_token_id(2)
    writer.add_unk_token_id(0)

    def tensor(name, array):
        writer.add_tensor(name, array.astype(np.float32),
                          raw_dtype=gguf.GGMLQuantizationType.F32)

    scale = 0.05
    tensor("token_embd.weight", rng.normal(0, scale, (vocab, DIM)))
    tensor("output_norm.weight", np.ones(DIM))
    tensor("output.weight", rng.normal(0, scale, (vocab, DIM)))
    for i in range(BLOCKS):
        tensor(f"blk.{i}.attn_norm.weight", np.ones(DIM))
        tensor(f"blk.{i}.attn_q.weight", rng.normal(0, scale, (DIM, DIM)))
        tensor(f"blk.{i}.attn_k.weight", rng.normal(0, scale, (DIM, DIM)))
        tensor(f"blk.{i}.attn_v.weight", rng.normal(0, scale, (DIM, DIM)))
        tensor(f"blk.{i}.attn_output.weight", rng.normal(0, scale, (DIM, DIM)))
        tensor(f"blk.{i}.ffn_norm.weight", np.ones(DIM))
        tensor(f"blk.{i}.ffn_gate.weight", rng.normal(0, scale, (FFN, DIM)))
        tensor(f"blk.{i}.ffn_up.weight", rng.normal(0, scale, (FFN, DIM)))
        tensor(f"blk.{i}.ffn_down.weight", rng.normal(0, scale, (DIM, FFN)))

    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    return path


def tiny_gguf() -> str:
    """A process-wide cached tiny GGUF (building it takes ~0.3 s)."""
    global _CACHE
    if _CACHE is None or not os.path.exists(_CACHE):
        _CACHE = build_tiny_gguf()
    return _CACHE
