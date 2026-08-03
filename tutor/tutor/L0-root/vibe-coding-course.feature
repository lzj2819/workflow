Feature: Vibe coding course submission and assessment

  # SC-001
  @TC-001 @REQ-001
  Scenario: Submit an assignment instruction
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 返回唯一提交编号；服务器记录作业、姓名和小组。

  # SC-002
  @TC-002 @REQ-002
  Scenario: Save course configuration
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 配置重新打开后值一致。

  # SC-003
  @TC-003 @REQ-003
  Scenario: Upload conversation material
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出当前作业项目相关的完整Codex对话。

  # SC-004
  @TC-004 @REQ-004
  Scenario: Upload project materials
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出代码、截图和项目结果，且材料关联到作业、姓名和小组。

  # SC-005
  @TC-005 @REQ-005
  Scenario: Process a validated submission
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 校验通过后状态进入processing。

  # SC-006
  @TC-006 @REQ-006
  Scenario: Revalidate a modified identity on a new submission
    Given 学生已有一次提交记录，且插件设置中的姓名或小组信息已被修改
    When 学生再次发起提交并上传材料包
    Then 本次提交存在独立的校验时间或校验记录；当前身份有效时进入processing；当前姓名或小组无效时即使上一次提交有效，本次提交仍进入rejected并记录具体原因。

  # SC-007
  @TC-007 @REQ-007
  Scenario: Confirm material receipt
    Given 提交校验通过
    When 材料包上传完成
    Then 接收确认包含提交编号和received_at。

  # SC-008
  @TC-008 @REQ-008
  Scenario: Assess a submission
    Given 提交状态为processing且材料可读取
    When Agent开始独立评估
    Then 结果包含等级、每个维度文字依据、建议和评分时间。

  # SC-009
  @TC-009 @REQ-009
  Scenario: Preserve grade history
    Given 教师已登录并具有课程查看权限
    When 教师打开课程、小组或学生提交详情
    Then 系统同时保留原始等级、最终等级、操作者和时间。

  # SC-010
  @TC-010 @REQ-010
  Scenario: Generate a group presentation view
    Given 课程中至少存在一个小组提交
    When 教师选择一个或多个小组并生成展示视图
    Then 展示视图中的小组与所选小组一致；视图可在教师网页端打开。

  # SC-011
  @TC-011 @REQ-011
  Scenario: Assess incomplete materials
    Given 材料目录存在但为空
    When 提交
    Then 材料不完整时仍生成结果，并列出缺失材料对评估的影响。

  # SC-012
  @TC-012 @REQ-012
  Scenario: Retry failed assessment
    Given Agent首次失败
    When Agent首次失败
    Then 首次失败后自动重试一次；再次失败标记scoring_failed并通知教师。

  # SC-013
  @TC-013 @NFR-001
  Scenario: Handle target scale data
    Given 单门课程配置
    When 压力测试请求
    Then 目标规模数据可正常创建、查询和展示；失败则不通过。

  # SC-014
  @TC-014 @NFR-002
  Scenario: Meet concurrent submission success rate
    Given 30名学生同时发起提交请求，持续5分钟
    When 并发测试开始发起提交请求
    Then 窗口内成功接收并返回提交编号的请求数/有效提交请求总数>=95%。

  # SC-015
  @TC-015 @NFR-003
  Scenario: Meet upload and scoring time limits
    Given 课程运行期间全部有效提交
    When 有效提交上传开始
    Then 满足时限的提交数/有效提交总数>=95%，上传确认和评分完成均需满足。

  # SC-016
  @TC-016 @NFR-004
  Scenario: Delete expired records
    Given 课程结束时仍在保存期内的全部提交材料和评分记录
    When 课程结束后1年的到期处理
    Then 全部目标记录不可被教师端读取，并存在包含记录范围、操作者和时间的删除审计记录。
