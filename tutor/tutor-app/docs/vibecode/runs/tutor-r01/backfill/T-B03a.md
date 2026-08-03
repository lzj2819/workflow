# T-B03a — ACCESS-GATE：教师认证与课程授权（Phase 5 / B-03）

- worktree：`tutor-app/.worktrees/B03a-access-gate`（分支 tutor-r01/B03a-access-gate，需先由协调者创建）
- 允许路径（仅这些）：
  - `server/course_app/teacher_web/access_gate/**`
  - `server/migrations/versions/0012_access_gate.py`（`down_revision="11a22f91f4b3"`）
  - `server/tests/test_b03a_*.py`

## 目标

实现 MOD-05 认证授权闸（A-001/KD-005 教师侧）：教师账号（v1 运维预置单教师，DD-004）+ 会话签发/校验 + 课程范围授权（TeacherAccessGrant，LCD-006 本地持有）+ AccessDeniedLogged 追加审计（ST-ACCESS-DENIED-LOG，不随提交删除）。

## 交付物

1. 迁移 `0012_access_gate.py`：`teacher_accounts`（账号、口令哈希 PBKDF2/scrypt 标准库实现、状态）+ `teacher_sessions`（不透明令牌哈希、教师、过期、滑动续期）+ `teacher_access_grants`（teacher_id、course_id）+ `access_denied_log`（追加：教师/课程/动作/时间/来源）。
2. `AccessGateService`：login(account, password) → 会话（12h 滑动）；verify(session_token) → AuthContext；authorize（三种冻结端口形状适配：L14 operator 形、L15 AuthorizedQueryContext 形、L16 AuthContext 形）——无权课程 → 403 + 追加 AccessDeniedLogged；会话非法 → 401。
3. 运维预置 CLI：`python -m course_app.teacher_web.access_gate.cli provision`（建教师+授权课程；幂等；口令只经参数/环境传入，不写日志）。
4. 测试：预置幂等、登录成功/失败、会话滑动续期与过期、三种 authorize 形状、403 审计追加（审计不含口令/令牌明文）。

## 禁止

- 改 L14/L15/L16/L17 代码（端口形状适配放本包）；口令/令牌明文入库入日志；引入新依赖；改其他目录/契约。

## 验证

- `python -m unittest discover -s server/tests -p "test_b03a_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`、迁移可导入

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B03a-completion.md`。
