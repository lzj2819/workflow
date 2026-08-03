"""延迟计算器"""

from mock_framework.config import SimulatorConfig
from mock_framework.models.arch import NFR


class LatencyCalculator:
    """延迟计算器"""

    def __init__(self, config: SimulatorConfig, nfrs: list[NFR]):
        self.component_latency = config.latency_model.components
        self.network_overhead = config.latency_model.network_overhead
        self.concurrency_penalty = config.latency_model.concurrency_penalty
        self.total_nfr_target = self._extract_nfr_target(nfrs)

    def _extract_nfr_target(self, nfrs: list[NFR]) -> float:
        """从 NFR 提取延迟目标"""
        for nfr in nfrs:
            if "latency" in nfr.metric.lower() or "延迟" in nfr.metric:
                return nfr.threshold
        return 0.0

    def calculate(
        self, component: str, payload_size_kb: float = 0, concurrent_users: int = 1
    ) -> int:
        """计算延迟"""
        comp_config: dict = self.component_latency.get(component, {})
        base: int = int(comp_config.get("base_ms", 5))
        per_kb: float = float(comp_config.get("per_kb_ms", 0))
        network: int = int(self.network_overhead.get("intra_service_ms", 2))
        penalty: int = (concurrent_users // 100) * int(
            self.concurrency_penalty.get("per_100_concurrent_ms", 3)
        )
        return base + int(per_kb * payload_size_kb) + network + penalty
