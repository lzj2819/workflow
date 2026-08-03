# 03 State and Data — CMP-MATERIAL-COLLECTOR（L2）

## 1. 状态所有权注册表

| state_id | 状态 | Owner child_id | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-03 | `MaterialManifest` + 材料暂存引用 | CMP-MC-MANIFEST-BUILDER（代表 CMP-MATERIAL-COLLECTOR） | CMP-PENDING-QUEUE、CMP-UPLOAD-CLIENT、CMP-STATUS-PRESENTER | CMP-MC-MANIFEST-BUILDER | 任务创建时生成；任务进入 `received`/`rejected` 后由 MOD-01 队列协调清理 | 清单一次生成；同一 submission UUID 重传复用同一版本 | 仅保留路径引用/元数据与任务所需暂存；材料含个人信息/第三方代码，终态后清理 | L1 `ST-03`；REQ-D004；D-AC-REQ-003-01；KD-004 |
| ST-L2-MC-01 | `MaterialCandidateSet` | CMP-MC-DIRECTORY-SCANNER | CMP-MC-FILTER-POLICY | CMP-MC-DIRECTORY-SCANNER | 单次采集请求；过滤完成或失败后释放 | 一个请求一个候选集；类别候选来自配置目录映射 | 不对外持久化；路径只在本机使用 | 父 `ST-03` 的内部实现分解；REQ-DD004 |
| ST-L2-MC-02 | `FilteredMaterialSet` + `CollectionDiagnostics` | CMP-MC-FILTER-POLICY | CMP-MC-MANIFEST-BUILDER、CMP-STATUS-PRESENTER（经父编排读取） | CMP-MC-FILTER-POLICY | 清单构建后随请求结束；警告随任务清单交回 | 白名单过滤、大小累计、`missing_categories` 与扫描/过滤诊断透传在同一请求内一致 | 不含文件正文；不得记录不必要的个人信息 | KD-004；LCD-003；D-AC-REQ-003-01 |
| ST-L2-MC-03 | `ManifestBuildResult` | CMP-MC-MANIFEST-BUILDER | 父 `CMP-MATERIAL-COLLECTOR` facade、CMP-PENDING-QUEUE | CMP-MC-MANIFEST-BUILDER | 构建完成即交回；最终由父 `ST-03` 生命周期管理 | 身份快照、类别、条目和诊断一次性绑定 | 不复制正文；路径/大小/类别遵循父清单隐私边界 | 父 `IC-M01-03`；CT-001 `material_chunks[]` |

无状态持有者：`CMP-MC-DIRECTORY-SCANNER` 和 `CMP-MC-FILTER-POLICY` 的长期状态均为空；上表中的状态是请求级中间结果，不形成新的持久数据所有权。

## 2. 存储意图

- 本层沿用父层 DU-1 本机存储意图，不引入服务端存储、共享数据库、消息总线或独立缓存平台。
- `ST-03` 的具体持久化机制不在本层选择；遵守父层 `A-007` 对本地持久化机制的 implementation_detail 委托。
- 本层优先保存路径引用和元数据；是否需要任务级暂存副本由 MOD-01 上传/队列详细设计决定，本层不扩大存储承诺。
- 材料内容仅在扫描/上传所需时读取；清单不把文件正文嵌入内部契约，不向 `CMP-STATUS-PRESENTER` 暴露正文。

## 3. 关键数据流

### 3.1 写入流

1. `CMP-PENDING-QUEUE` 通过 `IC-M01-03` 传入任务 UUID、身份快照、配置快照和采集时刻。
2. `CMP-MC-DIRECTORY-SCANNER` 读取三个目录，写入请求级 `ST-L2-MC-01`。
3. `CMP-MC-FILTER-POLICY` 读取候选集，写入 `ST-L2-MC-02`：通过项、过滤原因、累计大小、超预算告警、空类别信息。
4. `CMP-MC-MANIFEST-BUILDER` 读取过滤结果与身份快照，生成 `ST-L2-MC-03`，再提交为父 `ST-03`。

### 3.2 读取流

- `CMP-PENDING-QUEUE` 读取 `MaterialManifest` 作为采集完成判断和后续上传编排输入。
- `CMP-UPLOAD-CLIENT` 将 Manifest 条目映射为 CT-001 `material_chunks[]`，但不改变类别、字段或顺序语义。
- `CMP-STATUS-PRESENTER` 读取 `missing_categories[]`、过滤警告和预算提示；不读取或复制材料正文。

### 3.3 清理流

- 任务进入父层终态 `received` 或 `rejected` 后，`CMP-PENDING-QUEUE` 协调清理；本组件删除/释放其 ST-03 关联路径引用和请求级缓存。
- `upload_failed` 或结果未知时不得清理可用于断点续传的清单/暂存引用；必须保持同一 submission UUID 的快照语义。

### 3.4 生命周期状态归属

- 生命周期状态机（`collecting` / `manifest_ready` / `collection_failed` / `retained_for_upload` / `cleaned`）的各迁移 owner、前置条件、触发事件、成功/失败分支与可观测副作用定义在 `04-contracts-and-runtime.md` §4.3 状态机要素表。
- `collecting`、`manifest_ready`、`collection_failed` 的迁移 owner 为 `CMP-MC-MANIFEST-BUILDER`（代表 `CMP-MATERIAL-COLLECTOR`）；`retained_for_upload → cleaned` 由 `CMP-PENDING-QUEUE` 协调触发、本组件执行清理。
- 状态迁移的写入目标与本表 §1 注册表一致：`manifest_ready` 写 `ST-03`；请求级 `ST-L2-MC-01/02/03` 随 `collecting` 结束释放或交回。

## 4. 一致性、幂等与并发规则

| 规则 | 内容 |
|---|---|
| `INV-L2-MC-01` 类别一致性 | `code_dir`、`screenshot_dir`、`result_dir` 分别产生 `code`、`screenshot`、`result`；不把目录名直接暴露为新的 CT-001 类别 |
| `INV-L2-MC-02` 预算口径 | 仅对白名单通过项累计大小；超 500MB 形成告警并交回上游，由服务端最终判定是否拒绝 |
| `INV-L2-MC-03` 空类别 | 目录存在但为空时保留类别为空并记录缺失类别；不在本层制造服务端 `rejected` |
| `INV-L2-MC-04` 快照 | 清单绑定任务创建时刻；重试只重用已有清单，不因文件变化重排条目 |
| `INV-L2-MC-05` 幂等 | 以父任务 `submission_uuid` 作为关联键；本组件不生成替代幂等键 |
| `INV-L2-MC-06` 并发 | 同一任务只允许一个 active collection；重复触发返回已有构建结果或显式 busy，不创建第二份 ST-03 |

## 5. 所有权确认

- `ST-03` 的父组件所有权未转移给 `CMP-PENDING-QUEUE`、`CMP-UPLOAD-CLIENT` 或任何兄弟组件。
- `Submission`、远端提交状态机、课程归属校验结论仍归父层/服务端链路；本层只保存客户端材料清单视图。
- 本层不重新分配 `ST-01` 配置、`ST-04` PendingTask 或 `ST-05` UploadCheckpoint 的所有权。
