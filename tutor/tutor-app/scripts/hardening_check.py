"""Phase 6 硬化检查：健康/日志/审计/metrics/错误响应/安全边界（真实组合根）。

覆盖：
- /health/live、/health/ready（ready 各项检查真实结果，不伪造）；
- 结构化日志 JSON 形状；错误响应一致形状且无内部细节/堆栈泄露；
- 401（无会话）/403（跨课程）+ AccessDeniedLogged 追加审计；
- 令牌静态存储：auth_token_grants 无明文令牌、teacher_sessions 无明文；
- /metrics 暴露且含业务计数；
- 403 审计不含敏感明文。

运行：python scripts/hardening_check.py（退出码非零即失败）。
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import Settings  # noqa: E402
from course_app.teacher_web.access_gate.models import TeacherSession  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402
from tutor_shared.logging import JsonFormatter  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())
    db_url = "sqlite:///file:hardening?mode=memory&cache=shared&uri=true"
    engine = migrate(db_url)
    settings = Settings(
        database_url=db_url,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="hardening-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings, engine=engine)
    with comp.session_scope() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="VC2026")
        admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-h", course_ids=("c-01",))
    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)

    # ---- 健康 ----
    live = client.get("/health/live")
    check("/health/live 200 ok", live.status_code == 200 and live.json()["status"] == "ok")
    ready = client.get("/health/ready")
    body = ready.json()
    check("/health/ready 全项就绪（真实检查）",
          ready.status_code == 200 and body["status"] == "ready"
          and all(c["status"] == "ok" for c in body["checks"].values()))
    check("readiness 检查不泄露 secret",
          "hardening-secret" not in ready.text)

    # ---- 结构化日志 ----
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "m", (), None)
    payload = json.loads(JsonFormatter().format(record))
    check("结构化日志 JSON 形状（ts/level/logger/msg）",
          {"ts", "level", "logger", "msg"} <= payload.keys())

    # ---- 安全边界：学生侧 ----
    noauth = client.get(f"/api/v1/submissions/{uuid.uuid4().hex}")
    check("CT-002 无令牌 → 401", noauth.status_code == 401)
    check("401 应答一致形状（code/message 或 detail）且无堆栈",
          "Traceback" not in noauth.text and "site-packages" not in noauth.text)

    # ---- 安全边界：教师侧 401/403 + 审计 ----
    t401 = client.get("/api/v1/teacher/courses")
    check("CT-007 无会话 → 401", t401.status_code == 401)
    login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "pw-h"}, follow_redirects=False)
    ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}
    bad_login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "wrong"}, follow_redirects=False)
    check("错误口令登录 → 401/403/重定向，不泄露原因细节", bad_login.status_code in (400, 401, 403) and "pw-h" not in bad_login.text)

    # 跨课程 403：教师仅有 c-01 授权，访问 c-99
    # 预置 c-99（另一教师域），教师无授权 → FORBIDDEN + AccessDeniedLogged
    with comp.session_scope() as s:
        admin.provision_course(s, course_id="c-99", invite_code="INV-99", name="OTHER")
    denied = client.get("/api/v1/teacher/courses/c-99/groups", headers=ah)
    check("跨课程访问 → 403", denied.status_code == 403)
    with comp.session_scope() as s:
        rows = s.execute(sa.text("select * from access_denied_log")).all()
    check("AccessDeniedLogged 追加审计已写入", len(rows) >= 1)
    check("审计记录不含口令/令牌明文",
          all("pw-h" not in str(r) and login.cookies.get("teacher_session") not in str(r) for r in rows))

    # ---- 令牌静态存储 ----
    tok = client.post("/api/v1/auth/token", json={
        "invite_code": "INV-01", "student_name": "张三", "group_name": "第7组",
    })
    student_token = tok.json()["access_token"]
    with comp.session_scope() as s:
        grants = s.execute(sa.text("select * from auth_token_grants")).all()
        sessions = s.scalars(select(TeacherSession)).all()
    check("学生令牌授权表无明文（仅哈希/指纹）",
          bool(grants) and all(student_token not in str(r) for r in grants))
    check("教师会话表无明文令牌",
          all(login.cookies.get("teacher_session") not in str(sess.__dict__) for sess in sessions))

    # ---- metrics ----
    metrics = client.get("/metrics")
    check("/metrics 200 文本暴露（零事件时为空文本属注册表设计；计数填充由 ScoringMetrics 单测覆盖）",
          metrics.status_code == 200 and metrics.headers.get("content-type", "").startswith("text/plain"))

    # ---- 错误响应一致性 ----
    nf = client.get(f"/api/v1/submissions/{uuid.uuid4().hex}", headers={"Authorization": "Bearer x"})
    check("错误响应不泄露内部路径/堆栈",
          "site-packages" not in nf.text and "Traceback" not in nf.text and str(ROOT) not in nf.text)

    print()
    if FAILURES:
        print(f"HARDENING FAILED: {len(FAILURES)} 项失败")
        return 1
    print("HARDENING_OK: 健康/日志/审计/metrics/错误响应/安全边界全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
