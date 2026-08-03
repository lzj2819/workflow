"""Phase 6 并发探针：30 并发提交（真实 PostgreSQL + 组合根 + TestClient）。

口径声明（非正式负载测试）：单进程 TestClient 驱动 30 线程，各自完成
auth-token + CT-001 提交；统计接收成功率与接收确认延迟分布。验证 NFR-002/003
的「30 并发、30 秒内接收确认」目标在本环境的可实现性证据，正式压测留待部署环境。

运行：python scripts/concurrency_probe.py（需 tutor-db-1 容器健康）。
"""
from __future__ import annotations

import os
import statistics
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from fastapi.testclient import TestClient  # noqa: E402

from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import Settings  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402

DB_URL = os.environ.get("DATABASE_URL", "postgresql://tutor:tutor@localhost:5432/tutor")
PROBE_COURSE = "probe-course"
THREADS = 30
RECEIPT_TARGET_SECONDS = 30


def main() -> int:
    migrate(DB_URL)
    data_dir = Path("data/concurrency-probe")
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=DB_URL,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="probe-secret",
        log_level="ERROR",
    )
    comp = build_composition(settings)
    with comp.session_scope() as s:
        admin.provision_course(s, course_id=PROBE_COURSE, invite_code="PROBE-INV", name="并发探针")
        admin.import_roster(
            s, course_id=PROBE_COURSE,
            entries=[{"student_name": f"学生{i:02d}", "group_name": "探针组"} for i in range(THREADS)],
        )
    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)

    results: list[dict] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        name = f"学生{i:02d}"
        try:
            tok = client.post("/api/v1/auth/token", json={
                "invite_code": "PROBE-INV", "student_name": name, "group_name": "探针组",
            })
            if tok.status_code != 200:
                with lock:
                    results.append({"i": i, "ok": False, "stage": "token", "code": tok.status_code})
                return
            headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
            start = time.monotonic()
            r = client.post("/api/v1/submissions", json={
                "submission_uuid": uuid.uuid4().hex,
                "invite_code": "PROBE-INV",
                "student_name": name,
                "group_name": "探针组",
                "assignment": "hw-probe",
                "material_chunks": [
                    {"category": "对话", "filename": "d.json", "content_ref": f"turns {i}"},
                    {"category": "代码", "filename": "a.py", "content_ref": f"print({i})"},
                ],
            }, headers=headers)
            elapsed = time.monotonic() - start
            with lock:
                results.append({
                    "i": i, "ok": r.status_code == 200 and r.json().get("status") == "received",
                    "stage": "submit", "code": r.status_code,
                    "status": r.json().get("status"), "elapsed": elapsed,
                })
        except Exception as exc:  # noqa: BLE001
            with lock:
                results.append({"i": i, "ok": False, "stage": "exception", "error": repr(exc)})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=RECEIPT_TARGET_SECONDS + 30)
    wall = time.monotonic() - t0

    ok = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    latencies = sorted(r["elapsed"] for r in ok)
    print(f"threads={THREADS} ok={len(ok)} failed={len(failed)} wall={wall:.2f}s")
    if latencies:
        print(f"receipt latency: min={latencies[0]:.2f}s p50={statistics.median(latencies):.2f}s max={latencies[-1]:.2f}s")
    for r in failed[:5]:
        print("failed sample:", r)
    alive = sum(1 for t in threads if t.is_alive())
    print(f"success_rate={len(ok) / THREADS * 100:.1f}% (target >=95%); alive_threads={alive}")
    if len(ok) / THREADS >= 0.95 and (not latencies or latencies[-1] <= RECEIPT_TARGET_SECONDS):
        print("PROBE_OK: 30 并发接收成功率与 30 秒确认目标达成（探针口径）")
        return 0
    print("PROBE_FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
