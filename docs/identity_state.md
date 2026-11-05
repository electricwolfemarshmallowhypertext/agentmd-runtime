# Durable Agent Identity

AgentMD identity state answers one question: **which continuing agent is this?**
It is deliberately separate from the AI Work Lead packet, which answers **what
is currently true about the work?**

## Storage and integrity

Identity is file-native. Each version is an immutable JSON record under:

```text
.agentmd/identity/records/00000001.json
```

Every record contains the complete identity state, its SHA-256 hash, the
previous state and receipt hashes, change provenance, the signer public key,
and an Ed25519 signature. Rollback appends a new signed version containing a
historical state; it does not delete or rewrite history.

Runtime identity records are ignored by Git by default.

## Key custody

AgentMD accepts an external Ed25519 private key through `--signing-key`.
AgentMD does not generate, copy, export, or store that private key. The operator
is responsible for keeping it outside the workspace and inaccessible to
untrusted agents and tools.

The stable agent ID is derived from the SHA-256 fingerprint of the corresponding
public key:

```text
agentmd:<64-character-public-key-hash>
```

If an LLM or tool can access the private key, it can authorize identity changes.
Therefore model processes must not receive the key or permission to invoke
signing on the operator's behalf.

## Validation

Before AgentMD stores an identity change, it verifies:

- strict JSON and `identity-change.v1` schema conformance
- workspace containment and symlink rejection for change/import inputs
- bounded add, replace, or remove operations
- expected agent ID and source version
- high-confidence secret patterns
- the external signing key matches the established identity
- the complete existing signature and hash chain

Writes use a workspace lock and atomic file replacement. Failed validation does
not append an identity version.

## Verification assurance

`identity verify` without a fingerprint proves that the stored chain is
self-consistent. It does not rule out wholesale replacement by a different
self-consistent identity.

`identity verify --trust-fingerprint <fingerprint>` additionally proves that
the chain is signed by the public key the operator selected out of band.

## Commands

```powershell
.\agentmd.cmd identity init --name "Continuing Agent" --purpose "Preserve continuity" --signing-key C:\secure\agentmd-ed25519.pem
.\agentmd.cmd identity verify --trust-fingerprint "sha256:<trusted-fingerprint>"
.\agentmd.cmd identity history
.\agentmd.cmd identity apply --change identity-change.json --signing-key C:\secure\agentmd-ed25519.pem
.\agentmd.cmd identity rollback --version 1 --signing-key C:\secure\agentmd-ed25519.pem
.\agentmd.cmd identity export --output identity-export.json --signing-key C:\secure\agentmd-ed25519.pem
.\agentmd.cmd identity import --input identity-export.json --trust-fingerprint "sha256:<trusted-fingerprint>"
```

Import accepts an empty destination or an exact prefix of the exported history.
It rejects a conflicting history and refuses to rewind a destination with newer
records.

## Schemas

- `schemas/agent-identity.schema.json`: signed identity version
- `schemas/identity-change.schema.json`: bounded change proposal
- `schemas/identity-envelope.schema.json`: signed export envelope

## Explicit exclusions

This implementation does not include:

- Anchor's SQLite database or code
- private-key storage
- unsigned exports or validation bypass flags
- Ollama/compiler loops
- tool/security policy systems
- automatic identity changes from model output
- signatures for existing Lead, context, or skill receipts
- external notarization, transparency logs, or hardware attestation
