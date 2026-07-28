---
doc_id: UNKNOWN-MOD-05-v1.0-CMP-PRESENTATION-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-05-v1.0
parent_arch: architecture
module_name: CMP-PRESENTATION
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:57.752038'
interface_refs: []
dependency_refs:
- CMP-TEACHER-UI
- CMP-REVIEW-QUERY
- CMP-REVIEW-COMMAND
event_refs: []
implementation_surfaces:
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D002: REQ-DD002
run_id: run_sess_28ffa69f
project_id: UNKNOWN-MOD-05-v1.0-CMP-PRESENTATION-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-05-v1.0-CMP-PRESENTATION-v1.0:root:run_sess_28ffa69f
artifact_type: prd
generator: prd-generation
schema_version: '2.0'
generator_version: '2.0'
input_artifacts: []
requirement_ids:
- REQ-DD002
doc_type: prd
oracle_blocked_count: 0
ready_for_test_generation: true
review_method: inheritance_allocation_gate
---

# Problem Statement

## 目标用户
该模块的上游调用方和受其行为影响的系统用户

## 痛点描述
上层节点中与 CMP-PRESENTATION 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-PRESENTATION 只承接自身拥有的行为（展示视图生成、缺失标记装配、快照写入与幂等再生成），避免把父层复杂度平移到子 PRD。

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

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-010-01
- type: functional
- verifies: [REQ-DD002]
- release_scope: current
- actor: 教师
- preconditions: 课程中至少存在一个小组提交
- trigger: 教师选择一个或多个小组并生成展示视图
- response: 生成展示视图，包含项目结果、过程摘要、评分和教师批注
- observable_oracles: 展示视图中的小组与所选小组一致；视图可在教师网页端打开
- boundaries: 小组缺少某类材料 -> 展示缺失标记，不隐藏缺口
- exceptions: 小组无可用提交 -> 阻止生成并说明原因
- evidence_refs: D-010 | parent_acceptance_contract:AC-REQ-010-01 | parent_acceptance_contract:D-AC-REQ-010-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD002 | functional | current | D-AC-REQ-010-01 | ready | - |