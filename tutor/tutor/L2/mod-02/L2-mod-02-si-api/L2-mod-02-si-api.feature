Feature: SI-API 验收测试

  # SC-001
  @TC-001 @REQ-DD003
  Scenario: 返回接收确认并异步创建评分任务
    Given 提交校验通过
    When 材料包上传完成
    Then 返回接收确认并异步创建评分任务

  # SC-002
  @TC-002 @REQ-DD003
  Scenario: 接收确认包含提交编号和 received_at
    Given 提交校验通过
    When 材料包上传完成
    Then 接收确认包含提交编号和 received_at

  # SC-003
  @TC-003 @REQ-DD003
  Scenario: 状态依次可观察为 received、processing、scored 或 scoring_failed
    Given 提交校验通过
    When 材料包上传完成
    Then 状态依次可观察为 received、processing、scored 或 scoring_failed

  # SC-004
  @TC-004 @REQ-DD003
  Scenario: 仍为每个任务生成独立编号和状态
    Given 提交校验通过；并发提交达到至少 30 个
    When 材料包上传完成
    Then 仍为每个任务生成独立编号和状态

  # SC-005
  @TC-005 @REQ-DD003
  Scenario: 再次失败标记 scoring_failed 并通知教师
    Given 提交校验通过；Agent 首次失败后自动重试一次
    When 材料包上传完成
    Then 再次失败标记 scoring_failed 并通知教师
