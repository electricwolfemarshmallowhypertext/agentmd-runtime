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
- source artifact SHA-256 hashes
- previous valid receipt hash for chain continuity
- validation status
- advisory trust metadata (`trust-weight.v1` source history, current observations, and unverified-source flags)
- skill edit id/type/reason/score delta/edit hash and validation receipt hash (for skill gate records)

Lead compilation verifies the latest receipt hash before using its trust history. Invalid or modified receipts are ignored and reported as validation warnings. Replayed artifact/run pairs are not counted again. Trust metadata remains advisory and source identity is explicitly classified as asserted.

## Tamper limitations

Current integrity guarantees are local hash-based and file-based.

Limitations:

- no external notarization
- no transparency log
- no hardware-backed attestation
- no signature chain across environments
- anyone with write access can still replace a receipt chain and recompute unsigned hashes

## What is not yet cryptographically signed

- receipts are not signed with asymmetric keys
- releases are not tied to receipt signatures
- receipt provenance is not anchored to an external immutable ledger

For stable release hardening, signed receipts and external attestation can be added as later phases.
