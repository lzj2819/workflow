Feature: CMP-SCORING-ORCHESTRATOR 验收测试

  # SC-001
  @TC-001 @REQ-DD002
  Scenario: 生成 A–E 等级、五个维度依据和教师专用改进建议
    Given 提交状态为 processing 且材料可读取
    When Agent 开始独立评估
    Then 生成 A–E 等级、五个维度依据和教师专用改进建议

  # SC-002
  @TC-002 @REQ-DD002
  Scenario: 结果包含等级、每个维度文字依据、建议和评分时间
    Given 提交状态为 processing 且材料可读取
    When Agent 开始独立评估
    Then 结果包含等级、每个维度文字依据、建议和评分时间

  # SC-003
  @TC-003 @REQ-DD002
  Scenario: 建议默认不暴露给学生
    Given 提交状态为 processing 且材料可读取
    When Agent 开始独立评估
    Then 建议默认不暴露给学生

  # SC-004
  @TC-004 @REQ-DD002
  Scenario: 仍生成结果，并列出缺失材料对评估的影响
    Given 提交状态为 processing 且材料可读取；材料不完整
    When Agent 开始独立评估
    Then 仍生成结果，并列出缺失材料对评估的影响
