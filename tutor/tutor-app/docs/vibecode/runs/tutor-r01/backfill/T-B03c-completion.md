# T-B03c 完成记录 — RETENTION-GOVERNANCE：保留治理与 CT-011

- 分支：tutor-r01/B03c-retention（worktree `tutor-app/.worktrees/B03c-retention`）
- SHA：3373e4879c2b803bca4ec1e5ba80148615b35a30
- 基线：先合并 main（fast-forward，无冲突）

## 改动

- `server/migrations/versions/0014_retention.py`（down_revision="11a22f91f4b3"，并行多头）：
  `deletion_batches`（batch_id/course_id/scope/retention_due_at/status 五态/
  exclusions/failed_items/cleared_submission_ids/applied_purge_marks/confirmed_at/
  confirmed_by/时间戳）+ `deletion_audit_records`（只追加：batch/动作/范围/操作者/
  submission 快照/时间；永久留存不在删除范围）。
- `server/course_app/teacher_web/retention/`（新组件，6 文件）：
  - `models.py` / `errors.py`：聚合与审计模型、冻结错误类型
    （NOT_FOUND 404 / BATCH_NOT_EXPIRED 409 / Ct014ValidationError）。
  - `service.py` `RetentionService`：
    - `mark_due_batches(now)`：retention_due_at = 课程结束 + 1 年（2/29 归并
      2/28）；课程结束时间经注入的 CP-COURSE-ENDTIME 只读端口解析（默认绑定
      L01 `admin.get_course_end_time`，FLOW-011 同进程，非网络调用）；时钟可
      注入；(course_id, scope) 确定性批次键，重复执行幂等；未到期
      pending_mark、到期 awaiting_confirm；executing/partially_failed/
      completed 不回退。
    - `confirm_batch`：未到期 → BatchNotExpiredError；executing 及之后状态
      重复确认幂等（返回现状、不重发 CT-012、不重复写审计）；**审计先行**——
      DeletionConfirmed 审计行先 flush 再 enqueue CT-012（同事务，KD-002）；
      CT-012 载荷与 contracts/ct-012.json 冻结字段精确一致
      （batch_id/submission_ids/scope/operator/executed_at/audit_record_id/v=1，
      无多余字段）；exclusions 从待删范围剔除，已删除提交不进入范围。
    - `handle_ct014`：按 batch_id + purged_at 幂等回写（applied_purge_marks
      去重，重复事件空操作）；无失败项 → completed + RecordsDeleted 审计；
      有失败项 → partially_failed + failed_items 保留供重跑；cleared 并集
      累积，重跑成功收敛 completed。
    - `list_batches`：M05-IC-06 只读批次视图（course/batch/submission 过滤）。
  - `api.py`：CT-011 FastAPI APIRouter（不挂载）
    `POST /api/v1/teacher/deletion-batches/{batch_id}/confirm`；Bearer 会话
    认证 + 课程范围授权经 ACCESS-GATE（403 + AccessDeniedLogged 由 GATE 记录）；
    错误码只映射 CT-011 父冻结值（401/403/404/409）；响应含
    batch_id/batch_status/pending_deletion_scope。
  - `read_port.py` `RetentionViewPortAdapter`：L15 RetentionViewPort 实现，
    读取失败转 L15 RetentionViewUnavailableError（不降级缺字段）。
- `server/tests/test_b03c_retention.py`：28 测试（SQLite + StaticPool）。

## 验证（worktree 根，2026-07-21）

- `python -m unittest discover -s server/tests -p "test_b03c_*.py" -v`：28/28 OK。
- `python -m unittest discover -s server/tests`：322/322 OK（无回归）。
- `ruff check server/course_app/teacher_web/retention server/migrations/versions/0014_retention.py server/tests/test_b03c_retention.py`：All checks passed。
- `py_compile` 全部新文件通过；迁移可导入（revision=0014_retention，
  down_revision=11a22f91f4b3）；upgrade/downgrade 在 SQLite 可执行（测试覆盖）。

## 契约影响

- CT-011：实现端点与父冻结语义（confirm=true、exclusions、BATCH_NOT_EXPIRED、
  重复确认幂等、审计先于清除）；响应字段满足 required，附字段在
  additionalProperties=true 允许范围内。**无契约变更**。
- CT-012：发布侧载荷与冻结 event schema 精确一致（含 additionalProperties=false）；
  dedup_key=batch_id（消费方 SI-PURGE 按 batch_id 幂等，与既有实现一致）。
- CT-014：消费侧按 batch_id + purged_at 幂等（冻结 idempotency 条款）。
- M05-IC-06：读端口按 L15 冻结 RetentionBatchView 形状实现。
- CP-COURSE-ENDTIME：仅同进程只读调用，未升级为网络契约。

## 边界与风险

- 未实现/未声称 AssessmentResult（MOD-04）删除接线（CCR-001 pending）；
  未声称 SCENARIO-016 完成（保持 blocked）。
- CT-011 路由不挂载（挂载归 T-B03d 组合根）；CT-012/CT-014 投递由既有
  Outbox/RELAY 承担。
- 风险（低）：executing 状态的批次若 CT-014 长期不到达无自动重发机制
  （重复确认按幂等返回现状不重发）；重跑依赖 SI-PURGE 侧重跑 CT-012 后
  CT-014 新 purged_at 回写，重发编排归组合根/运维。
