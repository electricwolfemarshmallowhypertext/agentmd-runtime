# AgentMD proof and verification scope

## Published baseline versus this branch

The public baseline is [v0.3.0-alpha.3](https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/releases/tag/v0.3.0-alpha.3), commit `6602fc4874c1824faa4d2fd23d3ec560fd39db21`. September 29, 2026 Windows CI logged 41 passing CLI tests, the indicator scanner and then-current dependency audits. The commit was verified; the annotated tag was unsigned. Historical proof artifacts are no longer available through the run artifact listing. Those facts do not assert a current passing security gate.

This October review branch is unreleased. Its acceptance checks require observable outcomes, not merely a green test count:

1. A real local command reads selected context files and verifies their manifest SHA256 values.
2. It executes syntax, repository scanner, CLI regressions and Git checks, records actual log/diff/status hashes, and emits a Lead Artifact from those results.
3. The compiler consumes that artifact; an independent reader checks artifact source hashes, canonical packet hash, receipt hash and predecessor links.
4. Repeated compiles with unchanged explicit inputs produce byte-identical JSON/Markdown, with no duplicate trust observations.
5. Invalid timestamps/workspaces, secret-shaped keys, bad destinations and ordinary write failures do not silently replace a valid output bundle.
6. A real failed command, launch failure, timeout and output-limit event are recorded truthfully and return nonzero.

## Reproduce local evidence

```bash
python -m pip install --only-binary=:all: --require-hashes -r requirements-ci.lock
python -m cli.agentmd doctor
python -m cli.agentmd run --task "verify this checkout" -- python scripts/verify_local.py
python -m cli.agentmd lead compile --artifact .agentmd/verification/run.lead-artifact.json
python -m cli.agentmd lead compile --artifact .agentmd/verification/run.lead-artifact.json
```

Real verification logs and report are in `.agentmd/verification/`; execution receipts are in `receipts/`; compiled packet and receipts are in `.sticky/`. They are local, ignored runtime evidence, not published proof. `scripts/demo-lead-compile.ps1` remains a canned input/format demonstration; printed repeated hashes from one execution are not independent repeated runs.

## What is not established

- The legacy API is not fully installed/booted/validated; its remaining dependency audit findings remain a release blocker. See `docs/security_hardening_todo.md`.
- Example provider artifacts do not establish live provider calls. The local runner is not a tool-specific integration or sandbox.
- A source's `verified` claim is still asserted, not authenticated. Receipts establish bytes and local process outcomes, not semantic truth.
- Skill validation receipts bind externally supplied scores and hashes. They do not execute or authenticate an evaluator or prove improvement.
- Multi-output replacement rolls back ordinary I/O errors, not process/power loss or concurrent writers. Use one writer per workspace.
- The specific earlier blocked skill-root symlink probe was not executed/retried; nested-root checks are defensive code changes, not a claim that that probe was verified.
- New Windows runtime/wrapper execution, production credentials, account governance and signed attestation are not covered by Linux local evidence.
