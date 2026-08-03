"""Gap 检测器"""

import re
from typing import Optional

from mock_framework.models.arch import ArchDoc
from mock_framework.models.gap import Gap, GapReport, GapLocation
from mock_framework.models.loader import TestCase


class GapDetector:
    """Gap 检测器"""

    # 常见非组件词：平台术语、状态枚举、Gherkin 关键字、普通英文词
    NON_COMPONENT_WORDS = frozenset(
        {
            # 平台 / 技术术语
            "Telegram",
            "PC",
            "ID",
            "AI",
            "PNG",
            "Windows",
            "System",
            "API",
            "URL",
            "URI",
            "UI",
            "CLI",
            "HTTP",
            "HTTPS",
            "JSON",
            "YAML",
            "XML",
            "HTML",
            "SQL",
            "NoSQL",
            "CPU",
            "GPU",
            "RAM",
            "SSD",
            "OS",
            "SDK",
            "CDN",
            "DNS",
            "VPN",
            "SSH",
            "FTP",
            "SMTP",
            "IMAP",
            "TCP",
            "UDP",
            "IP",
            "IPv4",
            "IPv6",
            "JWT",
            "OAuth",
            "SSO",
            "LDAP",
            "SAML",
            "RBAC",
            "ACL",
            "CORS",
            "CSRF",
            "XSS",
            "TLS",
            "SSL",
            "MQTT",
            "AMQP",
            "JPEG",
            "JPG",
            "GIF",
            "PDF",
            "SVG",
            "BMP",
            "TIFF",
            "WEBP",
            # 性能指标 / 百分位
            "P50",
            "P90",
            "P95",
            "P99",
            "P999",
            # 状态 / 枚举值
            "FAILED",
            "FAIL",
            "NOT",
            "NO",
            "YES",
            "TEMPORARY",
            "PERMANENT",
            "DURATION",
            "PAUSED",
            "EXECUTING",
            "PENDING",
            "COMPLETED",
            "CANCELLED",
            "RUNNING",
            "SUCCESS",
            "SUCCEEDED",
            "ERROR",
            "ERR",
            "OK",
            "TRUE",
            "FALSE",
            "NULL",
            "NONE",
            "UNKNOWN",
            "UNBOUND",
            "BOUND",
            "ACTIVE",
            "INACTIVE",
            "GRANTED",
            "DENIED",
            "ALLOWED",
            "DISABLED",
            "ENABLED",
            "VISIBLE",
            "HIDDEN",
            "READONLY",
            "USER",
            "ADMIN",
            # Gherkin / 通用词
            "When",
            "Then",
            "Given",
            "And",
            "But",
            "As",
            "The",
            "A",
            "An",
            "Is",
            "Are",
            "Am",
            "Be",
            "Been",
            "Being",
            "Have",
            "Has",
            "Had",
            "Do",
            "Does",
            "Did",
            "Will",
            "Would",
            "Should",
            "Could",
            "Can",
            "May",
            "Might",
            "Shall",
            "Must",
            "With",
            "For",
            "From",
            "To",
            "In",
            "On",
            "At",
            "By",
            "Of",
            "About",
            "Above",
            "Across",
            "After",
            "Against",
            "Along",
            "Among",
            "Around",
            "Before",
            "Behind",
            "Below",
            "Beneath",
            "Beside",
            "Between",
            "Beyond",
            "During",
            "Except",
            "Inside",
            "Into",
            "Near",
            "Off",
            "Onto",
            "Outside",
            "Over",
            "Through",
            "Toward",
            "Under",
            "Until",
            "Upon",
            "Within",
            "Without",
            "And",
            "Or",
            "Nor",
            "If",
            "Else",
            "Because",
            "Since",
            "Although",
            "While",
            "Where",
            "When",
            "That",
            "Which",
            "Who",
            "Whom",
            "Whose",
            "What",
            "This",
            "These",
            "Those",
            "Such",
        }
    )

    def __init__(
        self,
        loader_config: Optional[object] = None,
        extra_non_component_words: Optional[set[str]] = None,
    ):
        """初始化 GapDetector

        Args:
            loader_config: 配置对象，用于读取 loader.gap_detector 相关配置。
            extra_non_component_words: 额外需要过滤的非组件词集合。
        """
        self._non_component_words = set(self.NON_COMPONENT_WORDS)
        self._chinese_mode_threshold = 0.5

        if extra_non_component_words:
            self._non_component_words |= set(extra_non_component_words)

        if loader_config is not None:
            gap_cfg = getattr(loader_config, "gap_detector", None)
            if gap_cfg is not None:
                extra = getattr(gap_cfg, "non_component_words", None) or []
                self._non_component_words |= set(extra)
                threshold = getattr(gap_cfg, "chinese_mode_threshold", None)
                if threshold is not None:
                    self._chinese_mode_threshold = float(threshold)

    def detect(self, test_cases: list[TestCase], arch_doc: ArchDoc) -> GapReport:
        """检测 Gap

        Args:
            test_cases: Loader 生成的测试用例
            arch_doc: 架构文档

        Returns:
            Gap 报告
        """
        gaps = []
        gap_counter = 1

        for tc in test_cases:
            new_gaps = []
            new_gaps.extend(self._check_missing_component(tc, arch_doc, gap_counter))
            gap_counter += len(new_gaps)
            gaps.extend(new_gaps)

            new_gaps = self._check_missing_api(tc, arch_doc, gap_counter)
            gap_counter += len(new_gaps)
            gaps.extend(new_gaps)

            new_gaps = self._check_missing_state(tc, arch_doc, gap_counter)
            gap_counter += len(new_gaps)
            gaps.extend(new_gaps)

            new_gaps = self._check_missing_nfr(tc, arch_doc, gap_counter)
            gap_counter += len(new_gaps)
            gaps.extend(new_gaps)

            new_gaps = self._check_missing_interface(tc, arch_doc, gap_counter)
            gap_counter += len(new_gaps)
            gaps.extend(new_gaps)

        return GapReport(total_gaps=len(gaps), gaps=gaps)

    def _is_chinese_dominant(self, text: str) -> bool:
        """判断文本是否以中文为主"""
        if not text:
            return False
        total = len(text)
        chinese_chars = sum(1 for ch in text if "一" <= ch <= "鿿")
        return chinese_chars / total >= self._chinese_mode_threshold

    def _is_likely_ui_label(self, param: str, full_step: str) -> bool:
        """判断引号内文本是否更像 UI 标签/消息/动作描述而非接口名"""
        param_lower = param.lower()

        # 中文为主的字符串通常是 UI 标签或用户消息
        if self._is_chinese_dominant(param):
            return True

        # 包含中文且包含 /，说明是中文说明性文本（如 /template 每日待办摘要）
        # 而非纯技术路径；真实 API 路径在本仓库均为英文
        if any("一" <= ch <= "鿿" for ch in param) and "/" in param:
            return True

        # 引号内容以动作动词开头，说明是描述性短语而非接口名
        action_verbs = ["调用", "请求", "访问", "发送"]
        if any(param.startswith(verb) for verb in action_verbs):
            return True

        # 包含 "api" 但无路径/协议/端口特征，更像描述性短语
        if "api" in param_lower and not re.search(r"[/.:]", param_lower):
            return True

        return False

    def _extract_component_candidates(
        self, text: str, known_names: Optional[set[str]] = None
    ) -> list[str]:
        """从步骤文本中提取候选组件名

        - 优先匹配已知名称中的多词组件名（如 "PC Agent"），避免被拆成 "PC" + "Agent"。
        - 中文为主的文本：只保留全大写缩写（≥2 个字母），过滤普通英文单词。
        - 英文为主的文本：保留首字母大写的英文单词（现有行为）。
        - 两种模式都会再经过 denylist 过滤。
        """
        candidates: list[str] = []
        remaining = text
        known_names = known_names or set()

        # 1. 优先提取已知的多词组件名（含空格），按长度降序避免短名覆盖长名
        multi_word_names = sorted(
            (n for n in known_names if " " in n),
            key=len,
            reverse=True,
        )
        for name in multi_word_names:
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            if pattern.search(remaining):
                candidates.append(name)
                remaining = pattern.sub("", remaining)

        # 2. 对剩余文本做原有单字提取
        if self._is_chinese_dominant(remaining):
            raw = re.findall(r"[A-Z][A-Za-z0-9]+", remaining)
            candidates.extend(
                c for c in raw if c.isupper() or (len(c) >= 2 and any(ch.islower() for ch in c))
            )
        else:
            candidates.extend(re.findall(r"[A-Z][a-zA-Z]+", remaining))

        return candidates

    def _collect_known_component_names(self, arch_doc: ArchDoc) -> set[str]:
        """收集架构文档中所有可被视为组件/接口/依赖的名称"""
        known = {c.name for c in arch_doc.components}
        known |= {i.name for i in arch_doc.interfaces}
        known |= set(getattr(arch_doc, "external_dependencies", []) or [])
        for artifact in getattr(arch_doc, "internals", []) or []:
            title = getattr(artifact, "title", None) or getattr(artifact, "name", None)
            if title:
                known.add(title)
        return known

    def _check_missing_component(
        self, test_case: TestCase, arch_doc: ArchDoc, counter: int
    ) -> list[Gap]:
        """检查缺失组件"""
        gaps: list[Gap] = []
        known_components = self._collect_known_component_names(arch_doc)

        # 从 gherkin steps 中提取组件名
        steps = test_case.gherkin.get("steps", [])
        for step in steps:
            text = step.get("text", "")
            found_components = self._extract_component_candidates(text, known_components)
            for component_name in found_components:
                if component_name in self._non_component_words:
                    continue
                if any(
                    component_name.lower()
                    in {token.lower() for token in re.findall(r"[A-Za-z0-9]+", known)}
                    for known in known_components
                ):
                    # Domain prose often shortens a declared multi-word component
                    # (for example Amazon ACL -> Amazon). This is a reference to a
                    # known boundary, not evidence for another missing component.
                    continue
                if component_name not in known_components:
                    # In Chinese business prose, capitalized vendor names, field
                    # acronyms, and role words are common (Amazon, ASIN, NFR,
                    # Agent). Treat an unknown token as a component only when the
                    # sentence explicitly labels it as one. English-dominant
                    # technical steps retain the existing heuristic.
                    if any("一" <= char <= "鿿" for char in text):
                        explicit_component = re.search(
                            rf"{re.escape(component_name)}\s*(?:服务|组件|模块|系统|网关|BC|连接池|数据库|缓存|队列)",
                            text,
                            re.IGNORECASE,
                        )
                        technical_name = re.search(
                            r"(?:Service|Controller|Gateway|Repository|Client|Worker|API)$",
                            component_name,
                            re.IGNORECASE,
                        )
                        if not explicit_component and not technical_name:
                            continue
                    # 避免重复报告同一组件
                    if not any(
                        g.location.step == text and g.type == "Missing Component" for g in gaps
                    ):
                        gap_id = f"GAP-{counter:03d}"
                        gaps.append(
                            Gap(
                                id=gap_id,
                                type="Missing Component",
                                severity="ERROR",
                                location=GapLocation(
                                    gherkin_file=test_case.source_feature,
                                    scenario=test_case.source_scenario,
                                    step=text,
                                ),
                                description=f"Gherkin引用了'{component_name}'组件，但架构文档未定义",
                                suggestion=f"补充架构文档：添加{component_name}组件定义",
                            )
                        )
                        counter += 1

        return gaps

    def _check_missing_api(self, test_case: TestCase, arch_doc: ArchDoc, counter: int) -> list[Gap]:
        """检查缺失 API / 接口"""
        gaps = []
        has_api_defs = bool(arch_doc.openapi.paths) or bool(arch_doc.interfaces)

        if not has_api_defs:
            steps = test_case.gherkin.get("steps", [])
            for step in steps:
                text = step.get("text", "")
                if "请求" in text or "API" in text or "调用" in text or "发送" in text:
                    gap_id = f"GAP-{counter:03d}"
                    gaps.append(
                        Gap(
                            id=gap_id,
                            type="Missing API",
                            severity="ERROR",
                            location=GapLocation(
                                gherkin_file=test_case.source_feature,
                                scenario=test_case.source_scenario,
                                step=text,
                            ),
                            description="Gherkin包含API相关步骤，但架构文档未定义接口",
                            suggestion="补充架构文档：添加OpenAPI或interfaces接口定义",
                        )
                    )
                    counter += 1

        return gaps

    def _check_missing_interface(
        self, test_case: TestCase, arch_doc: ArchDoc, counter: int
    ) -> list[Gap]:
        """检查步骤引用的接口是否在架构文档中定义"""
        gaps = []
        known_interfaces = {i.name.lower() for i in arch_doc.interfaces}

        steps = test_case.gherkin.get("steps", [])
        for step in steps:
            text = step.get("text", "")
            # 启发式：查找引号内的接口名或协议名
            params = re.findall(r'[“”"]([^“”"]+)[“”"]', text)
            for param in params:
                param_lower = param.lower()
                if param_lower not in known_interfaces:
                    # 检查是否看起来像接口名（含协议关键词或路径特征）
                    if any(kw in param_lower for kw in ["api", "grpc", "kafka", "webhook", "/"]):
                        # 过滤 UI 标签/用户消息等误报
                        if self._is_likely_ui_label(param, text):
                            continue
                        gap_id = f"GAP-{counter:03d}"
                        gaps.append(
                            Gap(
                                id=gap_id,
                                type="Missing Interface",
                                severity="WARNING",
                                location=GapLocation(
                                    gherkin_file=test_case.source_feature,
                                    scenario=test_case.source_scenario,
                                    step=text,
                                ),
                                description=f"Gherkin引用了接口'{param}'，但interfaces未定义",
                                suggestion=f"补充interfaces定义：添加{param}接口",
                            )
                        )
                        counter += 1

        return gaps

    def _check_missing_state(
        self, test_case: TestCase, arch_doc: ArchDoc, counter: int
    ) -> list[Gap]:
        """检查缺失状态"""
        gaps = []
        known_states = set(arch_doc.state_machine.states)

        steps = test_case.gherkin.get("steps", [])
        for step in steps:
            text = step.get("text", "")
            # 查找 "状态为XXX" 或 "变为XXX" 或 "应变为XXX"
            match = re.search(r"状态(?:为|应变为|变为)(\w+)", text)
            if match:
                state = match.group(1)
                if state not in known_states:
                    gap_id = f"GAP-{counter:03d}"
                    gaps.append(
                        Gap(
                            id=gap_id,
                            type="Missing State",
                            severity="WARNING",
                            location=GapLocation(
                                gherkin_file=test_case.source_feature,
                                scenario=test_case.source_scenario,
                                step=text,
                            ),
                            description=f"Gherkin引用状态'{state}'，但状态机未定义",
                            suggestion=f"补充状态机：添加状态'{state}'",
                        )
                    )
                    counter += 1

        return gaps

    def _check_missing_nfr(self, test_case: TestCase, arch_doc: ArchDoc, counter: int) -> list[Gap]:
        """检查缺失 NFR"""
        gaps = []
        known_nfr_metrics = {n.metric for n in arch_doc.nfrs}

        steps = test_case.gherkin.get("steps", [])
        for step in steps:
            text = step.get("text", "")
            # 查找性能指标
            match = re.search(r"(\d+)(ms|秒|s)", text)
            if match:
                # 简单检查：如果提到了时间但没有对应的 NFR
                if not known_nfr_metrics:
                    gap_id = f"GAP-{counter:03d}"
                    gaps.append(
                        Gap(
                            id=gap_id,
                            type="Missing NFR",
                            severity="WARNING",
                            location=GapLocation(
                                gherkin_file=test_case.source_feature,
                                scenario=test_case.source_scenario,
                                step=text,
                            ),
                            description="Gherkin包含性能指标，但NFR表格未定义",
                            suggestion="补充NFR表格：添加性能指标定义",
                        )
                    )
                    counter += 1

        return gaps
