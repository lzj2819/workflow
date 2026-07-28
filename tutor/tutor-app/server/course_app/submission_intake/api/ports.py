"""SI-API 消费端口抽象（IC-SI-01 / IC-SI-03 冻结面，进程内注入，DD-004）。

- IC-SI-03 归属校验端口（owner SI-VERIFY/MOD-03）：测试中以 L01
  `course_roster.verifier.verify_membership` 进程内包装注入；每次实时调用，不缓存。
- IC-SI-01 上传会话端口（owner SI-XFER/L08，同波次未集成）：本文件只定义
  消费方冻结面（create/append/finalize 的单请求编排形态），真实实现由
  集成方接线；测试注入 stub。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

# ---- IC-SI-03 归属校验端口（owner：SI-VERIFY） ----


@dataclass(frozen=True)
class MembershipResult:
    """IC-SI-03 输出：verified + course_id? + reason?（语义同 CT-003）。"""

    verified: bool
    course_id: str | None = None
    reason: str | None = None


class MembershipVerifierPort(Protocol):
    """IC-SI-03：每次调用实时执行名单核对，不缓存通过结论（REQ-006）。

    实现名单不可用时应抛 `course_roster.errors.RosterUnavailableError`
    （由编排层按 LCD-001 做有限快速重试后映射 503 暂态失败）。
    """

    def __call__(
        self, *, invite_code: str, student_name: str, group_name: str
    ) -> MembershipResult: ...


# ---- IC-SI-01 上传会话端口（owner：SI-XFER / L08，冻结面） ----

#: 会话终态值域（L1 04-contracts-and-runtime.md IC-SI-01 state）。
XFER_STATE_MERGED = "merged"
XFER_STATE_FAILED_TERMINAL = "failed_terminal"

#: IC-SI-01 错误码（映射 CT-001 的 413/415）。
XFER_ERROR_SIZE_LIMIT = "SIZE_LIMIT_EXCEEDED"
XFER_ERROR_TYPE_NOT_ALLOWED = "TYPE_NOT_ALLOWED"


@dataclass(frozen=True)
class MaterialChunk:
    """CT-001 material_chunks[] 元素（分片协议细节由 L08 详细设计承载）。"""

    category: str
    filename: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    content_ref: str | None = None


@dataclass(frozen=True)
class TransferResult:
    """IC-SI-01 合并结果：state + material_refs[]? + failure_reason? + error_code?。"""

    state: str
    material_refs: tuple[str, ...] = field(default_factory=tuple)
    failure_reason: str | None = None
    error_code: str | None = None  # SIZE_LIMIT_EXCEEDED / TYPE_NOT_ALLOWED


class TransferSessionPort(Protocol):
    """IC-SI-01：submission_uuid 唯一会话；重复 ingest 复用既有会话结果（幂等）。

    实现归 L08 SI-XFER；本叶子只做端口注入，不做跨叶子真实接线。
    """

    def ingest(
        self,
        *,
        submission_uuid: str,
        declared_categories: Sequence[str],
        chunks: Sequence[MaterialChunk],
    ) -> TransferResult: ...
