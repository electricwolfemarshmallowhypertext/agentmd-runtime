# Real local embedding/storage validation

This branch upgrades the **isolated memory engine**, not the entire legacy API or a model-provider integration. The tested path performs actual CPU inference, local Chroma storage and queryable SQLite fallback. No fabricated vectors, Firebase account operations or paid API calls are used.

## Exact model and runtime

- Public model: `sentence-transformers/all-MiniLM-L6-v2`.
- Immutable revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- `model.safetensors` SHA256: `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`.
- Ten approved safetensors/config/tokenizer/pooling files; no pickle weights or custom Python model code.
- Tested: Sentence Transformers 6.0.0, official Torch 2.14.1+cpu, Transformers 5.17.0, NumPy 1.26.4, Chroma 0.4.15 / hnswlib 0.7.3, PostHog 5.4.0, Pydantic 2.13.5 on Linux/Python 3.12.14.
- Engine loads with `trust_remote_code=False`, safetensors required, CPU device, and `local_files_only=True` by default. It does not silently fetch another hardcoded embedding model.

The complete tested dependency freeze, model-file manifest, downloads/checksums and offline command harness are in the repair evidence. Chroma's old native hnsw package required a local GCC build on Python 3.12; this is not a Windows or Python 3.11 execution claim. The API requirement `torch==2.14.1` permits the verified `+cpu` build; select the official CPU wheel explicitly rather than downloading an unnecessary CUDA closure for CPU validation.

## Exercise the actual engine

Provision an approved local model snapshot first; tests never download it. In the isolated model runtime:

```bash
AGENTMD_TEST_MODEL_PATH=/absolute/path/to/model \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m pytest -q tests/memory/test_memory_vectors.py
```

Tests are outside `apps/api/tests/conftest.py`, whose legacy Redis/Firebase fixtures can mutate real services. Do not interpret those misleadingly named fixtures as mocks or run them against real accounts without authorization. The ordinary CLI suite remains separate and does not install a large model runtime.

The observed checks cover scalar/batch 384-dimensional finite inference, repeat consistency and semantic ordering; real text/vector writes; thread/user/persona scope; transfers with distinct IDs; separate-process persistence reopen; actual missing-collection failure and compressed SQLite fallback/reopen; copy-to-fresh-location backup restore; unchanged original data on incompatible model/shape; and failed-copy backup cleanup. Synthetic security/error-injection tests remain deliberate synthetic tests, not claims of a live provider call.

## Storage contract and safe migration boundaries

The dimension comes from the loaded model, not a hardcoded 1024. Both schemas and storage require finite float32-representable vectors; the actual engine's model dimension is authoritative. Model/dimension labels alone are insufficient: stores also bind a SHA256 fingerprint of loaded weight tensors, tokenizer, transformer/pooling configuration and execution-library versions. A same-sized changed model cannot silently reuse a store.

A nonempty old store without that complete contract, or with a different contract, is rejected. This repair does **not** migrate production data. Back up a copy and plan explicit re-embedding into a new store before any production migration. A library/build change can intentionally invalidate the strict fingerprint.

- Chroma stores text documents and explicit vectors; SQLite fallback stores compressed text plus float32 vectors and remains queryable.
- Memory IDs include user/thread/persona/text; transfers cannot overwrite the source persona.
- Ordinary cleanup closes instance references, never resets or deletes persisted data.
- Quota checks reject new work rather than silently deleting old memories; the byte estimate is not a hard filesystem quota.
- Backups live outside the source tree, are staged and published only after completion, and include file-hash manifests. Retention does not count failed partial copies. A quiescent single writer is required; concurrent-writer/crash consistency is not guaranteed.
- A degraded Chroma operation is labelled via `storage_degraded`; local fallback is not a remote database or production availability guarantee.

## What remains unverified

Full legacy API boot and service wiring, live cloud/auth/provider integrations, existing production-store migration, native Windows behavior and model quality beyond the recorded local semantic checks. Source/hash integrity is not an authentication or broad model-safety proof.
