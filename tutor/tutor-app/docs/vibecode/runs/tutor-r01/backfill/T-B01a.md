# T-B01a — SI-STORE 材料存储真实实现（Phase 5 / B-01）

- worktree：`tutor-app/.worktrees/B01a-store`（分支 tutor-r01/B01a-store，基线 main 917f8d1）
- 允许路径（仅这些）：
  - `server/course_app/submission_intake/store/**`
  - `server/migrations/versions/0009_material_store.py`（`down_revision="11a22f91f4b3"`）
  - `server/tests/test_b01a_material_store.py`（及 `server/tests/b01a_*.py` 辅助）

## 目标

实现 IC-SI-02 材料存储端口（L08 `xfer/store.py` 的 MaterialStorePort）+ L02 的 MaterialMetadataReader + 课程配额（KD-004 200GB），为上传/清除链路提供真实（本地磁盘 + PG 登记）的材料存储。

## 交付物

1. 目录布局（DD-005）：`DATA_DIR/uploads/{session_id}/chunks/`（暂存）→ `DATA_DIR/materials/{course_id}/{submission_id}/{category}/`（正式）；文件名确定性（session/seq 派生）；跨设备 rename 安全（同卷原子移动，失败回退 copy+verify+delete）。
2. `FilesystemMaterialStore` 实现 MaterialStorePort：write_stage（流式写、sha256 同步计算、临时文件+原子 rename）/ promote_to_final（同 session 幂等，返回正式 material_refs）/ delete（幂等）。
3. MaterialFile 登记（PG）：ref、course_id、submission_id、category、path、size_bytes、sha256、state（staged/final/deleted）、created_at；`MaterialMetadataReader.read_metadata` 实现（L02 兼容形状）。
4. 课程配额：CourseQuotaUsage 表；promote 前检查 course 累计 ≤200GB，超限抛配额错误（稳定错误码 QUOTA_EXCEEDED，映射层后续使用）。
5. 迁移 `0009_material_store.py`（上述两表）。
6. 测试：tmp_path 磁盘 + SQLite；覆盖：写暂存/提升/删除幂等、原子性（中断不留半成品）、配额拒绝、元数据读取、promote 幂等（同 session 重复调用同 refs）。

## 禁止

- 改 contracts/shared/course_app 其他包（xfer/api/core/…）/既有迁移/兄弟目录；应用层重复加密（平台磁盘加密为基线，DD-005）；引入新依赖。
- 读取 DATA_DIR 以外路径；外发任何材料。

## 验证

- `python -m unittest discover -s server/tests -p "test_b01a_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（既有 183 项不得回归）
- `ruff check <改动路径>`、`py_compile`
- 迁移可导入、revision/down_revision 正确

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B01a-completion.md`：SHA、改动、验证结果、契约影响（预期无）、风险。
