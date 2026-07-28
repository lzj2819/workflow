"""CMP-PRES-GENERATION-COORDINATOR：CT-009 唯一编排入口（LCD-PRES-001）。

编排顺序（M05-FLOW-004 / PRES-FLOW-001）：
ACCESS-GATE 授权上下文 → 幂等命中检查 → M05-IC-02 读装配 → 课程范围
复核（FORBIDDEN）→ 资格判定（NO_AVAILABLE_SUBMISSION，持久化前终止）→
区块装配（PRES-IC-02）→ 快照写入（PRES-IC-03）→ 输出适配（PRES-IC-04）。

幂等命中先于读模型读取：相同参数 + 同一时间窗直接返回最新快照，
快照内容不随读模型后续变化而改变（一次性快照语义）。
"""
from __future__ import annotations

from collections.abc import Callable

from .assembler import assemble_block
from .errors import ForbiddenError, NoAvailableSubmissionError
from .missing_marks import evaluate_group
from .ports import AccessGatePort, AuthContext, ReadModelQueryPort
from .store import (
    Snapshot,
    SnapshotStore,
    default_time_window,
    generation_key,
    normalize_group_ids,
)


class PresentationCoordinator:
    """承接已授权 CT-009，编排一次生成生命周期（无持久状态所有权）。"""

    def __init__(
        self,
        *,
        read_model: ReadModelQueryPort,
        store: SnapshotStore,
        time_window_fn: Callable[[], str] = default_time_window,
    ) -> None:
        self._read_model = read_model
        self._store = store
        self._time_window_fn = time_window_fn

    @staticmethod
    def _check_scope(auth: AuthContext, course_ids: tuple[str, ...]) -> None:
        outside = sorted(set(course_ids) - set(auth.course_ids))
        if outside:
            raise ForbiddenError(
                f"教师 {auth.teacher_id} 对课程 {', '.join(outside)} 无授权范围"
            )

    def generate(
        self, *, auth: AuthContext, group_ids: list[str]
    ) -> Snapshot:
        """生成或幂等命中展示视图快照；返回 Snapshot 供输出适配。"""
        normalized = normalize_group_ids(group_ids)
        key = generation_key(
            teacher_id=auth.teacher_id,
            group_ids=normalized,
            time_window=self._time_window_fn(),
        )
        hit = self._store.find_latest(key)
        if hit is not None:
            # 幂等命中仍复核课程授权范围（FORBIDDEN 语义不因命中放宽）。
            self._check_scope(auth, hit.course_ids)
            return hit

        evaluations = [
            evaluate_group(
                group_id=gid, view=self._read_model.group_view(group_id=gid)
            )
            for gid in normalized
        ]
        self._check_scope(
            auth,
            tuple(ev.view.course_id for ev in evaluations if ev.view is not None),
        )
        rejected = [ev for ev in evaluations if not ev.eligible]
        if rejected:
            reasons = "; ".join(ev.reason or ev.group_id for ev in rejected)
            raise NoAvailableSubmissionError(
                f"选定小组中存在无可用提交的小组，已整体拒绝：{reasons}"
            )

        blocks = [assemble_block(ev) for ev in evaluations]
        versions = sorted(
            {ev.view.read_model_version for ev in evaluations if ev.view is not None}
        )
        return self._store.save(
            key=key,
            teacher_id=auth.teacher_id,
            course_ids=tuple(
                sorted(
                    {ev.view.course_id for ev in evaluations if ev.view is not None}
                )
            ),
            group_ids=normalized,
            blocks=blocks,
            source_read_model_version=",".join(versions) or None,
        )


__all__ = [
    "AccessGatePort",
    "AuthContext",
    "PresentationCoordinator",
    "ReadModelQueryPort",
]
