"""Wave 1 跨叶子集成冒烟（L01 + L02 + L03，SQLite 单库）。

链路：L01 预置课程/导入名单/归属校验 → L02 幂等创建提交（received，同事务 CT-004/CT-006 入队）
→ received→processing → L03 消费 CT-004（幂等）→ 认领 → 完成（CT-005 scored 入队）
→ L02 应用终态（scored，重复应用幂等）。

运行：python scripts/smoke_wave1.py（从 tutor-app 根；零参数；退出码非零即失败）。
"""
from __future__ import annotations

import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.models import OrchestratorBase  # noqa: E402
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.course_roster import admin, verifier  # noqa: E402
from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.submission_intake.core.integrity import MaterialMetadata  # noqa: E402
from course_app.submission_intake.core.models import Base as CoreBase  # noqa: E402
from course_app.submission_intake.core.service import SubmissionCoreService  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


class StubMetadataReader:
    """SI-STORE 元数据端口 stub（实现归 backfill）：按 ref 后缀返回类别。"""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        return MaterialMetadata(
            material_ref=material_ref,
            category=self._mapping[material_ref],
            size_bytes=128,
            declared=True,
        )


def main() -> int:
    engine = create_engine("sqlite:///:memory:")
    for base in (RosterBase, CoreBase, OrchestratorBase):
        base.metadata.create_all(engine)
    sm = sessionmaker(bind=engine)

    @contextmanager
    def tx():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---- L01：预置课程 + 导入名单 + 归属校验 ----
    with tx() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="Vibe Coding 2026")
        result = admin.import_roster(
            s, course_id="c-01",
            entries=[{"student_name": "张三", "group_name": "第7组"}],
        )
        check("L01 roster import imported_count=1", result.imported_count == 1)
        outcome = verifier.verify_membership(
            s, invite_code="INV-01", student_name="张三", group_name="第7组"
        )
        check("L01 verify_membership verified", outcome.verified is True and outcome.course_id == "c-01")
        bad = verifier.verify_membership(s, invite_code="NOPE", student_name="张三", group_name="第7组")
        check("L01 invalid invite → verified=False + reason", bad.verified is False and bool(bad.reason))
    with tx() as s:
        again = admin.import_roster(
            s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}]
        )
        check("L01 roster reimport idempotent (skipped_duplicates>=1)", len(again.skipped_duplicates) >= 1)

    # ---- L02：幂等创建（received + 同事务 CT-004/CT-006） ----
    outbox = InMemoryOutboxStore()
    reader = StubMetadataReader({"m-dialog": "对话", "m-code": "代码"})
    core = SubmissionCoreService(session_factory=tx, outbox_store=outbox, metadata_reader=reader)
    submission_uuid = uuid.uuid4().hex
    created = core.confirm_received(
        submission_uuid=submission_uuid,
        course_id="c-01",
        assignment="hw-01",
        student_name="张三",
        group_name="第7组",
        material_refs=["m-dialog", "m-code"],
        expected_categories=["对话", "代码", "截图", "结果"],
        verification={"verified": True},
    )
    check("L02 confirm_received status=received", created.status == "received")
    check("L02 missing_items 显式标记 截图/结果", set(created.missing_items) == {"截图", "结果"})
    again = core.confirm_received(
        submission_uuid=submission_uuid, course_id="c-01", assignment="hw-01",
        student_name="张三", group_name="第7组", material_refs=["m-dialog", "m-code"],
        expected_categories=["对话", "代码", "截图", "结果"], verification={"verified": True},
    )
    check("L02 幂等：同一 uuid → 同一 submission_id", again.submission_id == created.submission_id)
    outbox_payloads = [r for r in outbox._records.values()]
    check("L02 同事务入队 CT-004 + CT-006", sorted(r.contract_id for r in outbox_payloads) == ["CT-004", "CT-006"])
    ct004 = next(r for r in outbox_payloads if r.contract_id == "CT-004")
    check("L02 CT-004 dedup_key=submission_id", ct004.dedup_key == created.submission_id)

    moved = core.advance_to_processing(
        submission_id=created.submission_id, consumer_ack="task_persisted"
    )
    check("L02 received → processing", moved.status == "processing")

    # ---- L03：消费 CT-004（跨叶子契约保真）→ 认领 → 完成 ----
    outbox2 = InMemoryOutboxStore()
    orch = ScoringOrchestrator(session_factory=sm, lease_store=SqlaTaskLeaseStore(sm), outbox_store=outbox2)
    ingress = orch.handle_submission_received(ct004.payload)
    check("L03 CT-004 消费创建任务", ingress.created is True)
    dup = orch.handle_submission_received(ct004.payload)
    check("L03 重复事件幂等（created=False）", dup.created is False and dup.task_id == ingress.task_id)
    claimed = orch.claim_task(owner="worker-1")
    check("L03 认领任务", claimed is not None and claimed.task_id == ingress.task_id)
    committed = orch.complete_assessment(
        claimed.task_id,
        owner="worker-1",
        attempt_no=claimed.attempt_no,
        original_grade="B",
        dimension_rationales=[
            {"dimension": d, "rationale": f"smoke: {d}"}
            for d in ("需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性")
        ],
        teacher_suggestions=["smoke suggestion"],
    )
    check("L03 完成 scored", committed.outcome == "scored")
    ct005 = [r for r in outbox2._records.values() if r.contract_id == "CT-005"]
    check("L03 CT-005 scored 载荷入队", len(ct005) == 1 and ct005[0].payload["outcome"] == "scored")
    check("L03 CT-005 含 original_grade/五维/scored_at/v",
          ct005[0].payload["original_grade"] == "B"
          and len(ct005[0].payload["dimension_rationales"]) == 5
          and ct005[0].payload["v"] == 1)

    # ---- L02：应用终态（幂等） ----
    final = core.apply_scoring_outcome(submission_id=created.submission_id, outcome="scored")
    check("L02 processing → scored", final.status == "scored")
    replay = core.apply_scoring_outcome(submission_id=created.submission_id, outcome="scored")
    check("L02 重复终态事件幂等", replay.status == "scored")

    print()
    if FAILURES:
        print(f"SMOKE FAILED: {len(FAILURES)} 项失败")
        return 1
    print("SMOKE_OK: L01+L02+L03 跨叶子链路全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
