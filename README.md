# AgentMD Runtime

[![CI](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/ci.yml)
[![AgentMD Lead Demo](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/agentmd-lead-demo.yml/badge.svg?branch=main)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions/workflows/agentmd-lead-demo.yml)
[![Latest Release](https://img.shields.io/github/v/release/electricwolfemarshmallowhypertext/agentmd-runtime?display_name=tag)](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/releases)

**AgentMD compiles scattered AI/tool runs into one verified current-state packet.**

It compiles scattered AI/tool runs into one verified current-state packet, with schema validation, deterministic hashes, and proof receipts.

![AgentMD Flow](docs/assets/agentmd-flow.png)

## Proof

- Current public release: `v0.3.0-alpha.2`
- `v0.2.0`: AI Work Lead checkpoint
- `v0.3.0-alpha.2`: CI-verified alpha with gated skill edit primitive
- Published alpha CI status predates the September 2026 security audit
- Local security-hardening branch tests: `36 passed`
- Public `main` remediation and fresh CI proof are required before the next release
- Deterministic demo script: `scripts/demo-lead-compile.ps1`
- Lead Artifact schema validation is enforced (`schemas/lead-artifact.schema.json`)
- Lead receipts include chained hashes, source artifact hashes, replay resistance, and advisory `trust-weight.v1` metadata
- Source identity is asserted, not authenticated; AgentMD does not convert self-reported status into an authorization score
- Technical proof note: `docs/proof_note.md`

## Trust & adoption docs

- `docs/adoption_quickstart.md`
- `docs/compatibility_policy.md`
- `docs/cli_exit_codes.md`
- `docs/determinism.md`
- `docs/receipt_integrity.md`
- `docs/threat_model.md`
- `docs/identity_state.md`
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

`agentmd lead compile` turns scattered run artifacts into one verified operating picture with deterministic hashing and proof receipts.

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
- Strict validation dependency: `jsonschema`
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

## Durable Agent Identity

AgentMD can preserve a continuing agent identity separately from the current
state of work. Identity versions are immutable, hash-chained, and signed with
an external Ed25519 key that AgentMD never stores.

- Commands: `agentmd identity init|verify|history|apply|rollback|export|import`
- Schemas: `agent-identity.v1`, `identity-change.v1`, and `identity-envelope.v1`
- Storage: `.agentmd/identity/records/*.json`
- Rollback appends a new signed version; it never deletes history
- Export/import uses a signed envelope and requires explicit fingerprint trust
- Identity changes are schema-validated, secret-scanned, and atomically written

Identity answers "which continuing agent is this?" The AI Work Lead packet
continues to answer "what is currently true about the work?" The two states
remain separate. See `docs/identity_state.md` for the trust model and key
custody requirements.

## Core Commands

```powershell
.\agentmd.cmd doctor
.\agentmd.cmd resolve --task "review this repo for context drift"
.\agentmd.cmd receipt
.\agentmd.cmd run --adapter codex --task "review this repo for context drift"
.\agentmd.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
.\agentmd.cmd skill apply-edit --edit edits/validated-skill-edit.json
.\agentmd.cmd identity verify --trust-fingerprint "sha256:<trusted-fingerprint>"
.\agentmd.cmd identity history
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

CI installs from `requirements-ci.lock` with package hashes and runs dependency and repository security scans. Trust scoring is advisory metadata; it never grants execution permission.

## License

AgentMD Runtime is source-available under **BUSL-1.1**.

Commercial production use, hosted service use, resale, embedding into commercial products, or offering substantially similar functionality as a service requires a commercial license from the Licensor.

See `LICENSE`, `LICENSE.md`, and `NOTICE`.
