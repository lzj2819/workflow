# T-B03d 完成记录 — SSR 路由挂载 + 组合根

- 状态：**blocked（1 项跨叶子缺陷，待叶子修复授权；装配本身完成）**
- SHA：c694746194b5b668b2542b536ec4f83dba87132b（分支 tutor-r01/B03d-composition，已 merge main 无冲突）

## 改动（均在允许路径内）

- `server/course_app/composition.py`（新增）：`build_composition(settings, *, engine=None, clock=None) -> Composition`。
  - engine（settings.database_url）+ 缺模式告警（启动不自动迁移，运维跑 alembic）；
  - 事务边界：默认 `db.session_scope(engine)`（每组件独立小事务，与既有叶子测试接线一致）；仅 L02 用 scoped-session `core_tx` + `_ScopedOutboxStore`（SqlaOutboxStore 解析到同一线程会话），保证聚合写入与 Outbox 行同一本地事务（KD-002）；
  - FilesystemMaterialStore（兼 L02 metadata_reader）、L08 UploadTransferService、XferTransferAdapter、L09 create_router + create_multipart_router（multipart 先挂载；verifier 进程内包装 L01 verify_membership）；
  - AccessGateService + L14/L15/L16 三种冻结端口适配；ReviewCommandService（SubmissionStatusPort 由组合根绑定 SI-CORE 直读）；ReadModelProjector（M05-IC-01 绑定 L14 create_review_record）+ ProjectorReadModel（M05-IC-02 双侧面）；RetentionService + RetentionViewPortAdapter（M05-IC-06）+ CT-011 router + PurgeExecutor（CT-012 消费，CT-014 经 SqlaOutboxStore 工厂同事务入队）；
  - OutboxRelayer 消费注册（每 consumer 经 InboundDedup 包装）：CT-005→[L02 apply_scoring_outcome, projector]、CT-006→projector、CT-012→[purge, projector]、CT-014→[retention.handle_ct014, projector]；CT-004 归进程外 worker，不注册（UnknownContract 可观测重试）；
  - L17 api_client：InProcessTeacherApiClient（进程内调用组合根服务，v1 单进程形态；错误只映射冻结码）。
- `server/course_app/main.py`（改写）：`create_app(settings=None, *, composition=None)` 挂载全部 router + `/health/live`、`/health/ready`（config/contracts/database[组合根 engine SELECT 1]/storage）+ `/metrics`；`app.state.composition.relayer_tick()` 驱动钩子。
- `server/tests/test_b03d_composition.py`（新增，3 例）：全链路组合冒烟（SQLite+StaticPool+tmp DATA_DIR+时钟注入；worker 侧手工驱动 orchestrator 同 smoke_wave2 模式）、health/metrics、relay 重投幂等。
- `docs/operations.md`（追加「组合根启动与 relay 驱动」小节：uvicorn 命令、迁移命令、课程/教师预置 CLI）。

## 验证

- `python -m unittest discover -s server/tests -p "test_b03d_*.py" -v`：3 例，2 过 1 失败（失败即下方缺陷的见证断言）。
- `python -m unittest discover -s server/tests`：325 例，仅该 1 失败，无其他回归。
- worker：104 全绿；plugin：102 全绿。
- `ruff check`（三个文件）通过；`py_compile` 通过。

## 阻塞缺陷（跨叶子，需 Integration Owner 授权叶子修复）

**M05-IC-05 投影丢失 GradeAdjusted**：L14 `ReviewCommandService.apply_review` 对一次「批注+最终等级」调整只铸一个 `adjustment_id`，AnnotationSaved 与 GradeAdjusted 两个事件共用该 id（service.py L242/L274/L285）；而 B03b `ReadModelProjector._apply_review_event` 仅按 `adjustment_id` 去重，第一条事件应用后第二条被判重复跳过 → 读模型 final_grade 永不投影（批注正常）。B03b 单测未暴露（其测试事件人为使用 `adj-1`/`adj-1-g` 不同 id）。

- 复现：`test_b03d_composition.py::test_full_composition_flow` 中断言 `final_grade == "A"` 失败（实际 None）；进程内最小复现已核验（apply_review 两事件同 adjustment_id，publish 后 rm_submissions.final_grade 为 None）。
- 影响面：真实 SSR 复核表单单次提交「批注+等级」即触发，教师端 CT-007/CT-009/SSR 看不到最终等级。
- 建议修复（叶子侧，契约语义不变）：projector 去重键改为 `(adjustment_id, event_type)`（`_apply_review_event` 一处）；或 L14 每事件铸独立 id。需协调者授权一个小补丁任务（不在 T-B03d 允许路径内，本代理未改任何叶子文件）。

## 契约影响

无契约语义变更；无新公共错误码；不声称 SCENARIO-016；未接真实供应商/密钥/外发；未触碰 tutor 设计包。

## 风险

除上述阻塞缺陷外：dedup 记录与业务写入分属不同事务（消费者各自管理事务且均按业务键幂等），崩溃窗口内重投由消费者幂等兜底；CT-004 无注册消费者会按退避持续重试（可观测，符合 v1 进程外 worker 形态）。
