"""CMP-COURSE-ROSTER-ADMIN：Course 聚合维护、CT-013 名单导入、只读端口。

- CT-013 导入：逐项格式校验 + (姓名+小组) 去重 + conflicts[] 逐项报告 + 部分成功可见。
- 运维预置（LCD-004）：provision_course，幂等。
- CP-ROSTER-QUERY：每次调用直读当前已提交名单（LCD-002，无任何缓存）。
- CP-COURSE-ENDTIME：FLOW-011 实现形态（模块内只读端口，无网络契约）。

事务边界：本模块函数均在调用方提供的会话内 flush；提交由调用方
（单本地事务，03-state-and-data §3.1）负责。
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from course_app.course_roster.errors import (
    CourseNotFoundError,
    ProvisioningConflictError,
    RosterStoreError,
)
from course_app.course_roster.models import Course, InviteCode, RosterEntry


@dataclass(frozen=True)
class RosterQueryResult:
    """CP-ROSTER-QUERY 输出：课程解析结果 + 名单命中结果。"""

    course_id: str | None  # None = 邀请码未命中课程
    entry_found: bool


@dataclass
class ImportResult:
    """CT-013 import_result：imported_count / skipped_duplicates[] / conflicts[]。"""

    imported_count: int = 0
    skipped_duplicates: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)


def _require_non_empty(field_name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def provision_course(
    session,
    *,
    course_id: str,
    invite_code: str,
    course_end_time: datetime | None = None,
    name: str | None = None,
) -> Course:
    """运维预置（LCD-004，v1 非公共契约）：创建课程 + 邀请码；重复执行幂等。

    - 课程与邀请码均已存在且互相一致 → 幂等返回（可选字段仅补空，不覆盖）；
    - 课程已存在而邀请码未绑定 → 追加绑定（支持预置中断后重跑）；
    - 邀请码已映射到其他课程 → ProvisioningConflictError（P1 唯一映射）。
    """
    course_id = _require_non_empty("course_id", course_id)
    invite_code = _require_non_empty("invite_code", invite_code)

    course = session.get(Course, course_id)
    code = session.get(InviteCode, invite_code)
    if code is not None and code.course_id != course_id:
        raise ProvisioningConflictError(
            f"invite_code already mapped to course {code.course_id!r} (P1)"
        )
    if course is None:
        course = Course(course_id=course_id, name=name, course_end_time=course_end_time)
        session.add(course)
    else:
        if course.name is None and name is not None:
            course.name = name
        if course.course_end_time is None and course_end_time is not None:
            course.course_end_time = course_end_time
    if code is None:
        session.add(InviteCode(invite_code=invite_code, course_id=course_id))
    session.flush()
    return course


def _normalize_entry(raw: object) -> tuple[str | None, str | None, str | None]:
    """逐项格式校验（格式细则 delegated 至本层）：姓名/小组去空白后非空。"""
    if not isinstance(raw, Mapping):
        return None, None, "entry must be an object with student_name/group_name"
    name = raw.get("student_name")
    group = raw.get("group_name")
    if not isinstance(name, str) or not name.strip():
        return None, None, "student_name must be a non-empty string"
    if not isinstance(group, str) or not group.strip():
        return None, None, "group_name must be a non-empty string"
    return name.strip(), group.strip(), None


def import_roster(
    session,
    *,
    course_id: str,
    entries: Iterable[Mapping[str, object]],
) -> ImportResult:
    """CT-013 名单导入：逐项错误报告 + 去重 + 部分成功可见（单事务由调用方提交）。

    - 格式错误条目逐项进入 conflicts[]，不阻断其余条目（部分成功可见）；
    - 按 (student_name, group_name) 去重：对既有名单与同一文件内的重复条目
      均进入 skipped_duplicates[]（同一文件重复导入幂等，不产生重复条目）；
    - 课程不存在 → CourseNotFoundError（CT-013 NOT_FOUND）。
    """
    course = session.get(Course, course_id)
    if course is None:
        raise CourseNotFoundError(f"course {course_id!r} not found")
    existing = set(
        session.execute(
            sa.select(RosterEntry.student_name, RosterEntry.group_name).where(
                RosterEntry.course_id == course_id
            )
        )
    )
    seen = set(existing)
    result = ImportResult()
    for index, raw in enumerate(entries):
        name, group, error = _normalize_entry(raw)
        if error is not None:
            result.conflicts.append(
                {
                    "index": index,
                    "student_name": raw.get("student_name") if isinstance(raw, Mapping) else None,
                    "group_name": raw.get("group_name") if isinstance(raw, Mapping) else None,
                    "error": "FORMAT_ERROR",
                    "message": error,
                }
            )
            continue
        key = (name, group)
        if key in seen:
            result.skipped_duplicates.append(
                {"index": index, "student_name": name, "group_name": group, "reason": "DUPLICATE"}
            )
            continue
        seen.add(key)
        session.add(RosterEntry(course_id=course_id, student_name=name, group_name=group))
        result.imported_count += 1
    session.flush()
    return result


def query_roster(
    session,
    *,
    invite_code: str,
    student_name: str,
    group_name: str,
) -> RosterQueryResult:
    """CP-ROSTER-QUERY：每次调用直读当前已提交名单（P3/LCD-002，不提供、不允许缓存）。

    存储故障 → RosterStoreError（由 VERIFIER 映射为 ROSTER_UNAVAILABLE，不携带内部细节）。
    """
    try:
        code = session.get(InviteCode, invite_code)
        if code is None:
            return RosterQueryResult(course_id=None, entry_found=False)
        hit = session.scalar(
            sa.select(sa.func.count())
            .select_from(RosterEntry)
            .where(
                RosterEntry.course_id == code.course_id,
                RosterEntry.student_name == student_name,
                RosterEntry.group_name == group_name,
            )
        )
        return RosterQueryResult(course_id=code.course_id, entry_found=bool(hit))
    except SQLAlchemyError as exc:
        raise RosterStoreError("roster store query failed") from exc


def get_course_end_time(session, course_id: str) -> datetime | None:
    """CP-COURSE-ENDTIME（FLOW-011 实现形态，只读，天然幂等）。

    返回最新已提交 course_end_time；课程不存在返回 None（「未找到」语义，
    由消费方 MOD-05 按无课程处理）。
    """
    try:
        course = session.get(Course, course_id)
    except SQLAlchemyError as exc:
        raise RosterStoreError("roster store query failed") from exc
    return None if course is None else course.course_end_time
