# Adoption Quickstart (15 minutes)

This quickstart shows the minimum GitHub Actions integration for AgentMD current-state compilation.

## Prerequisites

- Repository contains AgentMD files and CLI entrypoint.
- Python 3.11 runner.
- `requirements-cli.txt` available in repo root.

## 1. Install dependencies

```powershell
python -m pip install --only-binary=:all: --require-hashes -r requirements-ci.lock
```

## 2. Run compile from CI

For evidence from the actual checkout, run local verification and compile its generated artifact:

```powershell
python -m cli.agentmd run --task "verify this checkout" -- python scripts/verify_local.py
python -m cli.agentmd lead compile --artifact .agentmd/verification/run.lead-artifact.json
```

For a **canned input/format demo only** (not live model-provider proof):

```powershell
.\agentmd.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

Or run the deterministic demo wrapper:

```powershell
.\scripts\demo-lead-compile.ps1
```

## 3. Upload proof artifacts

Upload generated outputs as workflow artifacts:

```yaml
- name: Upload AgentMD proof artifacts
  uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1; same pin as repository workflow
  with:
    name: agentmd-proof
    if-no-files-found: error
    include-hidden-files: true
    path: |
      .sticky/current-state.json
      .sticky/current-state.md
      .sticky/receipts/*.jsonl
```

## Expected outputs

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`
- deterministic hash in command output

## Failure handling

- Non-zero exit from `agentmd lead compile` should fail the CI step.
- Missing/invalid artifact schema fails compile with explicit `lead_artifact_schema_*` messages.
- Missing required files fail with explicit `*_missing` messages.
- Keep `if-no-files-found: error` in artifact upload so silent output loss fails fast.
- On failure, capture step logs and uploaded artifacts from the last successful run for comparison.

The legacy API has only scoped local model/storage and client validation; see `embedding_validation.md` and `security_hardening_todo.md`. A passing compiler run is not a production release gate or authenticated truth proof.
