# 03 State and Data — CMP-CONFIG-STORE

## 1. State ownership registry

| state_id | State | Owner child_id | Readers | Writers | Lifecycle | Consistency boundary | Retention/privacy | Parent trace |
|---|---|---|---|---|---|---|---|---|
| `ST-01` | `PluginConfig`：邀请码、姓名、小组、三个目录、schema version、完整性元数据 | `CMP-CS-STATE-STORE` | `CMP-CS-CONFIG-PORT`；父层各配置读者通过 `IC-M01-02` | 仅 `CMP-CS-STATE-STORE` | 有效保存后持续存在，直到下一次有效保存；格式无效保存不改变 | 单配置记录原子替换；读者只能看到旧值或完整新值 | 学生本机持久化；含个人信息；不随本组件外发 | L1 `ST-01`; `REQ-D002/REQ-DD002`; `A-007` |
| `ST-CS-01` | `ValidatedConfigCandidate` | `CMP-CS-SCHEMA-VALIDATOR` | `CMP-CS-CONFIG-PORT`、STATE-STORE（仅提交时） | 每次 `SaveConfig` 新建 | 请求内短生命周期；提交结束即释放 | 纯函数式校验结果，不进入持久化 | 不持久化；可能包含个人信息，仅存在于当前进程请求 | `D-AC-REQ-002-01.exceptions`; `ST-01` invariant |
| `ST-CS-02` | `DirectoryProbeResult`：目录可读/空/错误明细 | `CMP-CS-DIRECTORY-PROBE` | `CMP-CS-CONFIG-PORT`；状态视图装配 | 保存时和读取时探测生成 | 保存请求或读取请求内短生命周期 | 每次探测结果自洽；读取探测不得改写 `ST-01` | 不持久化路径内容；错误只作为本地派生结果 | `D-AC-REQ-002-01.observable_oracles/boundaries` |
| `ST-CS-03` | `EffectiveConfig` / `ConfigView` 派生视图 | `CMP-CS-CONFIG-PORT` | `CMP-STATUS-PRESENTER`、父层配置读者 | 由 `ST-01` + 当前 `ST-CS-02` 装配 | 每次读取/保存响应生成；不独立留存 | 视图必须对应同一次读取的配置快照和目录探测结果 | 仅本地进程内；不成为新持久化状态 | `IC-M01-02`; `IC-M01-05` |

记录按稳定 `state_id` 排序。父层和兄弟节点的数据所有权未被重新分配。

## 2. Storage intent constrained by parent

- 使用父层允许的插件本地持久化机制；本层不选择数据库、云存储或独立服务。
- `CMP-CS-STATE-STORE` 是唯一写方；所有写入都以“校验通过的全量候选 + 目录完整性结果”为一次原子提交。
- 具体序列化编码、文件名、锁实现和原子替换 primitive 交给下一级详细设计；它们不能改变 `ST-01` 单写方和旧值保留语义。

## 3. Data flows

### 3.1 Save flow

1. `CMP-CS-CONFIG-PORT` 接收全量 `PluginConfigCandidate`。
2. `CMP-CS-SCHEMA-VALIDATOR` 执行字段、格式和 schema 兼容性校验。
3. 校验失败立即返回 `INVALID_CONFIG`；`ST-01` 不发生写入。
4. 校验通过后，`CMP-CS-DIRECTORY-PROBE` 生成三个目录的当前结果。
5. PORT 合并 `completeness[]`、`dir_errors[]` 和候选值，交给 STATE-STORE 原子提交。
6. 提交成功产生 `ConfigSaved`；失败返回持久化错误并保留旧状态。

### 3.2 Read flow

1. PORT 从 STATE-STORE 读取最近一次有效 `ST-01`。
2. DIRECTORY-PROBE 对当前目录重新探测。
3. PORT 装配 `EffectiveConfig`；当前目录错误只影响派生视图，不反写 `ST-01`。
4. 通过 `IC-M01-02` / `IC-M01-05` 返回给父层读取方或 STATUS-PRESENTER。

### 3.3 Schema evolution flow

- 读取带有已知兼容版本的记录时，STATE-STORE 归一化为当前内部模型。
- 遇到不支持且可能丢失数据的版本时，读取失败并保留原记录；不得以默认值覆盖旧配置。
- 新增可选字段只能在内部兼容范围内处理；若改变父层必需字段或错误语义，必须 `return_to_parent`。

## 4. Invariants, consistency and concurrency

1. `INV-CS-01`：格式未通过时不得写入；最近一次有效 `ST-01` 保持不变。
2. `INV-CS-02`：状态存储器是唯一持久化写方；其他子节点没有写接口。
3. `INV-CS-03`：一次有效保存要么完整替换配置记录，要么不改变记录；不允许部分字段落盘。
4. `INV-CS-04`：目录为空/不可读不能伪装为格式无效；应通过 `completeness[]` / `dir_errors[]` 显式暴露。
5. `INV-CS-05`：同一读请求的 `EffectiveConfig` 中配置值和目录错误来自同一次读取快照。
6. 并发保存按 STATE-STORE 的单写顺序串行化；后完成且格式有效的保存成为新的最近有效配置。
7. 读取失败、目录探测失败和持久化失败不能产生隐式重试写入；调用方可显式重试保存/读取。

## 5. CONFIG-PORT orchestration state table

`CMP-CS-CONFIG-PORT` 本身无持久状态（见 02 Child registry：仅持有 ephemeral 请求上下文）；下表是其**请求级编排状态机**。持久化状态 `ST-01` 的生命周期见 §1 与 §4 不变量，二者不在本表重复定义。

| 前置状态 | 触发事件 | 成功分支 | 失败分支 | 可观测副作用 |
|---|---|---|---|---|
| `Idle` | `SaveConfig` 到达 | 进入 `Validating` | —（入口无条件接受） | 记录操作类型=save 开始 |
| `Validating` | `ValidateConfigCandidate` 返回 | 校验通过 → `Probing` | `INVALID_CONFIG` → `Rejected`；不写 `ST-01` | `ConfigRejected{error_code, field_errors[]}`；结果=rejected_invalid |
| `Probing` | `ProbeDirectories` 返回 | 探测完成（目录空/不可读不阻断）→ `Committing`，缺失项进入 `completeness[]`/`dir_errors[]` | 探测内部错误归档为 `dir_errors[]` 后继续 `Committing`（不升级为格式失败） | `DirectoryProbeCompleted`；目录错误明细可定位 |
| `Committing` | `CommitValidConfig` 返回 | 提交成功 → `Done`；`ST-01` 原子替换 | `PERSISTENCE_FAILED` → `Rejected`；旧值保持可读，不重试写入 | `ConfigSaved{config_version}` 或结果=rejected_persistence |
| `Idle` | `ReadEffectiveConfig` 到达 | `Reading`：读取 `ST-01` 快照 + 重新探测目录 → 装配 `EffectiveConfig` → `Done` | 快照读取失败返回可识别错误；不得伪造配置结论；不反写 `ST-01` | `EffectiveConfig` 派生视图交付；结果=read |
| `Done` / `Rejected` | 请求结束 | 释放请求上下文 | — | 记录操作类型、结果、配置版本（不含邀请码明文/目录内容） |

边界规则：任一失败分支都不产生隐式重试写入；`Rejected` 终态保证 `ST-01` 最近一次有效值不变（`INV-CS-01`/`INV-CS-03`）。
