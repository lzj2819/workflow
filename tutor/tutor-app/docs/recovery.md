# Recovery — tutor-app / tutor-r01

## 恢复点（真相源）

1. `docs/vibecode/runs/tutor-r01/`：run-manifest（输入哈希 + gates）、execution-matrix、contract-freeze、task-registry、execution-log.jsonl、phase-1-verification-report。
2. 仓库根 `task_plan.md` / `progress.md` / `findings.md` / `AGENTS.md`。
3. 工作流仓库根的同名三文件为跨对话协调索引；冲突时以本仓库 run-scoped 文件为准，先做 Phase 0 对账。

## 新对话恢复步骤

1. 读 `AGENTS.md`、`task_plan.md`、`progress.md`、`findings.md`。
2. 读 run-manifest，核对 tutor 设计输入文件 SHA-256 与表内一致（任一不一致 → 不得 resume，报告用户）。
3. 读 task-registry 确认各任务状态；读 execution-log.jsonl 尾部事件。
4. `git status --short` + `git log -3 --oneline` 核对工作区。
5. 只继续 task_plan 中唯一 `in_progress` 的阶段；不得跳过 human gates（contract_change: CCR-001 pending）。

## 状态机与幂等要点（实现期）

- Submission 六态 + deleted；CT-003 每次重新校验；评分重试仅一次；Outbox 消费按业务键去重；重放守卫过滤已清除数据。
- 恢复运行 ≠ 恢复 Fixture 批准：任何 gate 批准必须为真实用户批准。
