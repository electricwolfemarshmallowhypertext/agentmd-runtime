# Compatibility Policy

This policy defines compatibility for AgentMD schema contracts used by the runtime.

## Scope

- `lead-artifact.v1` (`schemas/lead-artifact.schema.json`)
- `skill-edit.v1` (`schemas/skill-edit.schema.json`)

## Contract versions

- `lead-artifact.v1` is the current Lead Artifact input contract.
- `skill-edit.v1` is the current Skill Edit input contract.

## Non-breaking changes

Changes are non-breaking when existing valid payloads remain valid and semantics are preserved.

Examples:

- adding optional fields
- adding documentation metadata
- clarifying descriptions without changing validation behavior

## Breaking changes

Changes are breaking when currently valid payloads can fail validation, or behavior/meaning changes in incompatible ways.

Examples:

- changing required fields
- changing field types
- tightening enums so existing values fail
- changing semantics of accepted values without version bump

## Versioning rule

- Breaking schema changes require a new schema version identifier.
- Existing `v1` contracts should remain accepted for the deprecation window.

## Deprecation window

Placeholder policy (to finalize before stable release):

- minimum deprecation window: `TBD` (recommend >= 90 days)
- migration note required for every deprecation
- removal only after deprecation window ends and migration guidance is published

## October 2026 unreleased correction notes

The former `run --adapter ...` command only printed a guessed invocation. It now requires explicit argv after `--`; `--adapter` is only an optional label. Migrate to the documented local-command contract in `local_execution.md`; provider integrations are not silently selected.

Compiler output adds `evidence_status` and preserves execution outcomes. `what_is_true` remains for schema compatibility but is labelled source-reported verified claims in Markdown. Metadata-only/context/compiler/prepared receipts do not count as tool-run evidence; an empty discovery stays zero evidence. Invalid RFC3339 timestamps and failed required workspace validation now fail as the existing contract promised. Terminal loop status aliases are documented without narrowing the v1 input schema.
