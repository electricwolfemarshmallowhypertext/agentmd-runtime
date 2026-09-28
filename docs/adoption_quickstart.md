# Adoption Quickstart (15 minutes)

This quickstart shows the minimum GitHub Actions integration for AgentMD current-state compilation.

## Prerequisites

- Repository contains AgentMD files and CLI entrypoint.
- Python 3.11 runner.
- `requirements-cli.txt` available in repo root.

## 1. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements-cli.txt
python -m pip install pytest pyyaml
```

## 2. Run compile from CI

Use Lead Artifact inputs and compile a current-state packet:

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
  uses: actions/upload-artifact@v4
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
