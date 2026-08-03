---
doc_id: UNKNOWN-MOD-03-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN
parent_arch: architecture
module_name: MOD-03
author: Claude
status: complete
priority: P0
created_at: '2026-07-18T13:01:30.893746'
interface_refs: []
dependency_refs:
- MOD-02
- MOD-05
- MOD-01
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
上层节点中与 MOD-03 相关的行为需要被收窄到该模块边界内：服务器应使用课程邀请码、课程名单以及提交中的姓名和小组校验课程归属。

## 机会窗口
由 MOD-03 只承接自身拥有的行为（course-roster），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

### Must Have
- [REQ-D001] 服务器应使用课程邀请码、课程名单以及提交中的姓名和小组校验课程归属。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-005
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic]
  - evidence_refs: [user decision D-005, parent_requirement:REQ-005]
- [REQ-D002] 学生修改姓名或小组后，服务器应在每次提交时重新执行校验。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-006
  - source_kind: parent_requirement
  - implementation_surfaces: [frontend, domain_logic]
  - evidence_refs: [user decision D-006, parent_requirement:REQ-006]

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- 继承 `../../L0-root/architecture/01-system-overview.md` 与 `03-data-and-consistency.md` 定义的系统和数据边界；本节点仅实现 REQ-D006 的课程名单与身份复核职责，不新增边界。

## 外部依赖
- 继承父层已批准的课程名单数据源、提交服务和教师端集成；本节点不引入新的外部依赖。

## 明确约束
- 继承父层的课程归属校验、数据最小化、访问控制与审计约束；具体接口契约见 `../../L0-root/architecture/04-interface-contracts.md`。

## 需要人工确认的架构决策
- 本节点没有未决的架构决策；任何超出父层已批准契约的变更须返回 L0-root 处理。

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-003-01
- type: functional
- verifies: [REQ-D001]
- release_scope: current
- actor: 服务器接收服务
- preconditions: 提交任务包含身份、作业和目录配置
- trigger: 插件上传对话及材料包
- response: 服务器保存材料并执行课程邀请码、姓名和小组校验
- observable_oracles: 提交详情可列出对话、代码、截图、结果及缺失项；校验通过后状态进入 processing；校验失败时状态为 rejected 且记录原因
- boundaries: 材料目录存在但为空 -> ，提交进入评分并明确标记该材料缺失
- exceptions: 上传中断 -> ，提交状态为 upload_failed，教师端可见失败原因
- evidence_refs: D-003 | D-004 | D-005 | D-011 | parent_acceptance_contract:AC-REQ-003-01 | contract_projection:MOD-03:shared

## D-AC-REQ-006-01
- type: functional
- verifies: [REQ-D002]
- release_scope: current
- actor: 服务器身份校验服务
- preconditions: 学生已有一次提交记录；插件设置中的姓名或小组信息已被修改；新的提交包含课程邀请码、当前姓名和当前小组
- trigger: 学生再次发起提交并上传材料包
- response: 服务器针对本次提交读取并校验当前提交中的姓名和小组，不得沿用上一次提交的校验结果；校验通过则进入 processing，校验失败则进入 rejected
- observable_oracles: 本次提交存在独立的校验时间/校验记录；当前身份有效时本次提交进入 processing；当前姓名或小组无效时即使上一次提交有效，本次提交仍进入 rejected 并记录具体原因
- boundaries: 仅修改姓名、仅修改小组、同 -> 修改姓名和小组三种情况都分别触发本次提交的重新校验
- exceptions: 课程名单服务不可用 -> ，本次提交不复用旧校验结果，进入 identity_validation_failed 并记录可重试原因
- evidence_refs: D-006 | parent_acceptance_contract:AC-REQ-006-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-D001 | functional | current | D-AC-REQ-003-01 | ready | - |
| REQ-D002 | functional | current | D-AC-REQ-006-01 | ready | - |
