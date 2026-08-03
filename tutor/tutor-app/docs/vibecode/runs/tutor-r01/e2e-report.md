# E2E Report — tutor-r01 / B-05

- 日期：2026-07-21；执行：Integration Owner
- 范围：不依赖 L07（TD-01）与 CCR-001 的 scenario chain 联调。**SCENARIO-016 保持 blocked。**

## 结果

| 场景 | 脚本 | 结果 |
|---|---|---|
| SCENARIO-001 学生提交到评分完成主链路 | `scripts/e2e_scenario_001.py` | **E2E_OK**（18 断言全过） |
| SCENARIO-012 模型评估调用与失败重试链路 | `scripts/e2e_scenario_012.py` | **E2E_OK**（9 断言全过） |
| SCENARIO-016 保留期到期与确认删除链路 | — | **BLOCKED**（见下） |

## SCENARIO-001 覆盖点（真实组合根 + 真实 relay + 真实 rubric/ACL fake）

预置（课程/名单/教师）→ auth-token → CT-001 received（CT-004/006 入队）→ 进程外 worker 侧消费 CT-004（脚本驱动；生产为 DU-3 relay）→ LCD-003 received→processing（task_persisted ack）→ 认领 → L12（真实 RubricPromptComposer + ModelServiceAcl + FakeVendorAdapter，fake 来源标注）→ L03 scored → relay 投递 CT-005 → L02 scored + projector（M05-IC-01 建复核记录）→ CT-002 scored → 教师登录 → CT-007 original_grade=C → CT-008 final=A+批注 → CT-009 展示视图 → SSR 页面可见 final=A 与批注；负例：错误邀请码 → rejected。

## SCENARIO-012 覆盖点

- 子场景 A：MODEL_TIMEOUT 首败 → RetryEntered（attempts→2）→ 同租约任务内重试成功 → scored → CT-007 含 original_grade=B。
- 子场景 B：两次均败 → scoring_failed 终态 → CT-007 有 failure_reason + retry_record、无 original/final grade（不伪造）→ SSR 页展示原因、无 grade-value。

## 保持 blocked 的能力与可观测证据

| 项 | 状态 | 证据与原因 |
|---|---|---|
| SCENARIO-016 保留删除端到端 | **blocked** | CCR-001 pending：AssessmentResult 删除接线未获批准。组件级已就绪且经测试（B03c 到期标记/CT-011/审计先行/CT-012 发布、B01c CT-012 清除/CT-014 回传、B03b CT-012 自消费清除投影），但**不声称端到端完成**；CT-012 消费者仍冻结为 [MOD-02, MOD-05]（contracts/ct-012.json 未动） |
| REQ-003 完整 Codex 对话采集 | **blocked（TD-01）** | 宿主导出机制未确认；L07 未启动；host port 显式 HostUnsupportedError，插件组装（B-04）对该失败如实呈现不伪造 |
| 真实模型供应商评估 | **blocked（用户禁令）** | 仅 FakeModelProvider/FakeVendorAdapter；MODEL_PROVIDER=fake；无密钥、无外发 |

## 接线注记（生产接线建议，不阻塞本报告）

1. **received→processing 驱动**：生产环境 DU-2 需要一个「CT-004 消费确认 → advance_to_processing(task_persisted)」的接线点（本 E2E 由脚本显式驱动）。建议：DU-2 relayer 增加 CT-004 confirmed 后置钩子，或在 DU-3 relay 确认后写回 ack；登记为 Phase 5 遗留（见 phase-5-verification-report §6）。
2. relay 为进程内 tick 驱动钩子（组合根 relayer_tick）；生产需进程内调度器周期调用（docs/operations.md 已记）。
3. CT-004 的消费方在 DU-3 进程（生产）；本 E2E 由脚本扮演该消费方并验证载荷与确认语义。
