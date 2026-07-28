"""本地自动响应器

当 Skill 模式没有真正的 Claude Code 会话 attached 时（例如 CI 或批量回归），
LocalAutoResponder 可以替代文件 IPC，直接基于规则生成 simulator/validator 响应。

它主要用于：
1. 减少 Skill 模式下的 prompt 数量，避免数百次人工回答。
2. 在本地快速回归验证，捕获明显的架构/契约问题。
3. 作为 Phase 1 止血方案，修复上一版临时 auto-responder 的 task_id 和 ERROR 路径误判。

注意：这是一个启发式组件，结论置信度低于真实 LLM。关键失败应使用真实 LLM 复核。
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Any, Type, TypeVar, cast

from mock_framework.logger import get_logger
from mock_framework.models.simulator import ExecutionTrace, TraceStep
from mock_framework.models.validator import DimensionResult, FailureAnalysis
from mock_framework.simulator.llm_client import LLMClient, TokenBudgetExceeded

T = TypeVar("T")

logger = get_logger("local_auto_responder")


class LocalAutoResponder:
    """基于规则的本地 prompt 响应器"""

    # 触发 ERROR 路径的中文关键词
    ERROR_PATH_KEYWORDS = [
        "未绑定",
        "无权限",
        "拒绝",
        "不存在",
        "无效",
        "失败",
        "超时",
        "错误",
        "不支持",
        "非法",
        "越权",
        "阻断",
        "被阻断",
        "崩溃",
    ]

    # 创建/发送任务的语义
    TASK_CREATION_KEYWORDS = [
        "创建任务",
        "发送任务",
        "新建任务",
        "提交任务",
        "分配任务",
        "生成任务",
    ]

    # 查询/操作已有任务的语义
    TASK_OPERATION_KEYWORDS = [
        "查询任务",
        "取消任务",
        "暂停任务",
        "恢复任务",
        "完成任务",
        "更新任务",
        "修改任务",
        "任务状态",
        "task_id",
        "任务ID",
    ]

    def __init__(self) -> None:
        """初始化本地响应器"""
        self._logger = get_logger("LocalAutoResponder")

    async def execute_simulator_prompt(self, prompt: str, schema: Type[T]) -> dict[str, Any]:
        """执行 simulator prompt，返回符合 LLMClient 约定的 dict。"""
        step_text = self._extract_step_text(prompt)
        is_error = self._is_error_path(step_text)

        if is_error:
            result: dict[str, Any] = {
                "action": "error",
                "target": None,
                "data": {"error_code": self._infer_error_code(step_text)},
                "status": "ERROR",
                "reasoning": f"步骤 '{step_text}' 属于预期错误路径",
            }
        elif self._is_task_creation(step_text):
            result = {
                "action": "create",
                "target": "task",
                "data": {"task_id": self._generate_task_id(step_text)},
                "status": "OK",
                "reasoning": f"步骤 '{step_text}' 创建任务并返回 task_id",
            }
        elif self._is_task_operation(step_text):
            result = {
                "action": "query",
                "target": "task",
                "data": {"task_id": self._generate_task_id(step_text)},
                "status": "OK",
                "reasoning": f"步骤 '{step_text}' 操作任务并返回 task_id",
            }
        else:
            result = {
                "action": "call",
                "target": None,
                "data": {},
                "status": "OK",
                "reasoning": f"步骤 '{step_text}' 正常执行",
            }

        self._logger.debug("Simulator response: %s", result)
        return result

    async def execute_validator_prompt(self, prompt: str, schema: Type[T]) -> dict[str, Any]:
        """执行 validator prompt，返回五维验证结果。"""
        trace_summary = self._extract_trace_summary(prompt)
        gherkin_expectations = self._extract_gherkin_expectations(prompt)

        steps = trace_summary.get("steps", [])
        gherkin_steps = self._extract_gherkin_steps(gherkin_expectations)
        scenario_name = gherkin_expectations.get("source_scenario", "unknown")
        test_case_id = gherkin_expectations.get("test_case_id", "unknown")

        # 判断预期错误路径
        expects_error = any(self._is_error_path(step_text) for step_text in gherkin_steps)
        has_error_step = any(step.get("status") in ("ERROR", "FAIL") for step in steps)

        # 判断是否期望返回 task_id
        expects_task_id = any(
            self._is_task_creation(step_text) or self._is_task_operation(step_text)
            for step_text in gherkin_steps
        )
        has_task_id = self._trace_has_task_id(trace_summary)

        # 默认五维 PASS
        dimensions: dict[str, DimensionResult] = {
            "structure": DimensionResult(status="PASS", detail="结构完整"),
            "flow": DimensionResult(status="PASS", detail="流程符合预期"),
            "state": DimensionResult(status="PASS", detail="状态转换正确"),
            "contract": DimensionResult(status="PASS", detail="契约满足"),
            "performance": DimensionResult(status="PASS", detail="性能指标在阈值内"),
        }

        failure_analysis: FailureAnalysis | None = None

        if expects_error:
            if not has_error_step:
                dimensions["contract"] = DimensionResult(
                    status="FAIL",
                    detail="场景属于预期错误路径，但 simulator 未返回 ERROR 状态",
                )
            else:
                # 预期错误路径且 simulator 正确返回 ERROR，整体通过
                dimensions["contract"] = DimensionResult(
                    status="PASS",
                    detail="预期错误路径，simulator 正确返回 ERROR",
                )
        else:
            if has_error_step:
                dimensions["contract"] = DimensionResult(
                    status="FAIL",
                    detail="非错误路径场景出现 ERROR 状态",
                )

        if expects_task_id and not has_task_id:
            dimensions["contract"] = DimensionResult(
                status="FAIL",
                detail="场景期望返回 task_id，但 trace 中未找到 task_id",
            )

        overall = "PASS" if all(d.status == "PASS" for d in dimensions.values()) else "FAIL"

        if overall == "FAIL":
            failed_dim = next(d for d, r in dimensions.items() if r.status == "FAIL")
            failure_analysis = FailureAnalysis(
                dimension=failed_dim,
                problem=dimensions[failed_dim].detail,
                severity="high",
                impact=f"{scenario_name} 未通过 {failed_dim} 维度验证",
                suggestion="请检查架构文档或重新用真实 LLM 验证",
            )

        result: dict[str, Any] = {
            "structure": dimensions["structure"].model_dump(),
            "flow": dimensions["flow"].model_dump(),
            "state": dimensions["state"].model_dump(),
            "contract": dimensions["contract"].model_dump(),
            "performance": dimensions["performance"].model_dump(),
            "overall": overall,
            "failure_analysis": failure_analysis.model_dump() if failure_analysis else None,
            "warning_analysis": None,
        }

        self._logger.debug("Validator response: %s", result["overall"])
        return result

    async def execute_modifier_prompt(self, prompt: str, schema: Type[T]) -> dict[str, Any]:
        """Modifier 在本地模式下返回空建议，不实际修改文件。"""
        return {
            "modifications": [],
            "reasoning": "LocalAutoResponder 不支持自动修改",
        }

    # ------------------------------------------------------------------
    # 文本解析辅助
    # ------------------------------------------------------------------

    def _extract_step_text(self, prompt: str) -> str:
        """从 simulator prompt 中提取步骤文本。"""
        match = re.search(r"【步骤】\n(.*?)\n\n【技术映射】", prompt, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 备用：直接查找 "步骤：" 或类似前缀
        match = re.search(r"步骤[：:]\s*(.+)", prompt)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_trace_summary(self, prompt: str) -> dict[str, Any]:
        """从 validator prompt 中提取 trace_summary JSON。"""
        return self._extract_json_block(prompt, "## 1. Simulator Execution Result")

    def _extract_gherkin_expectations(self, prompt: str) -> dict[str, Any]:
        """从 validator prompt 中提取 gherkin_expectations JSON。"""
        return self._extract_json_block(prompt, "## 2. Gherkin Expected Behavior")

    def _extract_json_block(self, prompt: str, header: str) -> dict[str, Any]:
        """从 prompt 中提取指定标题后的第一个 JSON 代码块。"""
        pattern = re.escape(header) + r"\s*```json\s*([\s\S]*?)```"
        match = re.search(pattern, prompt)
        if match:
            try:
                return cast(dict[str, Any], json.loads(match.group(1).strip()))
            except json.JSONDecodeError:
                self._logger.warning("Failed to parse JSON block after %s", header)
        return {}

    def _extract_gherkin_steps(self, gherkin_expectations: dict[str, Any]) -> list[str]:
        """从 gherkin_expectations 中提取步骤文本列表。"""
        gherkin = gherkin_expectations.get("gherkin", {})
        steps = gherkin.get("steps", [])
        return [s.get("text", "") for s in steps]

    # ------------------------------------------------------------------
    # 启发式判断
    # ------------------------------------------------------------------

    def _is_error_path(self, text: str) -> bool:
        """判断步骤文本是否属于预期错误路径。"""
        return any(kw in text for kw in self.ERROR_PATH_KEYWORDS)

    def _is_task_creation(self, text: str) -> bool:
        """判断步骤是否创建/发送任务。错误路径步骤或否定步骤不视为创建任务。"""
        if self._is_error_path(text):
            return False
        # 否定语义："不创建任务"、"不发送任务" 等
        if re.search(r"不\s*创建任务|不\s*发送任务|不\s*新建任务", text):
            return False
        return any(kw in text for kw in self.TASK_CREATION_KEYWORDS)

    def _is_task_operation(self, text: str) -> bool:
        """判断步骤是否查询/操作任务。错误路径步骤不视为操作任务。"""
        if self._is_error_path(text):
            return False
        return any(kw in text for kw in self.TASK_OPERATION_KEYWORDS)

    def _infer_error_code(self, text: str) -> str:
        """根据步骤文本推断错误码。"""
        if "未绑定" in text or "未授权" in text or "无权限" in text:
            return "USER_NOT_BOUND"
        if "不存在" in text:
            return "NOT_FOUND"
        if "无效" in text or "非法" in text:
            return "INVALID_ARGUMENT"
        if "超时" in text:
            return "TIMEOUT"
        if "不支持" in text:
            return "UNSUPPORTED_OPERATION"
        return "ERROR"

    def _generate_task_id(self, step_text: str) -> str:
        """生成确定性 task_id。

        注意：由于 simulator prompt 不包含 scenario id，不同步骤可能生成不同 task_id。
        Validator 目前只检查 task_id 是否存在，不检查跨步骤一致性。
        """
        suffix = uuid.uuid5(uuid.NAMESPACE_URL, step_text).hex[:8]
        return f"task-{suffix}"

    def _trace_has_task_id(self, trace_summary: dict[str, Any]) -> bool:
        """检查 trace 中是否包含 task_id 证据。

        由于 ValidatorAgentCore 的 prompt 默认不包含 step.output，
        我们通过 action/target 来推断：只要存在 create/query 任务的动作，
        即认为 simulator 返回了 task_id。
        """
        steps = trace_summary.get("steps", [])
        for step in steps:
            output = step.get("output") or {}
            data = step.get("data") or {}
            if "task_id" in output or "task_id" in data:
                return True
            action = step.get("action", "")
            target = step.get("target", "")
            if action in ("create", "query") and target == "task":
                return True
        return False

    def complete(self, prompt: str) -> dict[str, Any]:
        """同步完成 prompt，适配 LLMClient 接口。

        根据 prompt 内容自动判断是 simulator 还是 validator：
        - 包含 【步骤】/【技术映射】 视为 simulator prompt
        - 包含 "## 1. Simulator Execution Result" 视为 validator prompt
        """
        if "【步骤】" in prompt and "【技术映射】" in prompt:
            return asyncio.run(self.execute_simulator_prompt(prompt, dict))
        if "## 1. Simulator Execution Result" in prompt:
            return asyncio.run(self.execute_validator_prompt(prompt, dict))
        # 无法识别时返回空 OK，避免阻塞流程
        self._logger.warning("Unrecognized prompt type, returning empty OK response")
        return {"status": "OK", "action": "noop", "data": {}}


class LocalAutoResponderLLMClient(LLMClient):
    """将 LocalAutoResponder 适配为 LLMClient，用于 CLI 本地自动响应模式。"""

    def __init__(self, token_budget: int = 4000):
        self._responder = LocalAutoResponder()
        self.token_budget = token_budget
        self.tokens_used = 0

    def complete(self, prompt: str) -> dict[str, Any]:
        """同步完成 prompt。"""
        self.tokens_used = len(prompt) // 4
        if self.tokens_used >= self.token_budget:
            raise TokenBudgetExceeded(
                f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
            )
        result = self._responder.complete(prompt)
        self.tokens_used += 10
        return result
