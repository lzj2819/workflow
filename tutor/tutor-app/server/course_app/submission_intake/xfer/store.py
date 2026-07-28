"""IC-SI-02 材料存储端口抽象（owner：SI-STORE，实现归 backfill）。

本叶子只定义调用形状并注入抽象：
- write_stage：分片字节写入加密暂存区，返回暂存 material_ref；
- promote_to_final：合并后把暂存引用提升为正式 material_refs（唯一、幂等）；
- delete：幂等删除（重复删除为空操作），用于 abort/TTL 暂存清理。

目录布局、命名与加密参数归 SI-STORE（L2D-005 委托），本层不实现。
"""
from __future__ import annotations

from typing import Protocol, Sequence


class StorageIoError(Exception):
    """SI-STORE I/O 失败；错误码原样透传（IC-SI-02 既有错误分类），可重试。"""

    code = "STORAGE_IO_FAILED"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class MaterialStorePort(Protocol):
    """SI-STORE 端口协议（IC-SI-02）。"""

    def write_stage(
        self, *, session_id: str, seq: int, category: str, content: bytes
    ) -> str:
        """写暂存区，返回暂存 material_ref。"""
        ...

    def promote_to_final(
        self, *, session_id: str, staged_refs: Sequence[str]
    ) -> Sequence[str]:
        """暂存引用提升为正式 material_refs（同一 session 幂等）。"""
        ...

    def delete(self, material_ref: str) -> None:
        """幂等删除；重复删除为空操作。"""
        ...
