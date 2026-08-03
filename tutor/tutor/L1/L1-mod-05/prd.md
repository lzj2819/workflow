---
doc_id: UNKNOWN-MOD-05-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN
parent_arch: architecture
module_name: MOD-05
author: Claude
status: complete
priority: P0
created_at: '2026-07-18T13:01:31.655879'
interface_refs: []
dependency_refs:
- MOD-01
- MOD-02
- MOD-04
- MOD-03
event_refs: []
implementation_surfaces:
- frontend
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
doc_type: prd
schema_version: '2.0'
oracle_blocked_count: 0
ready_for_test_generation: true
review_method: inheritance_allocation_gate
---

# Problem Statement

## 目标用户
该模块的上游调用方和受其行为影响的系统用户

## 痛点描述
上层节点中与 MOD-05 相关的行为需要被收窄到该模块边界内：教师应能查看课程、小组、学生详情、提交材料、评分依据、建议和处理状态，并可批注及调整最终等级。

## 机会窗口
由 MOD-05 只承接自身拥有的行为（teacher-web），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

### Must Have
- [REQ-D001] 教师应能查看课程、小组、学生详情、提交材料、评分依据、建议和处理状态，并可批注及调整最终等级。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-009
  - source_kind: parent_requirement
  - implementation_surfaces: [frontend, domain_logic]
  - evidence_refs: [user decision D-009, parent_requirement:REQ-009]
- [REQ-D002] 教师应能选择小组并生成包含项目结果、过程摘要、评分和教师批注的展示视图。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-010
  - source_kind: parent_requirement
  - implementation_surfaces: [frontend, domain_logic]
  - evidence_refs: [user decision D-010, parent_requirement:REQ-010]

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- 继承 `../../L0-root/architecture/01-system-overview.md` 与 `03-data-and-consistency.md` 定义的系统和数据边界；本节点仅实现 REQ-D009、REQ-D010 的教师评阅与展示职责，不新增边界。

## 外部依赖
- 继承父层已批准的评分记录、材料存储和教师端集成；本节点不引入新的外部依赖。

## 明确约束
- 继承父层的教师授权、评分历史、材料可见性与数据保留约束；具体接口契约见 `../../L0-root/architecture/04-interface-contracts.md`。

## 需要人工确认的架构决策
- 本节点没有未决的架构决策；任何超出父层已批准契约的变更须返回 L0-root 处理。

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-009-01
- type: functional
- verifies: [REQ-D001]
- release_scope: current
- actor: 教师
- preconditions: 教师已登录并具有课程查看权限
- trigger: 教师打开课程、小组或学生提交详情
- response: 展示提交材料、处理状态、Agent 原始等级、依据、建议、批注和最终等级编辑入口
- observable_oracles: 教师可保存批注和调整后的等级；系统同时保留原始等级、最终等级、操作者和时间
- boundaries: 评分失败 -> 展示失败原因和重试结果，而不是伪造等级
- exceptions: 无权限访问其他课程 -> 拒绝读取并记录访问拒绝
- evidence_refs: D-009 | parent_acceptance_contract:AC-REQ-009-01

## D-AC-REQ-010-01
- type: functional
- verifies: [REQ-D002]
- release_scope: current
- actor: 教师
- preconditions: 课程中至少存在一个小组提交
- trigger: 教师选择一个或多个小组并生成展示视图
- response: 生成展示视图，包含项目结果、过程摘要、评分和教师批注
- observable_oracles: 展示视图中的小组与所选小组一致；视图可在教师网页端打开
- boundaries: 小组缺少某类材料 -> 展示缺失标记，不隐藏缺口
- exceptions: 小组无可用提交 -> 阻止生成并说明原因
- evidence_refs: D-010 | parent_acceptance_contract:AC-REQ-010-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-D001 | functional | current | D-AC-REQ-009-01 | ready | - |
| REQ-D002 | functional | current | D-AC-REQ-010-01 | ready | - |
