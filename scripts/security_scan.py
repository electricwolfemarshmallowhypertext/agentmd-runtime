from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MAX_SCAN_BYTES = 1_048_576
FULL_SHA = re.compile(r"^[a-f0-9]{40}$")
FORBIDDEN_REPO_PATHS = {
    ".githooks/post-merge",
    ".githooks/pre-commit",
    "canary.js",
}

PATTERNS = {
    "outbound_canary": re.compile(r"webhook[.]site", re.IGNORECASE),
    "encoded_shell_pipe": re.compile(r"base64\s+-d\s*\|\s*(?:ba)?sh", re.IGNORECASE),
    "download_to_shell": re.compile(r"(?:curl|wget)\b[^\r\n|]*\|\s*(?:ba)?sh", re.IGNORECASE),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in FORBIDDEN_REPO_PATHS:
            findings.append(f"{relative}:1: forbidden_repository_path")
        if path.resolve() == SELF or not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{relative}:{line}: {name}")
        if relative.startswith(".github/workflows/") and path.suffix in {".yml", ".yaml"}:
            for line_number, line_text in enumerate(text.splitlines(), start=1):
                match = re.search(r"\buses:\s*([^\s#]+)", line_text)
                if not match or match.group(1).startswith("./"):
                    continue
                action_ref = match.group(1)
                _, separator, ref = action_ref.rpartition("@")
                if not separator or not FULL_SHA.fullmatch(ref):
                    findings.append(f"{relative}:{line_number}: unpinned_action_ref")

    if findings:
        print("security scan: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("security scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
