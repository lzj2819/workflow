"""Assemble the deterministic Markdown view of the canonical PRD."""
from prd_flow.canonical import build_canonical_prd, render_canonical_prd


def assemble_prd(draft_content: dict) -> str:
    """Assemble a complete PRD from draft content.

    Args:
        draft_content: Dict mapping phase IDs to collected data.

    Returns:
        Complete PRD document as a string.
    """
    return render_canonical_prd(build_canonical_prd(draft_content))
