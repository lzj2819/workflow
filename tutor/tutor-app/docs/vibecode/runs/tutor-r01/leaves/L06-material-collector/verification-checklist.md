# Verification Checklist — L06

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/material-collector.test.js` 全绿
- [ ] `npm test` 全绿（既有测试不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] 三类目录（代码/截图/结果）收集为 manifest：category/path/size_bytes/sha256 齐全、确定性排序
- [ ] 白名单外文件被跳过并计数（不产生 items）
- [ ] 目录不存在 → 该类别入 missing_items；目录为空 → 同样入 missing_items；其余类别正常收集
- [ ] total_bytes 正确汇总；超 500MB 给出预检警告标志
- [ ] 同一目录两次收集 manifest 一致（快照稳定性）
- [ ] 端口形状与 plugin/src/ports/index.js 的 material_refs 一致
