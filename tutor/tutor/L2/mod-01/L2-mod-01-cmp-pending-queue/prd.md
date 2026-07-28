---
doc_id: UNKNOWN-MOD-01-v1.0-CMP-PENDING-QUEUE-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-01-v1.0
parent_arch: architecture
module_name: CMP-PENDING-QUEUE
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:52.849382'
interface_refs: []
dependency_refs:
- CMP-INTENT-PARSER
- CMP-STATUS-PRESENTER
- CMP-UPLOAD-CLIENT
- CMP-DIALOGUE-COLLECTOR
- CMP-MATERIAL-COLLECTOR
- CMP-CONFIG-STORE
event_refs: []
implementation_surfaces:
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D001: REQ-DD001
run_id: run_sess_2c704607
project_id: UNKNOWN-MOD-01-v1.0-CMP-PENDING-QUEUE-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-01-v1.0-CMP-PENDING-QUEUE-v1.0:root:run_sess_2c704607
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
上层节点中与 CMP-PENDING-QUEUE 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-PENDING-QUEUE 只承接自身拥有的行为（PendingTask 聚合的创建、状态机推进、失败原因记录、恢复调度（worker_job）；上传前置检查；任务终态清理），避免把父层复杂度平移到子 PRD。

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

## D-AC-REQ-001-01
- type: functional
- verifies: [REQ-DD001]
- release_scope: current
- actor: 学生
- preconditions: 插件已绑定课程且配置可读取
- trigger: 学生发送包含作业、姓名和小组的自然语言提交指令
- response: 插件创建提交任务并将身份、作业和配置目录提交到服务器
- observable_oracles: 返回唯一提交编号；服务器记录作业、姓名和小组；未包含任一必填信息时不创建可评分提交
- boundaries: 缺少作业、姓名或小组 -> ，返回具体缺失字段并保持提交状态为信息不完整
- exceptions: 插件无法连接服务器 -> ，保留本地待上传任务并显示失败原因
- evidence_refs: D-001 | parent_acceptance_contract:AC-REQ-001-01 | parent_acceptance_contract:D-AC-REQ-001-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD001 | functional | current | D-AC-REQ-001-01 | ready | - |