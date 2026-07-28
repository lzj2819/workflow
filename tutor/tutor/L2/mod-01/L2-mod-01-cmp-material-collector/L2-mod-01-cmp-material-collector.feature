Feature: CMP-MATERIAL-COLLECTOR 验收测试

  # SC-001
  @TC-001 @REQ-DD004
  Scenario: 服务器保存材料并执行课程邀请码、姓名和小组校验
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 服务器保存材料并执行课程邀请码、姓名和小组校验

  # SC-002
  @TC-002 @REQ-DD004
  Scenario: 提交详情可列出对话、代码、截图、结果及缺失项
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出对话、代码、截图、结果及缺失项

  # SC-003
  @TC-003 @REQ-DD004
  Scenario: 校验通过后状态进入 processing
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 校验通过后状态进入 processing

  # SC-004
  @TC-004 @REQ-DD004
  Scenario: 校验失败时状态为 rejected 且记录原因
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 校验失败时状态为 rejected 且记录原因

  # SC-005
  @TC-005 @REQ-DD004
  Scenario: 提交进入评分并明确标记该材料缺失
    Given 提交任务包含身份、作业和目录配置；材料目录存在但为空
    When 插件上传对话及材料包
    Then 提交进入评分并明确标记该材料缺失

  # SC-006
  @TC-006 @REQ-DD004
  Scenario: 提交状态为 upload_failed，教师端可见失败原因
    Given 提交任务包含身份、作业和目录配置；上传中断
    When 插件上传对话及材料包
    Then 提交状态为 upload_failed，教师端可见失败原因
