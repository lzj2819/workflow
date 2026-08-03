# T-B03d — SSR 路由挂载 + 组合根（Phase 5 / B-03 收尾）

- worktree：`tutor-app/.worktrees/B03d-composition`（分支 tutor-r01/B03d-composition，由协调者创建）
- 允许路径（仅这些）：
  - `server/course_app/composition.py`（新增）
  - `server/course_app/main.py`（改写为挂载组合根的 create_app）
  - `server/tests/test_b03d_composition.py`（及 `server/tests/b03d_*.py` 辅助）

## 目标

把全部已实现组件装配成可运行的 DU-2 应用：真实组合根 + 全部 router 挂载（L01 CT-003/CT-013、L09 CT-001/CT-002/auth-token、L14 CT-008、L15 CT-007、L16 CT-009、B03c CT-011、L17 SSR、health/metrics）+ 后台 relay（CT-005/CT-006/CT-012/CT-014 消费注册）。

## 交付物

1. `composition.py`：`build_composition(settings) -> Composition`：
   - engine（settings.database_url）+ 迁移提示（启动不自动迁移，运维跑 alembic）；
   - FilesystemMaterialStore（settings.data_dir）+ SqlaOutboxStore 工厂 + OutboxRelayer（注册：CT-005→[L02 apply_scoring_outcome, projector]、CT-006→projector、CT-012→purge executor、CT-014→retention handle_ct014；每 consumer 经 InboundDedup 包装）；
   - L02 SubmissionCoreService、L08 UploadTransferService、XferTransferAdapter、L09 create_router（verifier 进程内包装）；
   - ReadModelProjector + ProjectorReadModel（供 L15/L16 注入）；
   - AccessGateService + 三种 authorize 适配（L14/L15/L16）；
   - ReviewCommandService、RetentionService + CT-011 router + M05-IC-06 读端口、PurgeExecutor；
   - L17 create_router（api_client：进程内实现，直接调用本组合根服务——v1 单进程形态；HttpTeacherApiClient 留给真实部署）。
2. `main.py`：`create_app(settings=None)` 挂载全部 router + `/health/live`、`/health/ready`（接入 readiness 检查含 DB）、`/metrics`；提供 `relayer_tick()` 入口（组合根上的手动/定时驱动钩子，供进程内调度器或测试调用）。
3. 组合冒烟 `test_b03d_composition.py`（SQLite + tmp DATA_DIR + 时钟注入）：预置课程/教师 → 令牌 → 提交（JSON 通道）→ received → relayer_tick 驱动 CT-004 消费链路（worker 侧手工驱动 orchestrator，同 smoke_wave2 模式）→ CT-005 经 relay 到 L02+projector → 教师登录 → CT-007 详情（含 original_grade/批注入口）→ CT-008 调整 → CT-009 快照 → SSR 页面 200。
4. 运行手册更新：`docs/operations.md` 追加「组合根启动与 relay 驱动」小节（uvicorn 命令、迁移命令、教师/课程预置 CLI）。

## 禁止

- 改任何叶子/组件实现代码（只装配）；真实供应商/密钥/外发；声称 SCENARIO-016 完成；改契约。

## 验证

- `python -m unittest discover -s server/tests -p "test_b03d_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check server/course_app/composition.py server/course_app/main.py server/tests/test_b03d_composition.py`；`py_compile`

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B03d-completion.md`。
