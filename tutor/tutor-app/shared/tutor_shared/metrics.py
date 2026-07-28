"""基础 metrics 接口（进程内注册表 + 文本暴露格式）。

KPI 基线（06-deployment 基础级监控）：上传成功率、评分任务积压、
模型调用失败率、磁盘水位。本模块只提供计数/表盘原语与文本渲染；
具体指标登记在各自模块实现内（SM-001~003 统计由 backfill 落地）。
"""
from __future__ import annotations

import threading


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}

    def inc(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + amount

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def render_text(self) -> str:
        """Prometheus 风格纯文本暴露（无第三方依赖）。"""
        with self._lock:
            lines = [f"# TYPE {k} counter\n{k} {v}" for k, v in sorted(self._counters.items())]
            lines += [f"# TYPE {k} gauge\n{k} {v}" for k, v in sorted(self._gauges.items())]
        return "\n".join(lines) + ("\n" if lines else "")


registry = MetricsRegistry()
