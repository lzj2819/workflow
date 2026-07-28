"""步骤映射引擎"""

import re

from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc, InterfaceDef
from mock_framework.models.gherkin import Step
from mock_framework.models.loader import TechnicalMapping


class StepMapper:
    """步骤映射引擎"""

    def __init__(self, arch_doc: ArchDoc):
        self.arch_doc = arch_doc
        self.logger = get_logger("loader.step_mapper")

    def map_step(
        self, step: Step, step_index: int, current_phase: str = "given"
    ) -> list[TechnicalMapping]:
        """映射单个步骤

        Args:
            step: Gherkin 步骤
            step_index: 步骤索引
            current_phase: 当前步骤所处阶段（given/when/then），用于正确映射
                          And/But 等承接步骤

        Returns:
            技术映射列表（Then 可能对应多个验证点）
        """
        keyword = step.keyword.lower()

        # Given 阶段及其 And/But 承接步骤统一按 Given 映射
        if keyword == "given" or (keyword in ("and", "but") and current_phase == "given"):
            return [self._map_given(step, step_index)]
        # When 阶段及其 And/But 承接步骤统一按 When 映射
        elif keyword == "when" or (keyword in ("and", "but") and current_phase == "when"):
            return [self._map_when(step, step_index)]
        # Then 阶段及其 And/But 承接步骤统一按 Then 映射
        elif keyword == "then" or (keyword in ("and", "but") and current_phase == "then"):
            return self._map_then(step, step_index)

        return []

    def _extract_quoted_params(self, text: str) -> list[str]:
        """提取中文/英文引号包裹的参数"""
        # 匹配中文引号 "" 和英文引号 ""
        return re.findall(r"[\u201c\u201d\"]([^\u201c\u201d\"]+)[\u201c\u201d\"]", text)

    def _map_given(self, step: Step, step_index: int) -> TechnicalMapping:
        """映射 Given 步骤"""
        text = step.text
        params = self._extract_quoted_params(text)
        target: dict = {"params": params} if params else {}

        # 模式1: 接收到请求 → API 端点
        if "接收到" in text or "收到" in text:
            api_mapping = self._map_given_api(text, step_index)
            # 合并引号参数
            merged_target = dict(api_mapping.target)
            if params:
                merged_target["params"] = params
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type=api_mapping.mapping_type,
                target=merged_target,
                confidence=api_mapping.confidence,
            )

        # 模式2: 状态为"XXX" / 状态为XXX → 状态机（支持中文引号）
        match = re.search(r"状态为[\u201c\u201d\"]*([^\u201c\u201d\"]+)[\u201c\u201d\"]*", text)
        if match:
            state = match.group(1)
            target["state"] = state
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="state_machine",
                target=target,
                confidence="high" if state in self.arch_doc.state_machine.states else "low",
            )

        # 模式3: 用户"X"已... → 用户数据准备
        match = re.search(r"用户[\u201c\u201d\"]*([^\u201c\u201d\"]+)[\u201c\u201d\"]*", text)
        if match:
            target["user_id"] = match.group(1)
            if "已登录" in text or "已通过" in text or "已完成" in text:
                return TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="data_preparation",
                    target=target,
                    confidence="high",
                )

        # 模式4: 目标PC/设备 在线/就绪 → 设备状态
        if "PC" in text or "设备" in text:
            if "在线" in text or "就绪" in text or "运行中" in text:
                target["device_state"] = "online"
                return TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="device_state",
                    target=target,
                    confidence="high",
                )

        # 模式5: 已授权 → 权限准备
        if "已授权" in text or "授权" in text:
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="data_preparation",
                target=target,
                confidence="medium",
            )

        # 模式6: 存在/已注册 → 数据准备
        if "存在" in text or "已注册" in text or "已登录" in text:
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="data_preparation",
                target=target,
                confidence="medium",
            )

        # 模式7: 数量 → 并发参数
        match = re.search(r"(\d+)个", text)
        if match:
            target["concurrent_users"] = int(match.group(1))
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="concurrent_param",
                target=target,
                confidence="high",
            )

        return TechnicalMapping(
            step_index=step_index,
            text=text,
            mapping_type="vague",
            target=target,
            confidence="low",
        )

    def _map_given_api(self, text: str, step_index: int) -> TechnicalMapping:
        """映射 Given API 步骤（搜索 OpenAPI + interfaces）"""
        # 1. 查找匹配的 OpenAPI 路径
        for path, methods in self.arch_doc.openapi.paths.items():
            if any(kw in text for kw in ["登录", "login"]):
                if "login" in path.lower():
                    return TechnicalMapping(
                        step_index=step_index,
                        text=text,
                        mapping_type="api_endpoint",
                        target={"endpoint": path, "methods": list(methods.keys())},
                        confidence="high",
                    )

        # 2. 搜索 interfaces 中的 inbound 接口
        for iface in self.arch_doc.interfaces:
            if iface.direction == "inbound" and self._text_matches_interface(text, iface):
                return TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="api_endpoint",
                    target={
                        "interface": iface.name,
                        "protocol": iface.protocol,
                        "contract": iface.contract,
                    },
                    confidence="high",
                )

        return TechnicalMapping(
            step_index=step_index,
            text=text,
            mapping_type="api_endpoint",
            target={"description": "API 端点（未精确匹配）"},
            confidence="medium",
        )

    def _text_matches_interface(self, text: str, iface: InterfaceDef) -> bool:
        """判断步骤文本是否与接口定义匹配"""
        name_lower = iface.name.lower()
        text_lower = text.lower()
        # 直接包含接口名
        if name_lower in text_lower:
            return True
        # 协议关键词匹配
        protocol_keywords = {
            "telegram": ["telegram", "消息", "发送"],
            "kafka": ["kafka", "事件", "消息"],
            "grpc": ["grpc", "调用", "远程"],
            "https": ["https", "http", "请求", "webhook"],
        }
        for proto_key, keywords in protocol_keywords.items():
            if proto_key in name_lower or proto_key in iface.protocol.lower():
                if any(kw in text_lower for kw in keywords):
                    return True
        return False

    def _match_interface_for_action(self, text: str, step_index: int) -> TechnicalMapping | None:
        """为 When 步骤匹配 interfaces 中的接口"""
        text_lower = text.lower()
        for iface in self.arch_doc.interfaces:
            if self._text_matches_interface(text, iface):
                return TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="interface_call",
                    target={
                        "interface": iface.name,
                        "protocol": iface.protocol,
                        "direction": iface.direction,
                        "contract": iface.contract,
                    },
                    confidence="high",
                )
        return None

    def _map_when(self, step: Step, step_index: int) -> TechnicalMapping:
        """映射 When 步骤"""
        text = step.text
        params = self._extract_quoted_params(text)
        target: dict = {"params": params} if params else {}

        # 模式1: 发送消息/指令 → 消息发送
        if "发送消息" in text or "发送指令" in text or "输入" in text:
            target["action"] = "message_send"
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="message_send",
                target=target,
                confidence="high",
            )

        # 模式2: 接管/结束接管/人工干预 → 手动控制
        if "接管" in text or "人工干预" in text or "结束接管" in text:
            target["action"] = "takeover" if "接管" in text and "结束" not in text else "release"
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="manual_control",
                target=target,
                confidence="high",
            )

        # 模式3: 快捷指令 /template → 快捷指令
        if text.startswith("/") or "快捷指令" in text:
            target["action"] = "shortcut_command"
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="shortcut_command",
                target=target,
                confidence="high",
            )

        # 模式4: 处理/经过 → 数据流步骤
        if "处理" in text or "经过" in text:
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="data_flow",
                target=target or {"description": "数据处理流程"},
                confidence="medium",
            )

        # 模式5: 基于 interfaces 的精确接口调用（优先）
        iface_mapping = self._match_interface_for_action(text, step_index)
        if iface_mapping:
            return iface_mapping

        # 模式6: 提交/调用/发送 → API 调用
        if "提交" in text or "调用" in text or "发送" in text:
            return TechnicalMapping(
                step_index=step_index,
                text=text,
                mapping_type="api_call",
                target=target or {"description": "API 调用"},
                confidence="medium",
            )

        return TechnicalMapping(
            step_index=step_index,
            text=text,
            mapping_type="action",
            target=target,
            confidence="low",
        )

    def _map_then(self, step: Step, step_index: int) -> list[TechnicalMapping]:
        """映射 Then 步骤（可能返回多个映射）"""
        text = step.text
        params = self._extract_quoted_params(text)
        target_base: dict = {"params": params} if params else {}
        mappings = []

        # 模式1: 应被调用 → 接口/流程验证
        if "应被调用" in text or "应被查询" in text:
            # 优先匹配 interfaces
            matched_interface = False
            for iface in self.arch_doc.interfaces:
                if self._text_matches_interface(text, iface):
                    mappings.append(
                        TechnicalMapping(
                            step_index=step_index,
                            text=text,
                            mapping_type="interface_validation",
                            target={
                                **target_base,
                                "interface": iface.name,
                                "protocol": iface.protocol,
                                "direction": iface.direction,
                            },
                            confidence="high",
                        )
                    )
                    matched_interface = True
                    break
            if not matched_interface:
                mappings.append(
                    TechnicalMapping(
                        step_index=step_index,
                        text=text,
                        mapping_type="expected_call",
                        target={**target_base, "description": "验证组件被调用"},
                        confidence="high",
                    )
                )

        # 模式2: 响应应包含 / 应返回 / 应发送（通知/消息） → 结构/响应验证
        if "响应应包含" in text or "应返回" in text or "应发送" in text:
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="response_validation",
                    target={**target_base, "description": "验证响应结构或通知内容"},
                    confidence="high",
                )
            )

        # 模式3: 状态应变为 / 应更新为 / 状态为 → 状态验证（支持中文引号）
        match = re.search(
            r"状态(?:应变为|应更新为|为)[\"\"\"\"]*([^\"\"\"\"\"\"\"\"]+)[\"\"\"\"]*", text
        )
        if match:
            state = match.group(1)
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="state_validation",
                    target={**target_base, "expected_state": state},
                    confidence="high",
                )
            )

        # 模式4: 应在XXXms内 / 毫秒内 / 秒内 / s内 → 性能验证
        match = re.search(r"应在(\d+)(ms|毫秒内|秒内|s内)", text)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            threshold_ms = value if unit in ("ms", "毫秒内") else value * 1000
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="performance_check",
                    target={
                        **target_base,
                        "metric": "latency",
                        "threshold_ms": threshold_ms,
                        "operator": "less_than",
                    },
                    confidence="high",
                )
            )

        # 模式5: 应创建 / 应写入 → 副作用验证
        if "应创建" in text or "应写入" in text:
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="expected_side_effect",
                    target={**target_base, "description": "验证副作用发生"},
                    confidence="high",
                )
            )

        # 模式6: 应包含字段 / 应包含以下字段 → 字段列表验证
        if "应包含字段" in text or "应包含以下字段" in text:
            field_part = text.split("：")[-1] if "：" in text else text.split(":")[-1]
            fields = [f.strip() for f in re.split(r"[,，、]", field_part) if f.strip()]
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="field_validation",
                    target={**target_base, "required_fields": fields},
                    confidence="high",
                )
            )

        # 模式7: 应记录 / 应生成日志 / 审计 → 审计/日志验证
        if "应记录" in text or "应生成" in text or "审计" in text or "日志" in text:
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="audit_validation",
                    target={**target_base, "description": "验证审计记录生成"},
                    confidence="high",
                )
            )

        # 模式8: 不应 / 禁止 / 必须不 → 否定验证（安全相关）
        if "不应" in text or "禁止" in text or "必须不" in text:
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="negative_validation",
                    target={**target_base, "description": "验证否定条件"},
                    confidence="high",
                )
            )

        if not mappings:
            mappings.append(
                TechnicalMapping(
                    step_index=step_index,
                    text=text,
                    mapping_type="vague",
                    target=target_base,
                    confidence="low",
                )
            )

        return mappings
