# Skill Optimization (v0.3 Direction Stub)

Status: **PARTIALLY IMPLEMENTED**

## Purpose

AgentMD treats `skills/*/SKILL.md` files as external agent state.
v0.3 starts with a controlled skill-edit gate and keeps strict bounds to avoid uncontrolled self-evolving behavior.

## Core loop

```text
skill file
  -> run task/eval
  -> score output
  -> propose bounded add/delete/replace edit
  -> validate against held-out task
  -> accept only if score improves
  -> write skill receipt
```

## Design constraints

- Skill is external state, not model weight updates.
- Rollouts must be scored from explicit eval/task outcomes.
- Edit proposals are bounded to text operations only:
  - add
  - delete
  - replace
- Validation gate is mandatory before acceptance.
- Policy is accept-only-if-improved on held-out validation.
- Rejected edits are preserved in a rejected-edit buffer for traceability.
- Accepted edits generate a skill receipt with hashes, score delta, and validation summary.
- After a skill version is accepted, runtime execution should not require extra model calls for optimization during normal use.

## AgentMD alignment

This direction maps directly onto AgentMD primitives already in place:

- `skills/` for skill state
- validation/evals for scoring and gates
- deterministic hashes for state integrity
- receipts for audit trace

## Implemented now

- `agentmd skill apply-edit --edit <path>` command.
- Schema-validated edit payloads via `schemas/skill-edit.schema.json`.
- Bounded edit operations only:
  - add
  - delete
  - replace
- Validation gate: accept only when `validation_score > baseline_score` and a hash-verified `skill-validation.v1` receipt binds the evaluator result to the old and proposed skill hashes.
- Skill paths are restricted to workspace-local `skills/*/SKILL.md` files; absolute paths, traversal, and symlink escapes fail closed.
- Accepted writes are atomic and verify that the source skill did not change during validation.
- Accepted edit path:
  - updates skill file
  - writes `.sticky/skill-receipts/*.jsonl`
- Rejected edit path:
  - does not update skill file
  - writes `.sticky/rejected-skill-edits/*.jsonl`
- Safe failure on missing or ambiguous target.
- Validation receipt schema: `schemas/skill-validation.schema.json`.

## Not implemented yet

- Optimizer model that proposes edits automatically.
- Multi-epoch optimization loop over benchmark tasks.
- Benchmark harness and broad evaluation suite.
- Autonomous self-editing loop without explicit edit payloads.
- Cryptographically authenticated evaluator identity. Current validation receipts provide integrity and binding, not asymmetric proof of origin.
