Feature: CMP-UPLOAD-CLIENT 验收测试

  # SC-001
  @TC-001 @REQ-DD001
  Scenario: 插件创建提交任务并将身份、作业和配置目录提交到服务器
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 插件创建提交任务并将身份、作业和配置目录提交到服务器

  # SC-002
  @TC-002 @REQ-DD001
  Scenario: 返回唯一提交编号
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 返回唯一提交编号

  # SC-003
  @TC-003 @REQ-DD001
  Scenario: 服务器记录作业、姓名和小组
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 服务器记录作业、姓名和小组

  # SC-004
  @TC-004 @REQ-DD001
  Scenario: 未包含任一必填信息时不创建可评分提交
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 未包含任一必填信息时不创建可评分提交

  # SC-005
  @TC-005 @REQ-DD001
  Scenario: 返回具体缺失字段并保持提交状态为信息不完整
    Given 插件已绑定课程且配置可读取；缺少作业、姓名或小组
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 返回具体缺失字段并保持提交状态为信息不完整

  # SC-006
  @TC-006 @REQ-DD001
  Scenario: 保留本地待上传任务并显示失败原因
    Given 插件已绑定课程且配置可读取；插件无法连接服务器
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 保留本地待上传任务并显示失败原因

  # SC-007
  @TC-007 @REQ-DD003
  Scenario: 服务器保存材料并执行课程邀请码、姓名和小组校验
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 服务器保存材料并执行课程邀请码、姓名和小组校验

  # SC-008
  @TC-008 @REQ-DD003
  Scenario: 提交详情可列出对话、代码、截图、结果及缺失项
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出对话、代码、截图、结果及缺失项

  # SC-009
  @TC-009 @REQ-DD003
  Scenario: 校验通过后状态进入 processing
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 校验通过后状态进入 processing

  # SC-010
  @TC-010 @REQ-DD003
  Scenario: 校验失败时状态为 rejected 且记录原因
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 校验失败时状态为 rejected 且记录原因

  # SC-011
  @TC-011 @REQ-DD003
  Scenario: 提交进入评分并明确标记该材料缺失
    Given 提交任务包含身份、作业和目录配置；材料目录存在但为空
    When 插件上传对话及材料包
    Then 提交进入评分并明确标记该材料缺失

  # SC-012
  @TC-012 @REQ-DD003
  Scenario: 提交状态为 upload_failed，教师端可见失败原因
    Given 提交任务包含身份、作业和目录配置；上传中断
    When 插件上传对话及材料包
    Then 提交状态为 upload_failed，教师端可见失败原因
