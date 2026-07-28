# Forbidden Changes — L12

- 修改 `contracts/`、`shared/`、`worker/assessment_worker/`（engine 之外，含 model_provider.py）、`server/`、`plugin/`、`deploy/`、`docs/`。
- 接入真实模型供应商、发起任何网络调用、外发学生材料或业务标识。
- 实现编排器/rubric composer/结果发布/供应商 ACL 适配（backfill 或其他叶子）。
- 伪造评估结论充当真实评估（fake 输出必须可追溯为 fake）。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
