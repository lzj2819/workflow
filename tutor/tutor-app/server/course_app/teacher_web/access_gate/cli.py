"""ACCESS-GATE 运维预置 CLI（v1 单教师，DD-004）。

用法：
    python -m course_app.teacher_web.access_gate.cli provision \
        --account teacher@example.com --course-id CS101 [--course-id CS102]

口令只经参数/环境传入：--password 或环境变量 ACCESS_GATE_PROVISION_PASSWORD；
库连接取 --database-url 或环境变量 DATABASE_URL。口令不回显、不写日志；
输出仅含 teacher_id 与授权课程列表。幂等：重复执行收敛到同一状态。
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from course_app.db import session_scope
from course_app.teacher_web.access_gate.service import AccessGateService

PASSWORD_ENV = "ACCESS_GATE_PROVISION_PASSWORD"
DATABASE_URL_ENV = "DATABASE_URL"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="access_gate",
        description="ACCESS-GATE 运维预置（教师账号 + 课程授权；幂等）",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    provision = sub.add_parser("provision", help="预置教师账号并授权课程（幂等）")
    provision.add_argument("--account", required=True, help="教师账号（登录名）")
    provision.add_argument(
        "--password",
        default=None,
        help=f"口令（缺省读环境变量 {PASSWORD_ENV}；不回显、不写日志）",
    )
    provision.add_argument(
        "--course-id",
        dest="course_ids",
        action="append",
        default=[],
        help="授权课程（可重复）",
    )
    provision.add_argument(
        "--database-url",
        default=None,
        help=f"库连接（缺省读环境变量 {DATABASE_URL_ENV}）",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "provision":
        password = args.password or os.environ.get(PASSWORD_ENV)
        if not password:
            parser.error(
                f"password required: pass --password or set {PASSWORD_ENV}"
            )
        database_url = args.database_url or os.environ.get(DATABASE_URL_ENV)
        if not database_url:
            parser.error(
                f"database url required: pass --database-url or set {DATABASE_URL_ENV}"
            )
        import sqlalchemy as sa  # noqa: PLC0415

        from course_app.db import normalize_db_url  # noqa: PLC0415

        engine = sa.create_engine(normalize_db_url(database_url))
        try:
            service = AccessGateService(
                session_factory=lambda: session_scope(engine)
            )
            teacher_id = service.provision_teacher(
                account=args.account,
                password=password,
                course_ids=args.course_ids,
            )
        finally:
            engine.dispose()
        # 输出不含口令/令牌明文。
        print(f"provisioned teacher_id={teacher_id}")
        for course_id in args.course_ids:
            print(f"granted course_id={course_id}")
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover - argparse.error 已 SystemExit


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
