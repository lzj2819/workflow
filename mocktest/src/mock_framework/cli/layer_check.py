"""layer-check CLI command"""

import sys
from pathlib import Path

from mock_framework.layer_validation.validator import CrossLayerValidator
from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc


def layer_check_command(parent: str, children: list[str]) -> int:
    """Execute layer-check command."""
    logger = get_logger("cli.layer_check")
    logger.info("Checking architecture layer: %s", parent)

    # Load parent
    parent_doc = _load_arch_doc(parent)
    if not parent_doc:
        logger.error("Cannot load parent: %s", parent)
        return 1

    validator = CrossLayerValidator()

    # If no children are provided, validate the current layer only
    if not children:
        logger.info("No children provided, validating current layer only")
        report = validator.validate_current_layer(parent_doc)
    else:
        logger.info("Checking cross-layer consistency: %s → %s", parent, children)
        # Load children
        child_docs = []
        for child_path in children:
            child_doc = _load_arch_doc(child_path)
            if not child_doc:
                logger.error("Cannot load child: %s", child_path)
                return 1
            child_docs.append(child_doc)

        report = validator.validate(parent_doc, child_docs)

    if report.is_consistent:
        logger.info("✅ Layer check PASSED")
        return 0
    else:
        logger.error("❌ Found %d violations:", report.total_violations)
        for v in report.violations:
            logger.error("  [%s] %s: %s", v.severity, v.rule, v.detail)
        return 1


def _load_arch_doc(path: str) -> ArchDoc | None:
    """Load ArchDoc from file (placeholder — needs actual parser)"""
    from mock_framework.loader.arch_doc_parser import ArchDocParser
    try:
        return ArchDocParser().parse(path)
    except Exception:
        return None
