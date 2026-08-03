# T-B01a 完成记录 — SI-STORE 材料存储真实实现

- 状态：done
- 分支：tutor-r01/B01a-store（worktree `tutor-app/.worktrees/B01a-store`）
- SHA：47c3b6726143afa1d8be5161ebeb3df6650a90bf
- 基线：main 917f8d1（按任务文件）；提交仅含允许路径新增文件，未触碰禁止项。

## 改动

- `server/course_app/submission_intake/store/`（新增包）
  - `filesystem.py` — `FilesystemMaterialStore`：MaterialStorePort（write_stage /
    promote_to_final / delete）+ L02 MaterialMetadataReader（read_metadata）。
    - DD-005 布局：暂存 `DATA_DIR/uploads/{session_id}/chunks/{seq:06d}.chunk`；
      正式 `DATA_DIR/materials/{course_id}/{submission_id}/{category}/{seq:06d}-{sha256[:16]}.bin`；
      文件名/ref 均由 session/seq/sha 确定性派生（staged://、material:// 不透明 ref）。
    - write_stage：tmp 流式写 + sha256 同步 + fsync + 同卷原子 rename；失败清 tmp，
      不留半成品、不登记；同 session/seq 重写幂等（同 ref 原子覆盖）。
    - promote_to_final：同 session 幂等（已 final 返回首次 refs）；同卷 os.replace，
      失败回退 copy+sha256 verify+delete；单文件移动幂等（源缺失但目标 sha 吻合视为
      已移动），崩溃重试安全；promote 前配额检查，超限抛 `QuotaExceededError`
      （code=QUOTA_EXCEEDED），不移动任何文件、不改登记；成功后累计 CourseQuotaUsage。
    - delete：幂等（未知/已删除空操作）；final 删除扣减课程配额用量。
    - 身份解析：session_id → UploadSession.submission_uuid → Submission；
      提交未登记时回退 (`_unassigned`, submission_uuid)；解析器可注入（组合根 T-B03d 可替换）。
    - 路径约束：逐段校验 + resolve 后 DATA_DIR 前缀校验；不做应用层加密（DD-005 基线）。
  - `models.py` — MaterialFile（ref/session/seq/course/submission/category/path/
    size_bytes/sha256/state/时间戳）、CourseQuotaUsage（course_id/used_bytes）。
  - `errors.py` — QuotaExceededError（稳定错误码 QUOTA_EXCEEDED，映射层后续使用）。
- `server/migrations/versions/0009_material_store.py` — 两表；
  revision=0009_material_store，down_revision="11a22f91f4b3"（并行多头纪律）。
- `server/tests/test_b01a_material_store.py` — 18 项（tmp 磁盘 + SQLite）。

## 验证（worktree 根执行）

- `python -m unittest discover -s server/tests -p "test_b01a_*.py"` — 18 项全绿。
- `python -m unittest discover -s server/tests` — 201 项全绿（既有 183 无回归 + 新增 18）。
- `ruff check <改动路径>` — All checks passed；`py_compile` 全部通过。
- 迁移：单测覆盖可导入 + revision/down_revision + SQLite upgrade/downgrade；
  `python -m alembic heads`（server/ 下）显示 `0009_material_store (head)`。

## 契约影响

无。未修改 contracts/shared/course_app 其他包/既有迁移/兄弟目录；仅新增。
StorageIoError 沿用 L08 冻结定义；read_metadata 输出对齐 L02 MaterialMetadata 形状。

## 风险 / 集成注记

1. **身份解析时序**：现行编排（L09 orchestrator）中 transfer ingest（含 promote）先于
   SI-CORE confirm_received 创建 Submission，故首次链路 promote 时课程身份不可知，
   落 `_unassigned/{submission_uuid}` 路径且配额按 `_unassigned` 键计量。完整 DD-005
   课程目录归属需组合根注入 identity_resolver 或调整编排时序（超出本任务边界，
   提请 Integration Owner 在 T-B03d/集成裁决，必要时走 CCR）。
2. QuotaExceededError 非 StorageIoError 子类：当前会在 L08 finalize 处向上传播为
   未映射错误；HTTP/事件映射归后续映射层（任务文件既定）。
3. write_stage 的 MaterialFile 登记在独立事务提交；若调用方（L08）随后回滚，
   理论上存在孤儿暂存行/文件，由 abort/TTL 清理路径兜底（既有设计张力，非本次引入）。
