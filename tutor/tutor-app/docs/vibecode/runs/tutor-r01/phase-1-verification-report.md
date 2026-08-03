# Phase 1 Verification Report — tutor-r01

- 日期：2026-07-20（UTC 2026-07-19T16:5xZ 执行）
- 执行者：Integration Owner / Workflow Coordinator
- 范围：Phase 1 生产基线（契约 schema、monorepo 骨架、工程基线、测试骨架、MOD-02 复核）。**未实现任何 Leaf 业务功能。**

## 1. 环境

| 项 | 版本 |
|---|---|
| Python | 3.14.3 |
| Node.js | v24.14.0 |
| Docker / Compose | 29.1.3 / v2.40.3-desktop.1 |
| ruff | 0.15.21 |

## 2. 验证命令与结果

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python -m py_compile $(find . -name '*.py' -not -path './.git/*')` | OK（全部 .py 语法通过） |
| 2 | `for f in $(find . -name '*.js' ...); do node --check $f; done` | OK（全部 .js 语法通过） |
| 3 | `python -m unittest discover -s server/tests` | **OK，35 tests**（契约 14 + 平台 11 + 配置 6 + 布局 4） |
| 4 | `python -m unittest discover -s worker/tests` | **OK，8 tests**（fake provider/CT-010 schema 符合性/常量/入口） |
| 5 | `cd plugin && npm test`（node --test） | **OK，8 pass / 0 fail**（host 端口/fixture/配置校验/布局） |
| 6 | `ruff check server worker shared` | OK（首次 2 个未用导入，已 `--fix` 并回归通过） |
| 7 | `docker compose -f deploy/docker-compose.yml config --quiet` | OK（首次因缺 .env 失败，改 env_file required:false 后通过） |
| 8 | `python -m assessment_worker` 入口 | OK（经 worker 测试调用，输出结构化启动日志） |

未执行（需依赖安装/真实环境，Phase 2+）：`alembic upgrade head`（需 PostgreSQL）、`docker compose up`（需拉取镜像并安装 requirements）、真实 HTTP 端点（L09 落地）。

## 3. 失败与修复记录（证据）

1. 事件契约 5 文件缺 `publishes_events` 键 → 注册表 KeyError；修复：补键（[]）+ 注册表对问题文件不再继续构造（统一报错）。
2. Outbox 测试用未来时刻 T0 与真实时钟冲突 → 改为显式 `next_attempt_at`。
3. FLOW-011（internal_read）被误要求错误码 → 注册表规则收窄为 api/external_api。
4. 测试口径：`/api/v1` 前缀仅适用自有 api 契约（事件走 v 字段、CT-010 走供应商 ACL 封装）。
5. `node --test test/` 参数形态兼容问题 → 改 `node --test`（自动发现）。
6. compose env_file 缺失 → `required: false`。
7. ruff 报 2 个未用导入 → 已修复。

## 4. 交付物清单

- **contracts/**：CT-001~CT-014、AUTH-TOKEN、FLOW-011 共 16 个机器可读 schema + internal-contracts.json（5 模块 27 条内部契约索引）+ README。契约测试锁定：必需字段、错误码集合、事件 v=1、幂等声明、CT-001 限额/类别、CT-005 outcome/重试上界/五维基数、CT-010 数据最小化、CT-012 消费者冻结（CCR-001 未批）、AUTH-TOKEN 形状、FLOW-011 internal_read。
- **shared/tutor_shared/**：config、logging（JSON）、metrics、health、outbox（ABC + 内存实现 + 退避）、lease（ABC + 内存实现 + 重认领上限）。零第三方依赖。
- **server/**：course_app 包（settings 冻结常量、contracts_registry、health 装配、db 事务边界、main ASGI 工厂）、MOD-02/03/05 模块边界包、alembic 迁移入口（baseline 0001）、requirements.txt。
- **worker/**：assessment_worker 包（settings、ModelProvider 协议 + FakeModelProvider + 数据最小化校验、__main__ 任务入口）、MOD-04 两个叶子边界包、requirements.txt。
- **plugin/**：host 对话导出端口（校验 + 显式 HostUnsupportedError，TD-01 不虚构 API）、fixture、配置校验（IC-M01-02 形状）、核心端口类型（IC-M01-01..05）、package.json（零依赖）。
- **deploy/**：Dockerfile.server、Dockerfile.worker、docker-compose.yml（PostgreSQL 16 + DU-2/DU-3）。
- **根级**：.env.example（无真实 secret）、.gitignore、README。
- **docs/**：development、testing、configuration、operations、recovery + design/phase-1-detail-design（DD-001~DD-009）。
- **run 文档**：contract-change-request.md（CCR-001，pending）、execution-log.jsonl。

## 5. MOD-02 继承契约映射复核（findings 遗留 3 项「待复验」）

| 项 | 结论 | 证据 |
|---|---|---|
| (a) 直接 child_id 拥有 current REQ-D；内部支撑不进 direct children | **通过** | L1-mod-02 child-handoff §清单：SI-API/SI-CORE/SI-XFER 各自拥有 REQ-D；SI-PURGE/RELAY/STORE/VERIFY 标注「不作为 L2 target」；与 L2 terminal 16 节点清单一致 |
| (b) 父契约语义与 L0 CT-001/CT-004/CT-006/FLOW-008 一致 | **通过** | CT-006 发布时机（received 或 upload_failed 终态，LCD-002）：L0 CT-006 schema 含 `status` 字段承载状态，FLOW-008 描述 received 主路径；upload_failed 终态发布满足 AC-REQ-003-01 exceptions「教师端可见失败原因」，schema 未变，语义兼容。CT-004 确认语义（LCD-003 = MOD-04 评分任务持久化后确认）与 L0 CT-004「任务持久化后才推进事件确认」逐字一致。contracts/ct-001.json 字段/错误码/幂等经测试锁定 |
| (c) 状态机外部值域与父 AC/FLOW 终态一致（六态 + deleted） | **通过** | upload_failed/rejected/received/processing/scored/scoring_failed（CT-001、AC-REQ-007-01）+ deleted（FLOW-010 终态）；contracts/ct-002.json status enum 已含 deleted |

残留：设计包侧 strict audit 工具未重跑（属设计包内部事项）；实现期由 L02/L08/L09 任务包 verification-checklist 兜底复核。**MOD-02 可进入 Wave 1/2 实现。**

## 6. 是否达到「可进入 Wave 1」条件

| 条件 | 状态 |
|---|---|
| matrix gate 批准 | ✅ 2026-07-19 |
| 契约正式冻结 + 机器可读 schema + 契约测试 | ✅ |
| monorepo 骨架与工程基线（DB 基线/迁移入口/Outbox/租约/配置/日志/metrics/健康/compose） | ✅ |
| 测试骨架全绿（35+8+8） | ✅ |
| MOD-02 复核 | ✅ |
| L07（TD-01） | ❌ 仍 blocked：仅端口/fixture/unsupported 状态；真实宿主适配待确认 |
| CCR-001（TD-08） | ⏸ pending：不阻塞 Wave 1/2/3，阻塞 Phase 5 删除链路完整性声明 |

**结论：Wave 1 中 L01~L06 已具备开始条件；L07 除外（TD-01）。** 是否放行 Wave 1 由用户决定；本回合不创建任何 Leaf Owner 任务、不写业务代码。

## 7. 待办与门禁

- 待用户：① 是否放行 Wave 1（L01~L06）；② CCR-001 裁决；③ TD-01 宿主导出机制确认。
- 禁止事项保持：不接真实模型、不发学生材料、不读未授权 Codex 文件、不改 tutor 设计包、不自动批准 gate。
