---
doc_id: UNKNOWN-MOD-01-v1.0-CMP-MATERIAL-COLLECTOR-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-01-v1.0
parent_arch: architecture
module_name: CMP-MATERIAL-COLLECTOR
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:52.366887'
interface_refs: []
dependency_refs:
- CMP-DIALOGUE-COLLECTOR
- CMP-PENDING-QUEUE
- CMP-UPLOAD-CLIENT
- CMP-CONFIG-STORE
- CMP-INTENT-PARSER
- CMP-STATUS-PRESENTER
event_refs: []
implementation_surfaces:
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D004: REQ-DD004
run_id: run_sess_1485f391
project_id: UNKNOWN-MOD-01-v1.0-CMP-MATERIAL-COLLECTOR-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-01-v1.0-CMP-MATERIAL-COLLECTOR-v1.0:root:run_sess_1485f391
artifact_type: prd
generator: prd-generation
schema_version: '2.0'
generator_version: '2.0'
input_artifacts: []
requirement_ids:
- REQ-DD004
doc_type: prd
oracle_blocked_count: 0
ready_for_test_generation: true
review_method: inheritance_allocation_gate
---

# Problem Statement

## 目标用户
该模块的上游调用方和受其行为影响的系统用户

## 痛点描述
上层节点中与 CMP-MATERIAL-COLLECTOR 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-MATERIAL-COLLECTOR 只承接自身拥有的行为（按配置目录收集代码/截图/项目结果文件；白名单过滤与 500MB 预算预检（LCD-003）；生成 MaterialManifest 并关联作业/姓名/小组），避免把父层复杂度平移到子 PRD。

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

## D-AC-REQ-003-01
- type: functional
- verifies: [REQ-DD004]
- release_scope: current
- actor: 服务器接收服务
- preconditions: 提交任务包含身份、作业和目录配置
- trigger: 插件上传对话及材料包
- response: 服务器保存材料并执行课程邀请码、姓名和小组校验
- observable_oracles: 提交详情可列出对话、代码、截图、结果及缺失项；校验通过后状态进入 processing；校验失败时状态为 rejected 且记录原因
- boundaries: 材料目录存在但为空 -> ，提交进入评分并明确标记该材料缺失
- exceptions: 上传中断 -> ，提交状态为 upload_failed，教师端可见失败原因
- evidence_refs: D-003 | D-004 | D-005 | D-011 | parent_acceptance_contract:AC-REQ-003-01 | contract_projection:MOD-01:shared | parent_acceptance_contract:D-AC-REQ-003-01 | contract_projection:CMP-MATERIAL-COLLECTOR:shared

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD004 | functional | current | D-AC-REQ-003-01 | ready | - |