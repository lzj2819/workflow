# Completion Report — L08 SI-XFER（tutor-r01, W2）

- leaf：L08 SI-XFER（MOD-02 分片上传会话）
- 分支：`tutor-r01/L08-si-xfer`（worktree `.worktrees/L08-si-xfer`，基线 main a4d373f）
- 提交 SHA：`a59c906ec05d53854ee8158c326221366e8167c2`
- 状态：done

## 改动清单

| 文件 | 说明 |
|---|---|
| `server/course_app/submission_intake/xfer/__init__.py` | 包公共出口（原为占位 docstring，改为导出） |
| `server/course_app/submission_intake/xfer/errors.py`（新） | 错误类型：冻结码 SESSION_NOT_FOUND / CHUNK_OUT_OF_ORDER / SIZE_LIMIT_EXCEEDED / TYPE_NOT_ALLOWED + 包内追加 CHUNK_DIGEST_CONFLICT / ILLEGAL_STATE |
| `server/course_app/submission_intake/xfer/store.py`（新） | IC-SI-02 SI-STORE 端口抽象（MaterialStorePort Protocol：write_stage/promote_to_final/delete）+ StorageIoError；实现归 backfill |
| `server/course_app/submission_intake/xfer/models.py`（新） | ST-XFER-01/02/03：UploadSession、ChunkReceipt、FinalizeAttempt（独立 Base，sa.JSON，可移植类型） |
| `server/course_app/submission_intake/xfer/service.py`（新） | IC-SI-01 端口 UploadTransferService：create_session（submission_uuid 幂等 + ResumeUpload）/ append_chunk（严格 next_expected_seq、同摘要重放幂等、逐片 500MB 检查、白名单）/ finalize（L2D-003 先持久化 attempt 再 promote，merged 幂等）/ abort / mark_pending_verification / sweep_expired；可注入时钟（TTL/retry_window）与非阻塞 observer（ST-XFER-04） |
| `server/migrations/versions/0005_upload_sessions.py`（新） | 三表迁移；revision="0005_upload_sessions"，down_revision="9c99fa53f9f8"（多头合并留协调者） |
| `server/tests/test_l08_si_xfer.py`（新） | 25 项单测（SQLite 内存库 + FakeStore + MutableClock） |

## 验证命令与结果（worktree 根）

- `python -m unittest discover -s server/tests -p "test_l08_*.py" -v` → Ran 25 tests … OK
- `python -m unittest discover -s server/tests` → Ran 101 tests … OK（既有 76 项无回归，新增 25）
- `ruff check server/course_app/submission_intake/xfer server/tests/test_l08_si_xfer.py server/migrations/versions/0005_upload_sessions.py` → All checks passed!
- `python -m py_compile`（7 个新增/改动 .py）→ 全部通过
- 迁移检查：`python -m alembic heads` → `0005_upload_sessions (head)`；测试内断言 revision/down_revision 正确

## 语义断言覆盖（对照 verification-checklist）

- 建会话 → 追分片（乱序 seq=1 先至被拒）→ 有序合并：checkpoint 只含已确认分片（receipts/received_bytes/next_expected_seq 不含被拒分片）；重复分片同摘要幂等（duplicate，不重复落盘/累计），异摘要 CHUNK_DIGEST_CONFLICT 不覆盖 ✓
- STORAGE_IO_FAILED → interrupted_retryable（保留进度 + retry_deadline），同 submission_uuid 恢复续传；failed_terminal 后 append/finalize 均拒绝 ✓
- 逐片累计 >500MB 拒绝（SIZE_LIMIT_EXCEEDED，会话可继续）；合并时总量 >上限拒绝；类别/媒体类型白名单外拒绝（TYPE_NOT_ALLOWED；枚举对齐 contracts/ct-001.json）✓
- 合并前无 promote_to_final 调用、session.material_refs 为空；write_stage/promote_to_final 调用形状以 FakeStore 断言 ✓
- TTL 过期（可注入时钟）：惰性置 failed_terminal + sweep_expired 扫描两路径；重试窗口耗尽 → failed_terminal（retry_window_expired）✓
- finalize 幂等：重复调用返回同一 material_refs，promote 仅一次；attempt 先于 promote 持久化（L2D-003）✓

## 契约影响

无。未修改 contracts/、shared/、internal-contracts.json；CT-001 冻结语义（幂等键、类别枚举、500MB、白名单、四个冻结错误码）不变；IC-SI-01/IC-SI-02 字段/所有者/错误集合不变（CHUNK_DIGEST_CONFLICT、ILLEGAL_STATE 为包内追加，不进入父契约）；ST-02 状态值域未扩展（rejected 为分片操作结果而非状态）。SI-STORE 以抽象注入，HTTP 映射留 L09。

## 风险 / 阻塞

- 低风险：abort/TTL 终止映射为 failed_terminal（L1 ST-02 值域内最接近"不可继续"的值），abort 失败原因以 `aborted: <reason>` 记录；若 L09 需要区分用户中止与上传失败，可在映射层按 failure_reason 前缀区分，不需要改契约。
- 惰性 TTL 终止依赖写路径触发；纯空闲会话由 sweep_expired 扫描兜底（调度归部署层）。
- 无阻塞。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD`：

```
server/course_app/submission_intake/xfer/__init__.py
server/course_app/submission_intake/xfer/errors.py
server/course_app/submission_intake/xfer/models.py
server/course_app/submission_intake/xfer/service.py
server/course_app/submission_intake/xfer/store.py
server/migrations/versions/0005_upload_sessions.py
server/tests/test_l08_si_xfer.py
```

全部位于 allowed-context.md 允许路径内；forbidden-changes.md 各项未触碰。
