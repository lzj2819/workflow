"""Check strict-run dependencies, protocol support, and obvious secret leaks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import re
import sys
from pathlib import Path


REQUIRED_IMPORTS = ("yaml", "pydantic", "jsonschema", "gherkin")
SECRET_PATTERNS = {
    "api_key": re.compile(r"(?i)(?:api[_-]?key\s*[:=]\s*[\"']?)(?:sk-|key-)[A-Za-z0-9_-]{16,}"),
    "bearer_token": re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._-]{20,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
SCAN_SUFFIXES = {".yaml", ".yml", ".json", ".jsonl", ".log", ".txt", ".md", ".env"}
IGNORED_PARTS = {".git", ".deps", "node_modules", ".venv", "__pycache__"}


def supports_dependencies(candidate: str, imports: tuple[str, ...] = REQUIRED_IMPORTS) -> bool:
    try:
        return (
            subprocess.run(
                [candidate, "-c", ";".join(f"import {name}" for name in imports)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        return False


def scan_sensitive_files(paths: list[Path]) -> tuple[list[str], list[dict[str, str]]]:
    scanned: list[str] = []
    findings: list[dict[str, str]] = []
    files: list[Path] = []
    for root in paths:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    for path in sorted(set(files)):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES and path.name != ".env.example":
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        scanned.append(str(path))
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": str(path), "kind": kind})
    return scanned, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument(
        "--required-imports",
        default=",".join(REQUIRED_IMPORTS),
        help="Comma-separated dependency imports used by environment checks",
    )
    parser.add_argument("--scan-path", action="append", default=[])
    args = parser.parse_args()
    root = Path(args.root).resolve()
    required_imports = tuple(
        item.strip() for item in args.required_imports.split(",") if item.strip()
    )
    skill_root = Path(__file__).resolve().parents[1]
    driver = skill_root / "main_session_strict_driver.py"
    candidates = [
        os.environ.get("VALIDATE_ARCH_PYTHON", ""),
        sys.executable,
        shutil.which("python") or "",
        r"E:\anaconda\ANACONDA\python.exe",
    ]
    python = next(
        (
            item
            for item in dict.fromkeys(candidates)
            if item and supports_dependencies(item, required_imports)
        ),
        "",
    )
    errors = []
    warnings = []
    if not driver.is_file():
        errors.append(f"missing validate-arch driver: {driver}")
    if not (root / "src" / "mock_framework").is_dir():
        errors.append(f"missing mock_framework package under: {root / 'src'}")
    if not python:
        errors.append(
            "no Python interpreter with required imports "
            + ", ".join(required_imports)
            + "; set VALIDATE_ARCH_PYTHON"
        )
    required_files = (
        root / "src" / "mock_framework" / "mocktest_protocol.py",
        skill_root / "run_subagent_skill.py",
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"missing required workflow file: {path}")
    scan_roots = [
        root / "config",
        root / ".env.example",
        root / "examples",
        root / ".work" / "validate-arch",
        root / "output",
        root / "user" / "report",
        root / "user" / "l2" / "l2-report",
    ]
    scan_roots.extend(Path(path).resolve() for path in args.scan_path)
    scanned, secret_findings = scan_sensitive_files(scan_roots)
    for finding in secret_findings:
        errors.append(f"sensitive material detected ({finding['kind']}): {finding['path']}")
    if not (root / ".env.example").is_file():
        warnings.append("missing .env.example")
    print(
        json.dumps(
            {
                "status": "ok" if not errors else "error",
                "root": str(root),
                "driver": str(driver),
                "python": python,
                "required_imports": list(required_imports),
                "secret_scan_file_count": len(scanned),
                "secret_findings": secret_findings,
                "warnings": warnings,
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
