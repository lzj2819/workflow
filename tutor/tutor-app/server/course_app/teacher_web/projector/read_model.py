"""ProjectorReadModel：M05-IC-02 双侧面读端口实现（L15 query() / L16 group_view()）。

- 输出形状与 L15 `review_query.ports.ReadModelView`、L16
  `presentation.ports.GroupReadView/SubmissionView/MaterialRef/AnnotationView`
  冻结 dataclass 完全一致（Wave 3 StubReadModel 已验证兼容口径；本实现直接
  复用两侧端口 dataclass，不复制字段定义）；
- 只读天然幂等；短暂滞后按最终一致接受；读取失败抛对应侧面的
  ReadModelUnavailableError（L15 / L16 各自错误类型），不降级缺字段；
- 已清除（CT-012/CT-014）提交不出现于任何侧面（教师端不再可读，CT-012
  side_effects）；
- material_refs：消费契约集（CT-005/CT-006/CT-012/CT-014 + M05-IC-05）不携带
  材料引用明细（CT-006 仅 missing_items），读模型按空投影并如实返回；
  missing_marks 由 CT-006 missing_items 投影供给。
"""
from __future__ import annotations

from typing import Callable, ContextManager

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..presentation.errors import ReadModelUnavailableError as L16ReadModelError
from ..presentation.ports import (
    AnnotationView,
    GroupReadView,
    MaterialRef,
    SubmissionView,
)
from ..review_query.errors import ReadModelUnavailableError as L15ReadModelError
from ..review_query.ports import ReadModelView
from .models import (
    ProjectionCheckpoint,
    RmCourse,
    RmGroup,
    RmStudent,
    RmSubmission,
)

SessionScopeFactory = Callable[[], ContextManager[Session]]


class ProjectorReadModel:
    """M05-IC-02 读模型查询端口实现（owner：CMP-READMODEL-PROJECTOR）。"""

    def __init__(self, session_factory: SessionScopeFactory) -> None:
        self._session_factory = session_factory

    # ---- L15 侧面：ReadModelQueryPort.query() ----

    def query(
        self,
        *,
        course_id: str | None = None,
        group_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> ReadModelView:
        """按选择范围过滤的读模型视图（student_id 即学生姓名身份键）。"""
        try:
            with self._session_factory() as session:
                courses = self._courses(session, course_id)
                groups = self._groups(session, course_id, group_id)
                students = self._students(session, course_id, group_id, student_id)
                rows = self._submissions(
                    session,
                    course_id=course_id,
                    group_id=group_id,
                    student_id=student_id,
                    submission_id=submission_id,
                )
                submissions = tuple(self._submission_dict(r) for r in rows)
                top: dict = {}
                if submission_id and rows:
                    row = rows[0]
                    top = {
                        "material_refs": tuple(
                            dict(m) for m in (row.material_refs or [])
                        ),
                        "status": row.status,
                        "original_grade": row.original_grade,
                        "dimension_rationales": tuple(
                            dict(d) for d in (row.dimension_rationales or [])
                        ),
                        "teacher_suggestions": tuple(row.teacher_suggestions or ()),
                        "annotations": tuple(
                            dict(a) for a in (row.annotations or [])
                        ),
                        "final_grade": row.final_grade,
                        "missing_marks": tuple(row.missing_items or ()),
                        "failure_reason": row.failure_reason,
                        "retry_record": (
                            dict(row.retry_record) if row.retry_record else None
                        ),
                    }
                return ReadModelView(
                    courses=courses,
                    groups=groups,
                    students=students,
                    submissions=submissions,
                    **top,
                )
        except L15ReadModelError:
            raise
        except Exception as exc:
            raise L15ReadModelError(str(exc)) from exc

    # ---- L16 侧面：ReadModelQueryPort.group_view() ----

    def group_view(
        self,
        *,
        group_id: str,
        course_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> GroupReadView | None:
        """小组读模型视图；小组无记录返回 None（冻结端口语义）。"""
        try:
            with self._session_factory() as session:
                group = self._find_group(session, group_id, course_id)
                if group is None:
                    return None
                rows = self._submissions(
                    session,
                    course_id=group.course_id,
                    group_id=group.group_id,
                    student_id=student_id,
                    submission_id=submission_id,
                )
                views = tuple(self._submission_view(r) for r in rows)
                students = self._students(
                    session, group.course_id, group.group_id, student_id
                )
                return GroupReadView(
                    course_id=group.course_id,
                    group_id=group.group_id,
                    read_model_version=self._read_model_version(session),
                    students=students,
                    submissions=views,
                )
        except L16ReadModelError:
            raise
        except Exception as exc:
            raise L16ReadModelError(str(exc)) from exc

    # ---- 查询内部 ----

    @staticmethod
    def _courses(session: Session, course_id: str | None) -> tuple[dict, ...]:
        stmt = select(RmCourse).order_by(RmCourse.course_id)
        if course_id is not None:
            stmt = stmt.where(RmCourse.course_id == course_id)
        return tuple(
            {"course_id": row.course_id}
            for row in session.scalars(stmt).all()
        )

    @staticmethod
    def _groups(
        session: Session, course_id: str | None, group_id: str | None
    ) -> tuple[dict, ...]:
        stmt = select(RmGroup).order_by(RmGroup.course_id, RmGroup.group_id)
        if course_id is not None:
            stmt = stmt.where(RmGroup.course_id == course_id)
        if group_id is not None:
            stmt = stmt.where(RmGroup.group_id == group_id)
        return tuple(
            {"course_id": row.course_id, "group_id": row.group_id}
            for row in session.scalars(stmt).all()
        )

    @staticmethod
    def _students(
        session: Session,
        course_id: str | None,
        group_id: str | None,
        student_id: str | None,
    ) -> tuple[dict, ...]:
        stmt = select(RmStudent).order_by(
            RmStudent.course_id, RmStudent.group_id, RmStudent.student_name
        )
        if course_id is not None:
            stmt = stmt.where(RmStudent.course_id == course_id)
        if group_id is not None:
            stmt = stmt.where(RmStudent.group_id == group_id)
        if student_id is not None:
            stmt = stmt.where(RmStudent.student_name == student_id)
        return tuple(
            {
                "course_id": row.course_id,
                "group_id": row.group_id,
                "student_name": row.student_name,
            }
            for row in session.scalars(stmt).all()
        )

    @staticmethod
    def _submissions(
        session: Session,
        *,
        course_id: str | None,
        group_id: str | None,
        student_id: str | None,
        submission_id: str | None,
    ) -> list[RmSubmission]:
        stmt = select(RmSubmission).order_by(
            RmSubmission.received_at, RmSubmission.submission_id
        )
        if course_id is not None:
            stmt = stmt.where(RmSubmission.course_id == course_id)
        if group_id is not None:
            stmt = stmt.where(RmSubmission.group_id == group_id)
        if student_id is not None:
            stmt = stmt.where(RmSubmission.student_name == student_id)
        if submission_id is not None:
            stmt = stmt.where(RmSubmission.submission_id == submission_id)
        return list(session.scalars(stmt).all())

    @staticmethod
    def _find_group(
        session: Session, group_id: str, course_id: str | None
    ) -> RmGroup | None:
        stmt = (
            select(RmGroup)
            .where(RmGroup.group_id == group_id)
            .order_by(RmGroup.course_id)
        )
        if course_id is not None:
            stmt = stmt.where(RmGroup.course_id == course_id)
        return session.scalars(stmt).first()

    @staticmethod
    def _read_model_version(session: Session) -> str:
        position = session.scalar(
            select(func.coalesce(func.max(ProjectionCheckpoint.position), 0))
        )
        return f"pos:{position or 0}"

    # ---- 行 → 端口形状 ----

    @staticmethod
    def _submission_dict(row: RmSubmission) -> dict:
        """L15 submissions[] 元素（与 Wave 3 兼容口径一致的字典形状）。"""
        return {
            "submission_id": row.submission_id,
            "course_id": row.course_id,
            "student_name": row.student_name,
            "group_name": row.group_id,
            "status": row.status,
            "original_grade": row.original_grade,
            "final_grade": row.final_grade,
            "annotations": [dict(a) for a in (row.annotations or [])],
            "failure_reason": row.failure_reason,
            "retry_record": dict(row.retry_record) if row.retry_record else None,
        }

    @staticmethod
    def _submission_view(row: RmSubmission) -> SubmissionView:
        """L16 SubmissionView（冻结 dataclass 形状）。"""
        return SubmissionView(
            submission_id=row.submission_id,
            status=row.status,
            student_id=row.student_name or None,
            material_refs=tuple(
                MaterialRef(category=m["category"], ref=m["ref"])
                for m in (row.material_refs or [])
            ),
            original_grade=row.original_grade,
            final_grade=row.final_grade,
            dimension_rationales=tuple(
                dict(d) for d in (row.dimension_rationales or [])
            ),
            teacher_suggestions=tuple(row.teacher_suggestions or ()),
            annotations=tuple(
                AnnotationView(
                    operator=a.get("operator", ""),
                    excerpt=a.get("text", ""),
                    updated_at=a.get("updated_at"),
                )
                for a in (row.annotations or [])
            ),
            missing_marks=tuple(row.missing_items or ()),
            submitted_at=(
                row.received_at.isoformat() if row.received_at else None
            ),
        )


__all__ = ["ProjectorReadModel"]
