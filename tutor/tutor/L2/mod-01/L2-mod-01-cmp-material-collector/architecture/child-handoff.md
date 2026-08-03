# Leaf Gate Override ? CMP-MATERIAL-COLLECTOR

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-MATERIAL-COLLECTOR（L2 → L3）

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 节点 | `CMP-MATERIAL-COLLECTOR`（L2，MOD-01 内部组件） |
| 职责 | 收集三类配置目录材料；执行白名单与 500MB 客户端预检；生成并关联 `MaterialManifest` |
| 排除项 | 不导出对话、不上传、不做服务端归属校验、不创建公共契约或部署单元 |
| 父包 | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` |
| 当前 PRD | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-material-collector/prd.md` |
| 边界指纹 | 见 `architecture-manifest.yaml` 的 `boundary_fingerprint` |
| 绑定决策 | `KD-003`、`KD-004`、`KD-005`、`LCD-003`、`A-007`、DU-1 |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议 L3 细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| CMP-MC-DIRECTORY-SCANNER | 读取三个配置目录并产生候选文件集 | 递归深度、符号链接、忽略目录、排序、读取错误与 ACL 适配 | `REQ-DD004`；`REQ-D004/FR-004`；父本地文件系统边界 |
| CMP-MC-FILTER-POLICY | 执行白名单过滤和预算统计 | MIME/扩展名表、平台差异、过滤原因、500MB 预算精度 | `REQ-DD004`；`D-AC-REQ-003-01`；`KD-004`；`LCD-003` |
| CMP-MC-MANIFEST-BUILDER | 组装并输出 MaterialManifest | `material_chunks[]` 映射、身份快照、路径规范化、诊断字段兼容 | `REQ-DD004`；`D-AC-REQ-003-01`；父 `ST-03`；`IC-M01-03` |

所有 child 均有直接需求或父层追踪；`trace_exemption_reason` 不适用。

## 3. 契约清单

### 继承契约

| 契约 ID | 用途 | Owner → Consumer |
|---|---|---|
| `IC-M01-03` | 采集编排输入/Manifest 输出 | `CMP-PENDING-QUEUE` → `CMP-MATERIAL-COLLECTOR` |
| `CT-001` | 最终上传材料类别来源 | `MOD-02` → `CMP-UPLOAD-CLIENT`，本组件提供 `material_chunks[]` 来源 |

### L2 内部契约

| 契约 ID | 用途 | Owner → Consumer |
|---|---|---|
| `IC-L2-MC-01` | 候选文件集与空类别/扫描诊断 | `CMP-MC-DIRECTORY-SCANNER` → `CMP-MC-FILTER-POLICY` |
| `IC-L2-MC-02` | 过滤后材料、预算统计、`missing_categories` 与诊断透传 | `CMP-MC-FILTER-POLICY` → `CMP-MC-MANIFEST-BUILDER` |

各契约的字段级 required/produced 定义、错误码枚举（`MC-ERR-*`）与字段覆盖断言见 `04-contracts-and-runtime.md` §3.1；`IC-M01-03` 入口唯一，由 `CMP-MC-MANIFEST-BUILDER` 作为 facade 实现。

L3 细化不得把上述内部契约提升为跨模块契约；若要改变 CT-001 类别、字段、所有权、失败语义或版本，必须回到父层。

## 4. 状态所有权清单

| 状态 ID | 状态 | Owner |
|---|---|---|
| `ST-03` | MaterialManifest + 材料暂存引用 | `CMP-MC-MANIFEST-BUILDER` 代表 `CMP-MATERIAL-COLLECTOR` |
| `ST-L2-MC-01` | MaterialCandidateSet（请求级） | `CMP-MC-DIRECTORY-SCANNER` |
| `ST-L2-MC-02` | FilteredMaterialSet + CollectionDiagnostics（请求级） | `CMP-MC-FILTER-POLICY` |
| `ST-L2-MC-03` | ManifestBuildResult（构建中间结果） | `CMP-MC-MANIFEST-BUILDER` |

关键不变量：类别映射稳定、空类别保留、预检只告警、快照重传不重采、同一任务不并发生成第二份有效清单。

## 5. 决策与未解决风险

- **已决定**：三个 child 的责任拆分；白名单过滤后累计预算；空类别不在本层阻断；预算超限不替代服务端拒绝。
- **委托 L3**：目录遍历细节（`LCD-L2-MC-005`）、白名单表细节（`LCD-L2-MC-006`）、Manifest 编码细节（`LCD-L2-MC-007`）。
- **实现细节**：本地持久化机制、具体文件库、线程/缓冲区策略不在本层决定。
- **未解决风险**：宿主文件系统权限、符号链接和目录变化策略需在扫描器 L3 细化；若需要新外部依赖或改变 DU-1 边界，必须 `return_to_parent`。

## 6. 推荐下一步

1. 优先 `[NEXT CMP-MC-DIRECTORY-SCANNER]`，先锁定遍历/权限语义。
2. 然后细化 `[NEXT CMP-MC-FILTER-POLICY]`，与父 KD-004 白名单逐项对齐。
3. 最后细化 `[NEXT CMP-MC-MANIFEST-BUILDER]`，完成父 `material_chunks[]` 映射与字段兼容。

所需祖先上下文：本包七个文件；如需核对外部字段，再读取父包 `04-contracts-and-runtime.md` 的 CT-001/IC-M01-03 相关段落。无需读取兄弟组件内部。

## 7. 实际输入/输出与验证结果

### 实际输入

| 输入 | 路径 | 状态 |
|---|---|---|
| `parent_architecture` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` | 已读取；递归子包；目标唯一匹配 |
| `target_node_id` | `CMP-MATERIAL-COLLECTOR` | 父分解表、handoff 和 ST-03 所有权行交叉确认 |
| `current_prd` | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-material-collector/prd.md` | 已读取；`REQ-DD004` 与 `D-AC-REQ-003-01` 可追踪 |
| `output_dir` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L2/mod-01/L2-mod-01-cmp-material-collector` | 新建；未覆盖兄弟目录 |

### 实际输出

已生成七个文件：

1. `architecture-manifest.yaml`
2. `01-design-context.md`
3. `02-architecture-decomposition.md`
4. `03-state-and-data.md`
5. `04-contracts-and-runtime.md`
6. `05-local-decisions.md`
7. `child-handoff.md`

未生成 `parent-change-request.md`，因为没有 `return_to_parent` 决策。

### 交接检查

| 检查 | 结果 |
|---|---|
| 四项输入、父包类型、唯一目标、输出安全 | 通过 |
| 当前 PRD 需求与验收契约有 child/父追踪 | 通过 |
| child registry 含 `trace_exemption_reason` 列且三项均有追踪 | 通过 |
| ST-03 所有权、生命周期和隐私边界保持不变 | 通过 |
| CT-001 / IC-M01-03 标识、owner、字段语义、失败/版本边界未改 | 通过 |
| C1-C6 映射与成功/失败/生命周期流齐全 | 通过 |
| 决策队列无遗留 `decide_now`，无 `return_to_parent` | 通过；仅有 L3 `defer_to_next_level` |
| child、契约、状态、决策清单按稳定 ID 排序 | 通过 |
| 兄弟组件仅引用未重设计 | 通过 |

## 8. Human Gate

当前包已准备进入一次 Human Gate。批准后可使用 `[NEXT child_id]` 继续 L3 细化；如需改变父契约、所有权、部署或技术边界，应使用 `[PARENT_CHANGE]` 返回父层。
