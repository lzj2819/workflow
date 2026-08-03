# PRD-to-Architecture 全面重构报告

日期：2026-08-02

## 1. 审计范围

重构前完整读取 `prd-to-artecture-skill` 的 21 个项目自有文件，共 82,019 字节；当时全部为 Markdown/YAML 说明，没有 generator、canonical model、JSON Schema、validator 或测试。另以只读方式核对 canonical PRD v3、PRD Derive parser、Mocktest manifest/Markdown/JSON parser、Leaf Gate structured contract、Gherkin 边界和 Vibe `module-result` Schema。

## 2. 原设计中合理并保留的内容

- 顶层和递归细分确实是不同 authority scope，不能混成一个模糊提示词；
- 父 Architecture 对 Decompose 是绑定合同，不是背景材料；
- Decompose 每次只选一个父节点，不得重画父/兄弟边界；
- 需要改变父公共契约、状态所有权、技术或部署时必须回到父层批准并停止；
- 架构决策要区分当前必须决定、可下放和必须返父；
- 接口契约需要 provider/consumer、协议、Schema、side effects、依赖、错误/超时/重试、幂等和版本。

这些原则已从散落 prose 迁入 `authority_scope`、`parent_binding`、immutable snapshot、fingerprint、change request、decision enum 和 semantic validator。

## 3. 发现的不合理、重复与冲突

| 问题 | 风险 | 重构结果 |
|---|---|---|
| Top-Level 输出七份 Markdown，Decompose 又输出另一套七份 Markdown | 同一概念两套文件名、章节和交接方式，无法稳定串联 | 两种模式共享一个 `architecture/v2` JSON 和同一五件 bundle |
| 顶层输出没有强制稳定 Module ID，递归却要求 exact `target_node_id` | 第一层生成后无法无歧义进入下一层 | Top-Level 直接子节点强制 `MOD-*`；Decompose exact ID fail-closed |
| workbench、最终 Markdown、handoff 和 manifest 重复保存同一事实 | 人工改动后产生多权威漂移 | `architecture.json` 成为唯一机器权威，所有视图单向生成 |
| 英文/中文 Skill 与六组双语 reference 重复规则，细节不一致 | 更新一份后另一份继续生效 | 删除重复 reference 体系，只保留根合同和两个兼容入口 |
| 规范只描述“应该检查”，没有可执行 Schema/validator/test | 每次模型可自由改字段、漏章节 | 新增 JSON Schema、跨字段 validator、consumer profiles 和 9 个合同测试 |
| status、human gate、parent change 没有统一转换表 | draft/ready/PASS 可互相矛盾 | 固定 `PASS+approved+ready` 与 `FAIL+draft+not-ready` 语义 |
| 父边界靠 prose 记忆，无法证明生成期间没有变化 | 递归结果可能基于过期父包 | 固定 immutable snapshot + SHA-256 `boundary_fingerprint` 并重验 |
| 顶层 Skill 的 `agents/openai.yaml` 是非法 UTF-8 mojibake | UI/agent 配置不可可靠读取 | 以有效 UTF-8 重建 |
| 原输出与 PRD Derive、Mocktest、Leaf 的真实 parser 字段不完全对齐 | “看起来可交接”，真实工具却读不到 | 增加 `modules`、Leaf 六字段投影和兼容节点表头，并运行真实 parser/Gate 测试 |
| 把 Gherkin 当成 Architecture 下游容易误导 | 产生不存在的串行依赖 | 明确 Architecture 与 Gherkin 是 PRD 的并行分支 |

## 4. 统一后的 Architecture 合同

两种模式始终拥有相同顶层键、相同 `payload` 键、相同数组元素字段、相同默认空值、相同 ID/enum 和相同 12 节 Markdown 顺序。只有以下内容随模式改变：

- `architecture_mode`；
- 固定的 `authority_scope`；
- Decompose 必需而 Top-Level 禁止的 `parent_binding`；
- 合法直接子节点类型；
- 具体业务内容。

固定 PASS bundle：

```text
architecture.json
architecture.md
architecture-manifest.yaml
validation_report.json
execution_log.json
```

Decompose 父变更阻塞包仅允许多出 `parent-change-request.md`。

## 5. 两种模式的明确边界

### Top-Level

输入根级 approved canonical PRD v3；输出系统边界和第一层 `MOD-*` 模块。它可以定义跨模块契约、系统级数据所有权、技术和部署，但不能进入模块内部组件设计。

### Decompose

输入当前节点 PRD、approved 父 Architecture、exact `target_node_id`。它只定义该节点内部 `CMP-*`/`SUB-*`/`ADP-*`、内部契约和局部状态实现；不能重新生成 `MOD-*`，不能修改父公共边界或兄弟节点。

## 6. 下游兼容事实

- PRD Derive：直接读取 `architecture.json` 的 `modules` 投影，真实 parser 已通过；
- Mocktest：真实 `ArchDocParser` 已从固定 Markdown 节点表提取稳定 `MOD-ORDER`；
- Leaf Gate：用生成的 `architecture.json` 与真实脚本完成 structured contract 运行；
- Gherkin：记录为并行 PRD consumer，不伪造直接 Architecture contract；
- Vibe：Architecture 只提供 hashed bundle，`module-result.json` 仍由 command adapter 生成。

## 7. 验证证据

在已有 Anaconda Python（包含项目下游依赖）执行：

```powershell
E:\anaconda\ANACONDA\python.exe -m compileall -q scripts tests
E:\anaconda\ANACONDA\python.exe -m unittest discover -s tests -v
```

结果：10/10 PASS。覆盖不同业务内容同结构、输入重排同 canonical bytes、Schema/语义/profile、固定 bundle、故障变异 fail-closed、CLI 双模式同形状、Top→Module→Component 递归与祖先契约继承、父不可变性、PRD Derive、Mocktest parser、Leaf Gate 和 parent change stop。

这属于 producer contract 与真实相邻消费者兼容验证，不等于完成一次 Mocktest strict 业务验证、Leaf 的特定产品结论或整条生产 E2E。
