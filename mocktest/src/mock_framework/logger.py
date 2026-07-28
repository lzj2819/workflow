"""日志配置"""

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Rich 主题配置
theme = Theme(
    {
        "logging.level.debug": "dim cyan",
        "logging.level.info": "green",
        "logging.level.warning": "yellow",
        "logging.level.error": "bold red",
        "logging.level.critical": "bold white on red",
    }
)

console = Console(theme=theme)


def setup_logging(
    level: str = "INFO",
    format_type: str = "structured",
    output: str = "console",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """配置日志系统

    Args:
        level: 日志级别 DEBUG/INFO/WARNING/ERROR
        format_type: 格式类型 structured/simple
        output: 输出目标 console/file/both
        log_file: 日志文件路径（output 为 file/both 时必需）

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger("mock_framework")
    logger.setLevel(getattr(logging, level.upper()))

    # 清除已有 handler
    logger.handlers.clear()

    # 控制台输出
    if output in ("console", "both"):
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=True,
        )
        rich_handler.setLevel(getattr(logging, level.upper()))

        if format_type == "structured":
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            formatter = logging.Formatter("%(message)s")

        rich_handler.setFormatter(formatter)
        logger.addHandler(rich_handler)

    # 文件输出
    if output in ("file", "both") and log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, level.upper()))

        if format_type == "structured":
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        else:
            formatter = logging.Formatter("%(message)s")

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "mock_framework") -> logging.Logger:
    """获取 logger 实例"""
    return logging.getLogger(name)
