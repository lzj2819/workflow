# Completion Report — L04 CMP-CONFIG-STORE（tutor-r01, W1）

- leaf：L04 CMP-CONFIG-STORE（MOD-01 codex-plugin 插件配置，REQ-002 / AC-REQ-002-01）
- 分支：`tutor-r01/L04-config-store`（已合并 main，fast-forward 无冲突）
- 提交 SHA：`12927a56b81793b1ccd123b6ea274e3bd4273619`
- 状态：**done**

## 改动清单（全部在 allowed-context 内）

| 文件 | 说明 |
|---|---|
| `plugin/src/config_store/state-store.js` | CMP-CS-STATE-STORE（IC-CS-003）：ST-01 原子提交（临时文件 + rename，单写方串行化）、快照读取、schema v1 记录（`schema_version`/`config_version`/`config`/`completeness`/`dir_errors`/`saved_at`）、损坏/不支持版本可诊断错误且不覆盖原文件、进程内 lastGood（INV-3）。fs 原语可注入（writeFile/rename/readFile/mkdir/unlink）。 |
| `plugin/src/config_store/config-store.js` | CMP-CS-CONFIG-PORT（IC-M01-02）：`save()` / `get()` / `getRequired()` / `onChange()`；编排 validatePluginConfig（SCHEMA-VALIDATOR，只读复用 `plugin/src/config/plugin-config.js`，未修改）→ dirCheck 目录探测（DIRECTORY-PROBE，可注入）→ 原子提交 → ConfigSaved/ConfigRejected 事件（载荷不含配置值明文）。 |
| `plugin/test/config-store.test.js` | 10 项测试，覆盖 checklist 全部语义断言。 |

## 关键语义落地

- 格式无效（非对象、已填字段类型非 string）→ `INVALID_CONFIG` 拒绝保存，ST-01 不写入，旧有效配置保持可读（INV-3 / AC exceptions）。
- 必填为空 → 保存值并标记 `status:"incomplete"`，`missing[]`/`completeness[]` 显式列出缺失项（AC boundaries；任务包 §3）。
- 目录不可读 → 保存为不完整，`dir_errors[]` 含具体目录错误（`directory not readable: <field>=<path>`，与 plugin-config.js 冻结格式同源）；读取时重新探测且不反写 ST-01（LCD-CS-003）。
- 原子保存：rename 前任何失败 → `PERSISTENCE_FAILED`，旧文件字节不变，临时文件清理。
- 损坏文件（非法 JSON）→ `CONFIG_CORRUPT` 可诊断错误；进程内有 lastGood 时以 `stale:true` + `read_error` 提供旧值（不伪造结论）；读取无任何写副作用。
- 不支持 `schema_version` → `UNSUPPORTED_SCHEMA_VERSION`，保留原记录不以默认值覆盖（LCD-CS-004）。
- 重开（新实例）后值逐项一致；`config_version` 跨进程延续不回退。

## 验证命令与结果（worktree `plugin/`，Node v24.14.0）

- `node --test test/config-store.test.js` → **tests 10 / pass 10 / fail 0**
- `npm test` → **tests 18 / pass 18 / fail 0**（既有 8 项无回归 + 新增 10 项）
- `node --check src/config_store/state-store.js src/config_store/config-store.js test/config-store.test.js` → 通过（SYNTAX-OK）

结果尾部：

```
ℹ tests 18
ℹ pass 18
ℹ fail 0
```

## 契约影响

无。未修改 `contracts/`、`plugin/src/ports/`、`plugin/src/config/`、`plugin/src/host/`、`package.json`；IC-M01-02 的 owner/字段/失败语义与 versioning 未变（EffectiveConfig 产出六字段 + `completeness[]` + `dir_errors[]`，事件 ConfigSaved/ConfigRejected 与 L1 §3.1 一致）。

观察项（非契约变更，供协调者知悉）：L1 机器可读附录中目录字段写作 `screenshot_dir`/`result_dir`，而仓库冻结 schema（`plugin/src/config/plugin-config.js` 的 `REQUIRED_CONFIG_FIELDS`）为 `screenshots_dir`/`results_dir`；本实现按任务包交付物 1 与冻结 schema 采用后者，未改任何契约文件。

## 风险 / 阻塞

- 无阻塞。残余风险低：Windows 上 `fs.rename` 覆盖既有文件依赖 libuv `MOVEFILE_REPLACE_EXISTING` 行为（本机 Node 24 已验证通过）。
- `validatePluginConfig` 无需变更（复用满足全部校验需求）。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD`：

```
plugin/src/config_store/config-store.js
plugin/src/config_store/state-store.js
plugin/test/config-store.test.js
```

全部位于 allowed-context 可写路径内；未触碰 forbidden-changes 所列内容；未实现其他叶子职责。
