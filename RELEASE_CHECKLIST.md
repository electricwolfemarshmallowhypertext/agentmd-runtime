# Release checklist

Current published baseline: `v0.3.0-alpha.3` (`6602fc4874c1824faa4d2fd23d3ec560fd39db21`). This is the checklist for a future candidate, not evidence that it has been released.

- [ ] Review all changes against the published baseline; retain the independent audit evidence.
- [ ] Fresh hash-locked wheel install and `pip check` on supported OS/Python versions.
- [ ] Syntax and repository scanner pass; no secrets or unauthorized fixtures.
- [ ] All CLI regressions pass **and** real explicit-command outcomes are verified.
- [ ] Run `agentmd run --task "verify this checkout" -- python scripts/verify_local.py`; compile the generated artifact, not just canned provider fixtures.
- [ ] Independently verify source hashes, final packet hash, receipts/chain, repeat determinism and consistent failure outputs.
- [ ] Verify current CLI and API dependency audits; resolve the documented sentence-transformers migration blocker and verify the coordinated Google/telemetry update. Do not bypass them.
- [ ] Native Windows/Python 3.11 runner/wrapper proof and current exact-commit CI.
- [ ] Review account governance/credentials separately; source cleanup is not revocation proof.
- [ ] Obtain authorization for publication, then verify exact remote commit and CI before tagging. No tag/version is prescribed by this checklist.
