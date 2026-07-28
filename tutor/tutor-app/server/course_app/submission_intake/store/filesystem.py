"""SI-STORE 文件系统材料存储真实实现（T-B01a / IC-SI-02 / DD-005）。

目录布局（DD-005）：
- 暂存：`DATA_DIR/uploads/{session_id}/chunks/`（文件名由 session/seq 确定性派生）；
- 正式：`DATA_DIR/materials/{course_id}/{submission_id}/{category}/`
  （文件名 `{seq:06d}-{sha256[:16]}.bin` 确定性派生）。

语义：
- write_stage：临时文件流式写 + sha256 同步计算 + fsync + 同卷原子 rename；
  中断不留半成品（tmp 残留即清除），同 session/seq 重写幂等（同 ref 原子覆盖）；
- promote_to_final：同 session 幂等（已 final 直接返回首次 refs）；同卷原子移动，
  跨设备/失败回退 copy+verify+delete；单文件移动幂等（源缺失但目标 sha 吻合视为已移动），
  使崩溃后重试安全；promote 前做课程配额检查（KD-004 200GB，超限抛 QuotaExceededError，
  不移动任何文件）；
- delete：幂等；重复删除为空操作；final 删除同步扣减课程配额用量；
- read_metadata：L02 MaterialMetadataReader 兼容形状；未知/已删除 ref 抛
  MATERIAL_METADATA_UNAVAILABLE（由 SI-CORE 归一、事务回滚）。

身份解析：promote 时经 session_id → UploadSession.submission_uuid → Submission
解析 (course_id, submission_id)；提交记录尚未创建（首次 ingest 先于 SI-CORE 登记）
时回退 ("_unassigned", submission_uuid)。解析器可注入，组合根（T-B03d）可替换。

边界纪律：只读写 DATA_DIR 以内路径（逐段校验 + resolve 后前缀校验）；不做应用层
加密（DD-005 平台磁盘加密为基线）；不引入新依赖。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid as uuidlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, ContextManager, Sequence

from sqlalchemy.orm import Session

from course_app.settings import COURSE_QUOTA_BYTES
from course_app.submission_intake.core.errors import MaterialMetadataUnavailableError
from course_app.submission_intake.core.integrity import MaterialMetadata
from course_app.submission_intake.core.models import Submission
from course_app.submission_intake.xfer.models import UploadSession
from course_app.submission_intake.xfer.store import StorageIoError

from .errors import QuotaExceededError
from .models import (
    STATE_DELETED,
    STATE_FINAL,
    STATE_STAGED,
    CourseQuotaUsage,
    MaterialFile,
)

#: 提交记录尚未登记时的课程占位键（见模块 docstring 身份解析说明）。
UNASSIGNED_COURSE = "_unassigned"

STAGED_SCHEME = "staged://"
FINAL_SCHEME = "material://"

_WRITE_CHUNK = 1024 * 1024

#: promote 身份解析器：(db_session, upload_session_id) -> (course_id, submission_id)
IdentityResolver = Callable[[Session, str], tuple[str, str]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(_WRITE_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_segment(segment: str, field: str) -> None:
    """路径段安全校验：拒绝分隔符/父级引用/空段（防逃逸 DATA_DIR）。"""
    if (
        not segment
        or segment in (".", "..")
        or "/" in segment
        or "\\" in segment
        or "\x00" in segment
    ):
        raise StorageIoError(f"unsafe path segment in {field}: {segment!r}")


def default_identity_resolver(db: Session, session_id: str) -> tuple[str, str]:
    """默认身份解析：session → submission_uuid → Submission（存在则用真实身份）。"""
    upload = db.get(UploadSession, session_id)
    if upload is None:
        raise StorageIoError(f"unknown upload session: {session_id}")
    submission = (
        db.query(Submission)
        .filter(Submission.submission_uuid == upload.submission_uuid)
        .one_or_none()
    )
    if submission is None or not submission.course_id:
        return UNASSIGNED_COURSE, upload.submission_uuid
    return submission.course_id, submission.submission_id


class FilesystemMaterialStore:
    """MaterialStorePort（IC-SI-02）+ MaterialMetadataReader（L02）文件系统实现。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文；
    - `data_dir`：材料磁盘根（KD-002 本地磁盘；测试注入临时目录）；
    - `quota_bytes`：单课程配额（默认 KD-004 冻结 200GB；测试可缩小）；
    - `identity_resolver`：promote 身份解析（默认查 UploadSession/Submission）；
    - `clock`：可注入时钟（测试）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        data_dir: str | Path,
        *,
        quota_bytes: int = COURSE_QUOTA_BYTES,
        identity_resolver: IdentityResolver | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        # 根目录在初始化时归一为绝对路径：相对 data_dir（如 ./data）会导致
        # relative_to/前缀校验对绝对子路径误判（Phase 6 并发探针发现的缺陷）
        self._data_dir = Path(data_dir).resolve()
        self._quota_bytes = quota_bytes
        self._resolve_identity = identity_resolver or default_identity_resolver
        self._clock = clock or _utcnow

    # ---- MaterialStorePort：write_stage ----

    def write_stage(
        self, *, session_id: str, seq: int, category: str, content: bytes
    ) -> str:
        """流式写暂存（tmp + fsync + 原子 rename），登记 staged 行，返回暂存 ref。"""
        _check_segment(session_id, "session_id")
        _check_segment(category, "category")
        if seq < 0:
            raise StorageIoError(f"negative seq: {seq}")
        ref = f"{STAGED_SCHEME}{session_id}/{seq:06d}"
        chunks_dir = self._confined("uploads", session_id, "chunks")
        final_path = chunks_dir / f"{seq:06d}.chunk"
        tmp_path = chunks_dir / f".{seq:06d}.tmp-{uuidlib.uuid4().hex}"
        now = self._clock()
        try:
            chunks_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with open(tmp_path, "wb") as fh:
                view = memoryview(content)
                for offset in range(0, len(view), _WRITE_CHUNK):
                    block = view[offset : offset + _WRITE_CHUNK]
                    fh.write(block)
                    digest.update(block)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, final_path)
        except OSError as exc:
            # 原子性：中断不留半成品（tmp 即清；final 未被部分覆写）
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise StorageIoError(f"stage write failed: {exc}") from exc
        sha256 = digest.hexdigest()
        rel_path = final_path.relative_to(self._data_dir).as_posix()
        with self._session_factory() as db:
            row = db.get(MaterialFile, ref)
            if row is not None and row.state == STATE_FINAL:
                # 已提升后不应再暂存；幂等返回原暂存 ref，不回退状态
                return ref
            if row is None:
                row = MaterialFile(
                    material_ref=ref,
                    session_id=session_id,
                    seq=seq,
                    course_id=UNASSIGNED_COURSE,
                    submission_id="",
                    category=category,
                    path=rel_path,
                    size_bytes=len(content),
                    sha256=sha256,
                    state=STATE_STAGED,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                row.category = category
                row.path = rel_path
                row.size_bytes = len(content)
                row.sha256 = sha256
                row.state = STATE_STAGED
                row.updated_at = now
        return ref

    # ---- MaterialStorePort：promote_to_final ----

    def promote_to_final(
        self, *, session_id: str, staged_refs: Sequence[str]
    ) -> Sequence[str]:
        """暂存提升为正式（同 session 幂等：重复调用返回首次 material_refs）。"""
        _check_segment(session_id, "session_id")
        now = self._clock()
        with self._session_factory() as db:
            promoted = self._final_rows(db, session_id)
            if promoted:
                # promote 幂等：不产生不同正式引用
                return [row.material_ref for row in promoted]
            rows = self._staged_rows(db, session_id, staged_refs)
            course_id, submission_id = self._resolve_identity(db, session_id)
            _check_segment(course_id, "course_id")
            _check_segment(submission_id, "submission_id")
            incoming = sum(row.size_bytes for row in rows)
            usage = db.get(CourseQuotaUsage, course_id)
            used = usage.used_bytes if usage is not None else 0
            # 配额前置检查（KD-004）：超限拒绝，不移动任何文件、不改任何登记
            if used + incoming > self._quota_bytes:
                raise QuotaExceededError(
                    f"course {course_id} quota exceeded: "
                    f"used={used} + incoming={incoming} > {self._quota_bytes}"
                )
            final_refs: list[str] = []
            for row in rows:
                _check_segment(row.category, "category")
                filename = f"{row.seq:06d}-{row.sha256[:16]}.bin"
                rel_path = (
                    f"materials/{course_id}/{submission_id}/{row.category}/{filename}"
                )
                dst = self._confined(rel_path)
                src = self._confined(row.path)
                self._move_verified(src, dst, row.sha256)
                final_ref = (
                    f"{FINAL_SCHEME}{course_id}/{submission_id}/"
                    f"{row.category}/{filename}"
                )
                row.material_ref = final_ref
                row.course_id = course_id
                row.submission_id = submission_id
                row.path = rel_path
                row.state = STATE_FINAL
                row.updated_at = now
                final_refs.append(final_ref)
            if usage is None:
                usage = CourseQuotaUsage(
                    course_id=course_id, used_bytes=0, updated_at=now
                )
                db.add(usage)
            usage.used_bytes = used + incoming
            usage.updated_at = now
        self._prune_empty_staging_dirs(session_id)
        return final_refs

    # ---- MaterialStorePort：delete ----

    def delete(self, material_ref: str) -> None:
        """幂等删除：未知/已删除引用为空操作；final 删除扣减课程配额用量。"""
        now = self._clock()
        with self._session_factory() as db:
            row = db.get(MaterialFile, material_ref)
            if row is None or row.state == STATE_DELETED:
                return
            path = self._confined(row.path)
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                raise StorageIoError(f"delete failed: {exc}") from exc
            if row.state == STATE_FINAL:
                usage = db.get(CourseQuotaUsage, row.course_id)
                if usage is not None:
                    usage.used_bytes = max(0, usage.used_bytes - row.size_bytes)
                    usage.updated_at = now
            row.state = STATE_DELETED
            row.updated_at = now

    # ---- MaterialMetadataReader（L02 兼容形状） ----

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        """读已登记元数据；未知/已删除引用抛 MATERIAL_METADATA_UNAVAILABLE。"""
        with self._session_factory() as db:
            row = db.get(MaterialFile, material_ref)
            if row is None or row.state == STATE_DELETED:
                raise MaterialMetadataUnavailableError(
                    f"unknown material_ref: {material_ref}"
                )
            return MaterialMetadata(
                material_ref=row.material_ref,
                category=row.category,
                size_bytes=row.size_bytes,
                declared=True,
                filename=Path(row.path).name,
            )

    # ---- 内部 ----

    def _confined(self, *segments: str) -> Path:
        """拼接并校验路径严格位于 DATA_DIR 以内（不读写 DATA_DIR 以外路径）。"""
        for segment in segments:
            for part in Path(segment).parts:
                _check_segment(part, "path")
        root = self._data_dir.resolve()
        path = root.joinpath(*segments).resolve()
        if path != root and root not in path.parents:
            raise StorageIoError(f"path escapes DATA_DIR: {segments!r}")
        return path

    @staticmethod
    def _final_rows(db: Session, session_id: str) -> list[MaterialFile]:
        return (
            db.query(MaterialFile)
            .filter(
                MaterialFile.session_id == session_id,
                MaterialFile.state == STATE_FINAL,
            )
            .order_by(MaterialFile.seq)
            .all()
        )

    @staticmethod
    def _staged_rows(
        db: Session, session_id: str, staged_refs: Sequence[str]
    ) -> list[MaterialFile]:
        rows: list[MaterialFile] = []
        for ref in staged_refs:
            row = db.get(MaterialFile, ref)
            if (
                row is None
                or row.session_id != session_id
                or row.state != STATE_STAGED
            ):
                raise StorageIoError(
                    f"staged ref not promotable: {ref!r} (session={session_id})"
                )
            rows.append(row)
        rows.sort(key=lambda r: r.seq)
        return rows

    def _prune_empty_staging_dirs(self, session_id: str) -> None:
        """promote 后清理空的暂存目录（best-effort；非空或失败均忽略）。"""
        for path in (
            self._confined("uploads", session_id, "chunks"),
            self._confined("uploads", session_id),
        ):
            try:
                path.rmdir()
            except OSError:
                pass

    @staticmethod
    def _move_verified(src: Path, dst: Path, sha256: str) -> None:
        """同卷原子移动；失败回退 copy+verify+delete。单文件幂等（崩溃重试安全）。"""
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not src.exists():
                # 重试场景：源已被先前尝试移动；目标 sha 吻合则视为已完成
                if dst.exists() and _sha256_file(dst) == sha256:
                    return
                raise StorageIoError(f"staged file missing: {src}")
            try:
                os.replace(src, dst)
                return
            except OSError:
                # 跨设备 rename 等：回退 copy + sha256 verify + delete 源
                shutil.copyfile(src, dst)
                if _sha256_file(dst) != sha256:
                    dst.unlink(missing_ok=True)
                    raise StorageIoError(f"copy verify failed: {dst}")
                src.unlink()
        except OSError as exc:
            raise StorageIoError(f"promote move failed: {exc}") from exc
