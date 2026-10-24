# AgentMD Runtime

[![CI](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/ci.yml)
[![AgentMD Lead Demo](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/agentmd-lead-demo.yml/badge.svg?branch=main)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/agentmd-lead-demo.yml)
[![Latest Release](https://img.shields.io/github/v/release/electricwolfemarshmallowhypertext/agentmd-runtime?display_name=tag)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/releases)

**AgentMD compiles AI/tool run evidence into a reproducible current-state packet.**

Schema validation, deterministic hashes and receipts establish local integrity—not the truth of imported claims or authenticated provider identity.

![AgentMD Flow](docs/assets/agentmd-flow.png)

## Proof

- Public release baseline: `v0.3.0-alpha.3`, commit `6602fc4874c1824faa4d2fd23d3ec560fd39db21` (September 29, 2026).
- Its historical Windows CI and demo passed with 41 targeted CLI tests; that is not a current dependency-safety guarantee.
- October fixes on this review branch are local/unreleased. See `docs/proof_note.md` for outcome-based verification and remaining blockers.
- The compiler, file hashes, receipts and bounded skill edits are real local operations.
- `run` now executes caller-specified argv locally; provider-specific integrations are not implemented or verified.
- Example provider-named artifacts are fixtures, not evidence of calls to Codex, Claude or Gemini.
- Source identity is asserted, not authenticated; `what_is_true` means source-reported verified claims, never an authorization score.
- The isolated memory engine now has real offline MiniLM/Chroma/SQLite validation; see `docs/embedding_validation.md`. This does not establish full legacy API/production readiness.

## Trust & adoption docs

- `docs/adoption_quickstart.md`
- `docs/compatibility_policy.md`
- `docs/cli_exit_codes.md`
- `docs/determinism.md`
- `docs/receipt_integrity.md`
- `docs/threat_model.md`
- `docs/embedding_validation.md`
- `SECURITY.md`

## Problem

AI work is fragmented across chats, CLIs, CI logs, scripts, and partial artifacts. Teams lose truth-state when outputs are stale, contradictory, or unverifiable.

AgentMD creates one reproducible trace:

```text
task
  -> validate context
  -> compile current-state packet
  -> enforce schema gates
  -> write proof receipts
  -> preserve audit trail
```

## AI Work Lead

`agentmd lead compile` turns scattered run artifacts into one evidence-labelled operating picture with deterministic hashing and proof receipts.

![Verified Current-State Packet](docs/assets/current-state-packet.png)

The compiled packet includes:

- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- next clean action

Runtime outputs:

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`

## Lead Artifact v1

Lead Artifact is the portable input contract for any tool (Codex, Claude, Gemini, ChatGPT, Cursor, CI jobs, scripts).

- Schema: `schemas/lead-artifact.schema.json`
- Required version field: `schema_version: "lead-artifact.v1"`
- Strict validation dependency: `jsonschema`; calendar/timezone validation is built in and does not rely on optional format extras
- RFC3339 offsets and arbitrary fractional seconds are ordered chronologically; leap-second timestamps are rejected explicitly
- Invalid artifacts fail compile with explicit schema errors
- Artifact paths stay inside the workspace and hostile inputs are size/depth bounded
- High-confidence credential patterns fail closed before outputs are written
- Imported text is treated as untrusted data and escaped in Markdown output

Use the portable emitter prompt and template:

- `prompts/emit-lead-artifact.md`
- `examples/lead-artifacts/template.lead-artifact.json`

## Skill Edit Gate

AgentMD includes a gated SkillOpt-style primitive for controlled skill evolution without runtime optimizer calls.

- Command: `agentmd skill apply-edit --edit <path>`
- Input schema: `schemas/skill-edit.schema.json` (`skill-edit.v1`)
- Bounded edit types only: `add`, `delete`, `replace`
- Skill edits are restricted to workspace-local `skills/*/SKILL.md` files
- Acceptance policy: `validation_score > baseline_score` plus a matching hash-verified `skill-validation.v1` receipt
- Validation schema: `schemas/skill-validation.schema.json`
- Accepted edits: `.sticky/skill-receipts/*.jsonl`
- Rejected edits: `.sticky/rejected-skill-edits/*.jsonl`

Scope intentionally not implemented yet:

- optimizer model that proposes edits
- multi-epoch benchmark loop
- autonomous self-editing runtime

## Core Commands

```powershell
.\agentmd.cmd doctor
.\agentmd.cmd resolve --task "review this repo for context drift"
.\agentmd.cmd receipt
.\agentmd.cmd run --task "verify this checkout" -- python scripts/verify_local.py
.\agentmd.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
.\agentmd.cmd skill apply-edit --edit edits/validated-skill-edit.json
```

## Quickstart

```bash
git clone https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime.git
cd agentmd-runtime
```

```powershell
python -m pip install -r requirements-cli.txt
python -m pytest -q tests/agentmd/test_agentmd_cli.py
.\scripts\demo-lead-compile.ps1
```

For real local evidence (not the canned parser demo):

```bash
python -m cli.agentmd run --task "verify this checkout" -- python scripts/verify_local.py
python -m cli.agentmd lead compile --artifact .agentmd/verification/run.lead-artifact.json
```

The verification command runs the CLI checks, records actual Git diff/status and log hashes, and verifies selected context bytes before emitting its artifact. A zero-input compile reports zero evidence, never an invented run. See `docs/local_execution.md` for process, privacy, failure and sandbox boundaries.

CI installs from `requirements-ci.lock` with package hashes and runs dependency and repository security scans. Trust scoring is advisory metadata; it never grants execution permission.

## License

AgentMD Runtime is source-available under **BUSL-1.1**.

Commercial production use, hosted service use, resale, embedding into commercial products, or offering substantially similar functionality as a service requires a commercial license from the Licensor.

See `LICENSE`, `LICENSE.md`, and `NOTICE`.
