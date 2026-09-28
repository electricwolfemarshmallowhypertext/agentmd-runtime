# AgentMD: compiling scattered AI runs into one verified current-state packet

## 1. Problem

AI-assisted work creates scattered artifacts across Codex, Claude, Gemini, chats, CI, and scripts.  
The failure mode is losing the actual current state of work.

## 2. Claim

AgentMD compiles scattered AI/tool run artifacts into one deterministic current-state packet.

## 3. Proof task

Task:

> Compile scattered Codex, Claude, and Gemini run artifacts into one verified current-state packet.

Baseline:

- human reads artifacts manually

AgentMD path:

- `agentmd lead compile` via the demo script

## 4. Demo inputs and reference outputs

Demo inputs:

- `examples/lead-artifacts/run-codex.jsonl`
- `examples/lead-artifacts/run-claude.json`
- `examples/lead-artifacts/run-gemini.jsonl`

Reference outputs:

- `examples/lead-output/current-state.example.md`
- `examples/lead-output/current-state.example.json`

## 5. Before → After

Before:

- scattered Codex/Claude/Gemini run artifacts

After:

- one compiled current-state packet
- one receipt trail

## 6. Exact demo command

```powershell
.\scripts\demo-lead-compile.ps1
```

## 7. Generated runtime outputs

The compile writes:

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`

## 8. Packet excerpt (from example output)

Excerpt source: `examples/lead-output/current-state.example.md`

```text
Task: compile ai work lead state
Deterministic Hash: a9ccb7bd56bcf357aaf852683387eb72bc8b7f2f78b374ac55ad8680114282c4
Artifacts Ingested: 3

## What Changed
- README.md
- apps/api/src/memory/server.py
- cli/agentmd.py

## What Is True
- Endpoint returns latest receipt
- README includes AI Work Lead section

## What Is Unverified
- All receipt tests passed in CI

## What Contradicts Prior State
- Receipt includes git dirty status

## What Needs Human Approval
- Approve endpoint release gate exception
- Hold release until endpoint smoke test exists

## Open Loops
- Add integration coverage for lead compile (open)
- Confirm rollback procedure with ops (open)

## Next Clean Action
- Resolve human-approval items before the next run.
```

## 9. What the packet contains

- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- open loops
- next clean action

## 10. Minimum benchmark (single reproducible proof)

| Metric | Result |
|---|---|
| Lead artifacts processed | 3 |
| Schema validation | PASS |
| Current-state packet generated | PASS |
| Deterministic hash repeat match | PASS |
| Receipts written | PASS |
| Trust metadata written | PASS |
| Contradictions preserved | PASS |
| Open loops preserved | PASS |
| Time to compile | measured locally; not benchmarked |
| Local security and CLI tests | 36 passed |
| Published alpha CI | historical proof; fresh post-audit run pending |

## 11. Schema proof

Lead Artifact v1 validates input artifacts.  
Invalid artifacts fail clearly.

Schema:

- `schemas/lead-artifact.schema.json`

## 12. CI and release proof

- Published alpha CI: historical proof from before the September 2026 security audit
- AgentMD Lead Demo: fresh post-audit run pending
- GitHub Actions: `https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions`
- Release: `v0.3.0-alpha.2`
- Release URL: `https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/releases/tag/v0.3.0-alpha.2`

Current verified facts:

- local security and CLI tests: `36 passed`
- workflows: fresh post-audit CI and AgentMD Lead Demo proof pending
- latest release: `v0.3.0-alpha.2`
- latest release commit: `6efc66d`

## 13. Skill gate proof

Accepted skill edit writes:

- `.sticky/skill-receipts/*.jsonl`

Rejected skill edit writes:

- `.sticky/rejected-skill-edits/*.jsonl`

Schema:

- `schemas/skill-edit.schema.json`

## 14. What this proves

- artifacts can be normalized
- schema validation works
- deterministic packet generation works
- proof receipts are written
- lead receipts preserve advisory source history without treating asserted identity as authenticated trust
- skill edits are gated by validation score and a hash-bound validation receipt

## 15. What this does not prove yet

- production SaaS readiness
- full adapter automation
- multi-user/team workflow
- autonomous optimizer loop
- cryptographic source identity and signed receipts
- independent security review of hostile-input controls

## 16. Boundaries

- Alpha release.
- Evaluation/research/internal testing use.
- Not production SaaS.
- Not an agent swarm.
- Not a hosted platform.
- Optimizer loop is not implemented yet.
