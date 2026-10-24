# PROJECT_STATUS

Status date: 2026-10-24. Local review branch; no new release is implied.

## Product and implemented behavior

AgentMD governs local context, normalizes tool-run artifacts and writes reproducible packets/receipts. The CLI performs real filesystem/schema/hash operations. `run` executes an explicit caller-provided local command with real terminal status and hash-only output receipts; it does not guess provider flags or pretend an adapter ran.

- Published baseline: `v0.3.0-alpha.3`, `6602fc4874c1824faa4d2fd23d3ec560fd39db21`.
- Historical September 29 Windows CI: 41 CLI tests plus scanner, dependency checks and demo. That historical result does not clear new advisories.
- October review branch corrects final packet hashing, RFC3339 validation/ordering, failed workspace gates, bundle preflight/rollback, secret-key diagnostics and terminal-loop recommendations.
- Additional defensive changes: nested workspace-root checks, receipt-chain continuity, zero-evidence honesty and real explicit-command execution.
- Local compiler outputs: `.sticky/current-state.json`, `.sticky/current-state.md`, `.sticky/receipts/*.jsonl`.
- Actual-checkout verification: `python -m cli.agentmd run --task "verify this checkout" -- python scripts/verify_local.py`, then compile `.agentmd/verification/run.lead-artifact.json`.

## What verification establishes

Acceptance is correct results on real local work, rejection without inconsistent outputs, source/packet/receipt hash agreement, and truthful process outcomes—not a test-count target. Parser/security regressions deliberately use synthetic inputs. Current commands and limitations are in `docs/proof_note.md` and `docs/local_execution.md`.

## Remaining blockers and non-goals

- Legacy API dependencies are not a supported production runtime: sentence-transformers requires a separately validated migration; the coupled OpenTelemetry/Firestore update passed offline dependency/client/serialization checks. Its direct audit gate remains failing, not bypassed.
- No real model-provider calls, provider credentials, hosted auth/account actions or cloud deployments were run.
- Skill edits verify supplied score/receipt/hash consistency, not the evaluator's truth or actual improvement; no optimizer/benchmark engine is implemented.
- Imported claims remain source assertions; hashes are not authentication or truth verification.
- No signature chain, external notarization, production-SaaS assurance or multi-user execution isolation.
- Windows wrapper execution and process behavior still need native-platform verification for these new changes.
- Account credential rotation/revocation and review/signature enforcement are not established by source cleanup.

No push, merge, tag or release is authorized by this local repair.
