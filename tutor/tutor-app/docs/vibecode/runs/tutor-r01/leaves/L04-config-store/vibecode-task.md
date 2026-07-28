# VibeCode Task — L04 CMP-CONFIG-STORE（W1）

- run：tutor-r01；leaf：L04；波次：W1；分支：`tutor-r01/L04-config-store`
- 模块：MOD-01 codex-plugin / CMP-CONFIG-STORE 插件配置持久化与校验（DU-1，Node ESM 零依赖）。

## 目标

实现插件配置的持久化、原子保存、校验与 IC-M01-02 配置端口（REQ-002 / AC-REQ-002-01）。

## 交付物

1. PluginConfig schema v1（含 `schema_version` 字段供演进）：invite_code、student_name、group_name、code_dir、screenshots_dir、results_dir。
2. 原子保存（临时文件 + rename）；读取损坏时保留上一次有效配置（INV-3）；无效配置拒绝保存且不覆盖旧值。
3. 不完整配置：任一必填为空时保存为「不完整」状态并列出缺失项（AC-REQ-002-01 boundaries）；目录不可读时给出具体目录错误。
4. IC-M01-02 配置端口实现：get() / getRequired() / save() / 变更订阅；配置重开后值一致。
5. 复用 `plugin/src/config/plugin-config.js` 的 validatePluginConfig（只读引用，不得修改；确需变更记入完成包由协调者处理）。
6. 测试：`plugin/test/config-store.test.js`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-config-store/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（03-state-and-data.md 的 ST-01/INV-3、04-contracts-and-runtime.md 的 IC-M01-02）
- 验收：根 PRD AC-REQ-002-01
- 仓库：`plugin/src/config/plugin-config.js`、`plugin/src/ports/index.js`、`contracts/internal-contracts.json`

## 关键语义

- 无效配置不得覆盖上一次有效配置；缺失项显式列出；配置不得包含 secret 明文日志输出。
- 不实现：意图解析（L05）、采集（L06/L07）、上传（L10）、队列（L11）、展示（L13）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
