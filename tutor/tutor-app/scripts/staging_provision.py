"""D-4 staging 预置：迁移 + 规模课程数据（AC-NFR-001：100 学生 / 25 小组）+ 教师。

用法：python scripts/staging_provision.py [--students 100] [--groups 25]
环境：staging 已启动（deploy/docker-compose.staging.yml），DATABASE_URL 指向 staging db。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.settings import Settings  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402

DB_URL = os.environ.get("DATABASE_URL", "postgresql://tutor:tutor@localhost:18001/tutor_staging")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=100)
    parser.add_argument("--groups", type=int, default=25)
    parser.add_argument("--course-id", default="staging-course")
    parser.add_argument("--invite-code", default="STAGING-INV-2026")
    args = parser.parse_args()

    migrate(DB_URL)
    settings = Settings(
        database_url=DB_URL,
        data_dir=Path("data/staging"),
        contracts_dir=ROOT / "contracts",
        teacher_session_secret=os.environ.get("TEACHER_SESSION_SECRET", "staging-secret-change-me"),
        log_level="WARNING",
    )
    comp = build_composition(settings)
    entries = []
    for n in range(1, args.students + 1):
        # 轮转分组，与 loadtest_nfr 的「学生 i ∈ 第((i-1)%25)+1 组」口径一致
        entries.append({"student_name": f"学生{n:03d}", "group_name": f"第{(n - 1) % args.groups + 1:02d}组"})
    with comp.session_scope() as s:
        admin.provision_course(
            s, course_id=args.course_id, invite_code=args.invite_code, name="staging 压测课程"
        )
        result = admin.import_roster(s, course_id=args.course_id, entries=entries)
    comp.access_gate.provision_teacher(
        account="teacher@staging.local", password="staging-pw", course_ids=(args.course_id,)
    )
    print(f"provisioned: course={args.course_id} students={len(entries)} groups={args.groups} imported={result.imported_count}")
    print("teacher=teacher@staging.local (password via env only in real use)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
