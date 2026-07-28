"""Submission 状态机（六态 + deleted；父层值域冻结，INV-2）。

合法迁移（SIC-INV-02）：
- ∅ → received / rejected / upload_failed（三条创建命令）
- received → processing（CT-004 task_persisted 确认，LCD-003）
- processing → scored / scoring_failed（CT-005 回写）
- 任一存续状态 → deleted（CT-012 清除）

终态（rejected / upload_failed / scored / scoring_failed / deleted）不可逆。
"""
from __future__ import annotations

from .errors import IllegalTransitionError

UPLOAD_FAILED = "upload_failed"
REJECTED = "rejected"
RECEIVED = "received"
PROCESSING = "processing"
SCORED = "scored"
SCORING_FAILED = "scoring_failed"
DELETED = "deleted"

STATUSES = (
    UPLOAD_FAILED,
    REJECTED,
    RECEIVED,
    PROCESSING,
    SCORED,
    SCORING_FAILED,
    DELETED,
)

#: ∅（未创建）可进入的三个创建终/始态。
CREATION_STATUSES = (RECEIVED, REJECTED, UPLOAD_FAILED)

#: CT-005 评分终态值域。
SCORING_OUTCOMES = (SCORED, SCORING_FAILED)

#: 终态：不可逆，只允许 → deleted 之外的迁移一律拒绝（deleted 自身亦终态）。
TERMINAL_STATUSES = (REJECTED, UPLOAD_FAILED, SCORED, SCORING_FAILED, DELETED)

#: 存续状态间合法迁移表（不含 ∅→创建态，创建路径由聚合 create 守卫）。
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    RECEIVED: frozenset({PROCESSING, DELETED}),
    PROCESSING: frozenset({SCORED, SCORING_FAILED, DELETED}),
    REJECTED: frozenset({DELETED}),
    UPLOAD_FAILED: frozenset({DELETED}),
    SCORED: frozenset({DELETED}),
    SCORING_FAILED: frozenset({DELETED}),
    DELETED: frozenset(),
}


def ensure_transition(current: str, target: str) -> None:
    """状态机守卫：非法迁移抛 ILLEGAL_TRANSITION，不产生任何副作用。"""
    if target not in LEGAL_TRANSITIONS.get(current, frozenset()):
        raise IllegalTransitionError(f"illegal transition: {current} -> {target}")
