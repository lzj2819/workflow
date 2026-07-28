# Verification Checklist — L05

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/intent-parser.test.js` 全绿
- [ ] `npm test` 全绿（既有测试不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] 完整指令（含作业+姓名+小组）→ complete=true 且三值正确提取
- [ ] 缺作业/缺姓名/缺小组/全缺 → complete=false 且 missing 精确列出缺失字段
- [ ] 同一输入重复解析输出完全一致（确定性）
- [ ] 中文姓名/组名（含空格与「第 X 组」形态）正确提取
- [ ] 与配置不一致的指令仍按当次指令输出（R-05）
- [ ] testcases.json 中本叶子的正/反场景全部通过
