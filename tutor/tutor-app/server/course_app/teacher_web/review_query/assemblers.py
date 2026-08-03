"""L15 CMP-REVIEW-QUERY 装配器（CMP-RQ-* 四个局部 child）。

- ScopeAssembler（CMP-RQ-SCOPE-ASSEMBLER）：按课程/小组/学生选择装配层级视图，
  只读消费 M05-IC-02；不做权限判断、不读 MOD-02/03 源数据。
- SubmissionDetailAssembler（CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER）：装配材料引用、
  处理状态、评分字段、批注、最终等级和缺失标记，结果分支委托 OutcomeAdapter。
- OutcomeAdapter（CMP-RQ-OUTCOME-ADAPTER）：scored/scoring_failed 显式分支
  （LCD-RQ-002）；失败分支只输出 failure_reason/retry_record，**不伪造等级**。
- RetentionViewAdapter（CMP-RQ-RETENTION-VIEW-ADAPTER）：经 M05-IC-06 规范化
  deletion_batches[]；无批次返回空数组，端口失败整体失败（LCD-RQ-003）。

所有装配器只读、无副作用：不写 ST-READ-MODEL / ST-DELETION-BATCH / ReviewRecord。
"""
from __future__ import annotations

from typing import Any

from .errors import (
    NotFoundError,
    ReadModelUnavailableError,
    RetentionViewUnavailableError,
)
from .ports import (
    AuthorizedQueryContext,
    ReadModelQueryPort,
    ReadModelView,
    RetentionBatchView,
    RetentionViewPort,
)


def _read_model_query(port: ReadModelQueryPort, **selector: str | None) -> ReadModelView:
    """M05-IC-02 调用收敛：端口失败向上抛，由 Facade 统一转可重试失败。"""
    try:
        return port.query(**selector)
    except ReadModelUnavailableError:
        raise
    except Exception as exc:  # 端口实现的未声明失败同样视为读取失败
        raise ReadModelUnavailableError(str(exc)) from exc


class ScopeAssembler:
    """CMP-RQ-SCOPE-ASSEMBLER：课程/小组/学生/提交层级选择与装配。"""

    def __init__(self, read_model: ReadModelQueryPort) -> None:
        self._read_model = read_model

    def course_list(self, context: AuthorizedQueryContext) -> dict[str, Any]:
        """课程列表视图：courses[]（RQ-IC-001）。"""
        view = _read_model_query(self._read_model, course_id=context.course_id)
        if not view.courses:
            raise NotFoundError("no courses in authorized scope")
        return {"courses": [dict(c) for c in view.courses]}

    def group_list(
        self, context: AuthorizedQueryContext, course_id: str, group_id: str | None
    ) -> dict[str, Any]:
        """小组列表视图：groups[]（可选 group_id 过滤时附 students[]）。"""
        view = _read_model_query(
            self._read_model, course_id=course_id, group_id=group_id
        )
        if not view.groups:
            raise NotFoundError("no groups found for course")
        hierarchy: dict[str, Any] = {"groups": [dict(g) for g in view.groups]}
        if group_id is not None:
            hierarchy["students"] = [dict(s) for s in view.students]
        return hierarchy

    def student_detail(
        self, context: AuthorizedQueryContext, course_id: str, student_id: str
    ) -> dict[str, Any]:
        """学生详情视图：students[] + submissions[]（该学生的提交目录）。"""
        view = _read_model_query(
            self._read_model, course_id=course_id, student_id=student_id
        )
        if not view.students:
            raise NotFoundError("student not found in authorized scope")
        return {
            "students": [dict(s) for s in view.students],
            "submissions": [dict(s) for s in view.submissions],
        }


class OutcomeAdapter:
    """CMP-RQ-OUTCOME-ADAPTER：评分结果显式分支（纯函数式转换，RQ-IC-003）。

    - scored：输出 original_grade/dimension_rationales/teacher_suggestions/
      final_grade（读模型投影事实，含教师调整后留痕）。
    - scoring_failed：只输出 failure_reason + retry_record；
      **不输出任何等级字段**（无有效评分结果时不得伪造）。
    - 其他处理状态：不输出等级字段；failure_reason 存在时原样呈现。
    """

    def adapt(self, view: ReadModelView) -> dict[str, Any]:
        outcome: dict[str, Any] = {}
        if view.status == "scoring_failed":
            outcome["failure_reason"] = view.failure_reason
            outcome["retry_record"] = view.retry_record
            return outcome
        if view.status == "scored":
            outcome["original_grade"] = view.original_grade
            outcome["dimension_rationales"] = [
                dict(d) for d in view.dimension_rationales
            ]
            outcome["teacher_suggestions"] = list(view.teacher_suggestions)
            outcome["final_grade"] = view.final_grade
            return outcome
        # received/processing/upload_failed/rejected：无评分结果可展示。
        if view.failure_reason is not None:
            outcome["failure_reason"] = view.failure_reason
        if view.retry_record is not None:
            outcome["retry_record"] = view.retry_record
        return outcome


class SubmissionDetailAssembler:
    """CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER：提交详情完整字段装配（RQ-IC-002）。"""

    def __init__(
        self, read_model: ReadModelQueryPort, outcome_adapter: OutcomeAdapter
    ) -> None:
        self._read_model = read_model
        self._outcome_adapter = outcome_adapter

    def assemble(
        self, context: AuthorizedQueryContext, course_id: str, submission_id: str
    ) -> dict[str, Any]:
        """提交详情视图：submissions[]/material_refs/status/annotations/
        missing_marks + 结果分支字段。无匹配提交 → NOT_FOUND，不制造空对象。"""
        view = _read_model_query(
            self._read_model, course_id=course_id, submission_id=submission_id
        )
        if not view.submissions or view.status is None:
            raise NotFoundError("submission not found in authorized scope")
        detail: dict[str, Any] = {
            "submissions": [dict(s) for s in view.submissions],
            "material_refs": [dict(m) for m in view.material_refs],
            "status": view.status,
            "annotations": [dict(a) for a in view.annotations],
            "missing_marks": list(view.missing_marks),
        }
        detail.update(self._outcome_adapter.adapt(view))
        return detail


class RetentionViewAdapter:
    """CMP-RQ-RETENTION-VIEW-ADAPTER：deletion_batches[] 规范化（RQ-IC-004）。"""

    def __init__(self, retention_view: RetentionViewPort) -> None:
        self._retention_view = retention_view

    def assemble(
        self,
        course_id: str,
        batch_id: str | None = None,
        submission_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """有批次返回完整批次列表；无批次返回空数组；端口失败向上抛。"""
        try:
            batches = self._retention_view.list_batches(
                course_id=course_id, batch_id=batch_id, submission_id=submission_id
            )
        except RetentionViewUnavailableError:
            raise
        except Exception as exc:
            raise RetentionViewUnavailableError(str(exc)) from exc
        return [self._normalize(b) for b in batches]

    @staticmethod
    def _normalize(batch: RetentionBatchView) -> dict[str, Any]:
        """仅暴露 CT-007 出参字段（不泄露超出契约的批次字段）。"""
        return {
            "batch_id": batch.batch_id,
            "retention_due_at": batch.retention_due_at,
            "scope": batch.scope,
            "batch_status": batch.batch_status,
            "exclusions": list(batch.exclusions),
        }
