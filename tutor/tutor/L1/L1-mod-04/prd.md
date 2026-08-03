---
doc_id: UNKNOWN-MOD-04-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN
parent_arch: architecture
module_name: MOD-04
author: Claude
status: complete
priority: P0
created_at: '2026-07-18T13:01:31.270316'
interface_refs: []
dependency_refs:
- MOD-02
- MOD-05
- MOD-01
- MOD-03
event_refs: []
implementation_surfaces:
- frontend
- domain_logic
- observability
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
上层节点中与 MOD-04 相关的行为需要被收窄到该模块边界内：Agent 应基于需求理解、Codex 迭代过程、代码质量、最终功能、文档/展示完整性输出 A–E 等级、分维度依据和改进建议。

## 机会窗口
由 MOD-04 只承接自身拥有的行为（assessment），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

### Must Have
- [REQ-D001] Agent 应基于需求理解、Codex 迭代过程、代码质量、最终功能、文档/展示完整性输出 A–E 等级、分维度依据和改进建议。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-008
  - source_kind: parent_requirement
  - implementation_surfaces: [frontend, domain_logic]
  - evidence_refs: [user decision D-008, parent_requirement:REQ-008]
- [REQ-D002] Agent 评分失败时系统应自动重试一次；仍失败时应标记“评分失败”并通知教师。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-012
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic]
  - evidence_refs: [user decision D-012, parent_requirement:REQ-012]

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- 继承 `../../L0-root/architecture/01-system-overview.md` 与 `02-runtime-architecture.md` 定义的系统边界；本节点仅实现 REQ-D008、REQ-D012 的评分编排与重试职责，不新增边界。

## 外部依赖
- 继承父层已批准的 Agent 评分服务、任务队列和教师通知集成；本节点不引入新的外部依赖。

## 明确约束
- 继承父层的评分时限、一次自动重试、失败状态可见性与审计约束；具体接口契约见 `../../L0-root/architecture/04-interface-contracts.md`。

## 需要人工确认的架构决策
- 本节点没有未决的架构决策；任何超出父层已批准契约的变更须返回 L0-root 处理。

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|
| SM-002 | SM-002 | 评分按时完成率 | >=95% | 课程期间全部有效提交中 10 分钟内完成评分的比例 | - |
| SM-003 | SM-003 | 教师评分覆盖率 | >=95% | 课程结束前具有 Agent 结果或明确失败状态的提交比例 | - |

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-008-01
- type: functional
- verifies: [REQ-D001, REQ-D002]
- release_scope: current
- actor: Agent 评分服务
- preconditions: 提交状态为 processing 且材料可读取
- trigger: Agent 开始独立评估
- response: 生成 A–E 等级、五个维度依据和教师专用改进建议
- observable_oracles: 结果包含等级、每个维度文字依据、建议和评分时间；建议默认不暴露给学生
- boundaries: 材料不完整 -> 仍生成结果，并列出缺失材料对评估的影响
- exceptions: 评估失败按 AC-REQ-007-01 重试并通知教师
- evidence_refs: D-008 | D-011 | D-012 | parent_acceptance_contract:AC-REQ-008-01 | contract_projection:MOD-04:shared

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-D001 | functional | current | D-AC-REQ-008-01 | ready | - |
| REQ-D002 | functional | current | D-AC-REQ-008-01 | ready | - |
