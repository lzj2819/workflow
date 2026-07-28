"""课程/邀请码运维预置工具（LCD-004，v1 非公共契约；幂等）。

用法：
    python -m course_app.course_roster.cli provision \
        --database-url sqlite:///roster.db \
        --course-id CS101 --invite-code INV-2026-CS101 \
        [--name "计算机导论"] [--course-end-time 2026-09-01T00:00:00+00:00]

DATABASE_URL 环境变量可替代 --database-url。重复执行为幂等（provision_course）。
前置：目标库已执行 0002_course_roster 迁移。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from course_app.course_roster.admin import provision_course
from course_app.course_roster.errors import ProvisioningConflictError


def _parse_dt(text: str | None) -> datetime | None:
    return None if text is None else datetime.fromisoformat(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="course_roster.cli", description="MOD-03 课程/邀请码运维预置（LCD-004，幂等）"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prov = sub.add_parser("provision", help="创建课程 + 邀请码（幂等）")
    prov.add_argument("--database-url", default=None, help="缺省读环境变量 DATABASE_URL")
    prov.add_argument("--course-id", required=True)
    prov.add_argument("--invite-code", required=True)
    prov.add_argument("--name", default=None)
    prov.add_argument("--course-end-time", default=None, help="ISO 8601，如 2026-09-01T00:00:00+00:00")
    args = parser.parse_args(argv)

    url = args.database_url or os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required (--database-url or env)", file=sys.stderr)
        return 2

    import sqlalchemy as sa  # noqa: PLC0415

    from course_app.db import normalize_db_url
    engine = sa.create_engine(normalize_db_url(url))
    try:
        with sa.orm.Session(engine) as session:
            try:
                course = provision_course(
                    session,
                    course_id=args.course_id,
                    invite_code=args.invite_code,
                    course_end_time=_parse_dt(args.course_end_time),
                    name=args.name,
                )
                payload = {
                    "course_id": course.course_id,
                    "invite_code": args.invite_code,
                    "name": course.name,
                    "course_end_time": course.course_end_time.isoformat()
                    if course.course_end_time
                    else None,
                    "status": "provisioned",
                }
                session.commit()
            except (ProvisioningConflictError, ValueError) as exc:
                session.rollback()
                print(f"provisioning rejected: {exc}", file=sys.stderr)
                return 1
    finally:
        engine.dispose()
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
