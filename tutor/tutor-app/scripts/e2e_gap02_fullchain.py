"""GAP-02 全链 E2E（PostgreSQL）：CT-001 提交 → CT-004 → DU-3 常驻 worker → 评分 → DU-2 relay → 读模型。

关键性质：**全程无手工 tick/调用**——DU-2 lifespan 调度器驱动 relay（读模型投影、
received→processing 推进钩子），DU-3 WorkerRunner 常驻循环驱动 CT-004 消费、
认领执行（ICT-003 真实材料读取）与 CT-005 发布。

为什么必须 PostgreSQL：系统组件按设计各自管理独立小事务（多连接），SQLite
单写者库锁在嵌套事务流下必然自锁；PG 多连接真实隔离是组件的事务语义前提。
本脚本同时构成 worker 认领循环的真实并发验证（PG SKIP LOCKED）。

前置：staging db 可达（deploy/docker-compose.staging.yml 的 db 服务）。
运行：python -m scripts.e2e_gap02_fullchain
      （DATABASE_URL 可覆盖，默认 postgresql://tutor:tutor@localhost:18001/tutor_staging）
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from fastapi.testclient import TestClient  # noqa: E402

from assessment_worker.runner import WorkerRunner  # noqa: E402
from assessment_worker.settings import Settings as WorkerSettings  # noqa: E402
from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import Settings  # noqa: E402

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://tutor:tutor@localhost:18001/tutor_staging"
)

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def wait_until(cond, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())
    # 每轮独立课程与邀请码，避免与既有 staging 数据相互干扰（幂等可复跑）
    course_id = f"gap02-{uuid.uuid4().hex[:8]}"
    invite_code = f"INV-G2-{uuid.uuid4().hex[:6]}"
    settings = Settings(
        database_url=DB_URL,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="gap02-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings)
    with comp.session_scope() as s:
        admin.provision_course(s, course_id=course_id, invite_code=invite_code, name="GAP-02 全链")
        admin.import_roster(s, course_id=course_id, entries=[{"student_name": "张三", "group_name": "第7组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-g2", course_ids=(course_id,))

    os.environ["RELAY_TICK_INTERVAL_SECONDS"] = "0.3"  # DU-2 进程内调度器（测试加速）
    app = create_app(settings=settings, composition=comp)

    # DU-3 常驻 worker（真实 PG 引擎自建；并发 3 槽验证认领循环）
    worker_settings = WorkerSettings(
        database_url=DB_URL,
        model_provider="fake",
        model_api_key=None,
        log_level="WARNING",
        claim_lease_seconds=30,
        data_dir=str(data_dir),
        worker_id="gap02-worker",
        concurrency=3,
        poll_interval_seconds=0.2,
    )
    runner = WorkerRunner(worker_settings, install_signals=False)
    worker_thread = threading.Thread(target=runner.run, daemon=True)
    worker_thread.start()

    try:
        with TestClient(app) as client:
            tok = client.post("/api/v1/auth/token", json={
                "invite_code": invite_code, "student_name": "张三", "group_name": "第7组",
            })
            headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

            # 连发 3 份提交（并发认领验证面）
            submission_ids: list[tuple[str, str]] = []
            for i in range(3):
                submission_uuid = uuid.uuid4().hex
                r1 = client.post("/api/v1/submissions", json={
                    "submission_uuid": submission_uuid,
                    "invite_code": invite_code,
                    "student_name": "张三",
                    "group_name": "第7组",
                    "assignment": f"hw-gap02-{i}",
                    "material_chunks": [
                        {"category": "对话", "filename": "d.json", "content_ref": f"user: build api {i}\nassistant: ok"},
                        {"category": "代码", "filename": "main.py", "content_ref": f"print('hello gap02 {i}')"},
                        {"category": "结果", "filename": "r.txt", "content_ref": "tests passed"},
                    ],
                }, headers=headers)
                check(f"CT-001 received #{i}", r1.status_code == 200 and r1.json()["status"] == "received")
                submission_ids.append((submission_uuid, r1.json()["submission_id"]))

            # 全自动：无手工 tick——等待状态机推进 received → processing → scored
            def status_of(uid: str) -> str | None:
                q = client.get(f"/api/v1/submissions/{uid}", headers=headers)
                return q.json().get("status") if q.status_code == 200 else None

            check(
                "全部提交自动推进至 processing（D-3 钩子 + worker CT-004 确认）",
                wait_until(
                    lambda: all(status_of(u) in ("processing", "scored") for u, _ in submission_ids),
                    timeout=20,
                ),
            )
            check(
                "全部提交自动推进至 scored（worker 常驻循环全自动，PG 并发认领）",
                wait_until(
                    lambda: all(status_of(u) == "scored" for u, _ in submission_ids),
                    timeout=40,
                ),
            )

            # 读模型自动投影：教师端可读评分结果（无手工 relay）
            login = client.post(
                "/teacher/login",
                data={"teacher_account": "teacher@example.com", "password": "pw-g2"},
                follow_redirects=False,
            )
            ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}
            _, sid0 = submission_ids[0]

            def detail_grade() -> str | None:
                d = client.get(
                    f"/api/v1/teacher/courses/{course_id}/submissions/{sid0}", headers=ah
                )
                return d.json().get("original_grade") if d.status_code == 200 else None

            check(
                "CT-007 读模型自动投影 original_grade（CT-005→relay→projector）",
                wait_until(lambda: detail_grade() is not None, timeout=15),
            )
            detail = client.get(
                f"/api/v1/teacher/courses/{course_id}/submissions/{sid0}", headers=ah
            )
            body = detail.json()
            check(
                "CT-007 详情含五维依据与教师建议（ICT-003 真实材料链）",
                len(body.get("dimension_rationales") or []) == 5
                and bool(body.get("teacher_suggestions")),
            )
            # 无重复评分结果（认领互斥）
            with comp.session_scope() as s:
                import sqlalchemy as sa  # noqa: PLC0415

                dup = s.execute(
                    sa.text(
                        "select submission_id, count(*) c from scoring_results"
                        " group by submission_id having c > 1"
                    )
                ).all()
            check("scoring_results 无重复（PG 认领互斥）", dup == [])
    finally:
        runner.request_shutdown()
        worker_thread.join(timeout=15)
        comp.engine.dispose()
    check("worker 优雅关闭", not worker_thread.is_alive())

    print()
    if FAILURES:
        print(f"GAP-02 FULLCHAIN FAILED: {len(FAILURES)} 项失败")
        return 1
    print("GAP02_FULLCHAIN_OK: CT-001→CT-004→worker→评分→relay→读模型 全自动链路（PG）通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
