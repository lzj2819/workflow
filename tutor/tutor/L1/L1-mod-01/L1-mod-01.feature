Feature: MOD-01 插件提交意图识别、配置与材料采集

  # SC-001
  @TC-001 @REQ-D001
  Scenario: 识别完整提交意图并创建提交任务
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 返回唯一提交编号；服务器记录作业、姓名和小组。

  # SC-002
  @TC-002 @REQ-D001
  Scenario Outline: 缺少任一必填信息时不创建可评分提交
    Given 插件已绑定课程且配置可读取
    When 学生发送缺少<missing_item>的自然语言提交指令
    Then 返回具体缺失字段<missing_item>并保持提交状态为信息不完整，不创建可评分提交

    Examples:
    | missing_item |
    | 作业 |
    | 姓名 |
    | 小组 |

  # SC-003
  @TC-003 @REQ-D001
  Scenario: 无法连接服务器时保留本地待上传任务
    Given 插件已绑定课程且配置可读取
    When 学生发送包含作业、姓名和小组的自然语言提交指令且插件无法连接服务器
    Then 保留本地待上传任务并显示失败原因。

  # SC-004
  @TC-004 @REQ-D002
  Scenario: 保存完整插件配置
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 配置重新打开后值一致。

  # SC-005
  @TC-005 @REQ-D002
  Scenario: 目录不可读时显示具体目录错误
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置且目录不可读
    Then 显示具体目录错误。

  # SC-006
  @TC-006 @REQ-D002
  Scenario Outline: 任一目录为空时配置保存为不完整
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和目录配置且<empty_dir>为空
    Then 配置保存为不完整并列出缺失项

    Examples:
    | empty_dir |
    | 代码目录 |
    | 截图目录 |
    | 项目结果目录 |

  # SC-007
  @TC-007 @REQ-D002
  Scenario: 配置格式无效时拒绝保存
    Given 插件设置页可用
    When 学生保存配置且配置格式无效
    Then 拒绝保存并保留上一次有效配置。

  # SC-008
  @TC-008 @REQ-D003
  Scenario: 提交详情列出完整Codex对话
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出当前作业项目相关的完整Codex对话。

  # SC-009
  @TC-009 @REQ-D003
  Scenario: 校验通过后提交进入processing
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包且课程邀请码、姓名和小组校验通过
    Then 校验通过后状态进入processing。

  # SC-010
  @TC-010 @REQ-D003
  Scenario: 校验失败时提交状态为rejected
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包且课程邀请码、姓名和小组校验失败
    Then 状态为rejected且记录原因。

  # SC-011
  @TC-011 @REQ-D004
  Scenario: 提交详情列出材料并关联身份信息
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包
    Then 提交详情可列出代码、截图、结果及缺失项，材料关联到作业、姓名和小组。

  # SC-012
  @TC-012 @REQ-D004
  Scenario Outline: 材料目录存在但为空时标记材料缺失
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包且<empty_material_dir>存在但为空
    Then 提交进入评分并明确标记该材料缺失

    Examples:
    | empty_material_dir |
    | 代码目录 |
    | 截图目录 |
    | 项目结果目录 |

  # SC-013
  @TC-013 @REQ-D004
  Scenario: 上传中断时提交状态为upload_failed
    Given 提交任务包含身份、作业和目录配置
    When 插件上传对话及材料包且上传中断
    Then 提交状态为upload_failed，教师端可见失败原因。

  # SC-101
  @COMP-001 @REQ-D001 @REQ-D002 @REQ-D003
  Scenario: 从保存配置到提交校验通过的完整旅程
    Given 插件设置页可用
    When 学生保存课程邀请码、姓名、小组和三个目录配置
    Then 配置重新打开后值一致。
    When 学生发送包含作业、姓名和小组的自然语言提交指令
    Then 返回唯一提交编号；服务器记录作业、姓名和小组。
    When 插件上传对话及材料包且课程邀请码、姓名和小组校验通过
    Then 校验通过后状态进入processing。
