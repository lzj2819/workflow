"""Structured, timeout-bounded pytest execution for later Coding work."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any


def run_pytest(
    *, python: str,
    workspace: Path,
    arguments: list[str] | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    workspace = workspace.resolve()
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [python, "-m", "pytest", *(arguments or ["-q"])],
            cwd=workspace,
            capture_output=True,
            text=True,
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
