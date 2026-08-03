# Completion Report — L05 CMP-INTENT-PARSER（tutor-r01 / W1）

- leaf：L05；分支：`tutor-r01/L05-intent-parser`；worktree：`tutor-app/.worktrees/L05-intent-parser`
- 提交 SHA：`86103269d52d98a0a7148730f29552708d1ca833`（1 个提交；此前已按协调者要求 fast-forward 合并 main，无冲突）

## 改动清单（全部在 allowed-context.md 允许路径内）

- `plugin/src/intent_parser/index.js`：IC-M01-01 入口 `parseSubmissionIntent(text, options?)` + `createIntentParser(rules?)`；COMMAND-ADAPTER 编排，空输入失败闭合（EMPTY_COMMAND → 三项全缺）
- `plugin/src/intent_parser/rules.js`：可配置关键词/模式规则表 `DEFAULT_RULES`（作业/姓名/小组，中英文标签 + 「第 X 组」序数形态），`FIELD_IDS`
- `plugin/src/intent_parser/extract.js`：FIELD-EXTRACTOR，规则表驱动候选提取；每次调用克隆正则（无 lastIndex 共享态），空捕获视为未提取
- `plugin/src/intent_parser/normalize.js`：NORMALIZER，外围 trim + 连续空白折叠为单空格（无损、幂等）
- `plugin/src/intent_parser/gate.js`：REQUIRED-FIELD-GATE，唯一放行点；候选=1 放行、=0 缺项、>1 冲突按缺项 fail-closed（LCD-IP-002，不猜测）
- `plugin/test/intent-parser.test.js`：15 个用例

输出形状对齐 `plugin/src/ports/index.js` 的 IntentResult：`{complete, assignment?, student_name?, group_name?, missing[]}`；complete=false 时附带已确定字段供展示诊断，`missing[]` 为闸门唯一权威。

## 验证命令与结果（worktree `plugin/` 目录）

- `node --test test/intent-parser.test.js`：`tests 15 / pass 15 / fail 0`（尾部：`ℹ pass 15`、`ℹ fail 0`）
- `npm test`（经 `npm --prefix <worktree>/plugin test`，等价于在 plugin/ 下执行）：`tests 23 / pass 23 / fail 0` —— 既有 8 个测试（plugin-config 4 + dialogue-export-port 3 + layout 1）全部通过，无回归
- `node --check`：`rules.js / normalize.js / extract.js / gate.js / index.js / intent-parser.test.js` 全部 OK

语义断言覆盖（verification-checklist）：

- 完整指令（标签式/自然形态/英文标签）→ complete=true 且三值正确 ✔
- 缺作业/缺姓名/缺小组/全缺（空、空白、非字符串）→ complete=false + missing 精确列出 ✔
- 同一输入重复解析（含新建解析器实例）输出完全一致 ✔
- 中文姓名含空格（「张 三」）与「第 12 组」形态正确提取 ✔
- R-05：指令与配置不一致以当次指令为准；配置不得静默补齐缺项 ✔
- 冲突字段（「姓名：张三，姓名：李四」）fail-closed 按缺项、不猜测 ✔
- 可配置规则表：自定义关键词生效、内置表不受影响 ✔
- testcases.json：TC-001/TC-003 本叶子切片（身份+作业提取）与 TC-004/TC-005（缺项不产出可提交意图 + 具体缺失字段）正反场景全部覆盖；TC-002（唯一提交编号，L11）、TC-006（断网保留，L10）非本叶子职责，已在测试文件头注释标明归属

## 契约影响

无。未修改 `IC-M01-01/02` 字段、owner 或语义；未新增跨模块契约；未触碰 `contracts/`、`plugin/src/ports/`、package.json；零运行时依赖、零 npm install、无网络/模型调用（确定性闸门）。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD` 输出恰为上述 6 个文件，全部位于 `plugin/src/intent_parser/**` 与 `plugin/test/intent-parser.test.js`（注意：main 已先合并进分支，故该三点 diff 仅含本叶子改动）。

## 风险 / 阻塞

- 无阻塞。
- 风险（低）：规则表为关键词/模式驱动，对无标签自由文本（如「作业 3」式口语）采取 fail-closed（按缺项返回、请学生补全），宁可漏放也不错放——符合 LCD-IP-002；提取规则按 LCD-IP-004 为可演进的 implementation_detail，后续叶子/集成阶段可扩充规则表而不触碰闸门语义。
