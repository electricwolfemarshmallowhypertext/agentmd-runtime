"""Produce a Lead Artifact from real, offline CLI verification of this checkout.

Run through `agentmd run -- ...` to bind the actual subprocess outcome to a
receipt. This is not a model/provider integration or an independent attestation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".agentmd" / "verification"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    # No environment-specific output override: all evidence remains workspace-local.
    OUT.resolve().relative_to(ROOT.resolve())
    OUT.mkdir(parents=True, exist_ok=True)
    context_raw = os.environ.get("AGENTMD_CONTEXT_FILE")
    if not context_raw:
        raise SystemExit("run this script through agentmd run to supply a context manifest")
    context = Path(context_raw).resolve()
    context.relative_to(ROOT.resolve())
    manifest = json.loads(context.read_text(encoding="utf-8"))
    verified_context = []
    for item in manifest["selected"]:
        path = (ROOT / item["path"]).resolve()
        path.relative_to(ROOT.resolve())
        actual = sha(path.read_bytes())
        if actual != item["sha256"]:
            raise SystemExit("selected context hash mismatch")
        verified_context.append({"path": item["path"], "sha256": actual})

    commands = [
        ("syntax", [sys.executable, "-m", "py_compile", "cli/agentmd.py", "scripts/security_scan.py", "scripts/verify_local.py"]),
        ("security_scan", [sys.executable, "scripts/security_scan.py"]),
        ("cli_regressions", [sys.executable, "-m", "pytest", "-q", "tests/agentmd/test_agentmd_cli.py"]),
        ("diff_check", ["git", "diff", "--check"]),
        ("git_diff", ["git", "diff", "--binary", "HEAD"]),
        ("git_status", ["git", "status", "--porcelain"]),
    ]
    checks = []
    for name, argv in commands:
        result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, check=False)
        path = OUT / (name + ".log")
        path.resolve().relative_to(ROOT.resolve())
        path.write_bytes(result.stdout)
        checks.append({"name": name, "argv": argv, "returncode": result.returncode,
                       "log": path.relative_to(ROOT).as_posix(), "sha256": sha(result.stdout)})
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    report = {"checks": checks, "context": verified_context, "script_sha256": sha(Path(__file__).read_bytes()),
              "context_manifest_sha256": sha(context.read_bytes()), "git_commit": commit}
    report_bytes = (json.dumps(report, indent=2) + "\n").encode()
    report_path = OUT / "verification-report.json"
    report_path.resolve().relative_to(ROOT.resolve())
    report_path.write_bytes(report_bytes)
    ok = all(check["returncode"] == 0 for check in checks)
    artifact = {
        "schema_version": "lead-artifact.v1", "run_id": "local-verification-" + sha(report_bytes)[:20],
        "tool": "agentmd-local-verification", "task": "Verify actual AgentMD checkout and CLI outcomes",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "claims": [{"claim": f"{check['name']} exited {check['returncode']}; log SHA256 {check['sha256']}",
                    "verification_status": "verified" if check["returncode"] == 0 else "contradicted"} for check in checks],
        "decisions": [], "files_touched": sorted(set(changed + untracked)), "open_loops": [],
        "contradictions": [] if ok else ["Local verification has failed commands"],
        "human_approval_items": ["Review local changes before any push, merge or release"],
        "verification_status": "verified" if ok else "failed",
        "context_bundle_hash": manifest["context_bundle_hash"],
        "source_artifacts": [report_path.relative_to(ROOT).as_posix(), *[check["log"] for check in checks]],
        "git_state": {"available": True, "commit": commit, "dirty": bool(changed or untracked),
                      "changed_files": changed, "untracked_files": untracked, "reason": None},
    }
    artifact_path = OUT / "run.lead-artifact.json"
    artifact_path.resolve().relative_to(ROOT.resolve())
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print("actual verification artifact:", artifact_path.relative_to(ROOT).as_posix())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
