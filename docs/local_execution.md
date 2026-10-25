# Real local command execution

```bash
python -m cli.agentmd run --task "verify this checkout" -- python scripts/verify_local.py
```

`run` requires explicit argv after `--`. It validates the workspace before launching, resolves a context manifest, writes a `prepared` receipt, starts the program with `shell=False` and `cwd` set to the workspace, and writes the actual terminal outcome. `--adapter` is an optional asserted label only; it never selects guessed provider flags. No command means a usage error, not pretend success.

The child receives `AGENTMD_CONTEXT_FILE` (absolute JSON manifest path) and `AGENTMD_TASK` (task string). The manifest contains selected paths/hashes and selection metadata, **not concatenated file contents**; the child must read the selected workspace files. stdin is closed. No task/argument string is shell-interpolated.

## Receipts and privacy

Pre/post receipts bind the context manifest and bundle hash, canonical argv hash, argument count, cwd, timeout and terminal return code. Output is not printed or retained: stdout/stderr get SHA256 digests, byte counts and completeness flags. At most `--output-limit` bytes per stream are hashed (default 1 MiB); overflow terminates the process and is not a successful run. Digests are integrity metadata, not encryption or strong privacy for low-entropy values.

Raw argv and output are intentionally omitted. Task, optional adapter label and workspace/context paths are recorded; do not put secrets there. Synthetic security test strings remain synthetic. Avoid secrets in command-line arguments even though receipts omit them, because OS process inspection can expose argv.

## Failure and process boundaries

- Actual process return codes propagate (negative signal returns map to `128 + signal`).
- Launch failure: 127; timeout: 124; interruption: 130; output-limit/incomplete stream: 125.
- Workspace/receipt failure: 1; usage error: 2.
- Default timeout is 300 seconds; permitted range is 0.1–3600 seconds.
- POSIX children use a new process group and are killed on timeout/overflow; Windows terminates the direct child only. This is not comprehensive process containment.
- A post-receipt write failure cannot undo an already executed command. Inspect the pre-receipt and workspace before retrying.

**This is not a sandbox.** The child inherits the caller's environment, filesystem/network access and privileges; `shell=False` prevents interpolation, not arbitrary program effects. Review and authorize the exact executable/arguments. Provider API calls can incur costs and need separately supplied configuration/authorization; no provider integration is implied or verified by local smoke checks.
