"""Bounded local Codex invocation for the Coding Executor."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def run_codex(
    *, prompt: str, workspace: Path, model: str, timeout_seconds: int = 600
) -> dict[str, Any]:
    """Ask the locally authenticated Codex CLI to edit one isolated workspace."""
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    executable = shutil.which("codex")
    if not executable:
        return {"status": "ERROR", "error_type": "CODEX_NOT_FOUND", "error_message": "codex is not on PATH"}

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [
                executable,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "--model",
                model,
                "-",
            ],
            cwd=workspace,
            input=prompt,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }
