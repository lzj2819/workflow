# Verification Checklist — L04

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/config-store.test.js` 全绿
- [ ] `npm test` 全绿（既有 8 项不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] 保存→重新读取值一致（含中文字段）
- [ ] 原子保存：写入中断（模拟 rename 前失败）不破坏旧配置
- [ ] 无效配置拒绝保存且旧有效配置保持可读（INV-3）
- [ ] 必填缺失 → 状态「不完整」+ 缺失项列表（invite_code/student_name/group_name/三个目录）
- [ ] 目录不可读 → 具体目录错误（注入 dirCheck 模拟）
- [ ] 损坏的配置文件（非法 JSON）读取时不覆盖旧值并给出可诊断错误
- [ ] IC-M01-02 端口形状与 plugin/src/ports/index.js 一致
