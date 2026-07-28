# 01 Design Context — CMP-UPLOAD-CLIENT（L2）

## 1. 本次设计范围

- **目标节点**：`CMP-UPLOAD-CLIENT`，父包 `architecture/L1/L1-mod-01` 中唯一匹配。
- **当前 PRD**：`prd/L2-PRD/mod-01/L2-mod-01-cmp-upload-client/prd.md`，当前需求映射为 `REQ-DD001`、`REQ-DD003`、`REQ-DD004`。
- **模式**：`new`；输出目录 `architecture/L2/mod-01/L2-mod-01-cmp-upload-client`，写入前不存在，不覆盖已有兄弟目录。
- **层级边界**：只细化上传客户端内部；`MOD-02`、`CMP-PENDING-QUEUE`、`CMP-CONFIG-STORE`、材料/对话采集器仅作为契约和数据来源引用。

## 2. 父边界快照

| 条目 | 内容 | 父层来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `CMP-UPLOAD-CLIENT`，L1 `MOD-01` 内的 CT-001/CT-002 consumer | 父 02 §2、child-handoff §2 | inherited-fixed |
| 职责 | 令牌换取；创建会话、逐分片、合并；维护 `UploadCheckpoint`；30 秒超时转 CT-002；断点续传 | 父 02 §2 | inherited-refinable（内部开放） |
| 排除项 | 不改变父契约；不拥有 Submission；不决定任务生命周期；不采集材料；不参与归属校验 | 父 01/02/03/04/05 | inherited-fixed |
| 部署 | `DU-1 student-plugin`，学生本机 Codex 环境内进程 | 父 manifest、child-handoff | inherited-fixed |
| 外部 Provider | `MOD-02` 提供 CT-001、CT-002 与 auth/token 附属端点 | 父 04 §1 | inherited-fixed |
| 父内部入口 | `IC-M01-04 UploadJob → UploadOutcome`，Owner 为 L1 `CMP-UPLOAD-CLIENT` | 父 04 §3 | inherited-fixed |
| 状态 | `ST-05 UploadCheckpoint`，仅记录服务端已确认分片，任务终态删除 | 父 03 §1/§2/§4 | inherited-fixed（所有权可在本节点内细化） |
| 关键决策 | `KD-003` HTTPS；`KD-005` token + submission UUID + 分片续传 + `/api/v1`；`A-007` 持久化机制为实现细节；`LCD-006` token 缓存策略下沉 | 父 05 | inherited-fixed/delegated |

## 3. 当前 PRD 需求分配

当前 PRD 的 `Requirements` 标题没有补充额外条目，frontmatter 与验收契约提供了本次实际需求来源；本层不虚构新的 REQ。

| 当前需求/契约 | 分类 | 父层追踪 | 本层承接 |
|---|---|---|---|
| `REQ-DD001` | allocated | 映射 `REQ-D001`；`D-AC-REQ-001-01`；父 `IC-M01-04`；CT-001 | 编排启动、认证、上传结果回调、提交编号传递 |
| `REQ-DD003` | allocated | 映射 `REQ-D003`；`D-AC-REQ-003-01` shared slice；CT-001 `material_chunks[]` | 原样发送采集器提供的对话材料条目，不重采集、不改类别 |
| `REQ-DD004` | allocated | 映射 `REQ-D004`；`D-AC-REQ-003-01`；CT-001 `material_chunks[]` | 原样发送代码/截图/结果材料及身份/作业字段，不重做服务端校验 |
| `D-AC-REQ-001-01` | allocated | 父 `AC-REQ-001-01`；CT-001/CT-002 | 连接成功返回提交编号；中断保留由队列负责，本节点返回可恢复结果 |
| `D-AC-REQ-003-01` | allocated | 父 shared projection `MOD-01:shared` | 上传完整材料包；服务器保存/校验结果由 MOD-02 权威，本节点只传输和反馈 |
| `30 秒未确认` | inherited | 父 NFR-003、CT-001 timeout | 只返回 `unknown`，由 Outcome Resolver 触发 CT-002，不伪造成功/失败 |
| `HTTPS/token/uuid/断点续传` | inherited | `KD-003`、`KD-005`、CT-001/CT-002 | 在四个内部子节点中实现，不改外部语义 |
| 其他 MOD-01 需求 | out-of-scope | 意图、配置、采集、展示由 L1 兄弟子节点承接 | 本层不重新设计 |

## 4. 局部驱动

1. **协议顺序完整性**：创建会话、发送未确认分片、提交合并必须保持 CT-001 顺序；不得把 checkpoint 当作服务端状态替代品。
2. **断点恢复正确性**：每个 `submission_uuid` 同时至多一个活跃执行；只有服务端确认过的分片才可跳过。
3. **结果未知安全性**：30 秒超时只表示客户端未获确认，必须走 CT-002；查询期间不能向父队列返回终态成功。
4. **认证边界**：令牌是访问凭据，不落盘；`AUTH_INVALID` 只能按父契约传回，不能由客户端推断名单结论。
5. **本地部署约束**：所有内部 child_id 都是进程内逻辑，网络出口仍属于 `CMP-UPLOAD-CLIENT` 的父边界。

## 5. 可复用能力与缺口

### 可复用能力

- 父包已给出 CT-001 的字段、分片顺序、幂等键与错误码。
- 父包已给出 CT-002 的路径、404、指数退避与只读语义。
- L1 `ST-05`、`IC-M01-04`、`INV-2/INV-5` 可直接作为本层状态与契约基线。
- `D-AC-REQ-001-01` 与 `D-AC-REQ-003-01` 提供成功、中断和服务器拒绝的可观测结果。

### 阻塞缺口

无。具体分片大小、HTTP 客户端库、checkpoint 的文件/KV 形式属于实现细节，不影响本层内部边界。

## 6. 拟生成文件与上下游影响

拟生成本包七个常规文件：manifest、设计上下文、内部结构、状态数据、契约运行时、局部决策、交接。不生成 `parent-change-request.md`。

上下游契约影响为**无变更**：父队列仍通过 `IC-M01-04` 启动并接收 `UploadOutcome`；`MOD-02` 仍是 CT-001/CT-002/auth-token Provider；配置、材料与对话仍由 L1 兄弟节点提供。

## 7. 假设、问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | `UploadJob.bundle_ref` 已由父队列/采集器准备完成，上传客户端不重新采集材料 | 继承父 `IC-M01-04`；写入内部契约 |
| 假设 | 令牌租约可在单次进程运行期间短暂复用 | 固定不落盘；具体缓存结构留实现细节 |
| 问题 | 父层未规定具体分片大小和 HTTP 客户端 | 记为 `LCD-UP-005`，不阻塞；不得改变 CT-001 语义 |
| 冲突 | 未发现当前 PRD 要求改变父职责、契约、所有权、技术或部署 | 不创建父层变更请求 |

## 8. 验证方法

交接前实际检查：输入/目标唯一匹配；四个 child_id 均有追踪；`ST-05` owner 只在目标节点内部下沉；机器可读契约覆盖必要字段、`next_hop`、错误/重试/幂等；三条运行流覆盖成功、失败恢复和生命周期；父契约语义逐项确认不变。

