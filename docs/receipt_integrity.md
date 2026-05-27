# Receipt Integrity

This document describes receipt integrity properties in AgentMD today.

## Receipt types

- Context/runtime receipts: `receipts/*.jsonl`
- Lead compile receipts: `.sticky/receipts/*.jsonl`
- Skill gate receipts: `.sticky/skill-receipts/*.jsonl`
- Rejected skill edit records: `.sticky/rejected-skill-edits/*.jsonl`

## What receipt hashes cover

AgentMD computes receipt hashes over the receipt payload fields present before the hash field is appended.

Implication:

- `receipt_hash` detects modifications to covered fields.
- `receipt_hash` does not self-sign the hash field itself (standard hash-append pattern).

## Provenance fields (examples)

Depending on receipt type, provenance includes:

- task / command
- selected context files
- file hashes
- context bundle hash
- current state hash
- git commit / dirty flag / changed files / untracked files
- source artifact references
- validation status
- skill edit id/type/reason/score delta/edit hash (for skill gate records)

## Tamper limitations

Current integrity guarantees are local hash-based and file-based.

Limitations:

- no external notarization
- no transparency log
- no hardware-backed attestation
- no signature chain across environments

## What is not yet cryptographically signed

- receipts are not signed with asymmetric keys
- releases are not tied to receipt signatures
- receipt provenance is not anchored to an external immutable ledger

For stable release hardening, signed receipts and external attestation can be added as later phases.
