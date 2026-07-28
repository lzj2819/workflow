---
doc_id: UNKNOWN-MOD-02-v1.0-SI-API-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-02-v1.0
parent_arch: architecture
module_name: SI-API
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:54.382788'
interface_refs: []
dependency_refs:
- SI-CORE
- SI-XFER
event_refs: []
implementation_surfaces:
- domain_logic
- observability
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D003: REQ-DD003
run_id: run_sess_42df8673
project_id: UNKNOWN-MOD-02-v1.0-SI-API-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-02-v1.0-SI-API-v1.0:root:run_sess_42df8673
artifact_type: prd
generator: prd-generation
schema_version: '2.0'
generator_version: '2.0'
input_artifacts: []
requirement_ids:
- REQ-DD003
doc_type: prd
oracle_blocked_count: 0
ready_for_test_generation: true
review_method: inheritance_allocation_gate
---

# Problem Statement

## 目标用户
该模块的上游调用方和受其行为影响的系统用户

## 痛点描述
上层节点中与 SI-API 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 SI-API 只承接自身拥有的行为（接收确认、认证/幂等接入与 30 秒同步接收编排），避免把父层复杂度平移到子 PRD。

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
| SM-001 | SM-001 | 提交接收成功率 | >=95% | 课程期间全部有效提交中成功返回接收确认的比例 |

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-007-01
- type: functional
- verifies: [REQ-DD003]
- release_scope: current
- actor: 服务器
- preconditions: 提交校验通过
- trigger: 材料包上传完成
- response: 返回接收确认并异步创建评分任务
- observable_oracles: 接收确认包含提交编号和 received_at；状态依次可观察为 received、processing、scored 或 scoring_failed
- boundaries: 并发提交达到至少 30 个 -> 仍为每个任务生成独立编号和状态
- exceptions: Agent 首次失败后自动重试一次 -> 再次失败标记 scoring_failed 并通知教师
- evidence_refs: D-007 | D-012 | D-014 | D-015 | parent_acceptance_contract:AC-REQ-007-01 | contract_projection:MOD-02:shared | parent_acceptance_contract:D-AC-REQ-007-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD003 | functional | current | D-AC-REQ-007-01 | ready | - |