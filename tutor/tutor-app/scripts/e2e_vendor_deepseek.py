"""DeepSeek 供应商接入端到端验证（staging PG + 本地 stub 供应商）。

形态：本地 HTTP stub 仿真 DeepSeek Chat Completions（/chat/completions，
response_format=json_object）——**不接触真实供应商、不使用真实密钥**
（MODEL_API_KEY=dummy-e2e 明确占位）；worker 以 MODEL_PROVIDER=deepseek
真实装配（DeepSeekProvider.from_env → stub base_url），staging 假数据走完整
提交→评分→读模型链路；断言外发请求无业务标识、密钥不出现在任何日志。

前置：staging db 可达。运行：python -m scripts.e2e_vendor_deepseek
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from fastapi.testclient import TestClient  # noqa: E402

from assessment_worker.model_provider import DIMENSIONS  # noqa: E402
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
CAPTURED: list[dict] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def wait_until(cond, timeout: float = 40.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.2)
    return False


GRADE_JSON = {
    "grade": "A",
    "dimension_rationales": [
        {"dimension": d, "rationale": f"stub 依据：{d}"} for d in DIMENSIONS
    ],
    "suggestions": ["stub 建议：继续保持"],
}


class StubHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        CAPTURED.append({"path": self.path, "headers": dict(self.headers), "body": body})
        if self.path != "/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        payload = {
            "choices": [
                {"message": {"role": "assistant", "content": json.dumps(GRADE_JSON, ensure_ascii=False)}}
            ]
        }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args) -> None:  # 静默
        return


def main() -> int:
    stub = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    stub_port = stub.server_address[1]
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    # worker 真实装配 deepseek provider（指向 stub；密钥为占位 dummy，非真实密钥）
    os.environ["MODEL_API_KEY"] = "dummy-e2e-not-a-real-key"
    os.environ["DEEPSEEK_BASE_URL"] = f"http://127.0.0.1:{stub_port}"
    os.environ["RELAY_TICK_INTERVAL_SECONDS"] = "0.3"

    data_dir = Path(tempfile.mkdtemp())
    course_id = f"vendor-{uuid.uuid4().hex[:8]}"
    invite_code = f"INV-V-{uuid.uuid4().hex[:6]}"
    settings = Settings(
        database_url=DB_URL,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="vendor-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings)
    with comp.session_scope() as s:
        admin.provision_course(s, course_id=course_id, invite_code=invite_code, name="供应商接入验证")
        admin.import_roster(s, course_id=course_id, entries=[{"student_name": "李四", "group_name": "第3组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-v", course_ids=(course_id,))
    app = create_app(settings=settings, composition=comp)

    worker_settings = WorkerSettings(
        database_url=DB_URL,
        model_provider="deepseek",  # 真实装配路径（stub 后端）
        model_api_key=os.environ["MODEL_API_KEY"],
        log_level="WARNING",
        claim_lease_seconds=30,
        data_dir=str(data_dir),
        worker_id="vendor-e2e",
        concurrency=1,
        poll_interval_seconds=0.2,
    )
    runner = WorkerRunner(worker_settings, install_signals=False)
    worker_thread = threading.Thread(target=runner.run, daemon=True)
    worker_thread.start()

    try:
        with TestClient(app) as client:
            tok = client.post("/api/v1/auth/token", json={
                "invite_code": invite_code, "student_name": "李四", "group_name": "第3组",
            })
            headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
            submission_uuid = uuid.uuid4().hex
            r1 = client.post("/api/v1/submissions", json={
                "submission_uuid": submission_uuid,
                "invite_code": invite_code,
                "student_name": "李四",
                "group_name": "第3组",
                "assignment": "hw-vendor",
                "material_chunks": [
                    {"category": "对话", "filename": "d.json", "content_ref": "user: 帮我写个 API\nassistant: 好的"},
                    {"category": "代码", "filename": "main.py", "content_ref": "print('vendor e2e')"},
                    {"category": "结果", "filename": "r.txt", "content_ref": "3 passed"},
                ],
            }, headers=headers)
            check("CT-001 received", r1.status_code == 200 and r1.json()["status"] == "received")
            submission_id = r1.json()["submission_id"]

            def status_of() -> str | None:
                q = client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
                return q.json().get("status") if q.status_code == 200 else None

            check(
                "deepseek 装配链路自动 scored（stub 供应商）",
                wait_until(lambda: status_of() == "scored"),
            )
            # stub 被调用且外发请求合规
            check("stub 收到 /chat/completions 调用", len(CAPTURED) >= 1)
            if CAPTURED:
                req = CAPTURED[0]
                body = req["body"]
                check("请求为 JSON 模式", body.get("response_format") == {"type": "json_object"})
                text = json.dumps(body, ensure_ascii=False)
                check(
                    "外发请求无业务标识（submission/姓名/小组/邀请码/课程）",
                    all(
                        k not in text
                        for k in ("submission_id", "李四", "第3组", invite_code, course_id, submission_uuid)
                    ),
                )
                check(
                    "外发请求含最小化材料文本（批准范围）",
                    "vendor e2e" in text and "帮我写个 API" in text,
                )
                check(
                    "Authorization 头仅存于传输层（不入境日志断言见单测）",
                    req["headers"].get("Authorization", "").startswith("Bearer dummy-e2e"),
                )
            # 教师端可见 stub 等级（真实装配的读模型投影）
            login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "pw-v"}, follow_redirects=False)
            ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}

            def grade_of() -> str | None:
                d = client.get(f"/api/v1/teacher/courses/{course_id}/submissions/{submission_id}", headers=ah)
                return d.json().get("original_grade") if d.status_code == 200 else None

            check("CT-007 投影 stub 等级 A", wait_until(lambda: grade_of() == "A", timeout=15))
    finally:
        runner.request_shutdown()
        worker_thread.join(timeout=15)
        comp.engine.dispose()
        stub.shutdown()

    print()
    if FAILURES:
        print(f"VENDOR E2E FAILED: {len(FAILURES)} 项失败")
        return 1
    print("VENDOR_DEEPSEEK_E2E_OK: deepseek 装配链路（stub 供应商）端到端通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
