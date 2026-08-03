"""Canonical dual-profile Architecture generation package."""

from .canonical import (
    ARTIFACT_SCHEMA_VERSION,
    ENVELOPE_SCHEMA_VERSION,
    SECTION_ORDER,
    build_canonical_architecture,
    canonical_json_text,
    render_canonical_architecture,
    validate_canonical_architecture,
    validate_parent_immutability,
)

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ENVELOPE_SCHEMA_VERSION",
    "SECTION_ORDER",
    "build_canonical_architecture",
    "canonical_json_text",
    "render_canonical_architecture",
    "validate_canonical_architecture",
    "validate_parent_immutability",
]
