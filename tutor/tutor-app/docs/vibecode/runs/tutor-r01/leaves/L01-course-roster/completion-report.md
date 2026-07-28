# Completion Report — L01 MOD-03 course-roster（W1）

- run：tutor-r01；leaf：L01；分支：`tutor-r01/L01-course-roster`
- 提交 SHA：**972e1f9**（`feat(l01): MOD-03 course-roster — Course 聚合、CT-003 归属校验、CT-013 名单导入、只读端口、迁移与测试`）
- 日期：2026-07-20

## 改动文件清单（9 个，全部在允许路径内）

| 文件 | 说明 |
|---|---|
| `server/course_app/course_roster/__init__.py` | 包边界说明（在原脚手架占位 docstring 上扩展） |
| `server/course_app/course_roster/errors.py` | 错误类型 + 拒绝原因编码（P5：INVALID_INVITE_CODE / ROSTER_ENTRY_NOT_FOUND） |
| `server/course_app/course_roster/models.py` | ST-COURSE（courses/invite_codes/roster_entries）+ ST-VERIFICATION-RECORD；sa 通用类型，无 PG 专有类型 |
| `server/course_app/course_roster/admin.py` | CMP-COURSE-ROSTER-ADMIN：provision_course（LCD-004 幂等）、import_roster（CT-013）、CP-ROSTER-QUERY、CP-COURSE-ENDTIME |
| `server/course_app/course_roster/verifier.py` | CMP-MEMBERSHIP-VERIFIER：CT-003 校验（P1–P5）、同事务逐条记录、ROSTER_UNAVAILABLE 映射 |
| `server/course_app/course_roster/api.py` | FastAPI APIRouter（不挂载）：POST /api/v1/courses/verify-membership、POST /api/v1/courses/{course_id}/roster |
| `server/course_app/course_roster/cli.py` | 运维预置 CLI（`python -m course_app.course_roster.cli provision`，幂等） |
| `server/migrations/versions/0002_course_roster.py` | 新建；`down_revision="0001_baseline"`（多头由协调者集成时合并） |
| `server/tests/test_l01_course_roster.py` | 18 项语义测试 |

注：允许路径按协调者 2026-07-20 勘误为 `server/course_app/course_roster/**`（与 Phase 1 脚手架包位置一致），allowed-context.md 已同步更新。

## 验证命令与原始输出尾部

运行目录：worktree 根（`.worktrees/L01-course-roster`）。

### 1. `python -m unittest discover -s server/tests -p "test_l01_*.py" -v`

```
test_ct003_response_fields_match_contract ... ok
test_ct003_store_failure_maps_roster_unavailable ... ok
test_ct013_response_fields_match_contract ... ok
test_ct013_unknown_course_404 ... ok
test_returns_course_end_time_and_none_for_unknown ... ok
test_import_dedup_conflicts_partial_success ... ok
test_import_unknown_course_raises_not_found ... ok
test_reimport_is_idempotent ... ok
test_migration_importable_and_revisions ... ok
test_provision_idempotent_and_p1_conflict ... ok
test_cli_provision_idempotent_and_conflict ... ok
test_each_call_writes_independent_record ... ok
test_hit_returns_verified_and_course_id ... ok
test_invalid_invite_code_reason ... ok
test_record_model_has_no_submission_id ... ok
test_rereads_current_roster_no_cache ... ok
test_roster_miss_reason ... ok
test_roster_unavailable_no_record_no_internals ... ok
----------------------------------------------------------------------
Ran 18 tests in 0.320s

OK
```

### 2. `python -m unittest discover -s server/tests`（回归）

```
Ran 53 tests in 0.407s

FAILED (failures=1)
```

唯一失败为 `test_platform.TestOutbox.test_full_cycle_with_retry`。**基线对照**：`git stash -u` 后在无本改动状态下全量为 `Ran 35 tests / FAILED (failures=1)`，同一用例失败（InMemoryOutboxStore 用真实时间与固定 T0=2026-07-20 比较，日期相关的既有缺陷）。本改动未引入回归：18 项新增全绿，其余 34 项既有用例全部通过。该文件（`server/tests/test_platform.py`、`shared/tutor_shared/outbox.py`）在本叶子只读范围内，未修复，移交协调者。

### 3. `python -m ruff check server/course_app/course_roster server/tests/test_l01_course_roster.py server/migrations/versions/0002_course_roster.py`

（checklist 原文路径 `server/course_roster` 按勘误更正为 `server/course_app/course_roster`）

```
All checks passed!
```

### 4. `python -m py_compile`（全部 9 个新增/改动 .py）

无输出，退出码 0。

## 语义断言覆盖（对照 verification-checklist.md）

- CT-003 命中 → verified=true + course_id ✔（test_hit_returns_verified_and_course_id / test_ct003_response_fields_match_contract）
- 拒绝原因区分邀请码无效 / 名单未命中 ✔（test_invalid_invite_code_reason / test_roster_miss_reason）
- 每次调用重新直读、名单变更后下一次即生效 ✔（test_rereads_current_roster_no_cache）
- 每次调用独立 VerificationRecord（invite_code/student_name/group_name/verified/reason?/verified_at），相同要素重复调用仍逐条 ✔（test_each_call_writes_independent_record）
- 名单查询异常 → ROSTER_UNAVAILABLE，不暴露内部细节，且不产生通过/拒绝记录（R2）✔（test_roster_unavailable_no_record_no_internals / test_ct003_store_failure_maps_roster_unavailable）
- CT-013 去重（姓名+小组）、逐项格式错误报告、conflicts[]、部分成功可见、重复导入幂等 ✔（test_import_dedup_conflicts_partial_success / test_reimport_is_idempotent / test_ct013_response_fields_match_contract）
- router 应答必填字段与 contracts/ct-003.json、ct-013.json 一致（required 齐备、additionalProperties 不越界）✔
- CP-COURSE-ENDTIME 只读端口返回 course_end_time，未找到返回 None ✔
- 运维预置 CLI 可运行、幂等、P1 冲突拒绝 ✔
- 迁移可导入、revision/down_revision 正确 ✔
- LCD-003：校验记录不含 submission_id（列集合断言）✔

## 契约影响

**无**。未修改 contracts/、shared/、course_app 其他文件、既有迁移、兄弟目录；未新增/修改任何契约；无事件发布/订阅；FLOW-011 保持模块内只读端口。CT-003/CT-013 应答字段经测试与冻结 JSON 比对一致。

## 风险 / 注记（非阻塞）

1. **CT-003 邀请码无效时 course_id 取值**：契约 response 将 `course_id` 列为 required 且 minLength 1，但「邀请码无效」情形下无课程可解析；父包运行流 R1 的拒绝应答为 `verified=false+reason`。实现按 checklist（未命中 → verified=false + reason）返回 `course_id: ""` + `reason=INVALID_INVITE_CODE`（VerificationRecord 中 course_id 存 NULL）。字段存在性保持与契约一致；若集成门对拒绝路径做 minLength 强校验，需父层澄清（候选 contract-change-request 事项，当前未触发）。
2. **CT-013 教师会话鉴权（AUTH_INVALID/FORBIDDEN + AccessDeniedLogged）未实现**：属 DU-2 平台面（KD-005，设计 delegated 至部署/详细设计），router 由集成方挂载时以依赖注入接入。本叶子实现 NOT_FOUND 映射与全部导入语义。
3. **既有失败**：`test_platform.TestOutbox.test_full_cycle_with_retry` 基线即失败（日期相关），与本叶子无关，超出可写范围，见上。
4. 迁移为多头中的一头（down_revision=0001_baseline），由协调者集成时按 run 约定合并。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD` 输出（9 行，与允许路径逐一比对）：

```
server/course_app/course_roster/__init__.py      ✔ allowed
server/course_app/course_roster/admin.py         ✔ allowed
server/course_app/course_roster/api.py           ✔ allowed
server/course_app/course_roster/cli.py           ✔ allowed
server/course_app/course_roster/errors.py        ✔ allowed
server/course_app/course_roster/models.py        ✔ allowed
server/course_app/course_roster/verifier.py      ✔ allowed
server/migrations/versions/0002_course_roster.py ✔ allowed
server/tests/test_l01_course_roster.py           ✔ allowed
```

无越界改动；未批准任何 gate；未安装依赖；未修改 tutor 设计包。
