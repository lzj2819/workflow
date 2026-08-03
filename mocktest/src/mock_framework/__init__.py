"""Mocktest v2 canonical architecture validation framework."""

__version__ = "2.0.0"
__author__ = "Workflow Team"

from .config import load_config
from .logger import setup_logging, get_logger

__all__ = ["load_config", "setup_logging", "get_logger"]
