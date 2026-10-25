# Security hardening status and remaining gates

Updated 2026-10-24. Separate historical cleanup, local fixes, and unverified administration.

## Published source baseline

The September audit originally inspected an older remote head (`0d4eab0`) with canary/hooks/package files. That historical inventory is not the current tree. Published `v0.3.0-alpha.3`/main baseline `6602fc4874c1824faa4d2fd23d3ec560fd39db21` contains no root `canary.js`, root `package.json`, or `.githooks/`; adoption, exit-code, determinism, receipt and threat-model docs are restored. September 29 exact-commit CI logged 41 passing CLI tests and then-current audits.

This does **not** establish historical credential safety or account cleanup:

- [ ] Independently confirm unauthorized apps/tokens/deploy keys/sessions/webhooks were audited and revoked.
- [ ] Confirm credential rotation where needed; no production credentials were inspected in this local repair.
- [ ] Require substantive review/signature enforcement before release. The observed main ruleset required PR/checks but zero reviewer approvals; the release tag was unsigned.

## October local branch fixes (unreleased)

- Final packet hashes cover warning fields and receipts bind that final hash.
- Timestamp format/calendar validation works without optional jsonschema extras; ordering uses UTC instant, including exact fractional seconds.
- Failed workspace validation prevents lead output replacement.
- Bundle preflight/staging/ordinary-error rollback preserves prior outputs; failed rollback retains recovery backups. No power-loss/concurrent-writer atomicity claim.
- Synthetic secret-shaped keys and values are rejected without echo; schema diagnostics omit instance values.
- Terminal loops are not recommended for closure.
- Nested skill/evaluator roots are checked against the workspace. The previously blocked specific skill-root symlink probe was not rerun; no runtime proof for that probe is claimed.
- Receipt history must have valid hashes and continuous retained predecessor links; unsigned replacement/recomputation remains possible.
- Empty discovery remains zero evidence, compiler receipts do not feed themselves back, and prepared receipts are not successful execution evidence.
- Local `run` now executes explicit argv and records actual failures/timeouts; it is not a sandbox/provider integration.

## Current dependency and model validation

The October advisory refresh found new issues despite September's successful audits.

- CLI/CI lock: certifi updated to `2026.10.19`, filelock to `4.2.1`; hash-lock installation and current audit must pass on the final branch. Colorama is retained explicitly for Windows hash-locked installs.
- Legacy API: unused `python-jose` removed (Firebase Admin handles token verification); aiohttp updated to `3.14.4`, Black to `26.10.1` with focused genuine local smoke checks.
- **Sentence Transformers `6.0.0`:** upgraded after approved real offline MiniLM CPU inference and Chroma/SQLite persistence/query/transfer/backup checks, not just a scanner pin bump. Corrected the old exception import, obsolete Chroma API, dimensions, text/thread/persona storage, fallback retrieval and destructive cleanup. Stores now require an actual loaded-model fingerprint and finite float32 vectors; existing unknown/mismatched stores are rejected, not silently migrated. See `embedding_validation.md`.
- **Coordinated OpenTelemetry/Firestore update:** API/SDK/OTLP exporter `1.45.1`, instrumentation `0.66b1`, Firestore `2.34.1`, protobuf `6.33.6`. The old Firestore `<5` protobuf conflict was resolved by a tested compatible Firestore update. Real offline client/protobuf roundtrips and instrumented HTTP/in-memory span export passed with existing Firebase Admin/AI Platform pins; this is not a live Firestore service or full API boot test.
- Audit gates remain enabled with no ignored findings. Direct auditing does not cover full transitive installation or production reachability; separate resolved slices/model runtime were also audited. Full legacy API boot and live cloud/auth integration remain unverified.

## Required before release

- [ ] Revalidate dependency gates and the supported legacy API/service scope on the release candidate; do not equate isolated model/client checks with full production integration.
- [ ] Re-run fresh hash-locked install, CLI outcomes, real local verification artifact, compiler repeat/integrity checks and all dependency audits on the final candidate.
- [ ] Run new behavior and wrappers natively on Windows/Python 3.11; Linux verification is not a Windows claim.
- [ ] Review local diff, unsigned-receipt limitations and all account-level unknowns.
- [ ] Obtain separate authorization for push, PR, merge, tag or release.
