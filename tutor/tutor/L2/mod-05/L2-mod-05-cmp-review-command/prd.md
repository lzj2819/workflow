---
doc_id: UNKNOWN-MOD-05-v1.0-CMP-REVIEW-COMMAND-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-05-v1.0
parent_arch: architecture
module_name: CMP-REVIEW-COMMAND
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:58.133788'
interface_refs: []
dependency_refs:
- CMP-REVIEW-QUERY
- CMP-TEACHER-UI
- CMP-PRESENTATION
event_refs: []
implementation_surfaces:
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D001: REQ-DD001
run_id: run_sess_bb825aaf
project_id: UNKNOWN-MOD-05-v1.0-CMP-REVIEW-COMMAND-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-05-v1.0-CMP-REVIEW-COMMAND-v1.0:root:run_sess_bb825aaf
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
上层节点中与 CMP-REVIEW-COMMAND 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-REVIEW-COMMAND 只承接自身拥有的行为（批注、最终等级调整、ReviewRecord 留痕与禁伪造校验），避免把父层复杂度平移到子 PRD。

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

## D-AC-REQ-009-01
- type: functional
- verifies: [REQ-DD001]
- release_scope: current
- actor: 教师
- preconditions: 教师已登录并具有课程查看权限
- trigger: 教师打开课程、小组或学生提交详情
- response: 展示提交材料、处理状态、Agent 原始等级、依据、建议、批注和最终等级编辑入口
- observable_oracles: 教师可保存批注和调整后的等级；系统同时保留原始等级、最终等级、操作者和时间
- boundaries: 评分失败 -> 展示失败原因和重试结果，而不是伪造等级
- exceptions: 无权限访问其他课程 -> 拒绝读取并记录访问拒绝
- evidence_refs: D-009 | parent_acceptance_contract:AC-REQ-009-01 | parent_acceptance_contract:D-AC-REQ-009-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD001 | functional | current | D-AC-REQ-009-01 | ready | - |