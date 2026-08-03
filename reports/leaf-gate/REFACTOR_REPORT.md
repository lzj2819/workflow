# Leaf Gate v2 重构报告

日期：2026-08-03

## 1. 结论

原 Leaf Gate 同时承担 legacy 文档发现、PRD/Architecture/Gherkin 再解析、trace/risk 生成、LLM 判断、formal 数量阈值和多套报告发布，形成多个事实源。现已收敛为一个只读 canonical v2 consumer：先验证 Mocktest 修复闭环和最新证据，再做确定性分层判定，并固定输出五件 bundle。

## 2. 已删除或替换的不合理设计

| 原设计 | 问题 | v2 处理 |
|---|---|---|
| 2,391 行脚本内并存 legacy/formal/LLM 三条决策链 | 同一输入可能得到不同语义 | 重写为单一 admission → evaluation → routing 流程 |
| 五份最终/错误/静态/decision/report schema | 输出存在多个结构事实源 | 合并为 `schemas/leaf-gate-run.schema.json` |
| Markdown/Feature 发现与启发式反向解析 | 重建上游已有结构，产生漂移 | canonical v2 只读 JSON；legacy 退出生产路径 |
| 自动覆写 `traceability.md`、`risks.md` 后再自我判定 | 同一阶段既造证据又审证据 | 删除写入与自判职责；Leaf Gate 对输入只读 |
| 要求所有 producer 共享 run ID | 与独立 PRD/Architecture/Gherkin/Mocktest run 不兼容 | 使用稳定 identity + artifact ID/version/file hash；仅 report/evidence 成对 run 一致 |
| 从 Testcases 场景 `status` 推断 Mocktest 结果 | Testcases 是生成合同，不是执行结果 | 读取 Mocktest v2 正交 states、coverage 与 recommendation |
| Mocktest defect 数参与是否分层 | 缺陷应先修复，不应被解释为拆分收益 | 非 PASS 先路由回 Architecture/Validation，不执行 Leaf 判断 |
| requirements/interfaces 轮询生成 children | 制造伪精确边界 | 逐字段投影 Architecture 显式 `payload.nodes` |
| wall-clock 时间、非稳定键序、重复 output writer | 相同输入输出不一致 | 禁止生成时间，稳定排序、LF、terminal newline、统一 publisher |
| 生产 annotation template 和自由文本 LLM prompt | annotation 成为旁路事实源，LLM 输出不可约束 | 删除 annotation；可选 judgement 使用固定五项 schema |
| 旧 discovery/structured 两套测试 | 各自验证不同产品 | 统一为 v2 admission/decision/bundle 回归测试 |

## 3. Mocktest 修复闭环

Leaf Gate 不再把 Mocktest 运行结束等同于可进入判定：

- `WARNING|FAIL|BLOCKED` → `RETURN_TO_ARCHITECTURE`；
- execution/audit/publication/evidence 错误 → `RETURN_TO_VALIDATION`；
- 修复后必须证明 Architecture bytes 已变化、affected testcase 均已重验、最终报告指向当前 Architecture/Testcases；
- 只有完整五维 PASS、ALLOW、全量 coverage 和完整修复历史才进入 layering evaluation。

因此最终修改建议报告的真正消费方是 Architecture 层；Leaf Gate 只消费问题已关闭后的最新证据。

## 4. 统一输入与输出

输入清单固定为 `leaf-gate-input/v2`，精确引用五个 canonical producer artifacts。输出始终只有：

1. `leaf_gate_report.json`
2. `leaf_gate_report.md`
3. `next_action.json`
4. `execution_log.json`
5. `bundle_manifest.json`

机器主报告始终包含相同顶层键：`schema_version`、`artifact_schema_version`、`run_id`、`identity`、`source_artifacts`、`input_fingerprint`、`admission`、`evaluation`、`decision`、`next_action`、`overall`、`errors`、`content_sha256`。错误和回退也保持同一结构，以空集合/null 表示未执行字段。

Markdown 固定七节：Identity、Admission、Repair Chain、Evaluation、Decision、Proposed Children、Next Action。

## 5. 状态与下一动作

| Admission/Decision | 是否允许 Leaf 判定 | 下一动作 |
|---|---:|---|
| `RETURN_TO_ARCHITECTURE` | 否 | Architecture 修复 + affected tests 重验 |
| `RETURN_TO_VALIDATION` | 否 | 修复执行/audit/publication 证据并重跑 |
| `INVALID` | 否 | 修复合同、hash、lineage、coverage 或 repair chain |
| `ADMITTED + CONTINUE_LAYERING` | 是 | `DECOMPOSE` |
| `ADMITTED + STOP_LAYERING` | 是 | `VIBECODE` |

## 6. 验证证据

标准库测试覆盖 13 项：STOP、CONTINUE 精确 child projection、WARNING/FAIL/BLOCKED 回架构、audit ERROR 回验证、repair chain 正反例、stale Mocktest hash、全量 coverage、缺 child plan、深度耗尽、固定输出、重复运行字节一致、中央合同版本覆盖和真实 CLI 发布。

执行命令：

```powershell
python -m unittest discover -s leaf-gate/tests -v
python -m py_compile leaf-gate/scripts/run_leaf_gate.py
```

当前结果：13/13 PASS，脚本编译 PASS。默认 Python 环境没有 pytest/jsonschema，因此测试改为零第三方依赖的 `unittest`；中央 schema 同时由 Python JSON parser 验证为合法 JSON。

## 7. 下游迁移

Vibe Coding 的遗留 `scan_leaves` 仍读取旧命名与 Markdown 集合，本轮未越界修改阶段⑥。接入时必须新增 fail-closed Coding adapter，验证 `leaf_gate_report.json`、`next_action.json` 和 `bundle_manifest.json` 后再创建任务包；不得回退旧文件名绕过 v2。
