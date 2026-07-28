"""CrossLayerValidator — 层间一致性验证"""

import re
from pathlib import Path
from typing import Optional

from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc, Constraint
from mock_framework.models.layer import ConsistencyReport, Violation


class CrossLayerValidator:
    """验证父层和子层之间的一致性"""

    def __init__(self) -> None:
        self.logger = get_logger("cross_layer_validator")

    def validate(self, parent: ArchDoc, children: list[ArchDoc]) -> ConsistencyReport:
        """
        验证父层与子层之间的一致性。

        Args:
            parent: 父层 ArchDoc
            children: 子层 ArchDoc 列表

        Returns:
            ConsistencyReport: 一致性报告
        """
        self.logger.info(
            "Validating cross-layer consistency: %s → %d children",
            parent.level_name,
            len(children),
        )

        violations: list[Violation] = []

        violations.extend(self._check_interface_matching(parent, children))
        violations.extend(self._check_nfr_bounds(parent, children))
        violations.extend(self._check_children_exist(parent, children))
        violations.extend(self._check_leaf_completeness(children))

        report = ConsistencyReport(violations=violations)
        self.logger.info("Cross-layer validation: %d violations", report.total_violations)
        return report

    def _check_interface_matching(
        self, parent: ArchDoc, children: list[ArchDoc]
    ) -> list[Violation]:
        """规则1: 父层 outbound 接口必须有子层 inbound 接口匹配"""
        violations: list[Violation] = []

        for p_out in [i for i in parent.interfaces if i.direction == "outbound"]:
            matched = any(
                self._fuzzy_match(c_in.contract, p_out.contract)
                or self._name_similar(c_in.name, p_out.name)
                for child in children
                for c_in in [i for i in child.interfaces if i.direction == "inbound"]
            )
            if not matched:
                violations.append(
                    Violation(
                        rule="parent_outbound_must_match_child_inbound",
                        detail=f"Parent outbound interface '{p_out.name}' has no matching child inbound",
                        severity="high",
                    )
                )

        return violations

    def _check_nfr_bounds(self, parent: ArchDoc, children: list[ArchDoc]) -> list[Violation]:
        """规则2: 子层 NFR 不能超过父层范围"""
        violations: list[Violation] = []

        parent_nfrs = [c for c in parent.constraints if c.type == "nfr"]
        if not parent_nfrs:
            return violations

        for child in children:
            child_nfrs = [c for c in child.constraints if c.type == "nfr"]
            for cn in child_nfrs:
                matching_pn = self._find_matching_nfr(parent_nfrs, cn)
                if matching_pn and not self._nfr_stricter_or_equal(cn, matching_pn):
                    violations.append(
                        Violation(
                            rule="child_nfr_must_be_stricter_than_parent",
                            detail=f"Child '{child.level_name}' NFR '{cn.description}' exceeds parent bounds",
                            severity="high",
                        )
                    )

        return violations

    def _check_children_exist(self, parent: ArchDoc, children: list[ArchDoc]) -> list[Violation]:
        """规则3: 父层声明的子层必须都存在"""
        violations: list[Violation] = []

        declared = set(parent.children_refs)
        if not declared:
            return violations

        # Extract child names from refs (e.g., "modules/payment.md" → "payment")
        declared_names = {Path(r).stem for r in declared}
        actual_names = {c.level_name for c in children}

        missing = declared_names - actual_names
        if missing:
            violations.append(
                Violation(
                    rule="declared_children_must_exist",
                    detail=f"Declared children not found: {missing}",
                    severity="medium",
                )
            )

        return violations

    def validate_current_layer(self, arch_doc: ArchDoc) -> ConsistencyReport:
        """
        仅验证单层自身的完整性，不检查子层是否存在。

        Args:
            arch_doc: 要验证的架构文档。

        Returns:
            ConsistencyReport: 单层验证报告。
        """
        self.logger.info("Validating current layer only: %s", arch_doc.level_name)

        violations = []

        # 当前层至少要有某种形式的设计内容
        has_content = bool(
            arch_doc.interfaces
            or arch_doc.components
            or arch_doc.internals
            or arch_doc.constraints
            or arch_doc.children_refs
        )
        if not has_content:
            violations.append(
                Violation(
                    rule="current_layer_must_have_design",
                    detail=f"Current layer '{arch_doc.level_name}' has no interfaces, components, internals, constraints, or children",
                    severity="medium",
                )
            )

        # 如果是叶子节点（没有声明子层），则要求有内部设计
        if not arch_doc.children_refs and not arch_doc.internals:
            violations.append(
                Violation(
                    rule="leaf_layer_must_have_internals",
                    detail=f"Current layer '{arch_doc.level_name}' is a leaf but has no internal design",
                    severity="medium",
                )
            )

        report = ConsistencyReport(violations=violations)
        self.logger.info("Current-layer validation: %d violations", report.total_violations)
        return report

    def _check_leaf_completeness(self, children: list[ArchDoc]) -> list[Violation]:
        """规则4: 叶子节点必须没有 children_refs 或必须有 internals"""
        violations = []

        for child in children:
            if child.children_refs and not child.internals:
                violations.append(
                    Violation(
                        rule="non_leaf_must_have_internals_or_children",
                        detail=f"'{child.level_name}' declares children but has no internal design",
                        severity="medium",
                    )
                )

        return violations

    def _fuzzy_match(self, contract_a: dict, contract_b: dict) -> bool:
        """模糊匹配两个接口契约"""
        # Simplified: check if path or name overlaps
        a_paths = set(contract_a.get("paths", {}).keys()) if isinstance(contract_a, dict) else set()
        b_paths = set(contract_b.get("paths", {}).keys()) if isinstance(contract_b, dict) else set()
        return bool(a_paths & b_paths) if (a_paths and b_paths) else False

    def _name_similar(self, name_a: str, name_b: str) -> bool:
        """判断两个名称是否相似"""
        a = name_a.lower().replace(" ", "").replace("-", "")
        b = name_b.lower().replace(" ", "").replace("-", "")
        return a == b or a in b or b in a

    def _find_matching_nfr(
        self, parent_nfrs: list[Constraint], child_nfr: Constraint
    ) -> Optional[Constraint]:
        """找到与子层 NFR 对应的父层 NFR"""
        child_metric = self._extract_metric(child_nfr.description)
        for pn in parent_nfrs:
            parent_metric = self._extract_metric(pn.description)
            if child_metric and parent_metric and child_metric == parent_metric:
                return pn
        return None

    def _extract_metric(self, description: str) -> Optional[str]:
        """从描述中提取指标名称"""
        metrics = ["latency", "throughput", "availability", "error_rate", "并发"]
        for m in metrics:
            if m in description.lower():
                return m
        return None

    def _nfr_stricter_or_equal(self, child: Constraint, parent: Constraint) -> bool:
        """判断子层 NFR 是否比父层更严格或相等"""
        # Extract threshold values from the value field like "latency < 100ms"
        child_val = self._extract_threshold(child.value)
        parent_val = self._extract_threshold(parent.value)

        if child_val is None or parent_val is None:
            return True  # Cannot compare, assume OK

        # For latency/smaller-is-better: child threshold must be <= parent threshold
        return child_val <= parent_val

    def _extract_threshold(self, description: Optional[str]) -> Optional[float]:
        if description is None:
            return None
        """从描述中提取阈值数值"""
        match = re.search(r"[<≤]?\s*(\d+(?:\.\d+)?)", description)
        if match:
            return float(match.group(1))
        return None
