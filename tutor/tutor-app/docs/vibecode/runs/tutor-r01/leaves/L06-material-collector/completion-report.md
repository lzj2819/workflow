# Completion Report — L06 CMP-MATERIAL-COLLECTOR（tutor-r01, W1）

- leaf：L06 CMP-MATERIAL-COLLECTOR
- 分支：`tutor-r01/L06-material-collector`（worktree：tutor-app/.worktrees/L06-material-collector）
- 提交 SHA：`f7f4dc26f6d1735876c9c3d592091eb5b6de51fb`
- 状态：done

## 改动清单（均在 allowed-context 内）

| 文件 | 说明 |
|---|---|
| `plugin/src/material_collector/index.js`（新增） | `collectMaterials(config, deps)`：三类目录（code/screenshot/result）扫描 → KD-004 白名单过滤 → MaterialManifest；`DEFAULT_WHITELIST`、`MAX_SUBMISSION_BYTES=524288000`、`MATERIAL_CATEGORIES`、`MaterialCollectionError`（MC-ERR-CONFIG-INVALID / MC-ERR-DIR-UNREADABLE / MC-ERR-COLLECT-BUSY） |
| `plugin/test/material-collector.test.js`（新增） | 9 例，node:test 临时目录夹具 |

实现要点：

- items：`{category, path, size_bytes, sha256(node:crypto), modified_at}`；确定性排序（category → path，POSIX 分隔符）。
- 只读取配置的三个目录；不递归子目录、不跟随符号链接、不读隐藏文件（跳过的符号链接/元数据失败记入 diagnostics）。
- 白名单外文件跳过并按类别计数（`skipped_by_category` + diagnostics），不产生 items。
- 目录不存在或为空 → 类别显式入 `missing_items` 并附 warnings（不隐藏缺口，AC-REQ-003-01 MOD-01 slice / INV-L2-MC-03）。
- `total_bytes` 仅累计白名单通过项（LCD-L2-MC-002）；超限置 `over_budget=true` 并追加预检告警（客户端预检，服务端权威不变，LCD-003）；可用 `deps.max_total_bytes` 注入预算验证。
- 端口形状对齐 IC-M01-03：`items` 可作 `CollectionBatch.material_refs`，`missing_items` 语义一致；类别 code/screenshot/result 与 CT-001 `material_chunks[]` 枚举（代码/截图/结果）一一对应。
- 零运行时依赖，Node ESM；幂等复用/并发守卫（INV-L2-MC-05/06）按设计归属 CMP-PENDING-QUEUE，本叶子不实现。

## 验证命令与结果（worktree 的 plugin/ 目录）

1. `node --check plugin/src/material_collector/index.js` 与 `node --check plugin/test/material-collector.test.js` → 通过（CHECK-OK）。
2. `node --test test/material-collector.test.js` → `tests 9, pass 9, fail 0`（duration ~155ms）。
3. `npm test`（`node --test` 全量） → `tests 17, pass 17, fail 0`；既有 8 例（layout / plugin-config / dialogue-export-port）无回归。

语义断言覆盖（对照 verification-checklist）：

- 三类目录收集 manifest：category/path/size_bytes/sha256 齐全、确定性排序 → TC1
- 白名单外文件跳过并计数（含隐藏文件/子目录不进入） → TC2
- 目录不存在/为空 → missing_items，其余类别正常 → TC3
- total_bytes 汇总正确；超 500MB 预检警告标志（over_budget + warnings） → TC4
- 同一目录两次收集 manifest 一致（固定 snapshot_at，快照稳定性） → TC5
- 端口形状与 ports/index.js material_refs 一致 + CT-001 类别枚举映射 → TC6
- 附加：MC-ERR-CONFIG-INVALID / MC-ERR-DIR-UNREADABLE 显式失败、白名单可配置覆盖 → TC7~TC9

## 契约影响

无。未修改 contracts/、ports/index.js 或任何共享契约；`items`/`missing_items` 仅按 IC-M01-03 既有形状产出，未新增跨组件字段或类别。

## 风险/阻塞

- 低风险：`missing_items`/类别值采用 code/screenshot/result（L2 契约内部标识），CT-001 中文类别映射交由上传侧（L10）执行，与父架构 INV-L2-MC-01 一致；集成时需在 L10 确认映射点。
- 无阻塞；无需 contract-change-request。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD`：

```
plugin/src/material_collector/index.js
plugin/test/material-collector.test.js
```

仅允许路径内两个新文件；未触碰 forbidden-changes 任何条目（无 package.json 改动、无 npm 依赖、无其他叶子职责）。
