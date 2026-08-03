Feature: CMP-CONFIG-STORE 验收测试

  # SC-001
  @TC-001 @REQ-DD002
  Scenario: 插件保存配置并在下次提交时使用
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 插件保存配置并在下次提交时使用

  # SC-002
  @TC-002 @REQ-DD002
  Scenario: 配置重新打开后值一致
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 配置重新打开后值一致

  # SC-003
  @TC-003 @REQ-DD002
  Scenario: 目录不可读时显示具体目录错误
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 目录不可读时显示具体目录错误

  # SC-004
  @TC-004 @REQ-DD002
  Scenario: 配置保存为不完整并列出缺失项
    Given 插件设置页可用；任一目录为空
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 配置保存为不完整并列出缺失项

  # SC-005
  @TC-005 @REQ-DD002
  Scenario: 拒绝保存并保留上一次有效配置
    Given 插件设置页可用；配置格式无效
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 拒绝保存并保留上一次有效配置
