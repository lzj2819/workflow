# plugin — DU-1 MOD-01 codex-plugin（Phase 1 骨架）

边界（TD-01，用户指令）：

- 本目录当前只包含 **host adapter 边界、核心端口（IC-M01-01..05 类型）、配置校验与测试骨架**。
- **不得虚构 Codex 宿主对话导出 API**：`src/host/dialogue-export-port.js` 只定义我们需要的端口形状与失败可观测；真实宿主适配待 TD-01 确认后在 L07 实现。
- 不得读取未授权的 Codex 日志或会话文件。
- 7 个叶子（L04~L07、L10、L11、L13）的实现目录在 Wave 1/2 由任务包创建。
