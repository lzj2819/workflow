"""ICT-003 生产实现：MOD-02 所有权材料只读端口（GAP-02）。

授权与边界（对齐 KD-001 数据最小化与 03-data-consistency 所有权表）：
- **授权以 L02 提交清单（submission_materials）为准**：仅可读属于当前评分提交
  清单内的 ref——跨提交/跨课程一律拒绝（提交归属课程，清单即课程隔离边界）。
  注：不以 material_files.course_id 判定（D-P5-01 勘误：promote 先于课程归属，
  v1 登记为 `_unassigned`，权威归属链是清单）；
- 仅 state=final 的登记材料可读（未登记/staged/deleted 拒绝）；
- 路径严格限定 DATA_DIR 以内（与 FilesystemMaterialStore._confined 同语义）；
- 单文件读取上限 = MAX_SUBMISSION_BYTES（KD-004 冻结上限派生，不新造口径）；
- 只读：不写、不删除、不转移所有权；每次 load_for 记结构化日志（ref 数/字节数，
  不含内容）并计 metrics（拒绝单独计数可告警）。

错误语义：任何读取失败（未登记/越权/超限/IO/非文本不可判定）抛
`MaterialContentUnreadableError`；消费方（worker 适配器）映射为 ICT-006 冻结
分类 MATERIAL_UNREADABLE，不新增错误码。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, ContextManager

import sqlalchemy as sa
from sqlalchemy.orm import Session

from tutor_shared.metrics import registry as metrics_registry

from course_app.settings import MAX_SUBMISSION_BYTES
from course_app.submission_intake.core.models import SubmissionMaterial

from .models import STATE_FINAL, MaterialFile

_logger = logging.getLogger("course_app.material_reader")


class MaterialContentUnreadableError(Exception):
    """ICT-003 读取失败（未登记/越权/超限/IO）；映射 MATERIAL_UNREADABLE。"""


def _check_segment(value: str, what: str) -> None:
    """与 filesystem._check_segment 同语义：拒绝路径逃逸段。"""
    if not value or value in (".", "..") or "/" in value or "\\" in value or "\x00" in value:
        raise MaterialContentUnreadableError(f"invalid {what}: {value!r}")


class MaterialContentReader:
    """MOD-02 材料只读端口（ICT-003 生产实现）。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文（只读使用）；
    - `data_dir`：材料磁盘根（与 SI-STORE 同一 DATA_DIR；worker 容器经只读卷挂载）；
    - `max_bytes`：单文件读取上限（默认 KD-004 MAX_SUBMISSION_BYTES 派生）；
    - `logger`：可注入（测试）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        data_dir: str | Path,
        *,
        max_bytes: int = MAX_SUBMISSION_BYTES,
        logger: logging.Logger | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._data_dir = Path(data_dir).resolve()
        self._max_bytes = max_bytes
        self._log = logger or _logger

    def load_for(
        self, *, course_id: str, submission_id: str, material_refs: list
    ) -> dict:
        """按授权上下文读取材料内容：{category: 文本} + readability 备注。

        授权：每个 ref 必须登记为 final 且 (course_id, submission_id) 精确匹配；
        任一 ref 越权/未登记即整体失败（不返回部分内容，防越权侧信道）。
        """
        if not isinstance(material_refs, (list, tuple)):
            raise MaterialContentUnreadableError("material_refs must be a list")
        refs: list[str] = []
        for item in material_refs:
            ref = item.get("ref") if isinstance(item, dict) else item
            if not isinstance(ref, str) or not ref:
                raise MaterialContentUnreadableError(f"invalid material ref: {item!r}")
            refs.append(ref)

        # 第一遍：授权与登记校验（任一拒绝即整体失败，不读盘）；
        # 授权以 L02 提交清单为准（D-P5-01：material_files.course_id 为 _unassigned
        # 勘误形态，权威归属链是 submission_materials）
        # 值在会话内提取（session_scope 提交后 ORM 实例过期，不可跨会话访问）
        rows: list[dict] = []
        with self._session_factory() as db:
            allowed_refs = set(
                db.scalars(
                    sa.select(SubmissionMaterial.material_ref).where(
                        SubmissionMaterial.submission_id == submission_id
                    )
                )
            )
            for ref in refs:
                if ref not in allowed_refs:
                    self._deny(
                        ref,
                        "not in submission manifest",
                        course_id=course_id,
                        submission_id=submission_id,
                    )
                    raise MaterialContentUnreadableError(
                        f"material out of authorized scope: {ref}"
                    )
                row = db.get(MaterialFile, ref)
                if row is None or row.state != STATE_FINAL:
                    self._deny(ref, "not registered as final material")
                    raise MaterialContentUnreadableError(
                        f"material not readable: {ref}"
                    )
                if row.size_bytes > self._max_bytes:
                    self._deny(ref, f"size {row.size_bytes} exceeds limit {self._max_bytes}")
                    raise MaterialContentUnreadableError(
                        f"material exceeds read limit: {ref}"
                    )
                rows.append(
                    {"ref": row.material_ref, "category": row.category, "path": row.path}
                )

        # 第二遍：限界读盘（utf-8，不可解码字节替换并记 readability）
        materials: dict[str, str] = {}
        readability: list[dict] = []
        total_bytes = 0
        for row in rows:
            path = self._confined(row["path"])
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise MaterialContentUnreadableError(
                    f"material read failed: {row['ref']}: {exc}"
                ) from exc
            if len(raw) > self._max_bytes:  # 登记与磁盘不一致时以实测为准
                self._deny(row["ref"], f"on-disk size {len(raw)} exceeds limit")
                raise MaterialContentUnreadableError(
                    f"material exceeds read limit: {row['ref']}"
                )
            total_bytes += len(raw)
            text = raw.decode("utf-8", errors="replace")
            if "�" in text:
                readability.append(
                    {"ref": row["ref"], "note": "non-utf8 bytes replaced"}
                )
            # 同类别多文件合并（对话/代码/截图/结果四类；与提交清单类别口径一致）
            existing = materials.get(row["category"])
            materials[row["category"]] = text if existing is None else f"{existing}\n{text}"

        self._log.info(
            "material load_for ok",
            extra={
                "course_id": course_id,
                "submission_id": submission_id,
                "refs": len(refs),
                "bytes": total_bytes,
            },
        )
        metrics_registry.inc("material_reads_total")
        return {"materials": materials, "readability": readability}

    def _confined(self, rel_path: str) -> Path:
        """拼接并校验路径严格位于 DATA_DIR 以内。"""
        for part in Path(rel_path).parts:
            _check_segment(part, "path")
        path = (self._data_dir / rel_path).resolve()
        root = self._data_dir
        if path != root and root not in path.parents:
            raise MaterialContentUnreadableError(f"path escapes DATA_DIR: {rel_path!r}")
        return path

    def _deny(self, ref: str, reason: str, **ctx) -> None:
        """拒绝可观测：告警日志 + 独立计数（不含内容，不泄露路径细节以外的信息）。"""
        self._log.warning(
            "material read denied",
            extra={"ref": ref, "reason": reason, **ctx},
        )
        metrics_registry.inc("material_read_denied_total")
