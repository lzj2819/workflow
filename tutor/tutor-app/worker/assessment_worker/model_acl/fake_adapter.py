"""FakeVendorAdapter：把 FakeModelProvider 包装为 ACL 的可替换适配器。

fake 可追溯性（KD-001 / 任务卡）：本适配器仅供链路测试，
- 无网络、无密钥、无任何外部调用；
- 输出为确定性假数据，不表达任何真实评估能力；
- ``vendor == "fake"`` 且 ``is_fake is True``，绝不假扮真实供应商。
真实供应商适配器以同一协议（evaluate(request) -> dict）后续接入（DD-009）。
"""
from __future__ import annotations

from assessment_worker.model_provider import FakeModelProvider


class FakeVendorAdapter:
    """ACL 供应商适配器的 fake 实现（标注 fake 来源）。"""

    vendor = "fake"
    is_fake = True

    def __init__(self, provider: FakeModelProvider | None = None) -> None:
        self._provider = provider if provider is not None else FakeModelProvider()

    def evaluate(self, request: dict) -> dict:
        """委托 FakeModelProvider 产出满足 CT-010 schema 的确定性假应答。"""
        return self._provider.evaluate(request)
