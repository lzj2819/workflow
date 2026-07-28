# 01 Design Context — L2 / CMP-TEACHER-UI

> 本包只细化 L1/MOD-05 的 `CMP-TEACHER-UI`。父层架构是绑定契约；本层不重画 MOD-05 边界、不设计兄弟节点内部、不改变父契约或部署方式。

## 1. 输入绑定与目标节点

| 输入 | 已解析值 | 证据 |
|---|---|---|
| `parent_architecture` | `architecture/L1/L1-mod-05` | 目录存在 manifest、五份设计文档和 child handoff |
| `target_node_id` | `CMP-TEACHER-UI` | 父 manifest、分解清单、handoff 唯一交叉匹配 |
| `current_prd` | `prd/L2-PRD/mod-05/L2-mod-05-cmp-teacher-ui/prd.md` | frontmatter 与两项当前验收契约 |
| `output_dir` | `architecture/L2/mod-05/L2-mod-05-cmp-teacher-ui` | new 模式写入前为空 |
| `mode` | `new` | 用户批准后执行；不覆盖既有包 |

## 2. 父边界快照

| 分类 | 父层约束 | 本层处理 |
|---|---|---|
| `inherited-fixed` | UI 是教师浏览器可观察面；服务端入口为 CMP-ACCESS-GATE | 原样保留；五个 child 只负责浏览器交互、页面状态和契约适配 |
| `inherited-fixed` | CT-007/008/009/011 的路径、字段、错误、幂等、版本和副作用不可变 | UI 只构造和透传请求，错误按父语义显示，不重新解释业务结果 |
| `inherited-fixed` | ReviewRecord、PresentationView、DeletionBatch、ST-READ-MODEL 等服务端状态不归 UI | 浏览器只保存选择、草稿、请求状态和通知显示状态 |
| `inherited-fixed` | 教师范围授权由 CMP-ACCESS-GATE 处理；UI 不做授权判定 | 收到 `FORBIDDEN` 时展示拒绝结果，不根据本地缓存放行 |
| `inherited-fixed` | DU-2 course-app；不新增服务、容器、公共运行时或跨模块依赖 | 所有请求沿 `UI → ACCESS-GATE → sibling/support component` 合法流执行 |
| `inherited-refinable` | 端内通知来自读模型派生条目；展示从读模型快照生成 | 本层决定通知和视图的浏览器呈现、刷新与过渡状态 |
| `delegated` | LCD-007 教师前端渲染技术交给 CMP-TEACHER-UI | 本层选择不绑定具体厂商的混合渲染策略；框架和组件库仍为实现细节 |
| `unresolved` | 视觉布局、设计系统 token、浏览器兼容矩阵未在 PRD/父层固定 | 留给下一层或实现阶段，不改变当前接口和状态边界 |

## 3. 当前 PRD 需求分配

| 当前需求 | 分类 | 本层承接 | 父层追踪 | 验收依据 |
|---|---|---|---|---|
| `REQ-DD001` 教师查看提交、评分结果、依据、建议、批注和最终等级编辑入口 | `allocated` | 查询浏览、详情展示、复核工作台、失败可见和保存反馈 | `REQ-D001`；CT-007/008；F3-1/F3-2/F3-3 | `D-AC-REQ-009-01` / `AC-REQ-009-01` |
| `REQ-DD002` 教师选择小组并打开包含结果、过程摘要、评分和批注的展示视图 | `allocated` | 小组选择、展示视图打开、缺失标记和生成失败反馈 | `REQ-D002`；CT-009；F4-1 | `D-AC-REQ-010-01` / `AC-REQ-010-01` |
| `D-AC-REQ-009-01` | `inherited` | 仅负责浏览器可观察结果；权限/业务不变量由父组件保证 | CT-007/008；NO_ORIGINAL_GRADE；FORBIDDEN | 教师能保存批注/等级，原始等级与最终等级均可见 |
| `D-AC-REQ-010-01` | `inherited` | 仅负责选择与打开视图；资格校验/快照写入由 CMP-PRESENTATION 负责 | CT-009；NO_AVAILABLE_SUBMISSION | 选中小组与展示视图一致，缺失标记不被隐藏 |
| `LCD-007` 前端渲染技术 | `allocated` | 采用混合渲染策略，隔离页面导航与局部交互状态 | KD-002/KD-005；DU-2 | 不改变父 API 和部署边界 |
| `A-005` 端内通知展示面 | `inherited-refinable` | 通知状态 child 负责列表/详情中的可见性、刷新和失败反馈 | CT-005；LCD-001 | scoring_failed 不被伪装成 scored |

## 4. 局部驱动与可复用能力

1. **结果透明**：原始等级、依据、建议、批注、最终等级、失败原因和重试结果必须区分呈现；UI 不补造缺失字段。
2. **操作安全**：写操作在 UI 边界生成稳定 `request_id` 或父契约要求的幂等上下文；重复提交不会被 UI 误判为两次成功。
3. **最终一致可见**：读模型可能秒级落后，UI 显示加载/刷新中状态，不引入跨模块同步读取。
4. **权限失败明确**：`AUTH_INVALID`、`FORBIDDEN`、`NOT_FOUND`、`VALIDATION_FAILED` 等按父错误语义映射为可观察结果，不用空页面掩盖错误。
5. **可组合页面**：课程浏览、复核、展示、删除确认和通知分别拥有局部状态，跨页面只共享教师会话与选定范围的浏览器上下文。

可复用能力：父层 `/api/v1` 会话约定、CMP-ACCESS-GATE 唯一路由、CT-007/008/009/011 响应 schema、父错误码目录、DU-2 既有日志/观测能力。本层不重造认证、授权、持久化、Outbox 或读模型投影。

## 5. 阻塞缺口

无。父节点责任、契约、状态所有权、部署约束和当前 PRD 的两个验收目标均可获得；未发现需要 `return_to_parent` 的边界变化。

## 6. 输出与上下游影响

拟创建严格七个文件：manifest、design context、decomposition、state/data、contracts/runtime、local decisions、child handoff。无 `parent-change-request.md`。

上下游影响为零：本层不新增/修改/删除父契约字段、端点、事件、错误码、版本、生产者或消费者；只把已有 `M05-BIND-CT-007/008/009/011-UI-GATE` 映射到内部 child。

交接验证：检查五个 child 的追踪列、父契约逐字段镜像、状态 owner 不越界、五条合法 UI 流、决策队列无未处理 `decide_now`、YAML 可解析和稳定排序。

## 7. C1-C6 预映射

| 映射 | 本层落点 |
|---|---|
| C1 | `02-architecture-decomposition.md` 的五个 child registry |
| C2 | `03-state-and-data.md` 的浏览器瞬时状态 owner 与一致性边界 |
| C3 | `04-contracts-and-runtime.md` 的五条 UI→GATE→业务节点流程 |
| C4 | `04-contracts-and-runtime.md` 的 CT-007/008/009/011 UI 实现映射 |
| C5 | UI 只依赖 CMP-ACCESS-GATE；不创建 Adapter/ACL 以外的外部依赖 |
| C6 | `05-local-decisions.md` 的渲染策略、局部状态和幂等键策略 |

## 8. 假设与问题登记

| 编号 | 类型 | 内容 | 处置 |
|---|---|---|---|
| Q-TUI-001 | 假设 | 当前教师会话由父层约定提供，UI 不负责登录/签发账号 | 继承 KD-005；不新增登录领域边界 |
| Q-TUI-002 | 非阻塞问题 | 具体视觉布局与设计系统未定义 | 下一层或实现阶段细化，不影响契约/状态设计 |
| Q-TUI-003 | 非阻塞问题 | 浏览器兼容矩阵未定义 | 作为实现验收输入补充，不改变架构边界 |
| Q-TUI-004 | 冲突检查 | PRD dependency_refs 指向兄弟节点，但未要求读取其内部结构 | 仅按父契约消费，不重设计兄弟内部 |
