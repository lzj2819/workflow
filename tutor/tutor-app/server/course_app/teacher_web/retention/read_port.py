"""M05-IC-06 读端口实现：L15 deletion_batches[] 视图接线（owner：RETENTION-GOVERNANCE）。

- 输出形状即 L15 `review_query.ports.RetentionBatchView` 冻结 dataclass；
- 只读天然幂等；读取失败抛 L15 RetentionViewUnavailableError（端口契约），
  调用方整体失败、不降级缺字段（LCD-RQ-003）。
"""
from __future__ import annotations

from ..review_query.errors import RetentionViewUnavailableError
from ..review_query.ports import RetentionBatchView
from .service import RetentionService


class RetentionViewPortAdapter:
    """L15 RetentionViewPort 形实现：委托 RetentionService.list_batches。"""

    def __init__(self, service: RetentionService) -> None:
        self._service = service

    def list_batches(
        self,
        *,
        course_id: str | None = None,
        batch_id: str | None = None,
        submission_id: str | None = None,
    ) -> tuple[RetentionBatchView, ...]:
        try:
            return self._service.list_batches(
                course_id=course_id, batch_id=batch_id, submission_id=submission_id
            )
        except RetentionViewUnavailableError:
            raise
        except Exception as exc:
            raise RetentionViewUnavailableError(str(exc)) from exc


__all__ = ["RetentionViewPortAdapter"]
