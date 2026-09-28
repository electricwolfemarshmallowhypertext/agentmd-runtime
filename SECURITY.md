# Security Policy

## Supported versions

AgentMD is an alpha project. Only the latest commit on the maintained branch is
eligible for security fixes. Published alpha tags are not production support
commitments.

## Reporting a vulnerability

Do not open a public issue for vulnerabilities, leaked credentials, or active
repository compromise. Use GitHub's private vulnerability reporting for this
repository. Include:

- affected commit or release
- reproduction steps
- expected impact
- relevant artifact, receipt, or workflow hashes
- whether credentials or outbound network access were involved

Do not include live secrets in the report. Revoke exposed credentials before
sharing redacted evidence.

## Security boundaries

- Lead Artifacts are untrusted input.
- Trust scores are advisory and never authorize execution.
- Receipt hashes detect changes but are not signatures.
- Skill edits are limited to workspace-local `skills/*/SKILL.md` files.
- AgentMD does not support executable serialization formats.
- External adapters are not executed by the v0.x runtime.

See `docs/threat_model.md`, `docs/receipt_integrity.md`, and
`docs/security_hardening_todo.md` for current guarantees and open work.
