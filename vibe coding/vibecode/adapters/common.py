"""Shared Day 2 production-adapter rules.

Adapters are intentionally fail-closed until their real module wiring is
implemented.  A controlled error is an executable integration boundary, not a
successful module result.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRODUCTION_MODULES = (
    "prd",
    "architecture",
    "gherkin",
    "mocktest",
    "leaf_gate",
    "coding",
    "backfill",
    "integration",
)

_ARTIFACT_TYPES = {
    "prd": "prd",
    "architecture": "architecture",
    "gherkin": "testcases",
    "mocktest": "mocktest",
    "leaf_gate": "leaf",
    "coding": "code",
    "backfill": "test_result",
    "integration": "test_result",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def controlled_error(
    *,
    module: str,
    input_path: Path,
    run_id: str,
    project_id: str,
    node_id: str,
    input_reference: str,
    parent_node_id: str | None = None,
    code: str = "MODULE_NOT_IMPLEMENTED",
    message: str | None = None,
) -> dict[str, Any]:
    """Return a formal, non-successful module result without inventing output."""
    if module not in PRODUCTION_MODULES:
        raise ValueError(f"unsupported production module: {module}")
    input_hash = sha256_file(input_path)
    text = message or f"Production adapter for {module} is not implemented in Day 2"
    return {
        "schema_version": "verilayer-artifact/v0.2",
        "run_id": run_id,
        "project_id": project_id,
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "artifact_id": f"{run_id}:{node_id}:{module}:result",
        "artifact_type": _ARTIFACT_TYPES[module],
        "status": "ERROR",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": "verilayer-production-adapter-skeleton",
        "input_artifacts": [input_reference],
        "requirement_ids": [],
        "content_path": None,
        "content_sha256": None,
        "error": {"category": "system", "code": code, "message": text},
        "module": module,
        "input_hash": input_hash,
        "output_artifacts": [],
        "output_hashes": {},
        "error_type": code,
        "error_message": text,
    }
