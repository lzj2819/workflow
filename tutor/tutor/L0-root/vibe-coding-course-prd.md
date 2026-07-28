---
doc_type: prd
schema_version: "2.0"
status: approved
release_scope_frozen: true
ready_for_test_generation: true
oracle_blocked_count: 0
review_method: independent_agent
agent_review_passed: true
---

# Problem Statement

大学 Vibe Coding 课堂通常只能收到最终代码或截图。面对约 100 名学生、20–50 个小组，教师无法逐一了解学生如何使用 Codex 迭代，也难以基于过程和结果进行一致评分与课堂展示。本产品通过 Codex Plugin 采集作业项目相关的完整 Codex 对话、代码、截图和项目结果，上传至租赁服务器，由服务器端 Agent 独立评估并生成 A–E 等级、依据与教师专用建议；教师在网页端查看全部课程数据、复核并调整最终等级，并按小组生成课堂展示视图。

# Scope and Non-goals

## Current Release

- 单门课程约 100 名学生、20–50 个小组。
- 至少支持 30 名学生同时提交。
- 插件自然语言触发提交；指令需包含作业、姓名和小组。
- 插件设置中配置课程邀请码、姓名、小组、代码目录、截图目录和项目结果目录。
- 每次提交采集当前作业项目相关的完整 Codex 对话，并按目录配置收集材料。
- 服务器接收后异步评分：上传确认目标为 30 秒内，评分完成目标为 10 分钟内。
- 教师网页端查看课程、小组、学生详情和提交处理状态。
- Agent 输出 A–E 等级、分维度依据和教师专用改进建议；教师可批注并调整最终等级，保留原始等级与调整记录。
- 默认等级区间：A=90–100，B=80–89，C=70–79，D=60–69，E=0–59。
- 教师可选择小组并生成课堂展示视图。
- 数据保存至课程结束后 1 年，再由教师确认删除。

## Non-goals / Exclusions

| Item | Release scope | scope_reason |
|---|---|---|
| 学生查看评分或建议 | not_applicable | 首版仅供教师评分复核和课堂讲评 |
| 学生查看其他小组或同学数据 | not_applicable | 首版不开放学生侧历史数据浏览 |
| 百分制评分 | out_of_version | 首版采用 A–E 等级制 |
| 自动按保存、会话结束或代码变更触发提交 | not_applicable | 首版仅响应学生自然语言指令 |

# Current Release — Functional Requirements

| ID | Requirement | Priority | Evidence |
|---|---|---|---|
| REQ-001 | 插件应识别包含作业、姓名和小组信息的自然语言提交意图，并启动一次提交。 | Must Have | user decision D-001 |
| REQ-002 | 插件应允许学生配置课程邀请码、姓名、小组、代码目录、截图目录和项目结果目录。 | Must Have | user decision D-002 |
| REQ-003 | 每次提交应采集当前作业项目相关的完整 Codex 对话。 | Must Have | user decision D-003 |
| REQ-004 | 每次提交应按插件配置收集代码、截图和项目结果文件，并将其关联到作业、姓名和小组。 | Must Have | user decision D-004 |
| REQ-005 | 服务器应使用课程邀请码、课程名单以及提交中的姓名和小组校验课程归属。 | Must Have | user decision D-005 |
| REQ-006 | 学生修改姓名或小组后，服务器应在每次提交时重新执行校验。 | Must Have | user decision D-006 |
| REQ-007 | 上传成功后系统应返回接收确认，并异步执行 Agent 评分。 | Must Have | user decision D-007 |
| REQ-008 | Agent 应基于需求理解、Codex 迭代过程、代码质量、最终功能、文档/展示完整性输出 A–E 等级、分维度依据和改进建议。 | Must Have | user decision D-008 |
| REQ-009 | 教师应能查看课程、小组、学生详情、提交材料、评分依据、建议和处理状态，并可批注及调整最终等级。 | Must Have | user decision D-009 |
| REQ-010 | 教师应能选择小组并生成包含项目结果、过程摘要、评分和教师批注的展示视图。 | Must Have | user decision D-010 |
| REQ-011 | 材料不完整时系统应允许提交进入评分，并在教师端标记缺失项。 | Must Have | user decision D-011 |
| REQ-012 | Agent 评分失败时系统应自动重试一次；仍失败时应标记“评分失败”并通知教师。 | Must Have | user decision D-012 |

# Current Release — Non-functional Requirements

| ID | Requirement | Priority | Evidence |
|---|---|---|---|
| NFR-001 | 系统应支持单门课程约 100 名学生、20–50 个小组的提交和教师查询。 | Must Have | user decision D-013 |
| NFR-002 | 系统应允许至少 30 名学生同时提交。 | Must Have | user decision D-014 |
| NFR-003 | 上传接收确认应在 30 秒内返回；Agent 评分完成目标为 10 分钟内。 | Must Have | user decision D-015 |
| NFR-004 | 提交内容和评分记录应保存至课程结束后 1 年，并由教师确认删除。 | Must Have | user decision D-016 |

# 架构输入契约

## 系统边界

- 产品范围包括：Codex Plugin、提交接收服务、课程/身份校验、提交元数据与材料存储、异步评估编排、Agent 评估服务、教师网页端和展示视图生成。
- 外部依赖包括：Codex 运行环境、租赁的云服务器环境、课程名单来源或教师维护的名单，以及 Agent 使用的模型服务（如有）。
- 架构必须保留以下业务链路：插件 → 服务器接收 → 持久化 → 异步评估 → 教师网页查询与展示。

## 明确约束

- 首版面向单门课程约 100 名学生、20–50 个小组，至少支持 30 个并发提交。
- 上传确认和 Agent 评估分别遵守 NFR-003 的 30 秒和 10 分钟目标。
- 提交材料和评估记录保存至课程结束后 1 年，并由教师确认删除且可审计。
- 课程、组别和学生数据必须遵守 REQ-005、REQ-006 和 REQ-009 的访问隔离规则。
- 上传失败和 Agent 失败必须保留可观察状态、重试记录和错误证据；Agent 失败自动重试一次。

## 需要人工确认的架构决策

- Agent 调用外部模型 API，还是在租赁服务器内运行模型。
- 材料存储、结构化元数据存储和异步任务执行采用独立托管服务，还是部署在同一组服务中。
- 云服务器地域、加密、备份、监控和灾难恢复等级。
- 单次提交最大大小、允许的文件类型和单课程存储配额。
- 插件/服务器认证协议、断点续传、重复提交幂等规则和 API 版本策略。

以上内容是架构输入和待决策项，不是新增产品需求。架构 Skill 不得在未记录决策来源的情况下擅自选择这些方案。

# Success Metrics

| ID | Metric | Target | Measurement |
|---|---|---|---|
| SM-001 | 提交接收成功率 | >=95% | 课程期间全部有效提交中成功返回接收确认的比例 |
| SM-002 | 评分按时完成率 | >=95% | 课程期间全部有效提交中 10 分钟内完成评分的比例 |
| SM-003 | 教师评分覆盖率 | >=95% | 课程结束前具有 Agent 结果或明确失败状态的提交比例 |

# Acceptance Contracts

## Functional Contracts

### AC-REQ-001-01

- verifies: [REQ-001]
- actor: 学生
- preconditions: 插件已绑定课程且配置可读取
- trigger: 学生发送包含作业、姓名和小组的自然语言提交指令
- response: 插件创建提交任务并将身份、作业和配置目录提交到服务器
- observable_oracles: 返回唯一提交编号；服务器记录作业、姓名和小组；未包含任一必填信息时不创建可评分提交
- boundaries: 缺少作业、姓名或小组时，返回具体缺失字段并保持提交状态为信息不完整
- exceptions: 插件无法连接服务器时，保留本地待上传任务并显示失败原因
- evidence_refs: [D-001]

### AC-REQ-002-01

- verifies: [REQ-002]
- actor: 学生
- preconditions: 插件设置页可用
- trigger: 学生保存课程邀请码、姓名、小组和三个目录配置
- response: 插件保存配置并在下次提交时使用
- observable_oracles: 配置重新打开后值一致；目录不可读时显示具体目录错误
- boundaries: 任一目录为空时，配置保存为不完整并列出缺失项
- exceptions: 配置格式无效时拒绝保存并保留上一次有效配置
- evidence_refs: [D-002]

### AC-REQ-003-01

- verifies: [REQ-003, REQ-004, REQ-005]
- actor: 服务器接收服务
- preconditions: 提交任务包含身份、作业和目录配置
- trigger: 插件上传对话及材料包
- response: 服务器保存材料并执行课程邀请码、姓名和小组校验
- observable_oracles: 提交详情可列出对话、代码、截图、结果及缺失项；校验通过后状态进入 processing；校验失败时状态为 rejected 且记录原因
- boundaries: 材料目录存在但为空时，提交进入评分并明确标记该材料缺失
- exceptions: 上传中断时，提交状态为 upload_failed，教师端可见失败原因
- evidence_refs: [D-003, D-004, D-005, D-011]

### AC-REQ-006-01

- verifies: [REQ-006]
- actor: 服务器身份校验服务
- preconditions: 学生已有一次提交记录；插件设置中的姓名或小组信息已被修改；新的提交包含课程邀请码、当前姓名和当前小组
- trigger: 学生再次发起提交并上传材料包
- response: 服务器针对本次提交读取并校验当前提交中的姓名和小组，不得沿用上一次提交的校验结果；校验通过则进入 processing，校验失败则进入 rejected
- observable_oracles: 本次提交存在独立的校验时间/校验记录；当前身份有效时本次提交进入 processing；当前姓名或小组无效时即使上一次提交有效，本次提交仍进入 rejected 并记录具体原因
- boundaries: 仅修改姓名、仅修改小组、同时修改姓名和小组三种情况都分别触发本次提交的重新校验
- exceptions: 课程名单服务不可用时，本次提交不复用旧校验结果，进入 identity_validation_failed 并记录可重试原因
- evidence_refs: [D-006]

### AC-REQ-007-01

- verifies: [REQ-007, NFR-003]
- actor: 服务器
- preconditions: 提交校验通过
- trigger: 材料包上传完成
- response: 返回接收确认并异步创建评分任务
- observable_oracles: 接收确认包含提交编号和 received_at；状态依次可观察为 received、processing、scored 或 scoring_failed
- boundaries: 并发提交达到至少 30 个时仍为每个任务生成独立编号和状态
- exceptions: Agent 首次失败后自动重试一次；再次失败标记 scoring_failed 并通知教师
- evidence_refs: [D-007, D-012, D-014, D-015]

### AC-REQ-008-01

- verifies: [REQ-008]
- actor: Agent 评分服务
- preconditions: 提交状态为 processing 且材料可读取
- trigger: Agent 开始独立评估
- response: 生成 A–E 等级、五个维度依据和教师专用改进建议
- observable_oracles: 结果包含等级、每个维度文字依据、建议和评分时间；建议默认不暴露给学生
- boundaries: 材料不完整时仍生成结果，并列出缺失材料对评估的影响
- exceptions: 评估失败按 AC-REQ-007-01 重试并通知教师
- evidence_refs: [D-008, D-011, D-012]

### AC-REQ-009-01

- verifies: [REQ-009]
- actor: 教师
- preconditions: 教师已登录并具有课程查看权限
- trigger: 教师打开课程、小组或学生提交详情
- response: 展示提交材料、处理状态、Agent 原始等级、依据、建议、批注和最终等级编辑入口
- observable_oracles: 教师可保存批注和调整后的等级；系统同时保留原始等级、最终等级、操作者和时间
- boundaries: 评分失败时展示失败原因和重试结果，而不是伪造等级
- exceptions: 无权限访问其他课程时拒绝读取并记录访问拒绝
- evidence_refs: [D-009]

### AC-REQ-010-01

- verifies: [REQ-010]
- actor: 教师
- preconditions: 课程中至少存在一个小组提交
- trigger: 教师选择一个或多个小组并生成展示视图
- response: 生成展示视图，包含项目结果、过程摘要、评分和教师批注
- observable_oracles: 展示视图中的小组与所选小组一致；视图可在教师网页端打开
- boundaries: 小组缺少某类材料时展示缺失标记，不隐藏缺口
- exceptions: 小组无可用提交时阻止生成并说明原因
- evidence_refs: [D-010]

# NFR Verification Contracts

### AC-NFR-001-01

- verifies: [NFR-001]
- release_scope: current
- population: 单门课程配置，100 名学生、20–50 个小组；包含创建、查询和展示操作的压力测试请求
- measurement_start: 压力测试开始接收课程数据时
- measurement_end: 全部规模数据完成创建、查询和展示验证时
- unit: 测试轮次
- threshold: 支持 100 名学生和 20–50 个小组
- exclusions: 未授权访问、故意损坏的输入数据
- pass_rule: 压力测试中目标规模数据可正常创建、查询和展示；失败则不通过
- evidence_refs: [D-017]

### Decision Registry

| Decision | Product decision |
|---|---|
| D-001–D-016 | Elicited scope, workflow, access, scoring, retention, scale, and timing decisions recorded in this PRD. |
| D-017 | NFR-001 passes when the 100-student/20–50-group pressure test supports create, query, and display. |
| D-018 | NFR-002 uses a 5-minute concurrency window and passes at >=95% successful receipt. |
| D-019 | NFR-003 uses >=95% on-time receipt and scoring over all valid course submissions. |
| D-020 | NFR-004 requires teacher-confirmed deletion after one year with audit evidence. |
| D-021 | Default grades are A=90–100, B=80–89, C=70–79, D=60–69, E=0–59. |

### AC-NFR-004-01

- verifies: [NFR-004]
- release_scope: current
- population: 课程结束时仍在保存期内的全部提交材料和评分记录
- measurement_start: 课程结束时间
- measurement_end: 课程结束后 1 年的到期处理完成时间
- unit: 提交记录
- threshold: 到期后经教师确认删除
- exclusions: 法律或学校政策要求保留的记录（如有，需由教师明确标记）
- pass_rule: 删除完成后，全部目标记录不可被教师端读取，并存在包含记录范围、操作者和时间的删除审计记录
- evidence_refs: [D-016, D-020]

### AC-NFR-002-01

- verifies: [NFR-002]
- release_scope: current
- population: 30 名学生同时发起的提交请求，持续 5 分钟
- measurement_start: 并发测试开始发起提交请求时
- measurement_end: 5 分钟测试窗口结束时
- unit: 提交请求
- threshold: 成功率不低于 95%
- exclusions: 未授权请求、客户端主动取消的请求
- pass_rule: 窗口内成功接收并返回提交编号的请求数 / 有效提交请求总数 >= 95%
- evidence_refs: [D-018]

### AC-NFR-003-01

- verifies: [NFR-003]
- release_scope: current
- population: 课程运行期间全部有效提交
- measurement_start: 有效提交上传开始时
- measurement_end: 课程运行结束且所有有效提交处理状态最终确定时
- unit: 提交
- threshold: 至少 95% 的提交在 30 秒内返回接收确认，且在 10 分钟内完成 Agent 评分
- exclusions: 学生主动取消、未通过身份校验、材料不完整的提交
- pass_rule: 满足时限的提交数 / 有效提交总数 >= 95%，上传确认和评分完成均需满足
- evidence_refs: [D-015, D-019]

# Oracle Coverage Ledger

| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |
|---|---|---|---|---|---|
| REQ-001 | functional | current | AC-REQ-001-01 | ready | - |
| REQ-002 | functional | current | AC-REQ-002-01 | ready | - |
| REQ-003 | functional | current | AC-REQ-003-01 | ready | - |
| REQ-004 | functional | current | AC-REQ-003-01 | ready | - |
| REQ-005 | functional | current | AC-REQ-003-01 | ready | - |
| REQ-006 | functional | current | AC-REQ-006-01 | ready | - |
| REQ-007 | functional | current | AC-REQ-007-01 | ready | - |
| REQ-008 | functional | current | AC-REQ-008-01 | ready | - |
| REQ-009 | functional | current | AC-REQ-009-01 | ready | - |
| REQ-010 | functional | current | AC-REQ-010-01 | ready | - |
| REQ-011 | functional | current | AC-REQ-003-01, AC-REQ-008-01 | ready | - |
| REQ-012 | functional | current | AC-REQ-007-01, AC-REQ-008-01 | ready | - |
| NFR-001 | nfr | current | AC-NFR-001-01 | ready | - |
| NFR-002 | nfr | current | AC-NFR-002-01 | ready | - |
| NFR-003 | nfr | current | AC-NFR-003-01 | ready | - |
| NFR-004 | nfr | current | AC-NFR-004-01 | ready | - |
| SM-001–SM-003 | metric | current | - | ready | 目标均为 >=95%，按课程期间有效提交统计 |

# Future Backlog / Documented Exclusions

- 学生查看评分、建议和历史提交：首版明确不包含。
- 百分制评分：首版明确不包含。
- 自动按保存、会话结束或代码变化提交：首版明确不包含。

# Risks, Dependencies, and Blocking Questions

## Risks and Dependencies

- 依赖 Codex Plugin 能读取当前会话相关对话并访问已配置目录。
- 依赖课程名单服务或服务器端名单维护，用于邀请码、姓名和小组校验。
- 依赖租赁服务器具备至少 30 个并发上传任务和异步 Agent 任务的容量。
- 完整对话和项目材料可能包含个人信息或第三方代码，需要访问审计和安全存储策略。

## Blocking Questions

当前业务验收阻塞为 0。教师调整等级是否必须填写理由，可在独立 review 或实现阶段作为可选产品决策补充。

# Agent Review Report

独立 Agent review：PASS。

- 覆盖账本已逐条映射 REQ-001..012、NFR-001..004 与 Acceptance Contracts。
- 决策证据已登记，NFR 合约字段完整，未发现未知引用或虚构响应。
- 当前 PRD 满足交接门槛，可进入下游测试用例生成。
