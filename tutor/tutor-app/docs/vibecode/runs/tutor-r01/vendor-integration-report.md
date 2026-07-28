# 供应商接入验证报告 — deepseek（受限实施）

- 日期：2026-07-25；执行：Integration Owner；基线：main `a5f41dc`
- 批准范围（用户 2026-07-25）：仅 deepseek；外发限最小化对话/代码/材料文本；密钥 .env；内部试用/灰度；不可用 → 无自动评分/稍后重试。
- 边界遵守：未接入其他供应商；未记录原始密钥；日志无材料/请求内容；未正式发布。

## 1. 交付物

| 项 | 位置 | 说明 |
|---|---|---|
| DeepSeekProvider | `worker/assessment_worker/model_provider_deepseek.py` | OpenAI 兼容 Chat Completions；`response_format=json_object`；温度 0.2 |
| provider 注册 | `model_provider.build_provider` | `MODEL_PROVIDER=fake|deepseek`；其他值启动即拒绝（fail fast） |
| 数据最小化闸 | provider `evaluate` 入口 `validate_request` | 业务标识（submission_id/姓名/小组/邀请码/课程）违例绝不外发；外发仅 evaluation_prompt + 三桶材料 + request_id |
| 强制超时 | httpx client timeout ≤ 180s（MODEL_CALL_TIMEOUT_SECONDS 封顶，构造期校验） | 与 ACL 预算层双重约束；超时 → MODEL_TIMEOUT |
| 重试 | REQ-012 任务内重试一次（既有 runner 机制） | MODEL_TIMEOUT/MODEL_ERROR 分类；畸形应答 → INVALID_RESPONSE_SCHEMA（ACL 终判，不猜测修补） |
| 审计 | `vendor_calls_total` / `vendor_failures_total` / `vendor_timeouts_total` + 结构化日志 | 日志仅含 model/status/duration/request_id；**无密钥、无内容** |
| 降级（kill switch） | `VENDOR_ENABLED=0` → 停止认领 | 任务保持 pending（稍后重试），不终态化、不耗业务重试预算 |
| 降级（熔断） | 连续 `VENDOR_CIRCUIT_THRESHOLD`(5) 次 MODEL_TIMEOUT/MODEL_ERROR → 冷却 `VENDOR_CIRCUIT_COOLDOWN_SECONDS`(60) 不认领 | 冷却后半开自动恢复；`vendor_circuit_opens_total` 可告警 |
| 密钥管理 | `.env` / compose env_file 注入 `MODEL_API_KEY` | `.env.example` 占位；密钥构造期非空校验；401/403 → DeepSeekAuthError |
| 配置 | `.env.example`、worker settings | DEEPSEEK_BASE_URL（默认 https://api.deepseek.com，境内）、DEEPSEEK_MODEL（默认 deepseek-chat）、VENDOR_* 三参 |

## 2. 验证证据

### 2.1 provider 单测（`worker/tests/test_vendor_deepseek.py`，10/10）

- 成功应答 → CT-010 形状（grade/五维依据/建议）；请求体为 JSON 模式且**无业务标识**（含中文姓名/小组名断言）；
- 最小化闸：携带 submission_id 的请求在 provider 入口即拒且**零外发**（captured 为空）；
- 超时 → TimeoutError（MODEL_TIMEOUT）；500/502/429 → ModelProviderError；401/403 → DeepSeekAuthError；畸形 JSON → `{"unparseable": True}` 交由 ACL 终判 INVALID_RESPONSE_SCHEMA；
- 空密钥构造即拒；**密钥与材料内容不出现在任何日志**（assertLogs 全文断言）。

### 2.2 kill switch / 熔断（同文件 2 项）

- kill switch：VENDOR_ENABLED=0 时 CT-004 照常入站建任务但**认领暂停**，任务保持 pending（无自动评分、不终态化）——稍后重试语义；
- 熔断：连续 2 次供应商失败（阈值=2 测试注入）→ 熔断开启暂停认领；冷却 0.6s 后自动半开恢复；成功重置计数。

### 2.3 staging 端到端（`scripts/e2e_vendor_deepseek.py`，8/8）

- 形态：staging PG + 本地 stub 供应商（仿真 /chat/completions）——**未接触真实供应商、未使用真实密钥**（dummy 占位）；worker 以 `MODEL_PROVIDER=deepseek` 真实装配（DeepSeekProvider.from_env → stub）；
- staging 假数据提交 → 自动 scored（无手工 tick）→ CT-007 投影 stub 等级 A；
- stub 捕获断言：请求为 JSON 模式；**外发文本无 submission_id/姓名/小组/邀请码/课程标识**；外发含批准范围内的最小化材料文本；Authorization 头仅存于传输层。

### 2.4 全量回归

- server+worker **473 tests 全绿**；ruff 全净；E2E SCENARIO-001/016 复跑通过；GAP-02 全链与 NFR 不受影响（fake 默认路径不变）。

## 3. 数据地域与合规决定（授权「自主决定」）

- 端点 `https://api.deepseek.com`（境内服务），学生材料不出境；密钥仅 .env/环境；外发字段白名单（evaluation_prompt、三桶材料、request_id）由 provider 构造，代码级不含其他字段；
- 合规备忘录已追加决策节（`vendor-compliance-memo.md` 附：供应商接入决策）。

## 4. 已知边界（如实登记）

1. **真实密钥首轮调用未执行**：无真实 key 可用；接入验证为 stub 形态。**发布检查表已列为灰度前置人工步骤**（真实 key + staging 假数据一笔提交，核对 CT-007 等级与无密钥日志）。
2. stub 未覆盖供应商真实应答风格漂移（真实模型 JSON 合规率）；`INVALID_RESPONSE_SCHEMA` 路径已由单测覆盖，灰度期经 `vendor_failures_total` + scoring_failed 可观测。
3. 熔断计数为进程内状态（多副本各自熔断；基线 2–3 副本下可接受，告警口径以 `vendor_circuit_opens_total` 为准）。
4. 模型版本锁定建议：灰度期间固定 `DEEPSEEK_MODEL`，版本变更另行评估（rubric 回归）。

## 5. 停止点

供应商接入受限实施完成。**等待用户最终发布批准**；发布前须完成检查表中的真实密钥首轮人工验证。
