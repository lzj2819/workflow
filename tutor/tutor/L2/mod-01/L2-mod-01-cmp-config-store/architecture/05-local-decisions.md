# 05 Local Decisions — CMP-CONFIG-STORE

本文件只记录 `CMP-CONFIG-STORE` 内部可独立决定的架构选择。父层公共契约、状态所有权、技术/部署边界不在本层重议。

## 1. Local decisions (`decide_now`)

### `LCD-CS-001` 校验先行并以单次原子提交完成保存

- **Source**：`REQ-DD002`、`D-AC-REQ-002-01.exceptions`、父 `ST-01`。
- **Alternatives**：
  1. 先写入再异步校验；会产生无效配置短暂可见，违反旧值保留语义。
  2. 每个字段分别写入；可能产生部分状态。
  3. 纯校验 → 目录探测 → 全量原子提交；选择此项。
- **Decision**：`CMP-CS-CONFIG-PORT` 只有在 schema 校验通过后才能调用 `CMP-CS-STATE-STORE` 的原子提交端口。
- **Consequence**：格式错误无写入；提交失败时旧配置仍可读；内部流程更容易验证。

### `LCD-CS-002` 区分格式无效与目录不完整

- **Source**：`D-AC-REQ-002-01.boundaries/exceptions`。
- **Alternatives**：
  1. 任何目录问题都拒绝保存；会丢失用户已输入的有效配置值。
  2. 任何目录问题都忽略；无法满足具体错误展示。
  3. 格式无效拒绝；目录为空/不可读时保存值并写入完整性/错误元数据；选择此项。
- **Decision**：目录问题不伪装成 schema 错误；通过 `completeness[]` 和 `dir_errors[]` 显式呈现。
- **Consequence**：允许下次提交前修复目录；父层上传前置检查仍可阻塞不完整配置。

### `LCD-CS-003` 保存时探测 + 读取时重新探测

- **Source**：`D-AC-REQ-002-01.observable_oracles`、父 `EffectiveConfig` 语义。
- **Alternatives**：
  1. 只在保存时探测；保存后目录变化无法及时反映。
  2. 只在读取时探测；保存响应无法完整说明当前目录问题。
  3. 保存时生成提交元数据，读取时生成派生当前视图；选择此项。
- **Decision**：保存流程探测并持久化完整性快照；读取流程可重新探测但不反写 `ST-01`。
- **Consequence**：值稳定、目录状态新鲜，且读取没有隐藏写副作用。

### `LCD-CS-004` 内部 schema version 与兼容读取

- **Source**：当前 PRD 的“schema 演进”细化焦点、父 `A-007`。
- **Alternatives**：
  1. 永不记录版本；格式演进无法安全判断。
  2. 版本随记录保存，已知兼容版本归一化读取，不兼容版本拒绝覆盖；选择此项。
  3. 遇到未知版本时丢弃旧值并使用默认值；会破坏旧配置保留语义。
- **Decision**：STATE-STORE 记录内部 schema version；兼容读取可归一化，不兼容记录保持原样并报错。
- **Consequence**：内部可演进，同时保持父层 `PluginConfig`/`EffectiveConfig` 语义稳定。

## 2. Inherited decisions

| ID | Inherited rule | Local treatment |
|---|---|---|
| `A-007` | 本地持久化机制是 implementation detail | 只规定原子替换与单写方，不选择具体存储技术 |
| `KD-005` | 邀请码用于父层令牌换取；本地任务使用幂等键 | 本组件只提供只读配置值，不实现上传/令牌协议 |
| `DU-1` | 学生本机 Codex Plugin 运行 | 不创建服务、容器或独立部署 |

## 3. Delegated to next level

| Decision | Classification | Follow-up target | Trigger |
|---|---|---|---|
| 具体序列化格式、编码和文件命名 | `defer_to_next_level` | `CMP-CS-STATE-STORE` | 开始详细持久化设计时 |
| 文件锁/并发写入 primitive | `defer_to_next_level` | `CMP-CS-STATE-STORE` | 需要确定本地并发保存策略时 |
| 目录探测的具体系统 API 与权限错误映射 | `defer_to_next_level` | `CMP-CS-DIRECTORY-PROBE` | 开始平台适配设计时 |
| 字段级错误文案与设置页交互 | `defer_to_next_level` | `CMP-CS-CONFIG-PORT` | 开始接口/展示适配设计时 |

## 4. Parent-owned decisions prohibited locally

以下事项不在本层决定：父层公共契约字段/版本/owner，`ST-01` 转移，网络协议、数据库/消息总线、服务端 `Submission`，兄弟组件职责，或 `DU-1` 部署边界。若后续需求要求改变其中任何一项，必须创建 `parent-change-request.md` 并停止本层设计。

## 5. Decision queue outcome

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why mapping is not enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| `LCD-CS-001` | current PRD / parent state | `REQ-DD002`, `ST-01` | `CMP-CS-CONFIG-PORT`, `CMP-CS-STATE-STORE` | 需要选择内部提交边界 | `decide_now` → resolved | — |
| `LCD-CS-002` | current PRD acceptance | `D-AC-REQ-002-01` | `CMP-CS-DIRECTORY-PROBE`, `CMP-CS-STATE-STORE` | 需要区分目录异常与格式无效 | `decide_now` → resolved | — |
| `LCD-CS-003` | parent contract | `IC-M01-02` | `CMP-CS-DIRECTORY-PROBE`, `CMP-CS-CONFIG-PORT` | 需要确定保存/读取两个时机 | `decide_now` → resolved | — |
| `LCD-CS-004` | current PRD / parent delegation | `A-007` | `CMP-CS-STATE-STORE` | 需要内部 schema 演进策略 | `decide_now` → resolved | — |
| `LCD-CS-005` | local refinement | `IC-CS-003` | `CMP-CS-STATE-STORE` | 具体平台 primitive 不影响当前边界 | `defer_to_next_level` | `CMP-CS-STATE-STORE` |

**结论**：无遗留 `decide_now`，无 `return_to_parent`；本包可进入 Human Gate。
