"""Create run-scoped workspaces without allowing path traversal."""

from __future__ import annotations

import re
from pathlib import Path


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class WorkspaceError(ValueError):
    """A workspace identifier or path violates the Day 2 isolation boundary."""


def prepare_workspace(root: Path, run_id: str, node_id: str) -> Path:
    if not _SAFE_ID.fullmatch(run_id) or not _SAFE_ID.fullmatch(node_id):
        raise WorkspaceError("run_id and node_id must be safe relative identifiers")
    root = root.resolve()
    workspace = (root / run_id / node_id).resolve()
    try:
        workspace.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError("workspace escapes its configured root") from exc
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace
