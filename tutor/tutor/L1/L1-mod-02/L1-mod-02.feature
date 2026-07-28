Feature: MOD-02 submission-intake 提交采集与接收
  This feature renders only frozen, evidence-backed test conditions from requirement-model.yaml.

  # SC-001
  @REQ-D001 @TC-001
  Scenario: 每次提交采集完整 Codex 对话
    Given 提交任务包含身份、作业和目录配置
    When 插件上传当前作业项目相关的完整 Codex 对话及材料包
    Then 服务器采集该完整 Codex 对话，提交详情可列出对话

  # SC-002
  @REQ-D002 @TC-002
  Scenario: 按插件配置收集材料并关联作业姓名小组
    Given 提交任务包含身份、作业和目录配置，且插件配置要求收集代码、截图和项目结果文件
    When 插件上传对话及材料包
    Then 服务器按插件配置收集代码、截图和项目结果文件，并将其关联到作业、姓名和小组，提交详情可列出代码、截图、结果及缺失项

  # SC-003
  @REQ-D003 @TC-003
  Scenario: 上传成功返回接收确认并异步评分
    Given 提交校验通过
    When 材料包上传完成
    Then 服务器返回包含提交编号和 received_at 的接收确认，并异步创建评分任务执行 Agent 评分

  # SC-004
  @REQ-D004 @TC-004
  Scenario: 材料不完整仍进入评分并标记缺失项
    Given 提交的材料不完整
    When 插件上传对话及材料包
    Then 系统允许提交进入评分，并在教师端标记缺失项，提交详情可列出缺失项

  # SC-005
  @REQ-D004 @TC-005
  Scenario: 空材料目录边界：进入评分并标记缺失
    Given 提交的材料目录存在但为空
    When 插件上传对话及材料包
    Then 提交进入评分并明确标记该材料缺失

  # SC-006
  @REQ-D005 @TC-006
  Scenario: 服务器保存材料并执行身份校验
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 服务器保存材料并执行课程邀请码、姓名和小组校验

  # SC-007
  @REQ-D006 @TC-007
  Scenario: 校验通过状态进入 processing
    Given 服务器已对提交执行课程邀请码、姓名和小组校验且校验通过
    When 服务器完成校验
    Then 提交状态进入 processing

  # SC-008
  @REQ-D007 @TC-008
  Scenario: 校验失败状态 rejected 且记录原因
    Given 服务器已对提交执行课程邀请码、姓名和小组校验且校验失败
    When 服务器完成校验
    Then 提交状态为 rejected 且记录原因

  # SC-009
  @REQ-D008 @TC-009
  Scenario: 上传中断状态 upload_failed 且教师端可见原因
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包过程中上传中断
    Then 提交状态为 upload_failed，教师端可见失败原因

  # SC-010
  @REQ-D009 @TC-010
  Scenario: 提交状态序列可观察
    Given 提交校验通过且材料包上传完成
    When 系统处理该提交
    Then 状态依次可观察为 received、processing、scored 或 scoring_failed

  # SC-011
  @REQ-D010 @TC-011
  Scenario: 并发 30 提交仍生成独立编号和状态
    Given 并发提交达到至少 30 个
    When 系统接收并处理这些并发提交
    Then 仍为每个任务生成独立编号和状态

  # SC-012
  @REQ-D011 @TC-012
  Scenario: Agent 重试后仍失败标记 scoring_failed 并通知教师
    Given 提交的异步评分任务已创建且 Agent 首次执行失败
    When 系统自动重试一次且再次失败
    Then 标记 scoring_failed 并通知教师

  # SC-013
  @MET-SM001 @TC-013
  Scenario: 提交接收成功率不低于 95%
    Given 按课程期间全部有效提交作为统计总体
    When 测量其中成功返回接收确认的提交比例
    Then 提交接收成功率 >= 95%

  # SC-COMP-001
  @COMP-001 @REQ-D003 @REQ-D005 @REQ-D006 @REQ-D009
  Scenario: 成功提交旅程：保存校验、接收确认与状态可观察
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 服务器保存材料并执行课程邀请码、姓名和小组校验
    When 服务器完成校验且校验通过
    Then 提交状态进入 processing
    When 材料包上传完成
    Then 服务器返回包含提交编号和 received_at 的接收确认，并异步创建评分任务执行 Agent 评分
    Then 状态依次可观察为 received、processing、scored 或 scoring_failed

  # SC-COMP-002
  @COMP-002 @REQ-D003 @REQ-D011
  Scenario: 评分失败旅程：Agent 重试后标记 scoring_failed 并通知教师
    Given 提交校验通过
    When 材料包上传完成
    Then 服务器返回包含提交编号和 received_at 的接收确认，并异步创建评分任务执行 Agent 评分
    When Agent 首次执行失败后系统自动重试一次且再次失败
    Then 标记 scoring_failed 并通知教师
