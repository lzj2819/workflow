"""D-4 正式压测脚本：AC-NFR-001（规模）与 AC-NFR-002（30 并发 5 分钟窗口 ≥95%）。

目标：staging 真实 uvicorn 服务（localhost:18000）。
用法：python scripts/loadtest_nfr.py [--base http://localhost:18000] [--scenario nfr001|nfr002|all]

AC-NFR-001：100 学生/25 组规模下创建、查询、展示全通过。
AC-NFR-002：30 并发提交持续 5 分钟，成功接收率 ≥95%（AC-NFR-002-01 pass_rule）。
"""
from __future__ import annotations

import argparse
import statistics
import sys
import threading
import time
import uuid

import httpx

RECEIPT_TARGET = 30.0
NFR002_PASS_RATE = 0.95


def token_for(base: str, invite: str, name: str, group: str) -> str:
    r = httpx.post(f"{base}/api/v1/auth/token", json={
        "invite_code": invite, "student_name": name, "group_name": group,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def teacher_login(base: str) -> str:
    r = httpx.post(f"{base}/teacher/login",
                   data={"teacher_account": "teacher@staging.local", "password": "staging-pw"},
                   follow_redirects=False, timeout=30)
    return r.cookies.get("teacher_session")


def nfr001(base: str, course_id: str, invite: str) -> bool:
    print("=== AC-NFR-001：规模创建/查询/展示 ===")
    teacher = teacher_login(base)
    ah = {"Authorization": f"Bearer {teacher}"}
    # 规模数据已由 staging_provision 提供（100 学生/25 组）；抽 20 名学生提交
    ok = 0
    for i in range(1, 21):
        name = f"学生{i:03d}"
        tok = token_for(base, invite, name, f"第{(i - 1) % 25 + 1:02d}组")
        r = httpx.post(f"{base}/api/v1/submissions", json={
            "submission_uuid": uuid.uuid4().hex, "invite_code": invite,
            "student_name": name, "group_name": f"第{(i - 1) % 25 + 1:02d}组",
            "assignment": "hw-nfr001",
            "material_chunks": [{"category": "代码", "filename": "a.py", "content_ref": f"print({i})"}],
        }, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        if r.status_code == 200 and r.json().get("status") == "received":
            ok += 1
    print(f"submissions created: {ok}/20")
    courses = httpx.get(f"{base}/api/v1/teacher/courses", headers=ah, timeout=30)
    groups = httpx.get(f"{base}/api/v1/teacher/courses/{course_id}/groups", headers=ah, timeout=30)
    pres = httpx.post(f"{base}/api/v1/teacher/presentations", json={"group_ids": ["第01组"]}, headers=ah, timeout=30)
    print(f"teacher courses={courses.status_code} groups={groups.status_code} presentation={pres.status_code}")
    passed = ok == 20 and courses.status_code == 200 and groups.status_code == 200 and pres.status_code == 200
    print("NFR001:", "PASS" if passed else "FAIL")
    return passed


def nfr002(base: str, invite: str, window_seconds: int = 300, threads: int = 30) -> bool:
    print(f"=== AC-NFR-002：{threads} 并发 × {window_seconds}s 窗口 ===")
    results: list[bool] = []
    latencies: list[float] = []
    lock = threading.Lock()
    stop = time.monotonic() + window_seconds

    def worker(i: int) -> None:
        name = f"学生{(i % 100) + 1:03d}"
        group = f"第{(i % 25) + 1:02d}组"
        while time.monotonic() < stop:
            try:
                tok = token_for(base, invite, name, group)
                start = time.monotonic()
                r = httpx.post(f"{base}/api/v1/submissions", json={
                    "submission_uuid": uuid.uuid4().hex, "invite_code": invite,
                    "student_name": name, "group_name": group, "assignment": "hw-nfr002",
                    "material_chunks": [
                        {"category": "对话", "filename": "d.json", "content_ref": f"turns {i}"},
                        {"category": "代码", "filename": "a.py", "content_ref": f"print({i})"},
                    ],
                }, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
                elapsed = time.monotonic() - start
                with lock:
                    results.append(r.status_code == 200 and r.json().get("status") == "received")
                    latencies.append(elapsed)
            except Exception:
                with lock:
                    results.append(False)
            if time.monotonic() >= stop:
                break

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=window_seconds + 90)

    total = len(results)
    ok = sum(results)
    rate = ok / total if total else 0.0
    print(f"requests={total} ok={ok} rate={rate * 100:.2f}% (pass_rule >= {NFR002_PASS_RATE * 100}%)")
    if latencies:
        print(f"receipt latency p50={statistics.median(latencies):.2f}s max={max(latencies):.2f}s (target <= {RECEIPT_TARGET}s)")
    passed = total > 0 and rate >= NFR002_PASS_RATE and max(latencies) <= RECEIPT_TARGET
    print("NFR002:", "PASS" if passed else "FAIL")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:18000")
    parser.add_argument("--scenario", default="all", choices=["nfr001", "nfr002", "all"])
    parser.add_argument("--course-id", default="staging-course")
    parser.add_argument("--invite-code", default="STAGING-INV-2026")
    parser.add_argument("--window", type=int, default=300)
    args = parser.parse_args()

    ok = True
    if args.scenario in ("nfr001", "all"):
        ok = nfr001(args.base, args.course_id, args.invite_code) and ok
    if args.scenario in ("nfr002", "all"):
        ok = nfr002(args.base, args.invite_code, window_seconds=args.window) and ok
    print("LOADTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
