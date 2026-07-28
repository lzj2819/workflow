# 05 Local Decisions — L2 / CMP-TEACHER-UI

> 决策按稳定 ID 排序。分类：`decide_now`、`defer_to_next_level`、`implementation_detail`、`return_to_parent`。

## 1. 本层决定（decide_now）

### LCD-TUI-001 混合渲染与局部交互策略

- 来源：父 LCD-007；教师端读多写少；DU-2 course-app；REQ-DD001/REQ-DD002。
- 备选：
  - (a) **采用：路由/首屏采用服务端可生成的页面壳，复核、选择、确认、刷新等局部交互使用浏览器瞬时状态**。不绑定具体框架；页面可渐进增强。
  - (b) 纯 SPA：交互统一，但会把首屏和全量数据装配推向浏览器，且增加会话/刷新状态复杂度。
  - (c) 纯服务端页面：简单但不利于批注草稿、二次确认和展示生成中的细粒度反馈。
- 结果：本层按页面旅程划分 child；不决定具体框架、组件库、打包器或部署方式。所有 API 仍经 `/api/v1` 与 CMP-ACCESS-GATE。

### LCD-TUI-002 局部状态而非共享客户端业务 store

- 来源：父状态所有权清单；UI 仅有浏览器瞬时状态。
- 采用：每个 child 拥有自己的 selection/draft/action status；仅通过 TUI-IC-01/02/06 传递范围和可观察结果。
- 后果：不会在浏览器端复制 ReviewRecord、PresentationView、DeletionBatch 或 TeacherAccessGrant；跨页面重载以 CT-007/CT-009 服务端结果为准。

### LCD-TUI-003 写操作幂等键在交互边界生成并锁定

- 来源：KD-005、CT-008 `request_id`、CT-009/CT-011 父幂等语义。
- 采用：用户一次明确提交建立一个 action context；提交期间禁用重复触发，网络失败时保留上下文供显式重试；不修改服务端幂等算法。
- 后果：避免双击产生多个客户端请求，同时仍依赖父组件的权威幂等记录。

### LCD-TUI-004 失败优先可见策略

- 来源：A-005、DF-2、D-AC-REQ-009-01。
- 采用：`scoring_failed`、failure_reason、retry_record、missing_marks 和父错误均有显式 UI 状态；没有等级时不显示可编辑最终等级的成功态。
- 后果：通知/详情/复核工作台共享同一错误语义，但不创建独立通知事实或修改读模型。

## 2. 交给下一层（defer_to_next_level）

| ID | 事项 | 目标 child | 触发条件 | 继承背景 |
|---|---|---|---|---|
| LCD-TUI-005 | 页面视觉布局、组件层次和导航细节 | CMP-TUI-COURSE-SUBMISSION-BROWSER / CMP-TUI-PRESENTATION-WORKSPACE | 进入 L3 UI 组件细化 | 本层只固定职责、契约和状态边界 |
| LCD-TUI-006 | 可访问性逐项规则、键盘顺序、屏幕阅读器文本 | 所有交互 child | 产品/设计验收标准补充 | 当前 PRD 未提供具体 UI 验收条目 |
| LCD-TUI-007 | 具体框架、组件库、浏览器兼容版本和构建配置 | 所有 child | 实现技术评审启动 | 本层不重选父技术栈，不在架构文档中造供应商依赖 |

## 3. 实现细节（implementation_detail）

- 页面文件命名、路由文件组织、组件 props 命名和 CSS token。
- loading skeleton、toast/modal 的具体视觉实现。
- 内存缓存、请求取消、浏览器 history 和 URL 参数编码的具体实现；必须遵守 scope_key 丢弃旧响应规则。
- 前端单元测试、端到端测试、构建流水线和部署 manifest；不属于本架构包。

## 4. 父层继承决策与禁止项

- 继承 KD-002（DU-2 共部署与父 Outbox）、KD-003（最小化观测）、KD-005（`/api/v1`、教师会话、写幂等键）、A-005（首版端内通知）。
- 继承 LCD-001（通知为投影派生）、LCD-004（展示从读模型快照生成）、LCD-006（授权数据由 GATE 本地持有）。
- 禁止修改 CT-007/008/009/011 字段/错误/版本/幂等；禁止 UI 直连兄弟节点、读模型、数据库或文件；禁止创建独立服务或客户端业务数据库；禁止把前端失败重写为业务成功。

## 5. 决策队列关闭

`decide_now` 4 项（LCD-TUI-001~004）均已决定；`defer_to_next_level` 3 项已明确目标与触发条件；无未处理 `decide_now`；无 `return_to_parent`；本轮不生成 `parent-change-request.md`。
