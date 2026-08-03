# Decompose Method Note

本目录不再保存与顶层模式平行的第二套 artifact spec。Decompose 的唯一执行合同位于仓库根 `SKILL.md`、`contracts/architecture-contract-v1.md`、canonical JSON Schema 和 compiler。

执行顺序只有四步：精确选择父节点并锁定 fingerprint；逐条分配当前 PRD；只设计所选节点内部；若触碰父边界则输出 parent change request 并停止。所有结果仍写入与 Top-Level 相同的 canonical 字段和 12 节视图。

