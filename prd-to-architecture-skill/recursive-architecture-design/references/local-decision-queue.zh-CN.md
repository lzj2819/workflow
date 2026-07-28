# 局部决策队列

当你发现“这里有好几种做法”时，用这份表判断该自己决定、留给下一层，还是必须回去找父层。它只处理子层细化发现的选择，不能代替父架构决策。

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|

使用 `LCD-001` 等稳定 ID。

| 分类 | 含义与行动 |
|---|---|
| `decide_now` | 当前层架构完整性所需的局部结构选择；比较 2-3 个局部方案并记录在 `05-local-decisions.md`。 |
| `defer_to_next_level` | 可交给某个子节点且不改变当前架构；在 `child-handoff.md` 记录目标和触发条件。 |
| `implementation_detail` | 编码、框架配置或局部实现；不作为架构决策。 |
| `return_to_parent` | 改变父职责、所有权、契约、依赖方向、ADR、技术、部署或公共边界；创建 `parent-change-request.md` 并在权威分解前停止。 |

改变父契约的标识符、所有者、路径/主题、必需/产出字段、副作用、依赖、错误/重试语义或版本时，必须 `return_to_parent`。跨父节点转移状态、创建独立服务/容器、推翻父技术或部署决策也必须返回父层。不得将此类问题标为暂缓或实现细节。
