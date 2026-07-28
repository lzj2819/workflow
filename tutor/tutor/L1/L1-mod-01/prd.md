---
doc_id: UNKNOWN-MOD-01-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN
parent_arch: architecture
module_name: MOD-01
author: Claude
status: complete
priority: P0
created_at: '2026-07-18T13:01:30.131634'
interface_refs: []
dependency_refs:
- MOD-05
- MOD-02
- MOD-03
event_refs: []
implementation_surfaces:
- domain_logic
- worker_job
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
上层节点中与 MOD-01 相关的行为需要被收窄到该模块边界内：插件应识别包含作业、姓名和小组信息的自然语言提交意图，并启动一次提交。

## 机会窗口
由 MOD-01 只承接自身拥有的行为（codex-plugin），避免把父层复杂度平移到子 PRD。

# Requirements

## Current Release — Functional Requirements

### Must Have
- [REQ-D001] 插件应识别包含作业、姓名和小组信息的自然语言提交意图，并启动一次提交。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-001
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic, worker_job]
  - evidence_refs: [user decision D-001, parent_requirement:REQ-001]
- [REQ-D002] 插件应允许学生配置课程邀请码、姓名、小组、代码目录、截图目录和项目结果目录。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-002
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic]
  - evidence_refs: [user decision D-002, parent_requirement:REQ-002]
- [REQ-D003] 每次提交应采集当前作业项目相关的完整 Codex 对话。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-003
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic, worker_job]
  - evidence_refs: [user decision D-003, parent_requirement:REQ-003]
- [REQ-D004] 每次提交应按插件配置收集代码、截图和项目结果文件，并将其关联到作业、姓名和小组。
  - release_scope: current
  - requirement_kind: atomic
  - parent_req: REQ-004
  - source_kind: parent_requirement
  - implementation_surfaces: [domain_logic, worker_job]
  - evidence_refs: [user decision D-004, parent_requirement:REQ-004]

## Current Release — Non-functional Requirements

# 架构输入契约

## 系统边界
- 继承 `../../L0-root/architecture/01-system-overview.md` 与 `02-runtime-architecture.md` 定义的系统边界；本节点仅实现 REQ-D001 至 REQ-D004 的插件侧提交采集职责，不新增边界。

## 外部依赖
- 继承父层已批准的宿主 Codex 环境、提交服务和本地文件系统集成；本节点不引入新的外部依赖。

## 明确约束
- 继承父层的身份校验、隐私保护、异步处理与可观测性约束；具体接口契约见 `../../L0-root/architecture/04-interface-contracts.md`。

## 需要人工确认的架构决策
- 本节点没有未决的架构决策；任何超出父层已批准契约的变更须返回 L0-root 处理。

# Success Metrics

| ID | Metric | Target | Measurement | Verifies |
|---|---|---|---|---|

# Acceptance Contracts

> 本节定义业务判定依据；不包含测试用例或 Gherkin。下游只能据此展开测试技术。

## D-AC-REQ-001-01
- type: functional
- verifies: [REQ-D001]
- release_scope: current
- actor: 学生
- preconditions: 插件已绑定课程且配置可读取
- trigger: 学生发送包含作业、姓名和小组的自然语言提交指令
- response: 插件创建提交任务并将身份、作业和配置目录提交到服务器
- observable_oracles: 返回唯一提交编号；服务器记录作业、姓名和小组；未包含任一必填信息时不创建可评分提交
- boundaries: 缺少作业、姓名或小组 -> ，返回具体缺失字段并保持提交状态为信息不完整
- exceptions: 插件无法连接服务器 -> ，保留本地待上传任务并显示失败原因
- evidence_refs: D-001 | parent_acceptance_contract:AC-REQ-001-01

## D-AC-REQ-002-01
- type: functional
- verifies: [REQ-D002]
- release_scope: current
- actor: 学生
- preconditions: 插件设置页可用
- trigger: 学生保存课程邀请码、姓名、小组和三个目录配置
- response: 插件保存配置并在下次提交时使用
- observable_oracles: 配置重新打开后值一致；目录不可读时显示具体目录错误
- boundaries: 任一目录为空 -> ，配置保存为不完整并列出缺失项
- exceptions: 配置格式无效 -> 拒绝保存并保留上一次有效配置
- evidence_refs: D-002 | parent_acceptance_contract:AC-REQ-002-01

## D-AC-REQ-003-01
- type: functional
- verifies: [REQ-D003, REQ-D004]
- release_scope: current
- actor: 服务器接收服务
- preconditions: 提交任务包含身份、作业和目录配置
- trigger: 插件上传对话及材料包
- response: 服务器保存材料并执行课程邀请码、姓名和小组校验
- observable_oracles: 提交详情可列出对话、代码、截图、结果及缺失项；校验通过后状态进入 processing；校验失败时状态为 rejected 且记录原因
- boundaries: 材料目录存在但为空 -> ，提交进入评分并明确标记该材料缺失
- exceptions: 上传中断 -> ，提交状态为 upload_failed，教师端可见失败原因
- evidence_refs: D-003 | D-004 | D-005 | D-011 | parent_acceptance_contract:AC-REQ-003-01 | contract_projection:MOD-01:shared

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-D001 | functional | current | D-AC-REQ-001-01 | ready | - |
| REQ-D002 | functional | current | D-AC-REQ-002-01 | ready | - |
| REQ-D003 | functional | current | D-AC-REQ-003-01 | ready | - |
| REQ-D004 | functional | current | D-AC-REQ-003-01 | ready | - |
