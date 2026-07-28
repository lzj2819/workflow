"""结构化日志（JSON 行格式，stdlib logging）。

约定字段：ts（UTC ISO8601）、level、logger、msg；extra 以同名键并入。
禁止写入 secret 与学生材料内容（KD-003 审计合规）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

_CONFIGURED = False
_RESERVED = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root = logging.getLogger()
        root.handlers[:] = [handler]
        root.setLevel(level.upper())
        _CONFIGURED = True
    return logging.getLogger(name)
