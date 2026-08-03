# 01 Design Context — CMP-CONFIG-STORE

## 1. Scope and preflight

- **当前节点**：`CMP-CONFIG-STORE`，L1 `MOD-01` 内的 L2 组件细化。
- **当前 PRD**：`prd/L2-PRD/mod-01/L2-mod-01-cmp-config-store/prd.md`。
- **父架构**：`architecture/L1/L1-mod-01`。
- **模式**：`new`；输出目录在写入前已确认为空。
- **当前需求**：`REQ-DD002`，映射父层 `REQ-D002`；验收契约为 `D-AC-REQ-002-01`。
- **本层目标**：细化配置端口内部的校验、目录探测、原子持久化与读模型装配。

父层是绑定契约。本层不重新划分 `MOD-01`，不重设计兄弟组件，不改变父层公共接口、部署形态或本地数据所有权。

## 2. Parent-boundary snapshot

### 2.1 Responsibility and exclusions

父层 `CMP-CONFIG-STORE` 的职责是：持久化和读取 `PluginConfig`，在保存时执行格式与目录可读性校验，保留完整性/缺失标记，格式无效时拒绝保存并保留上一次有效配置。

明确排除：网络调用、材料收集、对话导出、上传、远端归属校验、服务端 `Submission` 所有权、独立服务或独立部署。

### 2.2 State and data ownership

| Parent state | Owner | Readers | Writers | Binding rule |
|---|---|---|---|---|
| `ST-01 PluginConfig` | `CMP-CONFIG-STORE` | INTENT-PARSER、DIALOGUE-COLLECTOR、MATERIAL-COLLECTOR、UPLOAD-CLIENT、STATUS-PRESENTER（通过父端口读取） | 仅配置保存路径 | 校验+写入是单一原子步骤；无效格式不得覆盖最近一次有效配置 |

配置包含邀请码、姓名、小组、代码目录、截图目录、结果目录和 `completeness` 缺失项。个人信息仅存于学生本机；邀请码只作为父层上传流程的令牌换取输入。

### 2.3 Inherited contracts and flows

| Contract/flow | Parent meaning | L2 binding |
|---|---|---|
| `IC-M01-02` | 保存 `PluginConfig`；读取 `EffectiveConfig{fields..., completeness[]}`；产生 `ConfigSaved`/`ConfigRejected` | 由 `CMP-CS-CONFIG-PORT` 对外承接，由验证器、目录探测器和状态存储器内部实现 |
| `IC-M01-05` ConfigView | 向学生展示配置值、完整性与目录错误 | 本层只提供派生视图，不让展示器直接读取状态存储 |
| `R3` | 保存请求 → 校验 → 有效原子写入或拒绝 → 展示结果 | 外部顺序保持不变，仅细化内部协作 |

### 2.4 Inherited decisions and constraints

| Item | Classification | Child consequence |
|---|---|---|
| `KD-003` HTTPS | inherited-fixed | 本组件不发起网络调用；网络消费者的语义不受影响 |
| `KD-005` 令牌、幂等键、分片续传、`/api/v1` | inherited-fixed | 只提供邀请码读取，不实现上传协议 |
| `A-007` 本地持久化机制 | delegated/inherited boundary | 允许细化原子写入语义，不在本层选择具体数据库或服务 |
| `DU-1` student-plugin | inherited-fixed | 所有子节点均在 Codex Plugin 进程内运行 |

## 3. Requirement allocation

| Requirement | Classification | Parent trace | L2 allocation |
|---|---|---|---|
| `REQ-DD002` 插件配置管理 | allocated | `REQ-D002`；`D-AC-REQ-002-01`；父 `IC-M01-02` | 四个 L2 子节点共同实现；配置端口保持对外契约 |
| 配置重新打开后值一致 | allocated | `D-AC-REQ-002-01.observable_oracles` | `CMP-CS-STATE-STORE` 读取最近一次有效记录；`CMP-CS-CONFIG-PORT` 装配视图 |
| 目录不可读时显示具体错误 | allocated | `D-AC-REQ-002-01.observable_oracles` | `CMP-CS-DIRECTORY-PROBE` 产生可定位错误；端口映射到 `dir_errors[]` |
| 任一目录为空时保存为不完整并列出缺失项 | allocated | `D-AC-REQ-002-01.boundaries` | 目录探测结果写入完整性快照；不把目录问题误判为格式无效 |
| 配置格式无效时拒绝且保留旧值 | allocated | `D-AC-REQ-002-01.exceptions`；`ST-01` | schema 校验先行；状态存储只接受通过格式校验的候选配置 |
| 父层网络、上传、材料和服务端归属判断 | out-of-scope | 父 `CMP-*` 边界与 `CT-001` | 不在本组件实现或重新解释 |

## 4. Current-level drivers

1. **单一有效状态**：无效格式不得污染最近一次有效配置。
2. **完整性可见**：配置值与缺失项/目录错误必须能同时形成 `EffectiveConfig`。
3. **目录状态变化可处理**：保存时要检查目录；读取有效配置时要能反映当前目录不可读状态，但读取探测不得偷偷改写持久化值。
4. **边界隔离**：所有配置读者经过配置端口，只读访问；不得绕过端口直接操作 `ST-01`。
5. **演进可控**：持久化 schema 可增加版本信息，但不能改变父层 `PluginConfig` 和 `EffectiveConfig` 的公共字段语义。

## 5. Reusable capability, gaps, planned outputs and handoff validation

- **可复用父能力**：`ST-01` 单写方、`IC-M01-02` 配置端口、`IC-M01-05` ConfigView、`ConfigSaved/ConfigRejected` 事件语义、DU-1 本地运行边界。
- **当前 PRD 缺口**：没有给出具体序列化格式、锁实现或原子替换 API；这些不会改变本层结构，留给下一级详细设计。
- **本次创建文件**：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。
- **上游影响**：无；未请求修改父契约、所有权、依赖方向、技术选择或部署边界。
- **下游影响**：下一级可分别细化四个 `child_id`；必须携带本包全部七文件及父层 `IC-M01-02`/`IC-M01-05` 语义。
- **验证方法**：逐项核对父边界、需求追踪、状态单写方、契约字段/错误/版本、C1-C6 映射、稳定 ID 排序与交接清单。

## 6. Assumptions and open questions

- 格式无效是“拒绝保存”的条件；目录为空或不可读是“保存配置并标记不完整/目录错误”的条件，符合父层验收边界。
- 读取时的目录重新探测只影响派生 `EffectiveConfig`，不覆盖最近一次有效持久化配置。
- 具体文件格式、编码、锁和替换 primitive 是实现细节，不构成当前父层变更。
- 当前没有冲突，也没有 `return_to_parent` 事项。
