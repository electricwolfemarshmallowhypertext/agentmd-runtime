# CLI Exit Codes

This document describes observed/implemented exit code behavior for AgentMD commands.

## Global conventions

- `0`: success
- `1`: command executed but failed due to runtime/validation/schema/domain error
- `2`: CLI usage/argument parsing error (missing required option, invalid option usage)

## doctor

- Success: `0` when workspace validation passes.
- Validation failure: `1` when workspace checks fail.
- Internal error: `1` (unhandled runtime error path).

## resolve

- Success: `0` when context is resolved and output is written.
- Validation/schema failure: `1` if command raises runtime error during processing.
- Missing file/runtime failure: `1`.
- Usage error: `2` (for example, missing required `--task`).
- Internal error: `1`.

## receipt

- Success: `0` when receipt is written.
- Missing file/runtime failure: `1`.
- Usage error: `2` for CLI argument issues.
- Internal error: `1`.

## lead compile

- Success: `0` when packet and receipt are written.
- Validation failure: `1`.
- Schema failure: `1`.
- Missing file failure: `1`.
- Usage error: `2` for CLI argument issues.
- Internal error: `1`.

Notes:

- `lead compile` returns domain-specific error text (`lead_artifact_schema_*`, `*_missing`, etc.) while using exit code `1`.

## skill apply-edit

- Success: `0` for accepted or rejected edit outcomes with record written.
- Validation failure: `1`.
- Schema failure: `1`.
- Missing file failure: `1`.
- Ambiguous edit failure: `1` (`skill_edit_target_ambiguous`).
- Missing target failure: `1` (`skill_edit_target_not_found`).
- Usage error: `2` for CLI argument issues.
- Internal error: `1`.

Notes:

- `skill apply-edit` uses error code `1` for domain failures and disambiguates by message code.
