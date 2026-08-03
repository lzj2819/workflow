# VibeCode Task — L06 CMP-MATERIAL-COLLECTOR（W1）

- run：tutor-r01；leaf：L06；波次：W1；分支：`tutor-r01/L06-material-collector`
- 模块：MOD-01 codex-plugin / CMP-MATERIAL-COLLECTOR 三类目录材料收集与清单（DU-1，Node ESM 零依赖）。

## 目标

按插件配置从代码/截图/项目结果三个目录收集材料，产出 MaterialManifest（REQ-004 / KD-004 白名单与预算 / AC-REQ-003-01 MOD-01 slice）。

## 交付物

1. `collectMaterials(config, deps)` → `MaterialManifest {items[], missing_items[], total_bytes}`：items 含 category（代码/截图/结果）、path、size_bytes、sha256；确定性排序。
2. 文件类型白名单（KD-004：代码/文本/图片/常见文档/压缩包扩展名表，可配置）；白名单外文件跳过并计数报告。
3. 缺失处理：目录不存在或为空 → 对应类别进入 missing_items（不报错、不隐藏缺口）。
4. 预算统计：total_bytes 汇总；超过 500MB 单次上限时给出预检警告（客户端预检，服务端权威，MOD-01 LCD-003）。
5. IC-M01-03 材料侧端口形状对齐 plugin/src/ports/index.js（CollectionBatch.material_refs）。
6. 测试：`plugin/test/material-collector.test.js`（用临时目录构造夹具）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-material-collector/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（03-state-and-data.md 的 ST-03/INV-4、05-local-decisions.md 的 LCD-003）
- 验收：根 PRD AC-REQ-003-01（MOD-01 slice；材料目录存在但为空 → 标记缺失）
- 仓库：`plugin/src/ports/index.js`、`contracts/ct-001.json`（材料类别与限制）、`contracts/internal-contracts.json`

## 关键语义

- 采集快照：同一任务重传不重采（INV-4 的清单稳定性——manifest 一经产出即冻结引用）。
- 缺失显式标记，不隐藏；不得上传白名单外文件。
- 不实现：对话采集（L07）、配置（L04）、上传（L10）、队列（L11）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
