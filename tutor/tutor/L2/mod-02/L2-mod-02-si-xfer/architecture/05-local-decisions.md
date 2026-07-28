# 05 Local Decisions — SI-XFER L2 局部决策

## 局部决策队列

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| L2D-001 | L1 ST-02 单写者约束 / 并发要求 | ST-02、NFR-002 | XFER-SESSION、ST-XFER-01 | 父层要求同 session 串行化，但未指定内部并发控制方式 | decide_now | 本文件 L2D-001 |
| L2D-002 | L1 IC-SI-01 分片幂等和 CHUNK_OUT_OF_ORDER | IC-SI-01、KD-005 | XFER-CHUNK、ST-XFER-02 | 父层未规定重复分片和顺序冲突的内部判定顺序 | decide_now | 本文件 L2D-002 |
| L2D-003 | L1 IC-SI-01 finalize 幂等 / ST-02 merged | IC-SI-01、INV-2 | XFER-FINALIZE、ST-XFER-03 | 父层未规定 merge/promote 失败后的持久化检查点 | decide_now | 本文件 L2D-003 |
| L2D-004 | 当前 PRD observability implementation surface | REQ-DD001、REQ-DD002 | XFER-SESSION、XFER-CHUNK、XFER-FINALIZE | 父层只规定基础监控，未定义本组件的观测粒度和非阻塞原则 | decide_now | 本文件 L2D-004 |
| L2D-005 | L1 LCD-007 / SI-STORE 边界 | LCD-007、ST-03 | XFER-CHUNK、XFER-FINALIZE | 目录布局、文件命名和加密参数必须由材料存储 owner 决定 | defer_to_next_level | SI-STORE 细化包 |
| L2D-006 | L1 LCD-006 | LCD-006、ST-02 | XFER-SESSION | TTL、归档周期、扫描间隔属于实现参数，不影响 L2 结构 | implementation_detail | 实现阶段配置 |
| L2D-007 | L1 KD-004/KD-005 | KD-004、KD-005 | XFER-CHUNK | 分片大小、缓冲区和具体摘要库不改变当前边界 | implementation_detail | 实现阶段配置 |

无 `return_to_parent` 决策。

## decide_now 决策详情

### L2D-001：同一会话采用单写者/版本保护

| 方案 | 评估 |
|---|---|
| A. 允许多写者后合并 | 需要解决重复 seq、计数竞争和文件引用竞态，难以保证 ST-XFER-01 原子进度 |
| B. 引入公共消息队列串行化 | 改变父技术/部署边界，违反 KD-002，不接受 |
| C. 会话级版本保护/短锁，选定 | 在既有关系型数据库意图内保护单个 session；不同会话并行；冲突请求按既有可重试错误返回 |

**决定**：选择 C。会话 owner XFER-SESSION 在写入 ST-XFER-01 前检查版本/锁，XFER-CHUNK 和 XFER-FINALIZE 通过内部命令请求迁移；不新增运行时边界。

补充约束：XFER-CHUNK 和 XFER-FINALIZE 不直接写 ST-02；它们只能通过 IC-XFER-02/IC-XFER-04 请求 XFER-SESSION 执行会话状态迁移。SI-API 是 append、finalize、abort 的外部调用入口。

### L2D-002：严格 next_seq + 相同摘要重复幂等

| 方案 | 评估 |
|---|---|
| A. 允许任意顺序并维护稀疏分片图 | 恢复复杂度和缺口检查成本高，超出父层 `CHUNK_OUT_OF_ORDER` 语义 |
| B. 只接受严格 next_seq，重复已接受分片可重放，选定 | 与父层错误语义一致，状态简单，断点恢复可直接从 next_expected_seq 继续 |
| C. 每片立即覆盖同 seq | 会掩盖客户端或网络重试中的冲突，破坏幂等证据，拒绝 |

**决定**：选择 B。相同 `session_id+seq+digest` 返回原结果；不同摘要返回冲突；未到 next_seq 返回 `CHUNK_OUT_OF_ORDER`，不写入 ST-XFER-02。

### L2D-003：最终化使用持久化检查点并保持 finalize 幂等

| 方案 | 评估 |
|---|---|
| A. 直接调用 promote_to_final 后再写状态 | 崩溃窗口会造成正式材料存在但本层无可恢复记录 |
| B. 先持久化最终化尝试，再调用 SI-STORE，并以 attempt_id 重试，选定 | 保留诊断和恢复锚点；不要求跨存储分布式事务；同一 attempt_id 不重复产生业务结果 |
| C. 在 SI-XFER 内自建文件复制和回滚 | 转移 SI-STORE 所有权，违反父边界，拒绝 |

**决定**：选择 B。XFER-FINALIZE 先记录 ST-XFER-03，再读取完整分片清单并调用既有 `promote_to_final`；成功后写入 material_refs 并投影 `merged`。已 merged 的 finalize 返回原结果。

### L2D-004：上传观测非阻塞且最小化敏感数据

| 方案 | 评估 |
|---|---|
| A. 每个观测写入业务事务 | 观测故障会拖慢上传并扩大事务，违反 30 秒短路径目标 |
| B. 非阻塞计数/摘要并交给基础监控，选定 | 满足 observability surface，不改变 SI-API 的 SM-001 口径和 owner |
| C. 本层新增监控 API/独立指标服务 | 新增公共运行时和部署边界，拒绝 |

**决定**：选择 B。记录阶段、耗时、结果、错误类别、重复数、恢复数和 I/O 延迟；不记录材料内容、原始姓名或名单响应；观测失败不得阻塞业务。

### 状态结果与父层状态值域

- `accepted`、`duplicate`、`rejected` 是 IC-XFER-02 的分片操作结果，不是 ST-02 的新增状态。
- `rejected` 分支必须返回既有错误码和 `failure_reason`，且不得写入暂存或 ChunkReceipt。
- 只有 XFER-SESSION 可以把 ST-02 投影为 `interrupted_retryable` 或 `failed_terminal`；父层状态值域保持不变。

## 继承决策（不重开）

| 父决策 | 本层落实 |
|---|---|
| KD-002 | 继续使用 DU-2 进程内组件和既有数据库意图；不引入消息队列；Outbox 不属于本层 |
| KD-003 | 材料加密、备份和基础监控沿用；不选具体算法参数 |
| KD-004 | 500MB、类型白名单、课程配额通过 IC-SI-02/本地流式检查落实；不改变错误映射 |
| KD-005 | submission_uuid 幂等、分片续传、`/api/v1` 外部路径保持不变 |
| LCD-001 | ROSTER_UNAVAILABLE 仍由 L1 会话层承载；本层只提供保存/恢复能力 |
| LCD-005 | rejected 暂存清理时机为实现细节；本层提供 abort/expiry 清理入口 |
| LCD-006 | TTL/归档/扫描的具体数值不在架构层决定 |
| LCD-007 | SI-STORE 拥有目录、命名和加密参数；本层只依赖 IC-SI-02 |

## 委托与父层专属禁止项

- `L2D-005` 委托 SI-STORE 详细设计，不在 SI-XFER 复制其存储策略。
- 未创建服务、容器、部署单元、缓存、消息总线或公共运行时边界。
- 未修改父 API/事件/内部 IC-SI-01/02 的标识、所有者、必需字段、状态值、错误或版本。
- 未转移 SI-CORE、SI-STORE、SI-API、SI-RELAY 或 SI-VERIFY 的状态/数据/契约所有权。
- 未设计兄弟节点内部；所有兄弟只以边界依赖出现。
