# Testing — tutor-app

## 测试分层

| 层 | 位置 | 运行器 | 依赖 |
|---|---|---|---|
| 契约测试 | `server/tests/test_contracts_schema.py` | unittest | 零第三方 |
| 平台测试 | `server/tests/test_platform.py` | unittest | 零第三方 |
| server 配置/布局 | `server/tests/test_settings.py`、`test_layout.py` | unittest | 零第三方 |
| worker 测试 | `worker/tests/test_worker.py` | unittest | 零第三方 |
| plugin 测试 | `plugin/test/*.test.js` | node --test | 零依赖 |
| （后续）叶子验收 | 各叶子任务包 verification-checklist | 任务包指定 | — |

## 一键命令（仓库根）

```bash
PYTHONPATH="shared;server;worker" python -m unittest discover -s server/tests -t . -v
PYTHONPATH="shared;server;worker" python -m unittest discover -s worker/tests -t . -v
cd plugin && npm test
```

静态/语法检查：

```bash
python -m py_compile $(git ls-files '*.py')
node --check $(git ls-files '*.js')   # 或逐文件
```

格式化与静态检查（安装后）：`ruff check server worker shared`（配置待 Phase 2 引入时登记）。

## 契约测试覆盖点（Phase 1）

- 16 个契约文件齐备、可解析、结构合法（必需元数据键）；
- API 契约声明错误码；事件契约 `schemas.event` 含 `v`（const 1）；
- 幂等要求（idempotency 字段非空；事件消费去重键在 idempotency 中声明）；
- 关键契约必填字段与冻结设计逐字段一致（CT-001/004/005/008/010/013 等抽查）；
- CT-010 数据最小化：请求 schema 禁止业务标识字段。
