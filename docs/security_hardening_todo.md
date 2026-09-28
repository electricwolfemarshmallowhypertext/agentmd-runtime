# AgentMD Security Hardening TODO

Status: local hardening verified; public repository remediation pending

This checklist records the September 2026 security audit and is the gate for the
next network operation or release.

## Remote finding

- Last inspected remote head: `origin/main` at `0d4eab0`.
- Clean merge base: `c498d47653761b351a3fe0ba441f3fa9e92c431b`.
- Divergence at inspection: local branch 1 commit ahead; remote 23 commits ahead.
- The 23 remote-only commits are unsigned and share the message `chore: sync editor configuration`.
- Remote-only files: `.githooks/pre-commit`, `.githooks/post-merge`, `canary.js`, and `package.json`.
- The hook and npm lifecycle scripts decode and invoke an outbound HTTP command.
- Those files are absent locally, `core.hooksPath` is unset, and only sample hooks exist in `.git/hooks`.

## P0: Repository containment

- [x] Fetch and inspect `origin/main` without merging it.
- [x] Confirm the local working tree does not contain the outbound canary files.
- [x] Confirm no custom Git hooks are active locally.
- [x] Isolate work on `codex/security-hardening-2026` from the last clean lineage.
- [ ] Remove `.githooks/`, `canary.js`, and the introduced `package.json` from public `main`.
- [ ] Restore trust/adoption documentation deleted by the remote commits.
- [ ] Audit and revoke unauthorized GitHub apps, tokens, deploy keys, sessions, and webhooks.
- [ ] Protect `main` with reviewed changes and signed provenance.

## P0: File mutation boundaries

- [x] Restrict skill edits to workspace-local `skills/*/SKILL.md` files.
- [x] Reject absolute paths, traversal, and symlink escapes.
- [x] Write accepted skill edits atomically and verify the resulting hash.
- [x] Require hash-bound validation evidence before accepting an edit.

## P1: Hostile artifact handling

- [x] Enforce artifact byte, record, nesting, string, and collection limits.
- [x] Reject malformed JSONL atomically instead of partially compiling it.
- [x] Restrict artifact paths to the workspace unless explicitly trusted later.
- [x] Reject symlink escapes and duplicate run IDs.
- [x] Keep executable and binary serialization formats unsupported.

## P1: Schema hardening

- [x] Close undeclared top-level Lead Artifact fields.
- [x] Validate RFC 3339 timestamps and SHA-256 hash formats.
- [x] Add practical `maxLength` and `maxItems` constraints.
- [x] Add stable claim/evidence provenance fields without weakening v1 validation.

## P1: Receipt and trust integrity

- [x] Verify historical receipt hashes before consuming trust history.
- [x] Chain receipts with `previous_receipt_hash`.
- [x] Bind artifact hashes to receipts.
- [x] Deduplicate trust observations by artifact hash and `run_id`.
- [x] Separate asserted claim status from evaluator-observed status.
- [x] Keep trust advisory; never use it as execution authorization.
- [x] Document that asymmetric signing and external attestation remain future work.

## P1: Prompt-injection containment

- [x] Mark imported artifact content as untrusted data with per-claim provenance.
- [x] Sanitize generated Markdown/HTML output.
- [x] Prevent artifact text from becoming commands, policy, or permissions.
- [x] Preserve explicit human-approval items; AgentMD v0.x does not execute sensitive actions.

## P1: CI and dependency supply chain

- [x] Pin GitHub Actions to verified full commit SHAs.
- [x] Set workflow permissions to `contents: read`.
- [x] Disable checkout credential persistence.
- [x] Add job timeouts.
- [x] Install dependencies from a hash-locked requirements file.
- [x] Remove unpinned workflow-only Python installs and pip self-upgrades.
- [x] Add dependency auditing and repository secret/indicator scanning gates.
- [x] Upload only allowlisted proof artifacts.

## Release gate

- [x] `python -m py_compile cli/agentmd.py scripts/security_scan.py`
- [x] `python -m pytest -q tests/agentmd/test_agentmd_cli.py` (`36 passed` on Python 3.11)
- [x] `./scripts/demo-lead-compile.ps1`
- [x] Dependency audit passes (`pip-audit`: no known vulnerabilities).
- [x] Security regression tests pass.
- [x] Final diff contains no outbound canary indicators or secrets.
- [ ] No push, tag, or release until the local gate is complete.
