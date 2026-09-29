# AgentMD Threat Model

## Assets

- repository instructions, skills, memory, policies, and evals
- Lead Artifact inputs and compiled current-state packets
- execution and skill-edit receipts
- signed agent identity records and export envelopes
- Git and CI provenance
- credentials present in developer or CI environments

## Trust boundaries

### Lead Artifact boundary

Artifact content is untrusted even when it names a known AI tool. AgentMD bounds
file size, record count, JSON depth, schema shape, field lengths, paths, and
high-confidence secret patterns before compilation. Tool identity remains
asserted unless a future signed envelope proves otherwise.

### Workspace boundary

Artifact reads, resolved outputs, and skill mutations must remain beneath the
selected workspace. Skill mutations are further restricted to
`skills/*/SKILL.md`. Resolved symlinks may not escape those roots.

### Receipt boundary

Lead receipts bind source artifact hashes and chain to the previous valid
receipt. Modified receipts are excluded from trust history. Existing Lead,
context, and skill receipts are hash-based and are not asymmetrically signed.

### Identity boundary

Identity records and export envelopes are Ed25519-signed and hash-chained.
AgentMD stores the public key but never stores or generates the private key.
Cross-machine import requires an explicitly trusted public-key fingerprint.
Self-consistent verification proves internal chain integrity; fingerprint-pinned
verification additionally proves continuity with the key the operator trusts.

### CI boundary

CI uses immutable GitHub Action commit SHAs, read-only repository permissions,
non-persistent checkout credentials, hash-locked Python dependencies, explicit
timeouts, vulnerability auditing, and repository indicator scanning.

## Primary threats and controls

| Threat | Current control |
| --- | --- |
| Path traversal or absolute-path mutation | resolved workspace containment and skill-path allowlist |
| Symlink escape | containment checks use resolved paths |
| Oversized or deeply nested artifacts | byte, record, nesting, field, and collection limits |
| Partial malformed JSONL ingestion | explicit artifact compilation fails before outputs are written |
| Credential propagation | high-confidence secret patterns fail closed without echoing values |
| Markdown/HTML injection | untrusted packet text is escaped in Markdown output |
| Trust-score replay | source hash and run ID observations are deduplicated |
| Receipt-history modification | receipt hash verification and previous-hash chaining |
| Self-asserted skill score | accepted edits require a bound validation receipt |
| Identity record tampering | Ed25519 signatures, state hashes, and receipt-hash chaining |
| Identity substitution during import | required operator-pinned signer fingerprint |
| Identity history rewind | append-only versions and import prefix validation |
| CI dependency substitution | exact Action SHAs and hash-locked Python packages |
| Executable model/data formats | unsupported; AgentMD accepts JSON/JSONL artifacts only |

## Incident-derived controls

The hardening choices above follow concrete failure modes disclosed by OpenAI
and Hugging Face:

- OpenAI's 2026 Axios response showed that a compromised developer dependency
  downloaded by GitHub Actions could reach signing material. AgentMD therefore
  uses hash-locked, wheel-only CI installs, immutable Action SHAs, read-only
  workflow permissions, and non-persistent checkout credentials.
- OpenAI's 2026 Hugging Face incident report showed how agents chained exposed
  credentials, unintended network egress, parser/template vulnerabilities, and
  cross-run coordination into broader compromise. AgentMD therefore treats
  artifacts as untrusted data, does not execute artifact formats, bounds input,
  records provenance, and keeps consequential actions behind human approval.
- Hugging Face's Spaces disclosure emphasized revocation, fine-grained tokens,
  traceability, and managed secret storage. Repository credentials and external
  integrations must be short-lived, least-privileged, auditable, and rotated
  after suspected exposure.
- Hugging Face's pickle guidance confirms that scanning is not a complete
  defense against executable serialization. AgentMD keeps pickle and other
  executable model/data formats outside the accepted input contract.

Primary sources:

- `https://openai.com/index/axios-developer-tool-compromise/`
- `https://openai.com/index/hugging-face-incident-and-the-road-ahead/`
- `https://openai.com/safety/prompt-injections/`
- `https://huggingface.co/blog/space-secrets-disclosure`
- `https://huggingface.co/docs/hub/security-pickle`

## Explicit non-guarantees

- No cryptographic source identity for AI/tool artifacts yet.
- Lead, context, and skill receipts are not asymmetrically signed.
- Identity signatures prove control of the trusted private key, not that a
  human personally authored or approved the identity content.
- No sandboxed adapter execution because adapters are not executed in v0.x.
- No guarantee against a malicious actor who controls both the workspace and
  the external identity signing key.
- No production SaaS security claim.
- No runtime egress sandbox; AgentMD v0.x does not execute adapters, and CI
  network policy remains a repository/runner control.

## Required human gates

Human approval remains required before external communication, credential use,
permission expansion, production deployment, or resolving contradictory claims
into accepted truth.
