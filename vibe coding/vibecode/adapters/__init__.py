"""C-owned adapters that normalize Mocktest and Leaf handoffs."""

from .mocktest_adapter import (
    allocate_strict_run_layout,
    build_mocktest_formal_input,
    build_mocktest_formal_result,
    evaluate_mocktest_gate,
)
from .leaf_adapter import adapt_proposed_children, prepare_leaf_formal_input

__all__ = [
    "adapt_proposed_children",
    "allocate_strict_run_layout",
    "build_mocktest_formal_input",
    "build_mocktest_formal_result",
    "evaluate_mocktest_gate",
    "prepare_leaf_formal_input",
]
