# D-5 供应商合规调研备忘录（只读调研；不接入、不发送真实数据）

- 日期：2026-07-22；编制：Integration Owner；来源：公开官方资料（见文末 Sources）
- 用途：支持「真实模型供应商接入」决策（DD-009）。**本备忘录不构成接入；任何接入仍需用户逐项批准（决策包 D-5 八项清单）。**

## 1. 候选供应商合规对比（API/企业面）

| 维度 | Anthropic（Claude API） | OpenAI（API） | 阿里云百炼（通义千问） | DeepSeek（API） |
|---|---|---|---|---|
| API 数据用于训练 | **不用于训练（默认，无需退出）** | **不用于训练（默认）** | **官方承诺绝不用于模型训练** | **默认可能用于训练**（去标识化前提下；产品内可关闭「数据用于优化体验」） |
| 默认保留 | 7 天（2025-09 起，自 30 天降）；30 天可选（DPA） | ≤30 天（滥用监测日志，自动删除） | 依《百炼服务协议》存储调用数据（期限以协议为准；控制台历史 ≤100 条） | 删除后 48h 内全节点擦除；第三方称日志 ~90 天、备份 ~180 天 |
| 零保留（ZDR） | 符合条件的企业可协商（注意：Fable 5/Mythos 级强制 30 天安全保留，ZDR 被覆盖） | 审批制 ZDR（store=false 强制） | 无 ZDR 概念；可用专属版物理隔离替代 | 未见公开 ZDR |
| DPA/企业协议 | DPA、HIPAA BAA、SOC 2、GDPR SCC | DPA（Team/Enterprise/API；不含消费者） | SOC 2 无保留意见；专属 VPC/专属版（金融/医疗/政务，核心数据不出机房） | **未见公开企业 DPA**（隐私政策统一适用，不区分企业/个人） |
| 数据地域 | 美国（可经 Bedrock/Vertex/Foundry） | 美国（可经 Azure OpenAI 区域化） | 可选北京/新加坡/法兰克福/东京/弗吉尼亚；**国内地域满足数据不出境** | 境内存储，官方称不向境外传输 |
| 教育/敏感场景适配 | Claude for Education（不训练）；Gov 版 | ChatGPT Edu（默认不训练） | 专属版面向高合规行业 | 无专门教育版；敏感场景建议本地部署或签 DPA（不可得） |

## 2. 对本产品（高校课堂、学生材料出境）的合规解读

1. **数据出境红线**：学生材料（对话/代码）发送境外供应商属数据出境。若学校/法规要求境内处理，**仅阿里云百炼（国内地域）与 DeepSeek（境内存储）满足**；Anthropic/OpenAI 需校方书面批准且建议经云区域化服务（Bedrock/Azure）并签 DPA。
2. **训练用途**：DeepSeek 的默认训练许可与「学生材料最小化」原则冲突——若选 DeepSeek 必须先确认关闭路径在 API 侧可用且可审计，否则排除。其余三家 API 面默认不训练。
3. **ZDR/短保留**：OpenAI（审批制 ZDR）与 Anthropic（7 天默认/30 天 DPA）为最短保留；但 Fable 5 级模型强制 30 天安全保留，ZDR 承诺存在被覆盖风险（需条款锁定模型版本）。
4. **物理隔离替代**：阿里云专属版提供 100% 物理隔离（数据不出机房）——对高校合规叙事最强，成本与运维负担需评估。
5. **司法辖区风险**：OpenAI 曾被法院命令产出日志（2026-01，去标识化）；任何供应商的保留承诺均可被司法要求覆盖——材料最小化（KD-001）是我们的根本防线，已代码强制。

## 3. 建议（供用户决策，非结论）

- **首选评估路径**：阿里云百炼（国内地域 + 不训练承诺 + 专属版升级路径），与中国高校数据合规叙事最匹配；
- **次选**：OpenAI API + 审批制 ZDR（若校方接受境外处理且签 DPA）；
- **谨慎/暂缓**：DeepSeek（默认训练许可 + 无公开企业 DPA，除非其企业侧给出书面不训练承诺）；
- Anthropic 可列为备选（7 天保留 + 教育版），但同样属境外处理。
- 任何接入前置：决策包 D-5 八项（选择/DPA、最小化、学生授权、密钥、保留、审计、回退、强制超时层）逐项签字；rubric 样例回归（LCD-005）通过后才放量。

## Sources

- [Anthropic Privacy Center — How long do you store my data](https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data)
- [Fable 5 Ends Zero-Data-Retention for Enterprise (ClaudeAI News)](https://www.claudeainews.com/news/anthropic-fable-5-data-retention-enterprise.html)
- [Anthropic Data Retention Policy 2026 (Anarlog)](https://anarlog.so/blog/anthropic-data-retention-policy)
- [OpenAI — Data controls in the OpenAI platform](https://developers.openai.com/api/docs/guides/your-data)
- [OpenAI — Response to NYT data demands](https://openai.com/index/response-to-nyt-data-demands/)
- [ChatGPT Data Retention Policy (Anarlog)](https://anarlog.so/blog/chatgpt-data-retention-policy)
- [OpenAI DPA 示例（audiodiary.ai 镜像）](https://www.audiodiary.ai/OpenAI-dpa.pdf)
- [DeepSeek 隐私政策（官方）](https://cdn.deepseek.com/policies/zh-CN/deepseek-privacy-policy.html)
- [DeepSeek 用户协议（官方）](https://cdn.deepseek.com/policies/zh-CN/deepseek-terms-of-use.html)
- [DeepSeek 模型原理与训练方法说明（官方）](https://cdn.deepseek.com/policies/zh-CN/model-algorithm-disclosure.html)
- [阿里云百炼 — 合规资质与隐私说明（官方）](https://help.aliyun.com/zh/model-studio/privacy-notice)
- [阿里云百炼 — 产品介绍（官方）](https://help.aliyun.com/zh/model-studio/what-is-model-studio)
- [Azure OpenAI Data Retention（Microsoft Q&A）](https://learn.microsoft.com/en-us/answers/questions/2181252/azure-openai-data-retention-privacy-2025)
- [Anthropic vs OpenAI ZDR 对比（Digital Applied）](https://www.digitalapplied.com/blog/fable-5-30-day-data-retention-zdr-enterprise-2026)

---

## 附：供应商接入决策（2026-07-25，用户批准）

| 决策项 | 值 |
|---|---|
| 供应商 | **deepseek**（唯一批准；其他供应商接入需另行批准） |
| 允许外发数据 | 经 CT-010/KD-001 最小化处理后的对话、代码、材料文本（三桶：dialogue_summary / code / result_description）；业务标识（submission_id/姓名/小组/邀请码/课程）代码级拦截，绝不外发 |
| 数据地域与合规 | 协调者自主决定：**api.deepseek.com 境内服务**，学生数据不出境，符合教育数据合规口径；模型版本默认 `deepseek-chat`（可经 `DEEPSEEK_MODEL` 调整） |
| 密钥管理 | `.env` 文件（compose `env_file` 注入 `MODEL_API_KEY`）；.env 不入库；密钥不出现在任何日志/审计/应答 |
| 发布范围 | 内部试用、灰度（非正式发布） |
| 降级策略 | 供应商不可用 → **无自动评分/稍后重试**：`VENDOR_ENABLED=0` kill switch（停止认领，任务保持 pending）；连续失败熔断（`VENDOR_CIRCUIT_THRESHOLD` 次 MODEL_TIMEOUT/MODEL_ERROR → 冷却 `VENDOR_CIRCUIT_COOLDOWN_SECONDS`，期间不认领，冷却后半开自动恢复）；均不终态化任务、不耗 REQ-012 业务重试预算 |

实施与验证：见 `vendor-integration-report.md`。
