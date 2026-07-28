Feature: MOD-04 Agent 提交评估与评分失败恢复

  # SC-001
  @TC-001 @REQ-D001
  Scenario: Agent 对材料完整的提交生成结构化评估结果
    Given 提交状态为processing且材料可读取
    When Agent开始独立评估
    Then 结果包含A–E等级、五个维度中每个维度的文字依据、教师专用改进建议和评分时间。

  # SC-002
  @TC-002 @REQ-D001
  Scenario: 改进建议默认仅对教师可见
    Given 提交状态为processing且材料可读取
    When Agent开始独立评估
    Then 改进建议为教师专用，默认不暴露给学生。

  # SC-003
  @TC-003 @REQ-D001
  Scenario: 材料不完整时仍生成评估结果并说明影响
    Given 提交状态为processing但材料不完整
    When Agent开始独立评估
    Then 材料不完整时仍生成结果，并列出缺失材料对评估的影响。

  # SC-004
  @TC-004 @REQ-D002
  Scenario: Agent 评分失败后自动重试一次
    Given 提交状态为processing且材料可读取
    When Agent评分失败
    Then Agent评分失败后系统自动重试一次。

  # SC-005
  @TC-005 @REQ-D002
  Scenario: 重试后仍失败时标记评分失败并通知教师
    Given Agent评分失败后系统已自动重试一次
    When 重试后评分仍失败
    Then 重试后仍失败时系统标记“评分失败”并通知教师。

  # SC-006
  @TC-006 @MET-SM002
  Scenario: 评分按时完成率达到来源定义目标
    Given 课程期间全部有效提交
    When 统计10分钟内完成评分的提交比例
    Then 课程期间全部有效提交中10分钟内完成评分的比例>=95%。

  # SC-007
  @TC-007 @MET-SM003
  Scenario: 教师评分覆盖率达到来源定义目标
    Given 课程结束前全部提交
    When 统计具有Agent结果或明确失败状态的提交比例
    Then 课程结束前具有Agent结果或明确失败状态的提交比例>=95%。

  # SC-008
  @COMP-001 @REQ-D002
  Scenario: 评分失败到自动重试再到失败标记与教师通知的恢复路径
    Given 提交状态为processing且材料可读取
    When Agent评分失败
    Then Agent评分失败后系统自动重试一次。
    When 重试后评分仍失败
    Then 重试后仍失败时系统标记“评分失败”并通知教师。
