# Phase 1 详细设计记录（DD-001 ~ DD-009）

来源：用户 2026-07-19/07-20 决策重分类（TD-02~TD-10 除 TD-01/TD-08 外，均为 L0/L1 已冻结约束或 defer_to_detail_design 参数）。本文件为落地记录，不新增产品需求、不改变冻结契约。

## DD-001 服务端/Worker 技术栈（TD-02）

- 决定：Python 3.12+；Web 框架 FastAPI（L09 起接线）；ORM SQLAlchemy 2.x + psycopg 3；迁移 alembic。Worker 同语言，经共享 DB 与 DU-2 协作（KD-002）。
- 依据：DU-1/DU-2/DU-3 部署形态 L0 已定；pydantic 校验与 contracts/ JSON Schema 对齐；团队单语言（插件除外）降低运维成本。
- 插件：Node ESM 纯 JS + JSDoc（零运行时依赖，node:test 验证）；宿主绑定形态随 TD-01 定稿，仅适配层受影响。

## DD-002 数据库产品（TD-03）

- 决定：**PostgreSQL 16** 为唯一运行时数据库（用户指令 2026-07-20）；SQLite 仅可用于不触库的纯单元测试替身。
- 依据：KD-002 已定单一关系库 + 事务 + 备份要求；DU-2/DU-3 两进程并发访问与租约/Outbox 语义需要行级锁与 `FOR UPDATE SKIP LOCKED`；备份/加密生态成熟。
- 迁移入口：`server/alembic.ini` + `server/migrations/`（baseline 0001，无表；聚合表随叶子 migration 落地）。

## DD-003 教师前端形态（TD-02 / MOD-05 LCD-007）

- 决定：服务端渲染（SSR，Jinja2 模板 + 少量原生 JS）；展示视图导出为静态 HTML 快照（LCD-008），v1 不做 PDF。
- 依据：读多写少、百级学生规模；无 SPA 构建链可降低运维与验收复杂度；不满足时（交互密度上升）再评估 SPA，属实现细节演进。

## DD-004 认证细化（TD-05）

- 学生令牌（KD-005）：不透明随机令牌，服务端存哈希（AuthTokenGrant 审计表，MOD-02 ST-06）；TTL 30 天，过期凭邀请码+姓名+小组重新换领；泄露处置 = 运维轮换课程邀请码。
- 教师会话：HttpOnly + Secure + SameSite=Lax 会话 Cookie，TTL 12 小时滑动；TEACHER_SESSION_SECRET 仅环境变量。v1 教师账号运维预置（对齐 MOD-03 LCD-004；多教师/自助授权触发 MOD-05 Q-04 回父层）。
- CT-003 端点：DU-2 进程内直接调用承载（同契约语义）；若分进程则内网 + 共享密钥头（部署期再决，MOD-03 委托项）。

## DD-005 材料存储与加密参数（TD-06 / MOD-02 LCD-007 预登记）

- 目录布局：`DATA_DIR/materials/{course_id}/{submission_id}/{category}/...`；上传暂存：`DATA_DIR/uploads/{session_id}/chunks/`（转正式由 SI-STORE 落地）。
- 静态加密：以平台级磁盘加密为基线（KD-003「存储加密」）；应用层不重复加密。若目标平台无全盘加密 → 重新评估应用层信封加密（触发时再决）。
- 配额：按 course_id 目录计量，200GB 写入前检查（KD-004）；500MB 单次上限在 SI-XFER 预检 + SI-STORE 复核。

## DD-006 异步任务参数（TD-07 / MOD-02 LCD-008 预登记）

- Outbox 投递器：轮询间隔 1s（空闲退避至 5s），批 50 条；投递失败指数退避 1s→60s 封顶，无限重试直至确认（冻结重试策略）。
- 评分 worker：基线 2–3 副本（用户已定），按任务积压扩缩；租约 120s，reclaim_count>3 终态化（MOD-04 LCD-002）；期限跟踪不强杀（LCD-004）。
- 抽象落点：`shared/tutor_shared/outbox.py`、`shared/tutor_shared/lease.py`（PostgreSQL 实现随 L03/backfill）。

## DD-007 调整理由（TD-09）

- 决定：教师调整最终等级时理由字段**可选保留、不强制**（MOD-05 LCD-009 默认）；留痕四元组（原始/最终/操作者/时间）不变。contracts/ct-008.json 已含可选 `adjustment_reason`。

## DD-008 部署（TD-10）

- 决定：继承 KD-003 与 06-deployment；具体地域/域名/HTTPS 终止/备份工具/分机拓扑留 Phase 6 决策。Phase 1 仅固定配置项清单（docs/configuration.md）与 docker-compose 本地基线。

## DD-009 模型供应商配置（TD-04）

- 决定：继承 KD-001（外部 API + ACL + 数据最小化 + 供应商可替换）。供应商选择、模型版本、密钥管理为**实现细节**：经 `MODEL_PROVIDER` / `MODEL_API_KEY` 环境变量配置，密钥不入库不打日志；Phase 1 仅 `MODEL_PROVIDER=fake`。真实供应商接入在 L12/B-02 落地，接入前需用户提供合规确认。

## 保留事项

- TD-01（L07 真实阻塞）：Phase 1 仅落地 host 端口/fixture/失败可观测；确认宿主导出机制后实现真实适配。
- TD-08 → CCR-001（pending）：批准前 CT-012/CT-014 冻结不改、不实施。
