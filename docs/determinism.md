# Determinism

This document defines what AgentMD deterministic outputs mean today.

## What is deterministic

For `agentmd lead compile` with unchanged inputs:

- selected artifact normalization and ordering
- `context_bundle_hash` material from selected context path/hash pairs
- current-state packet structure/content
- `deterministic_hash` for the compiled packet

Deterministic behavior is validated by repeated compile runs using the same inputs.

## What is not deterministic

- receipt filenames (timestamp-based)
- receipt `timestamp` values
- receipt hashes (because receipt content includes timestamp)
- filesystem metadata/order outside runtime-controlled sorting

## Inputs that affect hashes

`deterministic_hash` and related packet content can change when any of these change:

- artifact file content
- artifact set (added/removed input files)
- normalized artifact fields (claims, decisions, open loops, contradictions, scores)
- selected context file paths/hashes
- workspace validation outcomes included in packet validation block
- git state inputs included in packet proof block when applicable

## Reproducing the demo

Use repository demo artifacts:

- `examples/lead-artifacts/run-codex.jsonl`
- `examples/lead-artifacts/run-claude.json`
- `examples/lead-artifacts/run-gemini.jsonl`

Run:

```powershell
.\scripts\demo-lead-compile.ps1
```

Expected:

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`
- printed `deterministic_hash`

To check deterministic repeat match, run the demo script twice without changing inputs and compare the printed deterministic hash values.
