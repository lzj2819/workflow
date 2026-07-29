"""Write small, hash-addressable execution evidence inside a run directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def write_json_evidence(output_dir: Path, name: str, value: Any) -> dict[str, str]:
    if not name or Path(name).name != name or not name.endswith(".json"):
        raise ValueError("evidence name must be a single .json filename")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = (output_dir / name).resolve()
    try:
        path.relative_to(output_dir)
    except ValueError as exc:
        raise ValueError("evidence path escapes output directory") from exc
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    path.write_bytes(raw)
    return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}
