---
doc_id: UNKNOWN-MOD-02-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN
parent_arch: architecture
module_name: MOD-02
author: Claude
status: complete
priority: P0
created_at: '2026-07-18T13:01:30.508230'
interface_refs: []
dependency_refs:
- MOD-04
- MOD-01
- MOD-05
- MOD-03
event_refs: []
implementation_surfaces:
- domain_logic
- worker_job
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
上层节点中与 MOD-02 相关的行为需要被收窄到该模块边界内：每次提交应采集当前作业项目相关的完整 Codex 对话。

## 机会窗口
由 MOD-02 只承接自身拥有的行为（submission-intake），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

### Must Have
- [REQ-D001] 每次提交应采集当前作业项目相关的完整 Codex 对话。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-003
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic, worker_job]
  - evidence_refs: [user decision D-003, parent_requirement:REQ-003]
- [REQ-D002] 每次提交应按插件配置收集代码、截图和项目结果文件，并将其关联到作业、姓名和小组。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-004
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic, worker_job]
  - evidence_refs: [user decision D-004, parent_requirement:REQ-004]
- [REQ-D003] 上传成功后系统应返回接收确认，并异步执行 Agent 评分。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-007
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic]
  - evidence_refs: [user decision D-007, parent_requirement:REQ-007]
- [REQ-D004] 材料不完整时系统应允许提交进入评分，并在教师端标记缺失项。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-011
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic]
  - evidence_refs: [user decision D-011, parent_requirement:REQ-011]

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- 继承 `../../L0-root/architecture/01-system-overview.md` 与 `02-runtime-architecture.md` 定义的系统边界；本节点仅实现 REQ-D005、REQ-D007、REQ-D011 的接收与异步协调职责，不新增边界。

## 外部依赖
- 继承父层已批准的提交服务、队列和 Agent 评分集成；本节点不引入新的外部依赖。

## 明确约束
- 继承父层的课程归属校验、接收确认时限、异步处理与失败可见性约束；具体接口契约见 `../../L0-root/architecture/04-interface-contracts.md`。

## 需要人工确认的架构决策
- 本节点没有未决的架构决策；任何超出父层已批准契约的变更须返回 L0-root 处理。

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|
| SM-001 | SM-001 | 提交接收成功率 | >=95% | 课程期间全部有效提交中成功返回接收确认的比例 | - |

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-003-01
- type: functional
- verifies: [REQ-D001, REQ-D002, REQ-D004]
- release_scope: current
- actor: 服务器接收服务
- preconditions: 提交任务包含身份、作业和目录配置
- trigger: 插件上传对话及材料包
- response: 服务器保存材料并执行课程邀请码、姓名和小组校验
- observable_oracles: 提交详情可列出对话、代码、截图、结果及缺失项；校验通过后状态进入 processing；校验失败时状态为 rejected 且记录原因
- boundaries: 材料目录存在但为空 -> ，提交进入评分并明确标记该材料缺失
- exceptions: 上传中断 -> ，提交状态为 upload_failed，教师端可见失败原因
- evidence_refs: D-003 | D-004 | D-005 | D-011 | parent_acceptance_contract:AC-REQ-003-01 | contract_projection:MOD-02:shared

## D-AC-REQ-007-01
- type: functional
- verifies: [REQ-D003]
- release_scope: current
- actor: 服务器
- preconditions: 提交校验通过
- trigger: 材料包上传完成
- response: 返回接收确认并异步创建评分任务
- observable_oracles: 接收确认包含提交编号和 received_at；状态依次可观察为 received、processing、scored 或 scoring_failed
- boundaries: 并发提交达到至少 30 个 -> 仍为每个任务生成独立编号和状态
- exceptions: Agent 首次失败后自动重试一次 -> 再次失败标记 scoring_failed 并通知教师
- evidence_refs: D-007 | D-012 | D-014 | D-015 | parent_acceptance_contract:AC-REQ-007-01 | contract_projection:MOD-02:shared

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-D001 | functional | current | D-AC-REQ-003-01 | ready | - |
| REQ-D002 | functional | current | D-AC-REQ-003-01 | ready | - |
| REQ-D003 | functional | current | D-AC-REQ-007-01 | ready | - |
| REQ-D004 | functional | current | D-AC-REQ-003-01 | ready | - |
