"""Canonical content hashing and validation for VeriLayer artifact envelopes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON exactly as the v0.3 content hash rule requires."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def content_sha256(path: Path) -> str:
    """Hash original bytes, except self-describing JSON omits its top-level hash."""
    raw = path.read_bytes()
    if path.suffix.lower() != ".json":
        return hashlib.sha256(raw).hexdigest()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON artifact must be an object for canonical content hashing")
    value = dict(value)
    value.pop("content_sha256", None)
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_content_hash(artifact: dict[str, Any], repository_root: Path) -> list[str]:
    """Return fail-closed errors for canonical content path/hash fields."""
    content_path = artifact.get("content_path")
    expected = artifact.get("content_sha256")
    if content_path is None and expected is None:
        return []
    if not isinstance(content_path, str) or not isinstance(expected, str):
        return ["content_path and content_sha256 must both be strings or both be null"]
    candidate = (repository_root / content_path).resolve()
    root = repository_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ["content_path escapes repository root"]
    if not candidate.is_file():
        return ["content_path does not identify a file"]
    actual = content_sha256(candidate)
    if actual != expected:
        return ["CONTENT_HASH_MISMATCH"]
    return []
