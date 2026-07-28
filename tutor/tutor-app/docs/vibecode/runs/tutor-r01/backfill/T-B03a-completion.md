# T-B03a 完成记录 — ACCESS-GATE：教师认证与课程授权

- 状态：done
- 分支 / worktree：`tutor-r01/B03a-access-gate`（`tutor-app/.worktrees/B03a-access-gate`）
- 提交 SHA：`e0137139a4f90423811e525718949d22732c119d`
  （`feat(b03a): access gate — teacher auth, sessions, course grants, denied audit`）
- 基线：合并 main 后实施（merge 无冲突）。

## 改动

- `server/migrations/versions/0012_access_gate.py`（down_revision=`11a22f91f4b3`，并行多头）：
  - `teacher_accounts`（账号、PBKDF2-HMAC-SHA256 口令哈希+盐+迭代次数、status∈{active,disabled}）
  - `teacher_sessions`（不透明令牌 sha256 哈希、教师、created/last_seen/expires，12h 滑动续期 DD-004）
  - `teacher_access_grants`（teacher_id+course_id 复合主键，LCD-006 本地持有）
  - `access_denied_log`（AccessDeniedLogged 追加审计：教师/课程/动作/来源/时间，ST-ACCESS-DENIED-LOG）
- `server/course_app/teacher_web/access_gate/`（新包）：
  - `models.py` / `errors.py`（内部 AuthInvalidError=401 语义、AccessDeniedError=403 语义）
  - `service.py` `AccessGateService`：provision（幂等，teacher_id 由账号确定性派生）、
    login（失败不区分账号/口令原因，防枚举）、verify_session（12h 滑动续期）、
    require_grant（拒绝先追加审计再抛错）
  - `adapters.py` 三种冻结端口形状适配器（不改 L14/L15/L16）：
    - L14 `ReviewCommandAccessGate`：authorize(teacher_session, submission_id)→AccessGrant；
      submission→course 经 SI-CORE 登记解析；提交不存在只认证放行（NOT_FOUND 归 L14 服务层）
    - L15 `ReviewQueryAccessGate`：authorize(teacher_session, course_id)→AuthorizedQueryContext；
      course_id=None 只认证（课程列表）
    - L16 `PresentationAccessGate`：authorize(authorization)→AuthContext（Bearer 解析；
      按端口契约只供给身份与授权范围，归属比对归 L16）
  - `cli.py`：`python -m course_app.teacher_web.access_gate.cli provision`（幂等；
    口令经 --password 或 ACCESS_GATE_PROVISION_PASSWORD；库连接 --database-url 或 DATABASE_URL；
    输出不含口令）
- `server/tests/test_b03a_access_gate.py`：32 个用例。

## 验证（worktree 根，全部通过）

- `python -m unittest discover -s server/tests -p "test_b03a_*.py" -v`：32 全绿
- `python -m unittest discover -s server/tests`：269 全绿（无回归）
- `python -m unittest discover -s worker/tests`：104 全绿
- plugin `npm test`：85 pass / 0 fail
- 冒烟：`scripts/smoke_wave1/2/3.py` 全部 SMOKE_OK
- `ruff check`（改动路径）：All checks passed
- `py_compile`：通过；`python -m alembic heads/history`：0012_access_gate 为 head、down=11a22f91f4b3 可导入

## 契约影响

- 无契约语义变更：只实现 L14/L15/L16 已冻结的 ACCESS-GATE 端口形状，未改任何叶子代码或 contracts。
- 新增迁移头 0012（并行多头之一），集成时需 alembic merge heads（backfill-plan 既定纪律）。

## 安全口径自查

- 口令/令牌明文不入库、不入审计、不出现在 CLI 输出（测试断言哈希落库与审计无明文）。
- 会话为不透明令牌（secrets.token_urlsafe），服务端只存 sha256；12h 滑动续期有持久化断言。

## 风险

- L14 适配器对"提交不存在"只认证即放行（NOT_FOUND 由 L14 服务层判定）——已认证教师可探测
  submission_id 存在性（仅能区分 404/403），v1 单教师运维模型下可接受，留痕由审计承担。
