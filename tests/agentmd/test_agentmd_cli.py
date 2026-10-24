from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cli.agentmd import app


runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ws() -> Path:
    base = REPO_ROOT / ".tmp" / "agentmd-tests"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def scaffold_workspace(root: Path) -> None:
    (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (root / "agentmd.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "limits:",
                "  max_file_bytes: 131072",
                "  max_total_bytes: 524288",
                "resolve:",
                "  max_skills: 4",
                "  max_memory: 4",
                "  max_policies: 4",
                "  max_evals: 4",
                "skills:",
                "  required_metadata: [id, name, description, version, permissions]",
                "  forbidden_permissions: [filesystem:write_outside_workspace]",
            ]
        ),
        encoding="utf-8",
    )
    (root / "skills" / "s1").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "s1" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s1",
                "name: Repo Drift Scan",
                "description: scan for context drift",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Skill",
                "Use for context drift checks.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "memory").mkdir(parents=True, exist_ok=True)
    (root / "memory" / "state.md").write_text("Current repo context state.\n", encoding="utf-8")
    (root / "policies").mkdir(parents=True, exist_ok=True)
    (root / "policies" / "p1.yaml").write_text("id: p1\nrules: []\n", encoding="utf-8")
    (root / "evals").mkdir(parents=True, exist_ok=True)
    (root / "evals" / "e1.jsonl").write_text('{"id":"e1","task":"drift"}\n', encoding="utf-8")
    (root / "receipts").mkdir(parents=True, exist_ok=True)


def valid_lead_artifact(run_id: str = "security-run-1", **overrides: object) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": "lead-artifact.v1",
        "run_id": run_id,
        "tool": "codex",
        "task": "security regression",
        "timestamp": "2026-09-28T12:00:00Z",
        "claims": [],
        "decisions": [],
        "files_touched": [],
        "open_loops": [],
        "contradictions": [],
        "human_approval_items": [],
        "verification_status": "unverified",
    }
    artifact.update(overrides)
    return artifact


def valid_skill_edit(skill_path: str, **overrides: object) -> dict[str, object]:
    edit: dict[str, object] = {
        "schema_version": "skill-edit.v1",
        "skill_id": "skill.s1",
        "skill_path": skill_path,
        "edit_id": "security-edit-1",
        "edit_type": "replace",
        "target": "Use for context drift checks.",
        "replacement": "Use for context drift checks with validation gates.",
        "reason": "Security regression coverage.",
        "baseline_score": 0.61,
        "validation_score": 0.74,
        "validation_task": "repo context drift review",
        "evidence": ["eval:heldout-1"],
        "proposed_by": "test-suite",
        "timestamp": "2026-09-28T12:00:00Z",
    }
    edit.update(overrides)
    return edit


def write_skill_validation_receipt(root: Path, edit: dict[str, object]) -> Path:
    skill_file = root / str(edit["skill_path"])
    old_text = skill_file.read_text(encoding="utf-8")
    target = str(edit["target"])
    replacement = str(edit["replacement"])
    proposed_text = old_text.replace(target, replacement, 1)
    receipt: dict[str, object] = {
        "schema_version": "skill-validation.v1",
        "evaluator": "test-suite",
        "skill_id": edit["skill_id"],
        "validation_task": edit["validation_task"],
        "baseline_score": edit["baseline_score"],
        "validation_score": edit["validation_score"],
        "old_hash": hashlib.sha256(skill_file.read_bytes()).hexdigest(),
        "proposed_new_hash": hashlib.sha256(proposed_text.encode("utf-8")).hexdigest(),
        "timestamp": "2026-09-28T12:00:00Z",
    }
    material = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(material).hexdigest()
    receipt_dir = root / "evals" / "skill-validation"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{edit['edit_id']}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt_path


def test_doctor_passes_with_valid_scaffold(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["doctor", "--root", str(ws)])
    assert result.exit_code == 0, result.stdout
    assert "doctor: PASS" in result.stdout


def test_doctor_fails_missing_agents_md(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "AGENTS.md").unlink()
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(check["name"] == "agents_exists" and check["ok"] is False for check in payload["checks"])


def test_doctor_fails_invalid_yaml_policy(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "policies" / "p1.yaml").write_text("rules: [good, bad\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("policy_yaml_invalid:" in err for err in payload["errors"])


def test_doctor_fails_invalid_jsonl_eval(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "evals" / "e1.jsonl").write_text('{"id":"ok"}\n{"id":\n', encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("eval_jsonl_invalid:" in err for err in payload["errors"])


def test_doctor_fails_duplicate_skill_ids(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "skills" / "s2").mkdir(parents=True, exist_ok=True)
    (ws / "skills" / "s2" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s1",
                "name: Duplicate Skill",
                "description: duplicate ID should fail",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Duplicate",
            ]
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("duplicate_skill_id:" in err for err in payload["errors"])


def test_resolve_includes_selected_and_excluded_reasons(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "agentmd.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "resolve:",
                "  max_skills: 1",
                "  max_memory: 4",
                "  max_policies: 4",
                "  max_evals: 4",
                "skills:",
                "  required_metadata: [id, name, description, version, permissions]",
                "  forbidden_permissions: [filesystem:write_outside_workspace]",
            ]
        ),
        encoding="utf-8",
    )
    (ws / "skills" / "s2").mkdir(parents=True, exist_ok=True)
    (ws / "skills" / "s2" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s2",
                "name: Drift Skill Two",
                "description: also mentions context drift",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Skill",
                "Also checks context drift.",
            ]
        ),
        encoding="utf-8",
    )
    output_path = ws / "custom-output" / "resolved.json"
    result = runner.invoke(
        app,
        [
            "resolve",
            "--root",
            str(ws),
            "--task",
            "review this repo for context drift",
            "--output",
            str(output_path),
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert output_path.exists()
    data = json.loads(result.stdout)
    assert data["task"] == "review this repo for context drift"
    assert data["selected"]
    assert data["excluded"]
    assert all("reason" in item for item in data["selected"])
    assert all("reason" in item for item in data["excluded"])
    assert data["context_bundle_hash"]


def test_receipt_includes_git_or_non_git_metadata(ws: Path) -> None:
    scaffold_workspace(ws)
    resolve_result = runner.invoke(
        app,
        ["resolve", "--root", str(ws), "--task", "generate an auditable receipt"],
    )
    assert resolve_result.exit_code == 0

    receipt_result = runner.invoke(app, ["receipt", "--root", str(ws)])
    assert receipt_result.exit_code == 0

    receipt_files = sorted((ws / "receipts").glob("*.jsonl"))
    assert receipt_files
    payload = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert payload["task"] == "generate an auditable receipt"
    assert "adapter" in payload
    assert isinstance(payload["selected_context_files"], list)
    assert isinstance(payload["file_hashes"], dict)
    assert payload["context_bundle_hash"]
    assert payload["receipt_hash"]
    assert "git_commit" in payload
    assert "git_dirty" in payload
    assert "changed_files" in payload
    assert "untracked_files" in payload
    if payload["git_available"]:
        assert payload["git_reason"] is None
        assert isinstance(payload["git_commit"], str) and payload["git_commit"]
    else:
        assert payload["git_reason"] == "not_a_git_repository"
        assert payload["git_commit"] is None


def test_receipt_uses_last_custom_resolved_output(ws: Path) -> None:
    scaffold_workspace(ws)
    custom_output = ws / "custom" / "resolved.json"
    resolve_result = runner.invoke(
        app,
        [
            "resolve",
            "--root",
            str(ws),
            "--task",
            "review this repo for context drift",
            "--output",
            str(custom_output),
        ],
    )
    assert resolve_result.exit_code == 0
    assert custom_output.exists()

    receipt_result = runner.invoke(app, ["receipt", "--root", str(ws)])
    assert receipt_result.exit_code == 0

    receipt_files = sorted((ws / "receipts").glob("*.jsonl"))
    payload = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert payload["resolved_context_file"] == "custom/resolved.json"
    assert payload["selected_context_files"], "receipt should include selected context from last custom resolved output"
    assert payload["context_bundle_hash"]



def test_lead_compile_ingests_artifact_and_writes_outputs(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "artifacts.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "run-1",
                "timestamp": "2026-05-20T00:00:00Z",
                "tool": "codex",
                "task": "compile current state",
                "files_touched": ["AGENTS.md", "memory/state.md"],
                "claims": [{"claim": "AGENTS.md exists", "verification_status": "verified"}],
                "decisions": [{"decision": "Defer deployment", "requires_human_approval": True}],
                "open_loops": ["Confirm policy owner"],
                "verification_status": "partial",
                "context_bundle_hash": "a" * 64,
                "receipt_hash": "b" * 64,
                "contradictions": [],
                "human_approval_items": [],
                "git_state": {
                    "available": False,
                    "commit": None,
                    "dirty": None,
                    "changed_files": ["AGENTS.md"],
                    "untracked_files": ["notes/tmp.md"],
                    "reason": "not_a_git_repository",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)],
    )
    assert result.exit_code == 0

    state_json = ws / ".sticky" / "current-state.json"
    state_md = ws / ".sticky" / "current-state.md"
    assert state_json.exists()
    assert state_md.exists()

    payload = json.loads(state_json.read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1
    assert payload["task"] == "compile current state"
    assert payload["proof"]["run_id"] == "run-1"
    assert payload["proof"]["context_bundle_hash"] == "a" * 64
    claim_source = payload["provenance"]["claims"]["AGENTS.md exists"][0]
    assert claim_source["run_id"] == "run-1"
    assert claim_source["source_sha256"]
    assert claim_source["source_authentication"] == "asserted"
    assert "AGENTS.md" in payload["current_state"]["what_changed"]
    loop_texts = {loop["text"] for loop in payload["current_state"]["open_loops"]}
    assert "Confirm policy owner" in loop_texts

    receipt_files = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))
    assert receipt_files


def test_lead_compile_is_deterministic_for_same_artifact_input(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "lead-input.jsonl"
    artifact = {
        "schema_version": "lead-artifact.v1",
        "run_id": "stable-run",
        "tool": "codex",
        "timestamp": "2026-05-20T01:02:03Z",
        "task": "deterministic packet",
        "files_touched": ["memory/state.md", "policies/p1.yaml"],
        "claims": [{"claim": "policy loaded", "verification_status": "verified"}],
        "decisions": [],
        "open_loops": ["confirm reviewer"],
        "contradictions": [],
        "human_approval_items": [],
        "verification_status": "verified",
        "context_bundle_hash": "c" * 64,
        "receipt_hash": "d" * 64,
        "git_state": {"available": False, "reason": "not_a_git_repository"},
    }
    artifact_path.write_text(json.dumps(artifact) + "\n", encoding="utf-8")

    first = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert first.exit_code == 0
    first_payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))

    second = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert second.exit_code == 0
    second_payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))

    assert first_payload == second_payload
    assert first_payload["deterministic_hash"] == second_payload["deterministic_hash"]


def test_lead_compile_preserves_contradictions_and_open_loops(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "contradictions.jsonl"
    artifact_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "lead-artifact.v1",
                        "run_id": "r1",
                        "tool": "codex",
                        "timestamp": "2026-05-20T00:00:00Z",
                        "task": "check contradiction handling",
                        "claims": [{"claim": "service door was sealed", "verification_status": "verified"}],
                        "decisions": [],
                        "files_touched": [],
                        "open_loops": ["Find Mara"],
                        "contradictions": [],
                        "human_approval_items": [],
                        "verification_status": "verified",
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "lead-artifact.v1",
                        "run_id": "r2",
                        "tool": "claude",
                        "timestamp": "2026-05-20T00:01:00Z",
                        "task": "check contradiction handling",
                        "claims": [{"claim": "service door was sealed", "verification_status": "contradicted"}],
                        "decisions": [],
                        "files_touched": [],
                        "open_loops": ["Inspect pantry"],
                        "contradictions": [],
                        "human_approval_items": [],
                        "verification_status": "contradicted",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0

    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    contradictions = payload["current_state"]["what_contradicts_prior_state"]
    assert any("service door was sealed" in item for item in contradictions)

    open_loop_texts = {loop["text"] for loop in payload["current_state"]["open_loops"]}
    assert open_loop_texts == {"Find Mara", "Inspect pantry"}
    approvals = payload["current_state"]["what_needs_human_approval"]
    assert any(item.startswith("Resolve contradiction: service door was sealed") for item in approvals)



def test_lead_compile_receipt_marks_source_identity_unverified(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "low-trust.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "low-trust-run",
                "tool": "claude",
                "timestamp": "2026-05-20T00:02:00Z",
                "task": "compile trust scoring",
                "claims": [
                    {"claim": "deployment gate passed", "verification_status": "contradicted"},
                    {"claim": "receipt was uploaded", "verification_status": "contradicted"},
                ],
                "decisions": [],
                "files_touched": ["cli/agentmd.py"],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "contradicted",
                "git_state": {"available": False, "reason": "not_a_git_repository"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0

    receipt_files = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))
    assert receipt_files
    receipt = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    trust = receipt["trust"]
    assert trust["version"] == "trust-weight.v1"
    assert trust["source_history"]["claude"]["contradicted_claims"] == 2
    assert trust["source_history"]["claude"]["trust_weight"] is None
    assert trust["source_history"]["claude"]["asserted_signal_weight"] < trust["low_trust_threshold"]
    assert any(
        flag["flag"] == "unverified_source_identity" and flag["source"] == "claude"
        for flag in trust["entry_flags"]
    )
    assert any("unverified_source_identity: claude" in warning for warning in receipt["validation_warnings"])


def test_lead_compile_trust_history_persists_across_receipts(ws: Path) -> None:
    scaffold_workspace(ws)
    first_artifact = ws / "trust-first.json"
    first_artifact.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "trust-run-1",
                "tool": "codex",
                "timestamp": "2026-05-20T00:03:00Z",
                "task": "compile trust history",
                "claims": [{"claim": "receipt includes git metadata", "verification_status": "verified"}],
                "decisions": [],
                "files_touched": ["cli/agentmd.py"],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
                "git_state": {"available": False, "reason": "not_a_git_repository"},
            }
        ),
        encoding="utf-8",
    )
    second_artifact = ws / "trust-second.json"
    second_artifact.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "trust-run-2",
                "tool": "codex",
                "timestamp": "2026-05-20T00:04:00Z",
                "task": "compile trust history",
                "claims": [{"claim": "receipt includes git metadata", "verification_status": "contradicted"}],
                "decisions": [],
                "files_touched": ["cli/agentmd.py"],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "contradicted",
                "git_state": {"available": False, "reason": "not_a_git_repository"},
            }
        ),
        encoding="utf-8",
    )

    first = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(first_artifact)])
    assert first.exit_code == 0
    second = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(second_artifact)])
    assert second.exit_code == 0

    receipt_files = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))
    assert len(receipt_files) == 2
    receipt = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    codex_history = receipt["trust"]["source_history"]["codex"]
    assert codex_history["confirmed_claims"] == 1
    assert codex_history["contradicted_claims"] == 1
    assert receipt["trust"]["current_observations"]["codex"]["contradicted_claims"] == 1


def test_lead_compile_does_not_double_count_replayed_artifact(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "replay.json"
    artifact_path.write_text(
        json.dumps(
            valid_lead_artifact(
                run_id="replay-run",
                claims=[{"claim": "same observation", "verification_status": "verified"}],
                verification_status="verified",
            )
        ),
        encoding="utf-8",
    )

    first = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    second = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert first.exit_code == 0
    assert second.exit_code == 0

    receipt_files = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))
    receipt = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    codex_history = receipt["trust"]["source_history"]["codex"]
    assert codex_history["confirmed_claims"] == 1
    assert receipt["trust"]["current_observations"] == {}
    assert receipt["previous_receipt_hash"]


def test_lead_compile_ignores_tampered_receipt_history(ws: Path) -> None:
    scaffold_workspace(ws)
    first_artifact = ws / "first.json"
    first_artifact.write_text(
        json.dumps(
            valid_lead_artifact(
                run_id="tamper-run-1",
                claims=[{"claim": "first observation", "verification_status": "verified"}],
                verification_status="verified",
            )
        ),
        encoding="utf-8",
    )
    first = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(first_artifact)])
    assert first.exit_code == 0

    first_receipt_path = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))[-1]
    tampered_receipt = json.loads(first_receipt_path.read_text(encoding="utf-8").strip())
    tampered_receipt["task"] = "tampered task"
    first_receipt_path.write_text(json.dumps(tampered_receipt) + "\n", encoding="utf-8")

    second_artifact = ws / "second.json"
    second_artifact.write_text(
        json.dumps(
            valid_lead_artifact(
                run_id="tamper-run-2",
                claims=[{"claim": "second observation", "verification_status": "contradicted"}],
                verification_status="contradicted",
            )
        ),
        encoding="utf-8",
    )
    second = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(second_artifact)])
    assert second.exit_code == 0

    second_receipt_path = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))[-1]
    second_receipt = json.loads(second_receipt_path.read_text(encoding="utf-8").strip())
    assert second_receipt["previous_receipt_hash"] is None
    assert second_receipt["trust"]["source_history"]["codex"]["confirmed_claims"] == 0
    assert any("receipt_history_hash_mismatch" in item for item in second_receipt["validation_warnings"])


def test_lead_compile_rejects_invalid_artifact_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "invalid-artifact.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "bad-run",
                "task": "missing required schema fields",
                "timestamp": "2026-05-20T11:00:00Z",
                "claims": "should-be-array",
                "decisions": [],
                "files_touched": [],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "lead_artifact_schema_invalid" in result.stdout


def test_lead_compile_rejects_missing_schema_version(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "missing-schema-version.json"
    artifact_path.write_text(
        json.dumps(
            {
                "run_id": "missing-version",
                "tool": "codex",
                "task": "missing schema version",
                "timestamp": "2026-05-20T11:30:00Z",
                "claims": [],
                "decisions": [],
                "files_touched": [],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "unverified",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "schema_version" in result.stdout


def test_lead_compile_accepts_valid_artifact_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "valid-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "valid-run",
                "tool": "codex",
                "task": "validate schema",
                "timestamp": "2026-05-20T12:00:00Z",
                "claims": [{"claim": "schema exists", "verification_status": "verified"}],
                "decisions": [{"decision": "accept artifact", "status": "verified"}],
                "files_touched": ["README.md"],
                "open_loops": ["confirm rollout"],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
                "context_bundle_hash": "e" * 64,
                "receipt_hash": "f" * 64,
                "source_artifacts": ["tool-output/123"],
                "git_state": {
                    "available": False,
                    "commit": None,
                    "dirty": None,
                    "changed_files": [],
                    "untracked_files": [],
                    "reason": "external",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1


def test_lead_compile_demo_artifacts_still_compile(ws: Path) -> None:
    scaffold_workspace(ws)
    demo_dir = ws / "examples" / "lead-artifacts"
    shutil.copytree(REPO_ROOT / "examples" / "lead-artifacts", demo_dir)
    result = runner.invoke(
        app,
        [
            "lead",
            "compile",
            "--root",
            str(ws),
            "--artifact",
            str(demo_dir / "run-codex.jsonl"),
            "--artifact",
            str(demo_dir / "run-claude.json"),
            "--artifact",
            str(demo_dir / "run-gemini.jsonl"),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 3
    assert payload["proof"]["run_id"] == "demo-run-003"


def test_lead_compile_template_artifact_compiles(ws: Path) -> None:
    scaffold_workspace(ws)
    template_path = ws / "template.lead-artifact.json"
    shutil.copy2(REPO_ROOT / "examples" / "lead-artifacts" / "template.lead-artifact.json", template_path)
    result = runner.invoke(
        app,
        [
            "lead",
            "compile",
            "--root",
            str(ws),
            "--artifact",
            str(template_path),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1
    assert payload["proof"]["run_id"] == "template-run-001"


def test_skill_apply_edit_accepts_and_writes_receipt(ws: Path) -> None:
    scaffold_workspace(ws)
    edit_path = ws / "accepted-edit.json"
    edit = {
        "schema_version": "skill-edit.v1",
        "skill_id": "skill.s1",
        "skill_path": "skills/s1/SKILL.md",
        "edit_id": "edit-accept-1",
        "edit_type": "replace",
        "target": "Use for context drift checks.",
        "replacement": "Use for context drift checks with validation gates.",
        "reason": "Improve held-out validation performance.",
        "baseline_score": 0.61,
        "validation_score": 0.74,
        "validation_task": "repo context drift review",
        "evidence": ["eval:heldout-1"],
        "proposed_by": "test-suite",
        "timestamp": "2026-05-27T00:00:00Z",
    }
    validation_receipt = write_skill_validation_receipt(ws, edit)
    edit["validation_receipt"] = validation_receipt.relative_to(ws).as_posix()
    edit_path.write_text(
        json.dumps(edit, indent=2)
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 0, result.stdout
    assert "decision: accepted" in result.stdout

    skill_body = (ws / "skills" / "s1" / "SKILL.md").read_text(encoding="utf-8")
    assert "validation gates." in skill_body

    receipt_files = sorted((ws / ".sticky" / "skill-receipts").glob("*.jsonl"))
    assert receipt_files
    receipt = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert receipt["decision"] == "accepted"
    assert receipt["score_delta"] > 0
    assert receipt["old_hash"] != receipt["new_hash"]
    assert receipt["validation_receipt_hash"]


def test_skill_apply_edit_rejects_and_writes_rejection_record(ws: Path) -> None:
    scaffold_workspace(ws)
    skill_path = ws / "skills" / "s1" / "SKILL.md"
    original = skill_path.read_text(encoding="utf-8")

    edit_path = ws / "rejected-edit.json"
    edit_path.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-reject-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks quickly.",
                "reason": "Try a shorter wording.",
                "baseline_score": 0.72,
                "validation_score": 0.58,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:10:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 0
    assert "decision: rejected" in result.stdout
    assert skill_path.read_text(encoding="utf-8") == original

    rejection_files = sorted((ws / ".sticky" / "rejected-skill-edits").glob("*.jsonl"))
    assert rejection_files
    rejection = json.loads(rejection_files[-1].read_text(encoding="utf-8").strip())
    assert rejection["decision"] == "rejected"
    assert rejection["old_hash"] == rejection["new_hash"]
    assert rejection["score_delta"] < 0


def test_skill_apply_edit_fails_invalid_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    edit_path = ws / "invalid-skill-edit.json"
    edit_path.write_text(
        json.dumps(
            {
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-invalid-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks with validation gates.",
                "reason": "Invalid payload should fail schema.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:20:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 1
    assert "skill_edit_schema_invalid" in result.stdout


def test_skill_apply_edit_fails_for_ambiguous_or_missing_target(ws: Path) -> None:
    scaffold_workspace(ws)
    skill_path = ws / "skills" / "s1" / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8") + "\nUse for context drift checks.\n",
        encoding="utf-8",
    )

    ambiguous_edit = ws / "ambiguous-skill-edit.json"
    ambiguous_edit.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-ambiguous-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks with validation gates.",
                "reason": "Ambiguous target should fail.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:30:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    ambiguous_result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(ambiguous_edit)])
    assert ambiguous_result.exit_code == 1
    assert "skill_edit_target_ambiguous" in ambiguous_result.stdout

    missing_edit = ws / "missing-target-skill-edit.json"
    missing_edit.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-missing-1",
                "edit_type": "replace",
                "target": "This target does not exist.",
                "replacement": "Replacement text.",
                "reason": "Missing target should fail.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:31:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    missing_result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(missing_edit)])
    assert missing_result.exit_code == 1
    assert "skill_edit_target_not_found" in missing_result.stdout


def test_skill_apply_edit_rejects_absolute_and_traversal_paths(ws: Path) -> None:
    scaffold_workspace(ws)
    outside_file = ws / "outside.md"
    outside_file.write_text("Use for context drift checks.\n", encoding="utf-8")

    absolute_edit = ws / "absolute-edit.json"
    absolute_edit.write_text(json.dumps(valid_skill_edit(str(outside_file))), encoding="utf-8")
    absolute_result = runner.invoke(
        app,
        ["skill", "apply-edit", "--root", str(ws), "--edit", str(absolute_edit)],
    )
    assert absolute_result.exit_code == 1
    assert "skill_edit_absolute_path_forbidden" in absolute_result.stdout

    traversal_edit = ws / "traversal-edit.json"
    traversal_edit.write_text(
        json.dumps(valid_skill_edit("skills/s1/../../outside.md", edit_id="security-edit-2")),
        encoding="utf-8",
    )
    traversal_result = runner.invoke(
        app,
        ["skill", "apply-edit", "--root", str(ws), "--edit", str(traversal_edit)],
    )
    assert traversal_result.exit_code == 1
    assert "skill_edit_path_outside_skills" in traversal_result.stdout
    assert outside_file.read_text(encoding="utf-8") == "Use for context drift checks.\n"


def test_skill_apply_edit_rejects_proposal_outside_workspace(ws: Path) -> None:
    scaffold_workspace(ws)
    outside_edit = ws.parent / f"{ws.name}-outside-edit.json"
    outside_edit.write_text(
        json.dumps(valid_skill_edit("skills/s1/SKILL.md")),
        encoding="utf-8",
    )
    try:
        result = runner.invoke(
            app,
            ["skill", "apply-edit", "--root", str(ws), "--edit", str(outside_edit)],
        )
    finally:
        outside_edit.unlink(missing_ok=True)

    assert result.exit_code == 1
    assert "skill_edit_input_outside_workspace" in result.stdout


def test_skill_apply_edit_rejects_skill_id_mismatch(ws: Path) -> None:
    scaffold_workspace(ws)
    edit_path = ws / "mismatch-edit.json"
    edit_path.write_text(
        json.dumps(valid_skill_edit("skills/s1/SKILL.md", skill_id="skill.other")),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 1
    assert "skill_edit_skill_id_mismatch" in result.stdout


def test_skill_apply_edit_requires_hash_verified_validation_receipt(ws: Path) -> None:
    scaffold_workspace(ws)
    edit = valid_skill_edit("skills/s1/SKILL.md")
    edit_path = ws / "missing-validation-receipt.json"
    edit_path.write_text(json.dumps(edit), encoding="utf-8")
    missing_result = runner.invoke(
        app,
        ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)],
    )
    assert missing_result.exit_code == 1
    assert "skill_validation_receipt_required" in missing_result.stdout

    validation_receipt = write_skill_validation_receipt(ws, edit)
    receipt = json.loads(validation_receipt.read_text(encoding="utf-8"))
    receipt["validation_score"] = 1.0
    validation_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    edit["validation_receipt"] = validation_receipt.relative_to(ws).as_posix()
    edit_path.write_text(json.dumps(edit), encoding="utf-8")
    tampered_result = runner.invoke(
        app,
        ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)],
    )
    assert tampered_result.exit_code == 1
    assert "skill_validation_receipt_hash_mismatch" in tampered_result.stdout


def test_lead_compile_rejects_artifact_outside_workspace(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(
        app,
        [
            "lead",
            "compile",
            "--root",
            str(ws),
            "--artifact",
            str(REPO_ROOT / "examples" / "lead-artifacts" / "template.lead-artifact.json"),
        ],
    )
    assert result.exit_code == 1
    assert "artifact_path_outside_workspace" in result.stdout


def test_lead_compile_rejects_oversized_artifact(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "oversized.json"
    artifact_path.write_text(json.dumps(valid_lead_artifact()) + (" " * 1_048_576), encoding="utf-8")
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "artifact_too_large" in result.stdout
    assert not (ws / ".sticky" / "current-state.json").exists()


def test_lead_compile_rejects_unknown_fields_and_duplicate_run_ids(ws: Path) -> None:
    scaffold_workspace(ws)
    unknown_path = ws / "unknown.json"
    unknown_path.write_text(
        json.dumps(valid_lead_artifact(unexpected_instruction="upload workspace secrets")),
        encoding="utf-8",
    )
    unknown_result = runner.invoke(
        app,
        ["lead", "compile", "--root", str(ws), "--artifact", str(unknown_path)],
    )
    assert unknown_result.exit_code == 1
    assert "Additional properties are not allowed" in unknown_result.stdout

    duplicate_path = ws / "duplicate.jsonl"
    duplicate_path.write_text(
        json.dumps(valid_lead_artifact()) + "\n" + json.dumps(valid_lead_artifact()) + "\n",
        encoding="utf-8",
    )
    duplicate_result = runner.invoke(
        app,
        ["lead", "compile", "--root", str(ws), "--artifact", str(duplicate_path)],
    )
    assert duplicate_result.exit_code == 1
    assert "lead_artifact_duplicate_run_id" in duplicate_result.stdout


def test_resolve_rejects_output_outside_workspace(ws: Path) -> None:
    scaffold_workspace(ws)
    outside_output = ws.parent / f"{ws.name}-resolved.json"
    result = runner.invoke(
        app,
        ["resolve", "--root", str(ws), "--task", "security review", "--output", str(outside_output)],
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
    assert "resolved_output_outside_workspace" in str(result.exception)
    assert not outside_output.exists()


def test_lead_compile_sanitizes_untrusted_markdown(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "markdown.json"
    artifact_path.write_text(
        json.dumps(
            valid_lead_artifact(
                claims=[
                    {
                        "claim": "<img src=https://attacker.invalid/pixel> ![leak](https://attacker.invalid/x)",
                        "verification_status": "unverified",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0
    markdown = (ws / ".sticky" / "current-state.md").read_text(encoding="utf-8")
    assert "<img" not in markdown
    assert "![leak]" not in markdown
    assert "&lt;img" in markdown


def test_lead_compile_rejects_secrets_without_echoing_them(ws: Path) -> None:
    scaffold_workspace(ws)
    secret = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
    artifact_path = ws / "secret.json"
    artifact_path.write_text(
        json.dumps(valid_lead_artifact(claims=[{"claim": secret, "verification_status": "unverified"}])),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "lead_artifact_secret_detected" in result.stdout
    assert secret not in result.stdout
    assert not (ws / ".sticky" / "current-state.json").exists()


def test_lead_compile_rejects_secret_in_auto_discovered_artifact(ws: Path) -> None:
    scaffold_workspace(ws)
    secret = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
    receipt_path = ws / "receipts" / "untrusted.jsonl"
    receipt_path.write_text(
        json.dumps(valid_lead_artifact(claims=[{"claim": secret, "verification_status": "unverified"}])) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])

    assert result.exit_code == 1
    assert "lead_artifact_secret_detected" in result.stdout
    assert secret not in result.stdout
    assert not (ws / ".sticky" / "current-state.json").exists()


def test_lead_compile_rejects_excessive_json_depth(ws: Path) -> None:
    scaffold_workspace(ws)
    nested: object = "value"
    for _ in range(40):
        nested = [nested]
    artifact_path = ws / "deep.json"
    artifact_path.write_text(
        json.dumps(valid_lead_artifact(claims=nested)),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])

    assert result.exit_code == 1
    assert "artifact_json_too_deep" in result.stdout
    assert not (ws / ".sticky" / "current-state.json").exists()


def test_receipt_ignores_resolved_pointer_outside_workspace(ws: Path) -> None:
    scaffold_workspace(ws)
    outside = ws.parent / f"{ws.name}-outside-resolved.json"
    outside.write_text(json.dumps({"task": "outside", "selected": []}), encoding="utf-8")
    pointer = ws / ".agentmd" / "last-resolved-path.txt"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(outside), encoding="utf-8")
    try:
        result = runner.invoke(app, ["receipt", "--root", str(ws)])
    finally:
        outside.unlink(missing_ok=True)

    assert result.exit_code == 0
    receipt_path = sorted((ws / "receipts").glob("*.jsonl"))[-1]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["task"] is None
    assert receipt["resolved_context_file"] is None


def test_receipt_does_not_hash_context_outside_workspace(ws: Path) -> None:
    scaffold_workspace(ws)
    outside = ws.parent / f"{ws.name}-outside-context.md"
    outside.write_text("sensitive outside content", encoding="utf-8")
    resolved = {
        "task": "tampered context",
        "selected": [{"path": f"../{outside.name}", "sha256": "0" * 64}],
    }
    resolved_path = ws / ".agentmd" / "resolved-context.json"
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(resolved), encoding="utf-8")
    try:
        result = runner.invoke(app, ["receipt", "--root", str(ws)])
    finally:
        outside.unlink(missing_ok=True)

    assert result.exit_code == 0
    receipt_path = sorted((ws / "receipts").glob("*.jsonl"))[-1]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["selected_context_files"] == []
    assert receipt["file_hashes"] == {}
    assert any(
        item.startswith("receipt_context_path_outside_workspace:")
        for item in receipt["validation"]["warnings"]
    )


def test_lead_compile_rejects_non_standard_json_numbers(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "non-standard.json"
    payload = json.dumps(valid_lead_artifact()).replace('"claims": []', '"claims": [NaN]')
    artifact_path.write_text(payload, encoding="utf-8")

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])

    assert result.exit_code == 1
    assert "non-standard JSON constant" in result.stdout
    assert not (ws / ".sticky" / "current-state.json").exists()


def test_lead_compile_sanitizes_untrusted_proof_markdown(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact = valid_lead_artifact(
        git_state={
            "available": True,
            "commit": "<img src=https://attacker.invalid/commit>",
            "dirty": True,
            "changed_files": ["![leak](https://attacker.invalid/changed)"],
            "untracked_files": ["<script>alert(1)</script>"],
            "reason": None,
        }
    )
    artifact_path = ws / "proof-markdown.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])

    assert result.exit_code == 0
    markdown = (ws / ".sticky" / "current-state.md").read_text(encoding="utf-8")
    assert "<img" not in markdown
    assert "<script>" not in markdown
    assert "![leak]" not in markdown
    assert "&lt;img" in markdown


def test_lead_compile_rejects_additional_provider_secrets(ws: Path) -> None:
    scaffold_workspace(ws)
    secrets = [
        "github_pat_" + "A" * 40,
        "sk-ant-" + "a" * 32,
        "AIza" + "A" * 35,
        "xoxb-" + "1234567890-ABCDEFGHIJ",
    ]
    for index, secret in enumerate(secrets):
        artifact_path = ws / f"provider-secret-{index}.json"
        artifact_path.write_text(
            json.dumps(valid_lead_artifact(run_id=f"secret-{index}", claims=[{"claim": secret, "verification_status": "unverified"}])),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
        assert result.exit_code == 1
        assert "lead_artifact_secret_detected" in result.stdout
        assert secret not in result.stdout


def _canonical_hash(value: dict, field: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_lead_warning_packet_and_receipt_bind_final_bytes(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "receipts" / "bad.jsonl").write_text("NOT JSON\n")
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])
    assert result.exit_code == 0, result.stdout
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    receipt = json.loads(next((ws / ".sticky/receipts").glob("*.jsonl")).read_text())
    assert packet["validation"]["warnings"]
    assert packet["deterministic_hash"] == _canonical_hash(packet, "deterministic_hash")
    assert receipt["current_state_hash"] == packet["deterministic_hash"]
    assert receipt["receipt_hash"] == _canonical_hash(receipt, "receipt_hash")


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-02-30T00:00:00Z", "2026-10-24", "2026-10-24T00:00:00", "2026-10-24T00:00:00+01:60", "2026-10-24T24:00:00Z", "2026-10-24T10:00:00.١Z"])
def test_lead_timestamp_validation_does_not_depend_on_optional_jsonschema_formats(ws: Path, timestamp: str) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact(timestamp=timestamp)))
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", "input.json"])
    assert result.exit_code == 1
    assert "schema_invalid" in result.stdout
    assert not (ws / ".sticky/current-state.json").exists()


@pytest.mark.parametrize("earlier,later", [
    ("2026-10-24T23:00:00+14:00", "2026-10-24T10:00:00Z"),
    ("2026-10-24T10:00:00.0000001Z", "2026-10-24T10:00:00.0000002Z"),
])
def test_lead_uses_chronological_instants_for_task_proof_and_loop_state(ws: Path, earlier: str, later: str) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps([
        valid_lead_artifact("z-earlier", timestamp=earlier, task="OLDER", open_loops=[{"text": "same loop", "status": "open"}]),
        valid_lead_artifact("a-later", timestamp=later, task="NEWER", open_loops=[{"text": "same loop", "status": "closed"}]),
    ]))
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", "input.json"])
    assert result.exit_code == 0, result.stdout
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    assert packet["task"] == "NEWER"
    assert packet["proof"]["run_id"] == "a-later"
    assert packet["current_state"]["open_loops"] == [{"text": "same loop", "status": "closed"}]
    assert "Close open loop" not in packet["current_state"]["next_clean_action"]


def test_lead_invalid_workspace_preserves_all_prior_outputs(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact()))
    args = ["lead", "compile", "--root", str(ws), "--artifact", "input.json"]
    assert runner.invoke(app, args).exit_code == 0
    before = {p: p.read_bytes() for p in (ws / ".sticky").rglob("*") if p.is_file()}
    (ws / "AGENTS.md").unlink()
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "lead_workspace_validation_failed" in result.stdout
    assert before == {p: p.read_bytes() for p in (ws / ".sticky").rglob("*") if p.is_file()}


def test_lead_preflights_receipt_directory_before_replacing_packet(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact()))
    args = ["lead", "compile", "--root", str(ws), "--artifact", "input.json"]
    assert runner.invoke(app, args).exit_code == 0
    before = [(ws / ".sticky" / name).read_bytes() for name in ["current-state.json", "current-state.md"]]
    # Ordinary in-workspace invalid destination; no blocked skill-root probe.
    shutil.rmtree(ws / ".sticky/receipts")
    (ws / ".sticky/receipts").write_text("not a directory")
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact(task="changed")))
    assert runner.invoke(app, args).exit_code == 1
    assert before == [(ws / ".sticky" / name).read_bytes() for name in ["current-state.json", "current-state.md"]]


def test_lead_rolls_back_packet_if_receipt_commit_fails(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact()))
    args = ["lead", "compile", "--root", str(ws), "--artifact", "input.json"]
    assert runner.invoke(app, args).exit_code == 0
    before = {p: p.read_bytes() for p in (ws / ".sticky").rglob("*") if p.is_file()}
    real_replace = Path.replace
    def fail_receipt_commit(path: Path, target: Path) -> Path:
        if Path(target).parent.name == "receipts":
            raise OSError("synthetic disk failure")
        return real_replace(path, target)
    monkeypatch.setattr(Path, "replace", fail_receipt_commit)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact(task="changed")))
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "prior output files preserved" in result.stdout
    assert before == {p: p.read_bytes() for p in (ws / ".sticky").rglob("*") if p.is_file()}


@pytest.mark.parametrize("nested", [False, True])
def test_lead_synthetic_secret_keys_never_reach_diagnostics(ws: Path, nested: bool) -> None:
    scaffold_workspace(ws)
    sentinel = "sk-" + "A" * 30  # Intentionally fake, nonworking security sentinel.
    data = valid_lead_artifact()
    if nested:
        data["claims"] = [{"claim": "ordinary", sentinel: "ordinary"}]
    else:
        data[sentinel] = "ordinary"
    (ws / "input.json").write_text(json.dumps(data))
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", "input.json"])
    assert result.exit_code == 1
    assert "lead_artifact_secret_detected" in result.stdout
    assert sentinel not in result.stdout
    assert not (ws / ".sticky").exists()


@pytest.mark.parametrize("status", ["closed", "completed", "done", "resolved", "cancelled", "canceled", "CLOSED"])
def test_lead_terminal_loops_not_recommended(ws: Path, status: str) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact(open_loops=[{"text": "finished", "status": status}, {"text": "work remains", "status": "open"}])))
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", "input.json"])
    assert result.exit_code == 0, result.stdout
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    assert packet["current_state"]["next_clean_action"] == "Close open loop: work remains"


def test_lead_no_input_is_honest_zero_evidence(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])
    assert result.exit_code == 0, result.stdout
    # Repeated compiles must not ingest their own receipts as phantom runs.
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])
    assert result.exit_code == 0
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    assert packet["artifacts_ingested"] == 0
    assert packet["artifacts"] == []
    assert packet["artifact_sources"] == []
    assert packet["proof"]["run_id"] is None
    assert packet["proof"]["timestamp"] is None
    assert packet["evidence_status"] == "no_evidence"
    assert "Collect a tool-run artifact" in packet["current_state"]["next_clean_action"]


def test_lead_missing_chain_predecessor_is_not_consumed(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "input.json").write_text(json.dumps(valid_lead_artifact()))
    args = ["lead", "compile", "--root", str(ws), "--artifact", "input.json"]
    assert runner.invoke(app, args).exit_code == 0
    assert runner.invoke(app, args).exit_code == 0
    first, second = sorted((ws / ".sticky/receipts").glob("*.jsonl"))
    first.unlink()
    assert runner.invoke(app, args).exit_code == 0
    receipt = json.loads(sorted((ws / ".sticky/receipts").glob("*.jsonl"))[-1].read_text())
    assert receipt["previous_receipt_hash"] is None
    assert any("receipt_history_chain_mismatch" in warning for warning in receipt["validation_warnings"])
    assert receipt["trust"]["current_observations"]  # Orphaned history must not suppress a real observation.


def _run_receipts(ws: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted((ws / "receipts").glob("*.jsonl"))]


def test_run_executes_real_context_hash_verification_without_shell(ws: Path) -> None:
    scaffold_workspace(ws)
    program = ws / "verify_context.py"
    program.write_text("""import hashlib, json, os
from pathlib import Path
manifest = json.loads(Path(os.environ['AGENTMD_CONTEXT_FILE']).read_text())
for entry in manifest['selected']:
    assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() == entry['sha256']
Path('verified.json').write_text(json.dumps({'selected': len(manifest['selected']), 'task': os.environ['AGENTMD_TASK']}))
print('context hashes verified')
""")
    task = "verify context; do not interpret $(anything)"
    args = ["run", "--root", str(ws), "--task", task, "--", sys.executable, str(program)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    verified = json.loads((ws / "verified.json").read_text())
    assert verified["selected"] > 0
    assert verified["task"] == task
    pre, post = _run_receipts(ws)
    assert pre["execution"]["status"] == "prepared"
    assert post["execution"]["status"] == "completed"
    assert post["execution"]["pre_receipt_hash"] == pre["receipt_hash"]
    assert post["execution"]["output"]["stdout"]["sha256"] == hashlib.sha256(("context hashes verified" + os.linesep).encode()).hexdigest()
    assert post["execution"]["context_manifest_sha256"] == hashlib.sha256((ws / ".agentmd/resolved-context.json").read_bytes()).hexdigest()
    assert post["receipt_hash"] == _canonical_hash(post, "receipt_hash")
    assert "verify_context.py" not in json.dumps(post)  # Actual argv is not logged.


@pytest.mark.parametrize("kind,expected_code,expected_status", [
    ("failed", 7, "failed"), ("launch", 127, "launch_failed"),
    ("timeout", 124, "timed_out"), ("output", 125, "output_limit_exceeded"),
])
def test_run_real_process_terminal_outcomes(ws: Path, kind: str, expected_code: int, expected_status: str) -> None:
    scaffold_workspace(ws)
    programs = {
        "failed": [sys.executable, "-c", "raise SystemExit(7)"],
        "launch": [str(ws / "nonexistent-executable")],
        "timeout": [sys.executable, "-c", "import time; time.sleep(20)"],
        "output": [sys.executable, "-c", "import sys; sys.stdout.write('X' * 200000)"],
    }
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "real process outcome", "--timeout", "0.2", "--output-limit", "1024", "--", *programs[kind]])
    assert result.exit_code == expected_code, result.stdout
    pre, post = _run_receipts(ws)
    assert post["execution"]["status"] == expected_status
    assert post["execution"]["launched"] is (kind != "launch")
    assert post["receipt_hash"] == _canonical_hash(post, "receipt_hash")
    if kind == "output":
        assert post["execution"]["output"]["stdout"]["hashed_bytes"] == 1024
        assert post["execution"]["output"]["stdout"]["complete"] is False


def test_run_invalid_workspace_never_launches_child(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "AGENTS.md").unlink()
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "must not launch", "--", sys.executable, "-c", "from pathlib import Path; Path('launched').touch()"])
    assert result.exit_code == 1
    assert not (ws / "launched").exists()
    assert _run_receipts(ws) == []


def test_run_requires_explicit_command_not_guessed_adapter(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "no guesses", "--adapter", "codex"])
    assert result.exit_code == 2
    assert _run_receipts(ws) == []


def test_run_does_not_echo_or_record_synthetic_output_or_argv(ws: Path) -> None:
    scaffold_workspace(ws)
    sentinel = "sk-" + "A" * 30  # Fake security sentinel, never a live credential.
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "privacy", "--", sys.executable, "-c", "import sys; print(sys.argv[1])", sentinel])
    assert result.exit_code == 0, result.stdout
    assert sentinel not in result.stdout
    assert all(sentinel not in json.dumps(receipt) for receipt in _run_receipts(ws))
    output = _run_receipts(ws)[-1]["execution"]["output"]["stdout"]
    assert output["sha256"] == hashlib.sha256((sentinel + os.linesep).encode()).hexdigest()


def test_run_failure_stays_failed_when_compiled_into_lead_state(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "actual failed work", "--", sys.executable, "-c", "raise SystemExit(7)"])
    assert result.exit_code == 7
    assert runner.invoke(app, ["lead", "compile", "--root", str(ws)]).exit_code == 0
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    assert packet["artifacts_ingested"] == 1  # Terminal receipt only, not prepared or compiler receipts.
    assert packet["artifacts"][0]["verification_status"] == "contradicted"
    assert packet["artifacts"][0]["execution"]["returncode"] == 7
    assert "Investigate local execution outcome: failed" in packet["current_state"]["next_clean_action"]
    assert runner.invoke(app, ["lead", "compile", "--root", str(ws)]).exit_code == 0
    again = json.loads((ws / ".sticky/current-state.json").read_text())
    assert again["artifacts_ingested"] == 1
    assert again["deterministic_hash"] == packet["deterministic_hash"]


def test_run_output_limit_detected_before_silent_child_timeout(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "bounded real output", "--timeout", "3", "--output-limit", "1024", "--", sys.executable, "-c", "import sys,time; sys.stdout.write('X'*1025); sys.stdout.flush(); time.sleep(20)"])
    assert result.exit_code == 125
    assert _run_receipts(ws)[-1]["execution"]["status"] == "output_limit_exceeded"


def test_run_reports_post_execution_workspace_failure(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "local workspace change", "--", sys.executable, "-c", "from pathlib import Path; Path('AGENTS.md').unlink()"])
    assert result.exit_code == 1
    terminal = _run_receipts(ws)[-1]
    assert terminal["execution"]["returncode"] == 0
    assert terminal["execution"]["workspace_validation_ok"] is False
    assert terminal["validation"]["ok"] is False


def test_bundle_failed_rollback_preserves_recovery_bytes(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cli.agentmd import _atomic_write_bundle
    old_path, second_path = ws / "old.txt", ws / "second.txt"
    old_path.write_text("previous contents")
    real_replace = Path.replace
    def fail_commit_and_rollback(path: Path, target: Path) -> Path:
        if target == second_path or path.suffix == ".bak":
            raise OSError("synthetic unavailable destination")
        return real_replace(path, target)
    monkeypatch.setattr(Path, "replace", fail_commit_and_rollback)
    with pytest.raises(ValueError, match="output_bundle_rollback_failed"):
        _atomic_write_bundle(ws, [(old_path, "new contents"), (second_path, "second")])
    backups = list(ws.glob("*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "previous contents"


def test_metadata_only_receipts_are_not_tool_run_evidence(ws: Path) -> None:
    scaffold_workspace(ws)
    assert runner.invoke(app, ["receipt", "--root", str(ws)]).exit_code == 0
    assert runner.invoke(app, ["lead", "compile", "--root", str(ws)]).exit_code == 0
    packet = json.loads((ws / ".sticky/current-state.json").read_text())
    assert packet["artifacts_ingested"] == 0
    assert packet["evidence_status"] == "no_evidence"
    assert any("artifact_metadata_not_run_evidence" in warning for warning in packet["validation"]["warnings"])


def test_lead_task_override_rejects_synthetic_secret_without_echo(ws: Path) -> None:
    scaffold_workspace(ws)
    sentinel = "sk-" + "A" * 30
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--task", sentinel])
    assert result.exit_code == 1
    assert sentinel not in result.stdout
    assert not (ws / ".sticky").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX signal lifecycle; Windows needs native interruption coverage")
def test_run_interrupt_terminates_real_child_and_writes_terminal_receipt(ws: Path) -> None:
    import signal
    import subprocess
    import time
    scaffold_workspace(ws)
    marker = ws / "child.pid"
    command = [sys.executable, "-m", "cli.agentmd", "run", "--root", str(ws), "--task", "interrupt local work", "--timeout", "10", "--", sys.executable, "-c", "import os,time; from pathlib import Path; Path('child.pid').write_text(str(os.getpid())); time.sleep(30)"]
    process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        child_pid = int(marker.read_text())
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 130, (stdout, stderr)
        terminal = _run_receipts(ws)[-1]
        assert terminal["execution"]["status"] == "interrupted"
        assert terminal["execution"]["launched"] is True
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_declared_discovered_artifact_still_requires_complete_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "receipts/incomplete.jsonl").write_text(json.dumps({"schema_version": "lead-artifact.v1"}) + "\n")
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])
    assert result.exit_code == 1
    assert "lead_artifact_schema_invalid" in result.stdout
    assert not (ws / ".sticky").exists()


def test_unhashed_execution_shaped_record_is_not_run_evidence(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "receipts/incomplete.jsonl").write_text(json.dumps({"execution": {}}) + "\n")
    result = runner.invoke(app, ["lead", "compile", "--root", str(ws)])
    assert result.exit_code == 1
    assert "lead_execution_receipt_invalid" in result.stdout
    assert not (ws / ".sticky").exists()


def test_run_nonfinite_timeout_rejected_before_any_launch(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["run", "--root", str(ws), "--task", "bounded run", "--timeout", "nan", "--", sys.executable, "-c", "from pathlib import Path; Path('launched').touch()"])
    assert result.exit_code == 2
    assert not (ws / "launched").exists()
    assert _run_receipts(ws) == []
    assert not (ws / ".agentmd").exists()
