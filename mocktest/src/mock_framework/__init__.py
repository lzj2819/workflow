"""Mock测试框架 - 消费Gherkin场景进行架构验证"""

__version__ = "0.1.0"
__author__ = "Claude"

from .config import load_config
from .logger import setup_logging, get_logger

__all__ = ["load_config", "setup_logging", "get_logger"]
