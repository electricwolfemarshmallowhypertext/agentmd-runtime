# PROJECT_STATUS

Status date: 2026-10-25. Local integration branch `codex/integrate-reviewed-fixes`; no new release is implied.

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

- Sentence Transformers 6.0.0 and the isolated memory engine passed actual offline model/storage validation, including persistence/fallback/backup and model contract checks; the coupled OpenTelemetry/Firestore update passed offline dependency/client/serialization checks. These are scoped runtime checks, not full production API assurance.
- Real local MiniLM CPU inference was run using an approved pinned safetensors snapshot. No paid model-provider calls, provider credentials, hosted auth/account actions or cloud deployments were run.
- Skill edits verify supplied score/receipt/hash consistency, not the evaluator's truth or actual improvement; no optimizer/benchmark engine is implemented.
- Imported claims remain source assertions; hashes are not authentication or truth verification.
- Signed, append-only identity history remains implemented separately from work state. Execution/Lead receipts remain unsigned; no external notarization, production-SaaS assurance or multi-user execution isolation.
- Windows/Python 3.12.10 integration verification: 87 CLI tests passed, one POSIX-only interruption test skipped; doctor, wrapper demo, real local execution and repeat compilation passed. Python 3.11 and complete Windows process-tree containment remain unverified.
- Account credential rotation/revocation and review/signature enforcement are not established by source cleanup.

No push, merge, tag or release is authorized by this local repair.

## Integration verification on 2026-10-25

- Imported repair commits `352b84a` and `ee1fb8c` from the supplied bundle after checking all archive SHA256 entries. Preserved identity commit `1400df6` and its tests.
- CLI/CI hash-lock audit and API direct-pin audit reported no known vulnerabilities. API direct-pin auditing does not verify a fully installed transitive environment.
- Local `apps.api.src.memory.server:app` startup and HTTP requests to `/health`, `/agentmd/results`, `/dashboard/agentmd-results.html`, and `/openapi.json` passed (200) using disposable SQLite storage. API smoke dependencies were installed in an ignored venv inheriting system packages; this is not a clean full-stack deployment qualification.
- `scripts/verify_local.py` completed through the real runner. Compiling its actual artifact twice produced byte-identical current-state JSON and Markdown and hash `ba24cb9711cc8586959624b827e96a13ab9fe3209b05cdb956acc617eb7c67ad`.
- Startup fixes verified: added the root `Dockerfile`, a restricted build context and `requirements-server.txt`. `apps.api.src.main` now forwards to the existing memory/results server; it no longer imports incomplete legacy provider wiring. This does not restore legacy chat/provider routes.
- Live-provider calls were not made. Existing provider-registry defaults are legacy model identifiers; no current live-test model or hosted destination is designated. Credential values were not printed.
- Native model/storage tests were not rerun: the approved model snapshot is absent. The review package's Linux model evidence remains a separate prior verification claim.
## Docker startup verification on 2026-10-25

- Docker was started by the operator. A clean Python 3.11 image built successfully from the root Dockerfile; `pip check` passed and an audit of its installed package freeze reported no known vulnerabilities.
- An isolated Compose project with fresh Redis/SQLite volumes and disposable secrets became healthy. `/health`, `/agentmd/results`, `/dashboard/agentmd-results.html` and `/openapi.json` returned HTTP 200. A real Redis ping passed; container-generated context and receipts appeared in the results API.
- Two isolated API startup regressions passed both on Windows and inside the clean image. The CLI suite remains 87 passed, 1 POSIX-only test skipped on Windows.
- Provider packages/credentials are unnecessary for this server. No provider was initialized or called. PostgreSQL migration, remote hosting and live model integrations remain unverified.
