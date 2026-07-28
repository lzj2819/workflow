---
doc_id: UNKNOWN-MOD-01-v1.0-CMP-CONFIG-STORE-v1.0
version: 1.0.0
layer: derive
parent_doc: UNKNOWN-MOD-01-v1.0
parent_arch: architecture
module_name: CMP-CONFIG-STORE
author: Claude
status: complete
priority: P0
created_at: '2026-07-19T17:47:51.170274'
interface_refs: []
dependency_refs:
- CMP-STATUS-PRESENTER
- CMP-PENDING-QUEUE
- CMP-DIALOGUE-COLLECTOR
- CMP-INTENT-PARSER
- CMP-MATERIAL-COLLECTOR
- CMP-UPLOAD-CLIENT
event_refs: []
implementation_surfaces:
- domain_logic
- integration_wiring
inheritance_complete: true
release_scope_frozen: true
requirement_id_mapping:
  REQ-D002: REQ-DD002
run_id: run_sess_97baee3d
project_id: UNKNOWN-MOD-01-v1.0-CMP-CONFIG-STORE-v1.0
node_id: root
parent_node_id: null
artifact_id: prd:UNKNOWN-MOD-01-v1.0-CMP-CONFIG-STORE-v1.0:root:run_sess_97baee3d
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
上层节点中与 CMP-CONFIG-STORE 相关的行为需要被收窄到该模块边界内：functional

## 机会窗口
由 CMP-CONFIG-STORE 只承接自身拥有的行为（PluginConfig 的持久化、读取、保存校验（格式、目录可读性）、不完整标记；拒绝无效配置并保留上一次有效配置），避免把父层复杂度平移到子 PRD。

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

## D-AC-REQ-002-01
- type: functional
- verifies: [REQ-DD002]
- release_scope: current
- actor: 学生
- preconditions: 插件设置页可用
- trigger: 学生保存课程邀请码、姓名、小组和三个目录配置
- response: 插件保存配置并在下次提交时使用
- observable_oracles: 配置重新打开后值一致；目录不可读时显示具体目录错误
- boundaries: 任一目录为空 -> ，配置保存为不完整并列出缺失项
- exceptions: 配置格式无效 -> 拒绝保存并保留上一次有效配置
- evidence_refs: D-002 | parent_acceptance_contract:AC-REQ-002-01 | parent_acceptance_contract:D-AC-REQ-002-01

## Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-DD002 | functional | current | D-AC-REQ-002-01 | ready | - |