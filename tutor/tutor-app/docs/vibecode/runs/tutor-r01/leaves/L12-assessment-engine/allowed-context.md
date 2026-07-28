# Allowed Context — L12 ASSESSMENT-ENGINE

## 可写路径（仅这些）

- `worker/assessment_worker/assessment_engine/**`
- `worker/tests/test_l12_assessment_engine.py`（如需辅助文件用 `worker/tests/l12_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`worker/assessment_worker/`（其余；含 model_provider.py、scoring_orchestrator/）、`server/`、`plugin/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装；**禁止再安装、禁止接入真实模型 API、禁止外发材料**（仅 FakeModelProvider）。
- 测试运行目录：worktree 根（`.worktrees/L12-assessment-engine`）。
