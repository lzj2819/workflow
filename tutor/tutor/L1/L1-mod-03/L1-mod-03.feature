Feature: MOD-03 课程归属校验（course-roster）
  本 Feature 仅渲染 requirement-model.yaml 中冻结的、证据充分的 Test Conditions。
  冻结范围：FULL；阻塞 IR：0；本产物非部分产物。

  # SC-001
  @REQ-D001 @TC-001
  Scenario: 上传材料包后保存材料并执行课程归属校验
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 服务器保存材料并执行课程邀请码、姓名和小组校验，提交详情可列出对话、代码、截图、结果及缺失项

  # SC-002
  @REQ-D001 @TC-002
  Scenario: 校验通过后提交进入 processing
    Given 提交任务包含身份、作业和目录配置，且课程邀请码、姓名和小组校验通过
    When 插件上传对话及材料包，服务器执行课程邀请码、姓名和小组校验
    Then 校验通过后提交状态进入 processing

  # SC-003
  @REQ-D001 @TC-003
  Scenario: 校验失败时提交为 rejected 并记录原因
    Given 提交任务包含身份、作业和目录配置，且课程邀请码、姓名或小组校验失败
    When 插件上传对话及材料包，服务器执行课程邀请码、姓名和小组校验
    Then 校验失败时提交状态为 rejected 且记录原因

  # SC-004
  @REQ-D001 @TC-004
  Scenario: 材料目录存在但为空时提交进入评分并标记材料缺失
    Given 提交任务包含身份、作业和目录配置，且材料目录存在但为空
    When 插件上传对话及材料包
    Then 提交进入评分并明确标记该材料缺失

  # SC-005
  @REQ-D001 @TC-005
  Scenario: 上传中断时提交状态为 upload_failed 且教师端可见失败原因
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包的过程中上传中断
    Then 提交状态为 upload_failed，教师端可见失败原因

  # SC-006
  @REQ-D002 @TC-006
  Scenario Outline: 修改姓名或小组后再次提交触发本次重新校验
    Given 学生已有一次提交记录，且本次修改情况为<修改情况>，新的提交包含课程邀请码、当前姓名和当前小组
    When 学生再次发起提交并上传材料包
    Then 本次提交触发重新校验，且本次提交存在独立的校验时间/校验记录

    Examples:
      | 修改情况       |
      | 仅修改姓名     |
      | 仅修改小组     |
      | 修改姓名和小组 |

  # SC-007
  @REQ-D002 @TC-007
  Scenario: 当前身份有效时再次提交进入 processing
    Given 学生已有一次提交记录，插件设置中的姓名或小组信息已被修改，新的提交包含课程邀请码、当前姓名和当前小组，且当前身份有效
    When 学生再次发起提交并上传材料包
    Then 本次提交进入 processing

  # SC-008
  @REQ-D002 @TC-008
  Scenario: 当前姓名或小组无效时即使上一次提交有效本次仍 rejected
    Given 学生已有一次提交记录且上一次提交有效，插件设置中的姓名或小组信息已被修改，新的提交包含课程邀请码、当前姓名和当前小组，且当前姓名或小组无效
    When 学生再次发起提交并上传材料包
    Then 本次提交仍进入 rejected 并记录具体原因

  # SC-009
  @REQ-D002 @TC-009
  Scenario: 课程名单服务不可用时进入 identity_validation_failed
    Given 学生已有一次提交记录，插件设置中的姓名或小组信息已被修改，新的提交包含课程邀请码、当前姓名和当前小组，且课程名单服务不可用
    When 学生再次发起提交并上传材料包
    Then 本次提交不复用旧校验结果，进入 identity_validation_failed 并记录可重试原因

  # SC-010
  @COMP-001 @REQ-D001 @REQ-D002
  Scenario: 首次提交校验通过后修改身份信息再次提交仍独立校验
    Given 提交任务包含身份、作业和目录配置，且课程邀请码、姓名和小组校验通过
    When 插件上传对话及材料包，服务器执行课程邀请码、姓名和小组校验
    Then 校验通过后提交状态进入 processing
    Given 学生已有一次提交记录，插件设置中的姓名或小组信息已被修改，新的提交包含课程邀请码、当前姓名和当前小组，且当前身份有效
    When 学生再次发起提交并上传材料包
    Then 本次提交进入 processing
