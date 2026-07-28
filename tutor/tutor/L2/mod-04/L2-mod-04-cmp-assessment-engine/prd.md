---
doc_id: UNKNOWN-MOD-04-v1.0-CMP-ASSESSMENT-ENGINE-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-04-v1.0
parent_arch: architecture
module_name: CMP-ASSESSMENT-ENGINE
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:55.480738'
interface_refs:
- ICT-002
- ICT-003
- ICT-004
dependency_refs:
- CMP-SCORING-ORCHESTRATOR
event_refs: []
implementation_surfaces:
- domain_logic
- observability
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D001: REQ-DD001
run_id: run_sess_32c0b219
project_id: UNKNOWN-MOD-04-v1.0-CMP-ASSESSMENT-ENGINE-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-04-v1.0-CMP-ASSESSMENT-ENGINE-v1.0:root:run_sess_32c0b219
artifact_type: prd
generator: prd-generation
schema_version: '2.0'
generator_version: '2.0'
input_artifacts: []
requirement_ids:
- REQ-DD001
doc_type: prd
oracle_blocked_count: 0
ready_for_test_generation: true
review_method: inheritance_allocation_gate
---

# Problem Statement

## 目标用户
该模块的上游调用方和受其行为影响的系统用户

## 痛点描述
上层节点中与 CMP-ASSESSMENT-ENGINE 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-ASSESSMENT-ENGINE 只承接自身拥有的行为（评估执行、等级/五维依据/教师建议校验与结果装配），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- [待补充；不得由生成器擅自决定]

## 外部依赖
- [待补充；不得由生成器擅自决定]

## 明确约束
- [待补充；不得由生成器擅自决定]

## 需要人工确认的架构决策
- [待补充；不得由生成器擅自决定]

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|
| SM-002 | SM-002 | 评分按时完成率 | >=95% | 课程期间全部有效提交中 10 分钟内完成评分的比例 |
| SM-003 | SM-003 | 教师评分覆盖率 | >=95% | 课程结束前具有 Agent 结果或明确失败状态的提交比例 |

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-008-01
- type: functional
- verifies: [REQ-DD001]
- release_scope: current
- actor: Agent 评分服务
- preconditions: 提交状态为 processing 且材料可读取
- trigger: Agent 开始独立评估
- response: 生成 A–E 等级、五个维度依据和教师专用改进建议
- observable_oracles: 结果包含等级、每个维度文字依据、建议和评分时间；建议默认不暴露给学生
- boundaries: 材料不完整 -> 仍生成结果，并列出缺失材料对评估的影响
- exceptions: 评估失败按 AC-REQ-007-01 重试并通知教师
- evidence_refs: D-008 | D-011 | D-012 | parent_acceptance_contract:AC-REQ-008-01 | contract_projection:MOD-04:shared | parent_acceptance_contract:D-AC-REQ-008-01 | contract_projection:CMP-ASSESSMENT-ENGINE:shared

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD001 | functional | current | D-AC-REQ-008-01 | ready | - |