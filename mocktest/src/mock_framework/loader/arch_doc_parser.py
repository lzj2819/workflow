"""架构文档解析器（支持单文件/多文件目录）"""

import json
import re
from pathlib import Path
from typing import Any, Literal, Optional, cast

import yaml  # type: ignore[import-untyped]

from mock_framework.logger import get_logger
from mock_framework.models.arch import (
    ArchDoc,
    ComponentSpec,
    Constraint,
    DataFlow,
    DataFlowStep,
    DesignArtifact,
    InterfaceDef,
    NFR,
    OpenAPISpec,
    StateMachine,
    StateTransition,
)


_GENERIC_RESPONSIBILITY_PREFIXES = ("Bounded Context:", "Module:", "BC:")


def _is_authoritative_responsibility(responsibility: str | None) -> bool:
    """职责是否为权威描述（来自模块清单表），而非 flowchart/heading 兜底生成的通用前缀。"""
    if not responsibility:
        return False
    return not responsibility.startswith(_GENERIC_RESPONSIBILITY_PREFIXES)


class MarkdownTableExtractor:
    """通用 Markdown 表格提取器"""

    TABLE_PATTERN = re.compile(
        r"(?:^|\n)\|([^\n]+?)\|\n\|[-|\s]+\|\n((?:\|[^\n]*\|\n?)+)",
        re.MULTILINE,
    )

    def extract_all(self, content: str) -> list[dict]:
        """提取所有表格，返回 {headers, rows} 列表"""
        tables = []
        for match in self.TABLE_PATTERN.finditer(content):
            header_line = match.group(1).strip()
            body = match.group(2).strip()

            headers = [h.strip() for h in header_line.split("|") if h.strip()]
            rows = []
            for row_line in body.split("\n"):
                row_line = row_line.strip()
                if not row_line.startswith("|"):
                    continue
                cells = [c.strip() for c in row_line[1:].split("|") if c.strip() or c == ""]
                # 确保列数与 header 一致
                while len(cells) < len(headers):
                    cells.append("")
                if len(cells) > len(headers):
                    cells = cells[: len(headers)]
                row_dict = {}
                for i, h in enumerate(headers):
                    row_dict[h] = cells[i] if i < len(cells) else ""
                rows.append(row_dict)

            tables.append({"headers": headers, "rows": rows})
        return tables

    def extract_by_header_keyword(self, content: str, keyword: str) -> Optional[dict]:
        """根据表格上方标题关键词提取特定表格"""
        tables = self.extract_all(content)
        # 查找 keyword 最近出现的表格
        keyword_pos = content.find(keyword)
        if keyword_pos == -1:
            return None

        best_table = None
        best_distance = float("inf")
        for match in self.TABLE_PATTERN.finditer(content):
            table_start = match.start()
            if table_start > keyword_pos:
                distance = table_start - keyword_pos
                if distance < best_distance:
                    best_distance = distance
                    header_line = match.group(1).strip()
                    body = match.group(2).strip()
                    headers = [h.strip() for h in header_line.split("|") if h.strip()]
                    rows = []
                    for row_line in body.split("\n"):
                        row_line = row_line.strip()
                        if not row_line.startswith("|"):
                            continue
                        cells = [c.strip() for c in row_line[1:].split("|") if c.strip() or c == ""]
                        while len(cells) < len(headers):
                            cells.append("")
                        if len(cells) > len(headers):
                            cells = cells[: len(headers)]
                        row_dict = {}
                        for i, h in enumerate(headers):
                            row_dict[h] = cells[i] if i < len(cells) else ""
                        rows.append(row_dict)
                    best_table = {"headers": headers, "rows": rows}

        return best_table


class MermaidExtractor:
    """通用 Mermaid 图提取器"""

    BLOCK_PATTERN = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

    def extract_all(self, content: str) -> list[dict]:
        """提取所有 mermaid 代码块，返回 {type, content, elements} 列表"""
        diagrams = []
        for match in self.BLOCK_PATTERN.finditer(content):
            block = match.group(1).strip()
            diagram_type = self._detect_type(block)
            elements = self._parse_elements(block, diagram_type)
            diagrams.append(
                {
                    "type": diagram_type,
                    "content": block,
                    "elements": elements,
                }
            )
        return diagrams

    def _detect_type(self, block: str) -> str:
        """检测 Mermaid 图类型"""
        first_line = block.split("\n", 1)[0].strip().lower()
        if "c4context" in first_line:
            return "c4_context"
        elif "c4container" in first_line:
            return "c4_container"
        elif "sequencediagram" in first_line:
            return "sequence_diagram"
        elif "statediagram" in first_line:
            return "state_diagram"
        elif "flowchart lr" in first_line or first_line == "flowchart":
            # flowchart 是 graph 的现代同义词；无方向时按 LR 处理
            return "graph_lr"
        elif "flowchart tb" in first_line or "flowchart td" in first_line:
            return "graph_tb"
        elif "flowchart bt" in first_line:
            return "graph_tb"
        elif "graph lr" in first_line:
            return "graph_lr"
        elif "graph tb" in first_line or "graph td" in first_line:
            return "graph_tb"
        elif "classdiagram" in first_line:
            return "class_diagram"
        return "unknown"

    def _parse_elements(self, block: str, diagram_type: str) -> dict[str, Any]:
        """解析图中元素"""
        elements: dict[str, Any] = {
            "nodes": [],
            "edges": [],
            "participants": [],
            "states": [],
            "transitions": [],
        }
        lines = block.split("\n")

        if diagram_type == "sequence_diagram":
            participants = self._parse_sequence_participants(lines)
            edges = self._parse_sequence_messages(lines)
            # 把 participant 别名映射回全名，让 data_flow 使用组件全名
            alias_map = {p["name"]: p["alias"] for p in participants if p.get("alias")}
            for edge in edges:
                edge["from"] = alias_map.get(edge["from"], edge["from"])
                edge["to"] = alias_map.get(edge["to"], edge["to"])
            elements["participants"] = participants
            elements["edges"] = edges
        elif diagram_type == "state_diagram":
            elements["states"], elements["transitions"] = self._parse_state_diagram(lines)
        elif diagram_type in ("graph_lr", "graph_tb"):
            elements["nodes"], elements["edges"] = self._parse_graph(lines)
        elif diagram_type in ("c4_context", "c4_container"):
            elements["nodes"], elements["edges"] = self._parse_c4_diagram(lines)

        return elements

    def _parse_sequence_participants(self, lines: list[str]) -> list[dict[str, Any]]:
        """解析 sequenceDiagram 参与者"""
        participants: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if line.startswith("participant ") or line.startswith("actor "):
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    rest = parts[1]
                    # participant Name as "Alias"
                    if " as " in rest:
                        name, alias = rest.split(" as ", 1)
                        alias = alias.strip().strip('"')
                        participants.append({"name": name.strip(), "alias": alias})
                    else:
                        participants.append({"name": rest.strip(), "alias": None})
        return participants

    def _parse_sequence_messages(self, lines: list[str]) -> list[dict]:
        """解析 sequenceDiagram 消息（支持空格和别名）"""
        edges = []
        for line in lines:
            line = line.strip()
            # 匹配: A->>B: message 或 A-->>B: message（支持空格在参与者名中）
            # 注意：参与者名可能是 alias（已在声明中定义），这里匹配单词或引号包裹的内容
            # 匹配: A->>B: message 或 A-->>B: message（支持有无空格）
            match = re.match(r"([\w\s]+?)\s*-+>>\s*([\w\s]+?)\s*:\s*(.+)", line)
            if match:
                from_p = match.group(1).strip()
                to_p = match.group(2).strip()
                msg = match.group(3).strip()
                edges.append({"from": from_p, "to": to_p, "message": msg, "type": "call"})
            # 也匹配简洁形式（无空格）
            else:
                match2 = re.match(r"(\w+)\s*-+>>\s*(\w+)\s*:\s*(.+)", line)
                if match2:
                    edges.append(
                        {
                            "from": match2.group(1).strip(),
                            "to": match2.group(2).strip(),
                            "message": match2.group(3).strip(),
                            "type": "call",
                        }
                    )
        return edges

    def _parse_state_diagram(self, lines: list[str]) -> tuple[list[str], list[dict]]:
        """解析 stateDiagram / stateDiagram-v2"""
        states = set()
        transitions = []
        depth = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("stateDiagram"):
                continue
            if stripped.endswith("{"):
                depth += 1
                continue
            if stripped == "}":
                depth -= 1
                continue
            if depth > 0:
                continue
            match = re.match(r"(\w+)\s*-->\s*(\w+)\s*:\s*(.+)", stripped)
            if match:
                from_s = match.group(1)
                to_s = match.group(2)
                trigger = match.group(3).strip()
                states.add(from_s)
                states.add(to_s)
                transitions.append({"from": from_s, "to": to_s, "trigger": trigger})
        return list(states), transitions

    @staticmethod
    def _clean_label(label: str) -> str:
        """清洗 graph 节点标签：去首尾引号、转义引号，取首行（去掉 \\n 后的描述后缀）。"""
        if not label:
            return label
        label = label.strip()
        # 去掉 mermaid 转义引号和首尾成对引号
        label = label.replace("&quot;", '"')
        if len(label) >= 2 and label[0] == '"' and label[-1] == '"':
            label = label[1:-1]
        # 含换行的复合标签（如 "Profile Intelligence\n本地 Agent 推理"）只取首段
        label = label.split("\\n", 1)[0].split("\n", 1)[0].strip()
        return label.strip('"').strip()

    def _parse_graph(self, lines: list[str]) -> tuple[list[dict], list[dict]]:
        """解析 graph LR/TB"""
        nodes = []
        edges = []
        node_ids = set()
        node_label_map = {}
        for line in lines:
            line = line.strip()
            if (
                line.startswith("graph ")
                or line.startswith("flowchart ")
                or line.startswith("subgraph")
            ):
                continue
            if line.startswith("end"):
                continue
            # 提取节点标签映射（支持 [] 和 () 两种形状）
            node_match = re.match(r"(\w+)\[(.+?)\]", line)
            if node_match:
                nid = node_match.group(1)
                label = self._clean_label(node_match.group(2))
                node_label_map[nid] = label
                if nid not in node_ids:
                    node_ids.add(nid)
                    nodes.append({"id": nid, "label": label})

            round_match = None
            if not any(line.startswith(kw) for kw in ("direction", "style", "class", "click")):
                round_match = re.match(r"(\w+)\((.+?)\)", line)
            if round_match:
                nid = round_match.group(1)
                label = self._clean_label(round_match.group(2))
                node_label_map[nid] = label
                if nid not in node_ids:
                    node_ids.add(nid)
                    nodes.append({"id": nid, "label": label})

            # Also extract nodes from anywhere in the line (after edges)
            # Find all node definitions with labels in the line
            all_square_nodes = re.findall(r"(\w+)\[(.+?)\]", line)
            for nid, label in all_square_nodes:
                label = self._clean_label(label)
                node_label_map[nid] = label
                if nid not in node_ids:
                    node_ids.add(nid)
                    nodes.append({"id": nid, "label": label})

            all_round_nodes = re.findall(r"(\w+)\((.+?)\)", line)
            for nid, label in all_round_nodes:
                label = self._clean_label(label)
                node_label_map[nid] = label
                if nid not in node_ids:
                    node_ids.add(nid)
                    nodes.append({"id": nid, "label": label})

            # 匹配边: A[...] -->|label| B[...] 或 A --> B
            clean_line = re.sub(r"\[.+?\]", "", line).strip()
            clean_line = re.sub(r"\(.+?\)", "", clean_line).strip()
            edge_match = re.match(r"(\w+)\s*-->(?:\|([^|]+)\|)?\s*(\w+)", clean_line)
            if edge_match:
                from_n = edge_match.group(1)
                label = edge_match.group(2)
                to_n = edge_match.group(3)
                if from_n not in node_ids:
                    node_ids.add(from_n)
                    display_label = node_label_map.get(from_n, from_n)
                    nodes.append({"id": from_n, "label": display_label})
                if to_n not in node_ids:
                    node_ids.add(to_n)
                    display_label = node_label_map.get(to_n, to_n)
                    nodes.append({"id": to_n, "label": display_label})
                edges.append(
                    {
                        "from": from_n,
                        "to": to_n,
                        "label": label.strip() if label else None,
                    }
                )
        return nodes, edges

    def _parse_c4_diagram(self, lines: list[str]) -> tuple[list[dict], list[dict]]:
        """解析 C4 图"""
        nodes = []
        edges = []
        for line in lines:
            line = line.strip()
            # Person/Container/System_Ext/ContainerDb etc.
            match = re.match(
                r'\s*(Person|System|System_Ext|Container|ContainerDb|Container_Boundary)\s*\(\s*(\w+)\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?(?:\s*,\s*"([^"]*)")?\s*\)',
                line,
            )
            if match:
                kind = match.group(1)
                nid = match.group(2)
                label = match.group(3)
                tech = match.group(4) or ""
                description = match.group(5) or ""
                nodes.append(
                    {
                        "id": nid,
                        "label": label,
                        "type": kind,
                        "tech": tech,
                        "description": description,
                    }
                )
            # Rel(A, B, "label", "protocol")
            rel_match = re.match(
                r'\s*Rel\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]*)")?\s*\)',
                line,
            )
            if rel_match:
                edges.append(
                    {
                        "from": rel_match.group(1),
                        "to": rel_match.group(2),
                        "label": rel_match.group(3),
                        "protocol": rel_match.group(4) or "",
                    }
                )
        return nodes, edges


class ArchDocParser:
    """架构文档解析器（支持单文件和多文件目录）"""

    def __init__(self) -> None:
        self.logger = get_logger("loader.arch_doc_parser")
        self.table_extractor = MarkdownTableExtractor()
        self.mermaid_extractor = MermaidExtractor()

    def parse(self, arch_path: str) -> ArchDoc:
        """解析架构文档（自动检测文件或目录）

        Args:
            arch_path: 架构文档路径（Markdown 文件或包含 .md 文件的目录）

        Returns:
            ArchDoc 对象
        """
        path = Path(arch_path)
        if path.is_dir():
            return self._parse_directory(path)
        else:
            return self._parse_single_file(path)

    # ============================================================
    # 多文件目录解析
    # ============================================================

    def _parse_directory(self, dir_path: Path) -> ArchDoc:
        """解析多文件架构目录"""
        self.logger.info(f"解析架构目录: {dir_path}")

        # 收集所有 .md 文件，按文件名排序
        md_files = sorted(dir_path.glob("*.md"))
        self.logger.info(f"发现 {len(md_files)} 个架构文件")

        # 初始化累积数据结构
        components: list[ComponentSpec] = []
        nfrs: list[NFR] = []
        interfaces: list[InterfaceDef] = []
        constraints: list[Constraint] = []
        internals: list[DesignArtifact] = []
        data_flow_steps: list[DataFlowStep] = []
        state_transitions: list[StateTransition] = []
        states: set[str] = set()
        openapi_paths: dict = {}
        openapi_components: dict = {}
        scope_parts: list[str] = []
        responsibilities: list[str] = []
        level_name = ""
        children_refs: list[str] = []
        external_dependencies: list[str] = []
        entity_owners: dict[str, str] = {}
        entity_details: dict[str, str] = {}

        for md_file in md_files:
            fname = md_file.name
            self.logger.debug(f"解析文件: {fname}")
            content = md_file.read_text(encoding="utf-8")

            if fname.lower() == "readme.md":
                # README 一般是导航/检查清单，不含结构化架构要素
                continue

            if fname.startswith("00"):
                # 00 前缀文件被视为严格 ArchDoc 汇总文档，整体并入
                parsed = self._parse_single_file(md_file)
                components.extend(parsed.components)
                entity_owners.update(parsed.entity_owners)
                entity_details.update(parsed.entity_details)
                interfaces.extend(parsed.interfaces)
                constraints.extend(parsed.constraints)
                internals.extend(parsed.internals)
                nfrs.extend(parsed.nfrs)
                data_flow_steps.extend(parsed.data_flow.sequence)
                if parsed.state_machine:
                    states.update(parsed.state_machine.states)
                    state_transitions.extend(parsed.state_machine.transitions)
                if parsed.openapi:
                    openapi_paths.update(parsed.openapi.paths)
                    openapi_components.update(parsed.openapi.components)
                if parsed.level_name and not level_name:
                    level_name = parsed.level_name
                continue

            # 按内容（而非文件名编号）分派：每个子解析器都按内容签名自过滤，
            # 无匹配时返回空，因此可安全地对每个文件运行全部解析器再合并。
            # 这样架构文档的编号方案与解析器的预期约定不一致时也能正确提取。
            piece = self._extract_from_content(content)
            components.extend(piece["components"])
            interfaces.extend(piece["interfaces"])
            constraints.extend(piece["constraints"])
            nfrs.extend(piece["nfrs"])
            internals.extend(piece["internals"])
            data_flow_steps.extend(piece["data_flow_steps"])
            states.update(piece["states"])
            state_transitions.extend(piece["transitions"])
            openapi_paths.update(piece["openapi_paths"])
            openapi_components.update(piece["openapi_components"])
            scope_parts.append(piece["scope"])
            responsibilities.extend(piece["responsibilities"])
            external_dependencies.extend(piece["external_dependencies"])
            children_refs.extend(piece["children_refs"])
            entity_owners.update(piece["entity_owners"])
            entity_details.update(piece["entity_details"])
            if piece["level_name"] and not level_name:
                level_name = piece["level_name"]

        # 从 data_flow_steps 构建 DataFlow
        data_flow = DataFlow(sequence=data_flow_steps)

        # 从 states + transitions 构建 StateMachine
        state_machine = StateMachine(
            states=list(states),
            transitions=state_transitions,
        )

        # 构建 OpenAPI
        openapi = OpenAPISpec(paths=openapi_paths, components=openapi_components)

        # 去重
        components = self._deduplicate_components(components)
        interfaces = self._deduplicate_interfaces(interfaces)
        constraints = self._deduplicate_constraints(constraints)
        responsibilities = list(dict.fromkeys(r for r in responsibilities if r))

        scope = "\n".join(s for s in scope_parts if s) or ""

        return ArchDoc(
            level_name=level_name or "system",
            level_depth=0,
            scope=scope,
            responsibilities=responsibilities,
            interfaces=interfaces,
            constraints=constraints,
            internals=internals,
            external_dependencies=list(dict.fromkeys(external_dependencies)),
            children_refs=children_refs,
            # 传统字段（向后兼容）
            openapi=openapi,
            data_flow=data_flow,
            state_machine=state_machine,
            nfrs=nfrs,
            components=components,
            entity_owners=entity_owners,
            entity_details=entity_details,
        )

    # ============================================================
    # 单文件解析（向后兼容）
    # ============================================================

    def _extract_from_content(self, content: str) -> dict:
        """按内容（而非文件名编号）从单个文件提取全部可识别的架构要素。

        每个子解析器按内容签名（Mermaid 图类型、表头、章节标记、代码块语言等）
        自过滤，无匹配时返回空结果，故可对任意文件安全地运行全部解析器再合并。
        """
        out: dict = {
            "components": [],
            "interfaces": [],
            "constraints": [],
            "nfrs": [],
            "internals": [],
            "data_flow_steps": [],
            "states": [],
            "transitions": [],
            "openapi_paths": {},
            "openapi_components": {},
            "scope": "",
            "responsibilities": [],
            "external_dependencies": [],
            "children_refs": [],
            "level_name": "",
            "level_depth": 0,
            "parent_ref": None,
            "entity_owners": {},
            "entity_details": {},
        }

        # C4 System Context -> 外部依赖 / 子系统 / scope
        p = self._parse_01_context_diagram(content)
        out["scope"] = p.get("scope", "")
        out["external_dependencies"].extend(p.get("external_systems", []))
        out["children_refs"].extend(p.get("subsystems", []))

        # 序列图 -> 数据流
        p = self._parse_02_domain_flow(content)
        out["data_flow_steps"].extend(p.get("steps", []))
        out["responsibilities"].extend(p.get("responsibilities", []))

        # graph LR（限界上下文/Context Map）-> 组件 + 拓扑数据流
        p = self._parse_03_bounded_context(content)
        out["components"].extend(p.get("components", []))
        out["responsibilities"].extend(p.get("responsibilities", []))
        out["data_flow_steps"].extend(p.get("data_flow_steps", []))

        # C4 Container -> 组件 + 接口
        p = self._parse_04_container_diagram(content)
        out["components"].extend(p.get("components", []))
        out["interfaces"].extend(p.get("interfaces", []))

        # ADR / 技术栈表 -> 约束 + 架构名
        p = self._parse_05_adr_summary(content)
        out["constraints"].extend(p.get("constraints", []))
        out["nfrs"].extend(p.get("nfrs", []))
        out["level_name"] = p.get("level_name", "")

        # 数据模型 / ENUM -> 内部制品 + 状态机
        p = self._parse_06_data_model(content)
        out["internals"].extend(p.get("internals", []))
        sm = p.get("state_machine", {})
        out["states"].extend(sm.get("states", []))
        for t in sm.get("transitions", []):
            out["transitions"].append(
                StateTransition(from_state=t["from"], to_state=t["to"], trigger=t["trigger"])
            )

        # 领域事件 -> 接口 + 内部制品
        p = self._parse_07_domain_events(content)
        out["internals"].extend(p.get("internals", []))
        out["interfaces"].extend(p.get("interfaces", []))

        # 接口契约（含 ### METHOD /path markdown 形式）-> 接口 + OpenAPI
        p = self._parse_08_interface_contracts(content)
        out["interfaces"].extend(p.get("interfaces", []))
        out["openapi_paths"].update(p.get("openapi_paths", {}))
        out["openapi_components"].update(p.get("openapi_components", {}))

        # 技术选型表 -> 约束
        p = self._parse_09_technology_choices(content)
        out["constraints"].extend(p.get("constraints", []))

        # 部署/伸缩/容灾表 -> 约束 + NFR
        p = self._parse_10_deployment(content)
        out["constraints"].extend(p.get("constraints", []))
        out["nfrs"].extend(p.get("nfrs", []))

        # 通用 Markdown 兜底（## 组件职责 / ## 非功能需求 表）
        out["components"].extend(self._extract_components(content))
        out["components"].extend(self._extract_components_from_headings(content))
        out["nfrs"].extend(self._extract_nfrs(content))
        out["entity_owners"].update(self._extract_entity_owners(content))
        out["entity_details"].update(self._extract_entity_details(content))

        package = self._extract_package_metadata(content)
        if package:
            self._apply_l1_package_conventions(out, content, package)

        return out

    def _parse_single_file(self, file_path: Path) -> ArchDoc:
        """解析单文件架构文档（向后兼容）

        优先走与目录解析一致的按内容提取（覆盖 C4/序列图/graph/Markdown 接口等），
        并合并传统的 YAML OpenAPI 与 Mermaid 状态机/数据流提取，确保严格单文件格式
        与聚合后的多图单文件都能完整提取。
        """
        content = file_path.read_text(encoding="utf-8")
        piece = self._extract_from_content(content)

        # 状态机：内容法（ENUM）合并传统 Mermaid stateDiagram
        states: set[str] = set(piece["states"])
        transitions = list(piece["transitions"])
        legacy_sm = self._extract_state_machine(content)
        states.update(legacy_sm.states)
        transitions.extend(legacy_sm.transitions)

        # 数据流：内容法（序列图）为空时回退传统提取
        data_flow = DataFlow(sequence=piece["data_flow_steps"])
        if not piece["data_flow_steps"]:
            data_flow = self._extract_data_flow(content)

        # OpenAPI：内容法（### METHOD /path）合并传统 YAML
        openapi_paths = dict(piece["openapi_paths"])
        openapi_components = dict(piece["openapi_components"])
        legacy_oa = self._extract_openapi(content)
        openapi_paths.update(legacy_oa.paths)
        openapi_components.update(legacy_oa.components)

        scope = "\n".join(s for s in [piece["scope"]] if s)

        return ArchDoc(
            level_name=piece["level_name"],
            level_depth=piece["level_depth"],
            parent_ref=piece["parent_ref"],
            scope=scope,
            responsibilities=list(dict.fromkeys(r for r in piece["responsibilities"] if r)),
            interfaces=self._deduplicate_interfaces(piece["interfaces"]),
            constraints=self._deduplicate_constraints(piece["constraints"]),
            internals=piece["internals"],
            external_dependencies=list(dict.fromkeys(piece["external_dependencies"])),
            children_refs=piece["children_refs"],
            openapi=OpenAPISpec(paths=openapi_paths, components=openapi_components),
            data_flow=data_flow,
            state_machine=StateMachine(states=list(states), transitions=transitions),
            nfrs=piece["nfrs"],
            components=self._deduplicate_components(piece["components"]),
            entity_owners=piece["entity_owners"],
            entity_details=piece["entity_details"],
        )

    def _extract_entity_owners(self, content: str) -> dict[str, str]:
        """Extract Aggregate/Entity -> Data Owner mappings from Markdown tables."""
        owners: dict[str, str] = {}
        aggregate_headers = {
            "aggregate",
            "aggregate root",
            "entity",
            "聚合",
            "聚合根",
            "实体",
            "状态/数据",
            "state/data",
        }
        owner_headers = {
            "data owner",
            "owner",
            "owner child_id",
            "数据所有者",
            "所有者",
        }
        for table in self.table_extractor.extract_all(content):
            normalized = {str(header).strip().lower(): header for header in table["headers"]}
            aggregate_header = next(
                (normalized[name] for name in aggregate_headers if name in normalized),
                None,
            )
            owner_header = next(
                (normalized[name] for name in owner_headers if name in normalized),
                None,
            )
            if not aggregate_header or not owner_header:
                continue
            for row in table["rows"]:
                entity = str(row.get(aggregate_header, "")).strip().strip("`")
                owner = str(row.get(owner_header, "")).strip().strip("`")
                if entity and owner:
                    owners[entity] = owner
        return owners

    def _extract_entity_details(self, content: str) -> dict[str, str]:
        """Extract searchable aggregate semantics from the same ownership tables."""
        details: dict[str, str] = {}
        aggregate_headers = {
            "aggregate",
            "aggregate root",
            "entity",
            "聚合",
            "聚合根",
            "实体",
            "状态/数据",
            "state/data",
        }
        owner_headers = {
            "data owner",
            "owner",
            "owner child_id",
            "数据所有者",
            "所有者",
        }
        for table in self.table_extractor.extract_all(content):
            normalized = {str(header).strip().lower(): header for header in table["headers"]}
            aggregate_header = next(
                (normalized[name] for name in aggregate_headers if name in normalized),
                None,
            )
            owner_header = next(
                (normalized[name] for name in owner_headers if name in normalized),
                None,
            )
            if not aggregate_header or not owner_header:
                continue
            for row in table["rows"]:
                entity = str(row.get(aggregate_header, "")).strip().strip("`")
                if not entity:
                    continue
                semantic_values = [
                    str(value).strip()
                    for header, value in row.items()
                    if header not in {aggregate_header, owner_header} and str(value).strip()
                ]
                if semantic_values:
                    details[entity] = "；".join(semantic_values)
        return details

    def _extract_package_metadata(self, content: str) -> dict[str, Any]:
        match = re.search(r"<!--\s*validate-arch-package:\s*(\{.*?\})\s*-->", content)
        if not match:
            return {}
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _clean_table_value(value: Any) -> str:
        return str(value or "").strip().strip("`").strip()

    @staticmethod
    def _row_value(row: dict[str, Any], *names: str) -> str:
        normalized = {str(key).strip().lower(): value for key, value in row.items()}
        for name in names:
            value = normalized.get(name.strip().lower())
            if value is not None:
                return ArchDocParser._clean_table_value(value)
        return ""

    @staticmethod
    def _expand_requirement_ids(value: str) -> list[str]:
        result: list[str] = []
        for prefix, start, end in re.findall(
            r"(?:(NFR|REQ)-)?D(\d{3})(?:\s*[~～\-–—]\s*(?:D)?(\d{3}))?",
            value,
            re.IGNORECASE,
        ):
            kind = (prefix or "REQ").upper()
            first = int(start)
            last = int(end) if end else first
            result.extend(f"{kind}-D{number:03d}" for number in range(first, last + 1))
        return list(dict.fromkeys(result))

    def _extract_child_registry(
        self, content: str, target_node_id: str
    ) -> tuple[list[ComponentSpec], dict[str, str]]:
        components: list[ComponentSpec] = []
        aliases: dict[str, str] = {}
        prefix = f"{target_node_id.strip().lower()}-" if target_node_id else ""
        for table in self.table_extractor.extract_all(content):
            headers = {str(header).strip().lower() for header in table["headers"]}
            if "child_id" not in headers or not (
                {"责任", "职责", "责任与拥有状态", "responsibility"} & headers
            ):
                continue
            for row in table["rows"]:
                child_id = self._row_value(row, "child_id")
                responsibility = self._row_value(
                    row, "责任", "职责", "责任与拥有状态", "responsibility"
                )
                if not child_id:
                    continue
                allocation = self._row_value(
                    row,
                    "分配需求",
                    "已分配状态/需求",
                    "requirements",
                )
                support_match = re.search(r"(?:支持|supports?)\s*[:：]?\s*(.*)$", allocation, re.I)
                owned_allocation = (
                    allocation[: support_match.start()] if support_match else allocation
                )
                requirements = self._expand_requirement_ids(owned_allocation)
                supports = (
                    self._expand_requirement_ids(support_match.group(1)) if support_match else []
                )
                if requirements:
                    responsibility = f"{responsibility} Requirements: {' '.join(requirements)}"
                if supports:
                    responsibility = f"{responsibility} Supports: {' '.join(supports)}"
                raw_dispatch_kind = self._row_value(
                    row,
                    "dispatch_kind",
                    "component_kind",
                    "派发类型",
                    "组件类型",
                    "运行类型",
                ).strip().lower()
                raw_dispatch_kind = {
                    "组件": "component",
                    "容器": "container",
                    "数据存储": "datastore",
                    "数据库": "datastore",
                    "外部": "external",
                    "标题": "heading",
                }.get(raw_dispatch_kind, raw_dispatch_kind)
                dispatch_kind: Literal[
                    "component", "container", "datastore", "external", "heading"
                ] | None = (
                    cast(
                        Literal["component", "container", "datastore", "external", "heading"],
                        raw_dispatch_kind,
                    )
                    if raw_dispatch_kind
                    in {"component", "container", "datastore", "external", "heading"}
                    else None
                )
                components.append(
                    ComponentSpec(
                        name=child_id,
                        responsibility=responsibility,
                        dispatch_kind=dispatch_kind,
                    )
                )
                aliases[child_id.lower()] = child_id
                local_name = child_id
                if prefix and child_id.lower().startswith(prefix):
                    local_name = child_id[len(prefix) :]
                aliases[local_name.lower()] = child_id
        return self._deduplicate_components(components), aliases

    @staticmethod
    def _component_terms(value: str) -> set[str]:
        translations = {
            "契约": "contract",
            "解析器": "resolver",
            "外呼": "outbound",
            "执行器": "executor",
            "候选": "candidate",
            "标准化器": "normalizer",
            "历史": "history",
            "适配器": "adapter",
            "诊断": "diagnostic",
            "边界": "boundary",
            "搜索": "search",
            "检索": "search",
        }
        text = value.lower()
        terms = set(re.findall(r"[a-z0-9]+", text))
        for source, target in translations.items():
            if source in value:
                terms.add(target)
        return terms

    def _canonical_component_ref(
        self,
        value: str,
        components: list[ComponentSpec],
        aliases: dict[str, str],
    ) -> str:
        cleaned = self._clean_table_value(value)
        cleaned = re.sub(r"[（(].*?[）)]", "", cleaned).strip()
        if not cleaned:
            return ""
        direct = aliases.get(cleaned.lower())
        if direct:
            return direct
        signal_terms = self._component_terms(cleaned)
        role_terms = {"resolver", "executor", "normalizer", "adapter", "boundary"}
        if not (signal_terms & role_terms):
            return cleaned
        scored: list[tuple[int, str]] = []
        for component in components:
            component_terms = self._component_terms(component.name)
            overlap = len(signal_terms & component_terms)
            if overlap and (signal_terms <= component_terms or overlap >= 2):
                scored.append((overlap, component.name))
        scored.sort(reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return scored[0][1]
        return cleaned

    def _extract_l1_contract_tables(
        self,
        content: str,
        package: dict[str, Any],
        components: list[ComponentSpec],
        aliases: dict[str, str],
    ) -> list[InterfaceDef]:
        interfaces: list[InterfaceDef] = []
        internal_names = {component.name for component in components}
        current_name = str(
            package.get("current_node_name") or package.get("target_node_id") or ""
        )
        for table in self.table_extractor.extract_all(content):
            headers = {str(header).strip().lower() for header in table["headers"]}
            is_parent = ({"父契约", "父级契约"} & headers) and (
                {"当前实现子节点", "l1 实现节点"} & headers
            )
            is_internal = ({"契约 id", "contract_id"} & headers) and (
                {"所有者 → 消费者", "owner → consumer"} & headers
            )
            if not is_parent and not is_internal:
                continue
            for row in table["rows"]:
                if is_parent:
                    contract_id = self._row_value(row, "父契约", "父级契约")
                    schema = self._row_value(row, "不可变字段/语义", "固定语义")
                    role = self._row_value(row, "角色", "Provider → Consumer")
                    implementation = self._row_value(row, "当前实现子节点", "L1 实现节点")
                    errors = self._row_value(row, "失败、幂等与版本", "错误、幂等与兼容性")
                    direct_chain = sorted(
                        (
                            (implementation.find(component.name), component.name)
                            for component in components
                            if component.name in implementation
                        ),
                        key=lambda item: item[0],
                    )
                    chain = [item[1] for item in direct_chain]
                    if not chain:
                        chain = [
                            self._canonical_component_ref(item, components, aliases)
                            for item in re.split(r"\s*(?:→|->)\s*", implementation)
                        ]
                        chain = [item for item in chain if item in internal_names]
                    role_parts = re.split(r"\s*(?:→|->)\s*", role, maxsplit=1)
                    if len(role_parts) > 1:
                        provider = self._clean_table_value(role_parts[0])
                        consumer = self._clean_table_value(role_parts[1])
                    else:
                        provider_match = re.search(r"([^；;]+?)\s*提供方", role)
                        consumer_match = re.search(r"([^；;]+?)\s*消费方", role)
                        provider = (
                            self._clean_table_value(provider_match.group(1))
                            if provider_match
                            else ""
                        )
                        consumer = (
                            self._clean_table_value(consumer_match.group(1))
                            if consumer_match
                            else ""
                        )
                    if chain and current_name and current_name in provider:
                        provider = chain[0]
                    if chain and current_name and current_name in consumer:
                        consumer = chain[0]
                    if not provider and chain:
                        provider = chain[0]
                    contract_type = "module_contract"
                else:
                    contract_id = self._row_value(row, "契约 ID", "contract_id")
                    schema = self._row_value(row, "触发与 schema", "触发与 schema 摘要")
                    owner_consumer = self._row_value(row, "所有者 → 消费者", "Owner → Consumer")
                    errors = self._row_value(row, "错误、幂等、兼容性", "错误、幂等与兼容性")
                    pair = re.split(r"\s*(?:→|->)\s*", owner_consumer, maxsplit=1)
                    provider = self._canonical_component_ref(pair[0], components, aliases)
                    consumer_values = re.split(r"[、,，]", pair[1] if len(pair) > 1 else "")
                    consumers = [
                        self._canonical_component_ref(item, components, aliases)
                        for item in consumer_values
                        if item.strip()
                    ]
                    consumer = ", ".join(consumers)
                    chain = [item for item in [provider, *consumers] if item in internal_names]
                    contract_type = "internal_port"
                if not contract_id:
                    continue
                interfaces.append(
                    InterfaceDef(
                        name=contract_id,
                        direction="outbound",
                        protocol=contract_type,
                        contract={
                            "contract_id": contract_id,
                            "contract_type": contract_type,
                            "provider": provider,
                            "consumer": consumer,
                            "required": self._extract_io_fields(schema, output=False),
                            "response": self._extract_io_fields(schema, output=True),
                            "schema": schema,
                            "errors": errors,
                            "implementation_chain": chain,
                        },
                        description=f"{provider} → {consumer}" if provider or consumer else "",
                    )
                )
        return interfaces

    def _extract_l1_nfrs_and_constraints(self, content: str) -> tuple[list[NFR], list[Constraint]]:
        nfrs: list[NFR] = []
        constraints: list[Constraint] = []
        for table in self.table_extractor.extract_all(content):
            headers = {str(header).strip().lower() for header in table["headers"]}
            if "当前需求" in headers and "本层落实" in headers:
                for row in table["rows"]:
                    requirement_id = self._row_value(row, "当前需求")
                    if not requirement_id.startswith("NFR-"):
                        continue
                    detail = self._row_value(row, "本层落实")
                    threshold = re.search(r"(\d+(?:\.\d+)?)\s*(秒|毫秒|ms|s|%|条)", detail)
                    if threshold:
                        nfrs.append(
                            NFR(
                                id=requirement_id,
                                metric=detail,
                                threshold=float(threshold.group(1)),
                                unit=threshold.group(2),
                            )
                        )
                    else:
                        constraints.append(
                            Constraint(
                                type="nfr",
                                description=detail,
                                target=requirement_id,
                            )
                        )
            if "继承规则" in headers and "本包约束" in headers:
                for row in table["rows"]:
                    rule_id = self._row_value(row, "ID")
                    description = self._row_value(row, "继承规则")
                    value = self._row_value(row, "本包约束")
                    if description:
                        constraints.append(
                            Constraint(
                                type="invariant",
                                description=description,
                                target=rule_id or None,
                                value=value or None,
                            )
                        )
        return nfrs, constraints

    def _apply_l1_package_conventions(
        self, out: dict[str, Any], content: str, package: dict[str, Any]
    ) -> None:
        components, aliases = self._extract_child_registry(
            content, str(package.get("target_node_id") or "")
        )
        if not components:
            return
        internal_names = {component.name for component in components}
        out["components"] = components
        out["children_refs"] = [component.name for component in components]
        out["level_name"] = str(
            package.get("current_node_name") or package.get("target_node_id") or out["level_name"]
        )
        level_match = re.search(r"(\d+)", str(package.get("level") or ""))
        out["level_depth"] = int(level_match.group(1)) if level_match else 0
        out["parent_ref"] = str(package.get("parent_ref") or "") or None
        responsibility = str(package.get("responsibility") or "")
        if responsibility:
            out["scope"] = responsibility
            out["responsibilities"].append(responsibility)

        canonical_steps: list[DataFlowStep] = []
        external: list[str] = list(out["external_dependencies"])
        seen_steps: set[tuple[str, str, str, str]] = set()
        for step in out["data_flow_steps"]:
            source = self._canonical_component_ref(step.from_component, components, aliases)
            target = self._canonical_component_ref(step.to_component, components, aliases)
            if source not in internal_names:
                external.append(source)
            if target not in internal_names:
                external.append(target)
            key = (source, target, step.action, step.message or "")
            if key in seen_steps:
                continue
            seen_steps.add(key)
            canonical_steps.append(
                DataFlowStep(
                    from_component=source,
                    to_component=target,
                    action=step.action,
                    message=step.message,
                )
            )
        out["data_flow_steps"] = canonical_steps
        out["external_dependencies"] = list(
            dict.fromkeys(item for item in external if item and item not in internal_names)
        )

        out["interfaces"].extend(
            self._extract_l1_contract_tables(content, package, components, aliases)
        )
        out["entity_owners"] = {
            entity: self._canonical_component_ref(owner, components, aliases)
            for entity, owner in out["entity_owners"].items()
        }
        nfrs, constraints = self._extract_l1_nfrs_and_constraints(content)
        out["nfrs"].extend(nfrs)
        out["constraints"].extend(constraints)
        self._extract_l1_lifecycle(content, out)
        out["internals"].append(
            DesignArtifact(
                type="other",
                format="table",
                content="Authoritative child registry: " + ", ".join(sorted(internal_names)),
            )
        )

    def _extract_l1_lifecycle(self, content: str, out: dict[str, Any]) -> None:
        """提取 L1 文档中反引号包裹的简洁生命周期链。"""
        seen = {(transition.from_state, transition.to_state) for transition in out["transitions"]}
        for lifecycle in re.findall(r"`([^`]*[→>-][^`]*)`", content):
            states = [part.strip() for part in re.split(r"\s*(?:→|--?>)\s*", lifecycle)]
            if len(states) < 2 or any(
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", state) for state in states
            ):
                continue
            out["states"].extend(state for state in states if state not in out["states"])
            for source, target in zip(states, states[1:]):
                if (source, target) in seen:
                    continue
                seen.add((source, target))
                out["transitions"].append(
                    StateTransition(
                        from_state=source,
                        to_state=target,
                        trigger="documented lifecycle",
                    )
                )

    # ============================================================
    # 各文件类型解析方法
    # ============================================================

    def _parse_01_context_diagram(self, content: str) -> dict:
        """解析 01-context-diagram.md"""
        result: dict[str, Any] = {"scope": "", "external_systems": [], "subsystems": []}

        # 提取 Overview 段落作为 scope
        overview_match = re.search(r"##?\s*Overview\s*\n\n?(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if overview_match:
            result["scope"] = overview_match.group(1).strip()

        # 解析 C4Context Mermaid
        diagrams = self.mermaid_extractor.extract_all(content)
        for d in diagrams:
            if d["type"] == "c4_context":
                for node in d["elements"].get("nodes", []):
                    if node.get("type") == "System_Ext":
                        result["external_systems"].append(node.get("label", node["id"]))
                    elif node.get("type") == "System":
                        result["subsystems"].append(node.get("label", node["id"]))

        return result

    def _parse_02_domain_flow(self, content: str) -> dict:
        """解析 02-domain-flow.md"""
        result: dict[str, Any] = {"steps": [], "responsibilities": []}

        diagrams = self.mermaid_extractor.extract_all(content)
        for d in diagrams:
            if d["type"] == "sequence_diagram":
                for edge in d["elements"].get("edges", []):
                    result["steps"].append(
                        DataFlowStep(
                            from_component=edge["from"],
                            to_component=edge["to"],
                            action=edge["type"],
                            message=edge.get("message", ""),
                        )
                    )

        # 从流程标题提取 responsibilities
        for match in re.finditer(r"##\s*Process-\d+:\s*(.+)", content):
            result["responsibilities"].append(match.group(1).strip())

        return result

    def _parse_03_bounded_context(self, content: str) -> dict:
        """解析 03-bounded-context-diagram.md"""
        result: dict[str, Any] = {"components": [], "responsibilities": [], "data_flow_steps": []}

        # 解析 graph LR/TB 中的节点作为 components
        diagrams = self.mermaid_extractor.extract_all(content)
        for d in diagrams:
            if d["type"] in ("graph_lr", "graph_tb", "graph_bt"):
                nodes = d["elements"].get("nodes", [])
                # id -> label 映射，用于把边的端点从 id 还原为可读组件名
                id_to_label = {
                    node.get("id", node.get("label")): node.get("label", node.get("id"))
                    for node in nodes
                }
                for node in nodes:
                    label = node.get("label", node.get("id"))
                    result["components"].append(
                        ComponentSpec(
                            name=label,
                            responsibility=f"Bounded Context: {label}",
                        )
                    )
                # graph 边作为模块拓扑数据流（端点用 label，与模块表英文名一致）
                for edge in d["elements"].get("edges", []):
                    src = id_to_label.get(edge.get("from"), edge.get("from"))
                    dst = id_to_label.get(edge.get("to"), edge.get("to"))
                    if src and dst:
                        result["data_flow_steps"].append(
                            DataFlowStep(
                                from_component=src,
                                to_component=dst,
                                action="call",
                                message=edge.get("label") or "",
                            )
                        )

        # 解析关系矩阵表格
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            if "Upstream" in table["headers"] and "Downstream" in table["headers"]:
                for row in table["rows"]:
                    upstream = row.get("Upstream", "")
                    downstream = row.get("Downstream", "")
                    pattern = row.get("Pattern", "")
                    if upstream and downstream:
                        result["responsibilities"].append(f"{upstream} -> {downstream} ({pattern})")

        return result

    def _parse_04_container_diagram(self, content: str) -> dict:
        """解析 04-container-diagram.md"""
        result: dict[str, Any] = {"components": [], "interfaces": []}

        diagrams = self.mermaid_extractor.extract_all(content)
        for d in diagrams:
            if d["type"] == "c4_container":
                for node in d["elements"].get("nodes", []):
                    if node.get("type") in ("Container", "ContainerDb"):
                        responsibility = node.get("description") or node.get("type", "")
                        result["components"].append(
                            ComponentSpec(
                                name=node.get("label", node["id"]),
                                responsibility=responsibility,
                                tech_stack=node.get("tech", None),
                                dispatch_kind=(
                                    "datastore" if node.get("type") == "ContainerDb" else "container"
                                ),
                            )
                        )
                for edge in d["elements"].get("edges", []):
                    result["interfaces"].append(
                        InterfaceDef(
                            name=f"{edge['from']}->{edge['to']}",
                            direction="outbound",
                            protocol=edge.get("protocol", ""),
                            contract={"label": edge.get("label", "")},
                        )
                    )

        # 解析接口标注表格
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers_lower = [h.lower() for h in table["headers"]]
            if any("protocol" in h for h in headers_lower):
                for row in table["rows"]:
                    proto = row.get("Protocol", row.get("protocol", ""))
                    fmt = row.get("Data Format", row.get("format", ""))
                    if proto:
                        result["interfaces"].append(
                            InterfaceDef(
                                name=f"接口_{len(result['interfaces']) + 1}",
                                direction="inbound",
                                protocol=proto,
                                contract={"format": fmt},
                            )
                        )

        return result

    def _parse_05_adr_summary(self, content: str) -> dict:
        """解析 05-adr-summary.md"""
        result: dict[str, Any] = {"constraints": [], "nfrs": [], "level_name": ""}

        # 提取架构名称
        title_match = re.search(r"#\s+(.+)", content)
        if title_match:
            result["level_name"] = title_match.group(1).strip()

        # 提取 Technology Stack 表格作为约束
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers = [h.lower() for h in table["headers"]]
            if any("technology" in h for h in headers):
                for row in table["rows"]:
                    tech = row.get("Technology", row.get("technology", ""))
                    where = row.get("Where Used", row.get("where used", ""))
                    if tech:
                        result["constraints"].append(
                            Constraint(
                                type="assumption",
                                description=f"使用 {tech} 于 {where}",
                                target=where,
                                value=tech,
                            )
                        )

        return result

    def _parse_06_data_model(self, content: str) -> dict:
        """解析 06-data-model.md"""
        result: dict[str, Any] = {
            "internals": [],
            "state_machine": {"states": [], "transitions": []},
        }

        # 提取每个 BC 的数据模型表格作为 DesignArtifact
        sections = re.split(r"\n##\s*BC-\d+:", content)
        for section in sections[1:]:
            bc_name = section.split("\n", 1)[0].strip()
            tables = self.table_extractor.extract_all(section)
            for table in tables:
                result["internals"].append(
                    DesignArtifact(
                        type="erd",
                        format="table",
                        content=f"BC: {bc_name}\nHeaders: {table['headers']}\nRows: {len(table['rows'])}",
                    )
                )

        # 从 Task 状态 ENUM 提取状态机状态
        status_match = re.search(r"status\s*ENUM\s*([^\n]+)", content, re.IGNORECASE)
        if status_match:
            enum_str = status_match.group(1)
            states = re.findall(r"[A-Z_]+", enum_str)
            result["state_machine"]["states"] = states

        # 也搜索所有 ENUM 定义作为状态
        for enum_match in re.finditer(r"ENUM\s*([^\n]+)", content, re.IGNORECASE):
            enum_str = enum_match.group(1)
            states = re.findall(r"[A-Z_]+", enum_str)
            result["state_machine"]["states"].extend(states)

        result["state_machine"]["states"] = list(dict.fromkeys(result["state_machine"]["states"]))

        return result

    def _parse_07_domain_events(self, content: str) -> dict:
        """解析 07-domain-events.md"""
        result: dict[str, Any] = {"internals": [], "interfaces": []}

        # 解析 Publisher/Consumer 矩阵
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers = [h.lower() for h in table["headers"]]
            if "event name" in headers or "publisher" in headers:
                for row in table["rows"]:
                    event = row.get("Event Name", row.get("event name", ""))
                    topic = row.get("Topic", row.get("topic", ""))
                    if event:
                        result["interfaces"].append(
                            InterfaceDef(
                                name=event,
                                direction="outbound",
                                protocol="kafka",
                                contract={"topic": topic, "delivery": "async"},
                            )
                        )

        # 解析 Protobuf 代码块为 DesignArtifact
        protobuf_blocks = self._extract_code_blocks(content, "protobuf")
        for block in protobuf_blocks:
            result["internals"].append(
                DesignArtifact(
                    type="openapi",
                    format="text",
                    content=block,
                )
            )

        return result

    def _extract_json_keys(self, block: str) -> list[str]:
        """从 JSON 字符串中提取顶层 key。"""
        try:
            data = json.loads(block)
        except Exception:
            return []
        if isinstance(data, dict):
            return list(data.keys())
        return []

    def _parse_interface_section(self, section: str) -> Optional[InterfaceDef]:
        """解析单个接口小节，提取方法/路径/输入字段/输出字段。"""
        m = re.search(r"(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)", section)
        if not m:
            return None
        method = m.group(1)
        path = m.group(2).strip()

        input_fields: list[str] = []
        output_fields: list[str] = []

        # 找到所有 ```json 块，并按其前面的 输入/输出 标签分类
        for code_match in re.finditer(r"```json\s*(.*?)\s*```", section, re.DOTALL):
            block = code_match.group(1)
            preceding = section[: code_match.start()]
            context = preceding[-200:]
            keys = self._extract_json_keys(block)
            if "输出" in context:
                output_fields.extend(keys)
            elif "输入" in context:
                input_fields.extend(keys)
            elif re.search(r"[-*]\s*\*\*输入\*\*", context):
                input_fields.extend(keys)

        return InterfaceDef(
            name=f"{method} {path}",
            direction="inbound",
            protocol="HTTP/JSON",
            contract={
                "method": method,
                "path": path,
                "required": input_fields,
                "response": output_fields,
            },
        )

    def _parse_contract_id_section(self, section: str) -> Optional[InterfaceDef]:
        """解析 ``### `contract_id` `` + ``| Field | Contract |`` 表形式的契约块。

        覆盖形如：
            ### `recommendation_request_command`
            | Field | Contract |
            |---|---|
            | `contract_id` | `recommendation_request_command` |
            | `contract_type` | `command_api` |
            | Provider | Recommendation Orchestration |
            | Consumer | ... |
            | Schema | 输入：`a`, `b`; 输出：`c`, `d` |
        """
        # 第一行为小节标题；从标题反引号中取 contract_id
        first_line = section.split("\n", 1)[0].strip()
        title_ids = re.findall(r"`([^`]+)`", first_line)
        if not title_ids:
            return None

        # 必须含 Field/Contract 表才按本格式处理
        tables = self.table_extractor.extract_all(section)
        field_table = None
        for table in tables:
            headers_lower = [h.lower() for h in table["headers"]]
            if "field" in headers_lower and "contract" in headers_lower:
                field_table = table
                break
        if field_table is None:
            return None

        # 表行 -> {field: value}（field 大小写不敏感归一）
        rows: dict[str, str] = {}
        for row in field_table["rows"]:
            keys = list(row.keys())
            if len(keys) < 2:
                continue
            field_key = row[keys[0]].strip().strip("`").strip()
            val = row[keys[1]].strip()
            if field_key:
                rows[field_key.lower()] = val

        contract_id = rows.get("contract_id", "").strip().strip("`") or title_ids[0]
        contract_type = rows.get("contract_type", "").strip().strip("`") or "contract"
        provider = rows.get("provider", "").strip()
        consumer = rows.get("consumer", "").strip()
        schema = rows.get("schema", "").strip()
        side_effects = rows.get("side_effects", "").strip()
        dependencies = rows.get("dependencies", "").strip()
        errors = rows.get("error / timeout / retry", "") or rows.get("error/timeout/retry", "")

        # 从 Schema 解析 输入/输出 字段
        required = self._extract_io_fields(schema, output=False)
        response = self._extract_io_fields(schema, output=True)

        contract: dict[str, Any] = {
            "contract_id": contract_id,
            "contract_type": contract_type,
            "provider": provider,
            "consumer": consumer,
            "required": required,
            "response": response,
            "schema": schema,
            "side_effects": side_effects,
            "dependencies": dependencies,
            "errors": errors.strip(),
        }
        return InterfaceDef(
            name=contract_id,
            direction="outbound",
            protocol=contract_type,
            contract=contract,
            description=f"{provider} → {consumer}" if provider or consumer else "",
        )

    def _extract_io_fields(self, schema: str, output: bool) -> list[str]:
        """从 Schema 文本中提取输入/输出或请求/响应字段。

        ``输出=False`` 取 ``输入/请求``，``输出=True`` 取 ``输出/响应``。
        """
        if not schema:
            return []
        markers = ("输出", "响应") if output else ("输入", "请求")
        matches = [(schema.find(marker), marker) for marker in markers if schema.find(marker) != -1]
        if not matches:
            return []
        idx, marker = min(matches)
        tail = schema[idx + len(marker) :]
        tail = re.sub(r"^\s*[:：]\s*", "", tail)
        next_stop = re.search(r"(?:输入|输出|请求|响应)\s*[:：]|[；。]", tail)
        segment = tail[: next_stop.start()] if next_stop else tail
        fields: list[str] = []
        for token in re.findall(r"`([^`]+)`", segment):
            fields.extend(part.strip() for part in re.split(r"[,，]", token) if part.strip())
        return fields

    def _parse_08_interface_contracts(self, content: str) -> dict:
        """解析 08-interface-contracts.md"""
        result: dict[str, Any] = {"interfaces": [], "openapi_paths": {}, "openapi_components": {}}

        # 按 ### 标题拆分成小节，逐个解析同步 API 契约
        sections = re.split(r"\n###\s+", content)
        for section in sections[1:]:
            itf = self._parse_interface_section(section)
            if itf is None:
                # 回退：解析 `### \`contract_id\`` + Field/Contract 表形式的契约块
                itf = self._parse_contract_id_section(section)
            if itf is None:
                continue
            result["interfaces"].append(itf)
            path = itf.contract.get("path", "")
            method = itf.contract.get("method", "").lower()
            if path and method:
                result["openapi_paths"].setdefault(path, {})[method] = {}

        # 提取 gRPC Protobuf 为 InterfaceDef
        grpc_sections = re.split(r"##\s*\d+\.\s*", content)
        for section in grpc_sections:
            if "service " in section.lower():
                svc_match = re.search(r"service\s+(\w+)\s*\{", section)
                if svc_match:
                    svc_name = svc_match.group(1)
                    result["interfaces"].append(
                        InterfaceDef(
                            name=svc_name,
                            direction="outbound",
                            protocol="gRPC/Protobuf",
                            contract={"content": section[:500]},
                        )
                    )

        # 提取错误码表格
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers = [h.lower() for h in table["headers"]]
            if "code" in headers and "meaning" in headers:
                for row in table["rows"]:
                    code = row.get("Code", row.get("code", ""))
                    meaning = row.get("Meaning", row.get("meaning", ""))
                    if code:
                        result["interfaces"].append(
                            InterfaceDef(
                                name=f"Error:{code}",
                                direction="outbound",
                                protocol="error_code",
                                contract={"meaning": meaning},
                            )
                        )

        return result

    def _parse_09_technology_choices(self, content: str) -> dict:
        """解析 09-technology-choices.md"""
        result: dict[str, Any] = {"constraints": []}

        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers = [h.lower() for h in table["headers"]]
            if "technology" in headers or "decision driver" in headers:
                for row in table["rows"]:
                    tech = row.get("Technology / Product", row.get("technology", ""))
                    driver = row.get("Decision Driver", row.get("decision driver", ""))
                    if tech:
                        result["constraints"].append(
                            Constraint(
                                type="assumption",
                                description=f"技术选型: {tech}",
                                value=tech,
                                target=driver,
                            )
                        )
            # Version Constraints
            if "version" in headers or "current" in headers:
                for row in table["rows"]:
                    item = row.get("Current", row.get("current", ""))
                    target_v = row.get("Target", row.get("target", ""))
                    if item:
                        result["constraints"].append(
                            Constraint(
                                type="dependency",
                                description=f"迁移路径: {item} -> {target_v}",
                                target=item,
                                value=target_v,
                            )
                        )

        return result

    def _parse_10_deployment(self, content: str) -> dict:
        """解析 10-deployment.md"""
        result: dict[str, Any] = {"constraints": [], "nfrs": []}

        # 解析部署拓扑 Mermaid
        diagrams = self.mermaid_extractor.extract_all(content)
        for d in diagrams:
            if d["type"] == "graph_tb":
                # 将部署图存为 DesignArtifact 的引用
                pass

        # 解析扩展策略表格
        tables = self.table_extractor.extract_all(content)
        for table in tables:
            headers = [h.lower() for h in table["headers"]]
            # Scaling Strategy
            if "component" in headers and "min instances" in headers:
                for row in table["rows"]:
                    comp = row.get("Component", "")
                    min_i = row.get("Min Instances", "")
                    max_i = row.get("Max Instances", "")
                    if comp:
                        result["constraints"].append(
                            Constraint(
                                type="nfr",
                                description=f"{comp} 伸缩策略",
                                target=comp,
                                value=f"min={min_i}, max={max_i}",
                            )
                        )
            # QAS / Availability
            if "requirement" in headers or "implementation" in headers:
                for row in table["rows"]:
                    req = row.get("Requirement", row.get("requirement", ""))
                    impl = row.get("Implementation", row.get("implementation", ""))
                    if req:
                        # 尝试提取时间值作为 NFR
                        time_match = re.search(r"(\d+)(秒|s|分钟|min)", req, re.IGNORECASE)
                        if time_match:
                            val = float(time_match.group(1))
                            unit = time_match.group(2)
                            result["nfrs"].append(
                                NFR(
                                    id=f"DEP-{len(result['nfrs']) + 1:03d}",
                                    metric=req[:30],
                                    threshold=val,
                                    unit=unit,
                                )
                            )
                        else:
                            result["constraints"].append(
                                Constraint(
                                    type="nfr",
                                    description=req,
                                    target="deployment",
                                    value=impl,
                                )
                            )
            # Fault Tolerance
            if "failure scenario" in headers or "rto" in headers:
                for row in table["rows"]:
                    scenario = row.get("Failure Scenario", "")
                    rto = row.get("RTO", "")
                    if scenario:
                        result["constraints"].append(
                            Constraint(
                                type="invariant",
                                description=f"容灾: {scenario}",
                                target="fault_tolerance",
                                value=rto,
                            )
                        )
            # Monitoring
            if "metric" in headers and "threshold" in headers:
                for row in table["rows"]:
                    metric = row.get("Metric", "")
                    threshold = row.get("Threshold", "")
                    if metric:
                        result["constraints"].append(
                            Constraint(
                                type="nfr",
                                description=f"监控: {metric}",
                                target="monitoring",
                                value=threshold,
                            )
                        )

        return result

    # ============================================================
    # 通用辅助方法
    # ============================================================

    def _extract_code_blocks(self, content: str, language: str) -> list[str]:
        """提取所有指定语言的代码块内容"""
        pattern = rf"```{language}\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)
        return [m.strip() for m in matches]

    def _extract_code_block(self, content: str, language: str) -> str:
        """提取第一个指定语言的代码块内容"""
        pattern = rf"```{language}\n(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _deduplicate_components(self, components: list[ComponentSpec]) -> list[ComponentSpec]:
        """按 name 去重组件；同名时优先保留权威职责（模块清单表的真实描述），
        而非 flowchart 兜底的 ``Bounded Context: ...`` / ``Module: ...`` / ``BC: ...``。"""
        best: dict[str, ComponentSpec] = {}
        order: list[str] = []
        for c in components:
            if c.name not in best:
                best[c.name] = c
                order.append(c.name)
            elif _is_authoritative_responsibility(
                c.responsibility
            ) and not _is_authoritative_responsibility(best[c.name].responsibility):
                best[c.name] = c
        return [best[n] for n in order]

    def _deduplicate_interfaces(self, interfaces: list[InterfaceDef]) -> list[InterfaceDef]:
        """按 name+protocol 去重接口"""
        seen = set()
        result = []
        for i in interfaces:
            key = (i.name, i.protocol)
            if key not in seen:
                seen.add(key)
                result.append(i)
        return result

    def _deduplicate_constraints(self, constraints: list[Constraint]) -> list[Constraint]:
        """按 description 去重约束"""
        seen = set()
        result = []
        for c in constraints:
            if c.description not in seen:
                seen.add(c.description)
                result.append(c)
        return result

    # ============================================================
    # 单文件向后兼容解析方法（保留原有逻辑）
    # ============================================================

    def _extract_openapi(self, content: str) -> OpenAPISpec:
        """提取 OpenAPI YAML 代码块"""
        yaml_content = self._extract_code_block(content, "yaml")
        if not yaml_content:
            return OpenAPISpec()

        try:
            data = yaml.safe_load(yaml_content)
            return OpenAPISpec(
                paths=data.get("paths", {}),
                components=data.get("components", {}),
            )
        except yaml.YAMLError:
            return OpenAPISpec()

    def _extract_data_flow(self, content: str) -> DataFlow:
        """提取 Mermaid sequenceDiagram（向后兼容）"""
        mermaid_blocks = self._extract_code_blocks(content, "mermaid")

        for block in mermaid_blocks:
            if "sequenceDiagram" in block:
                lines = block.strip().split("\n")
                sequence = []

                for line in lines:
                    line = line.strip()
                    if line.startswith("sequenceDiagram"):
                        continue

                    # 匹配: A->>B: message 或 A-->>B: message
                    match = re.match(r"([\w-]+)\s*-?>>\s*([\w-]+)\s*:\s*(.+)", line)
                    if match:
                        from_c = match.group(1)
                        to_c = match.group(2)
                        msg = match.group(3).strip()
                        sequence.append(
                            DataFlowStep(
                                from_component=from_c,
                                to_component=to_c,
                                action="call",
                                message=msg,
                            )
                        )

                return DataFlow(sequence=sequence)

        return DataFlow()

    def _extract_state_machine(self, content: str) -> StateMachine:
        """提取 Mermaid stateDiagram-v2（向后兼容）"""
        mermaid_blocks = self._extract_code_blocks(content, "mermaid")

        for block in mermaid_blocks:
            if "stateDiagram" in block:
                lines = block.strip().split("\n")
                states = set()
                transitions = []

                depth = 0
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("stateDiagram") or stripped.startswith("[*]"):
                        continue
                    if stripped.endswith("{"):
                        depth += 1
                        continue
                    if stripped == "}":
                        depth -= 1
                        continue
                    if depth > 0:
                        continue
                    match = re.match(r"(\w+)\s*-->\s*(\w+)\s*:\s*(.+)", stripped)
                    if match:
                        from_s = match.group(1)
                        to_s = match.group(2)
                        trigger = match.group(3).strip()
                        states.add(from_s)
                        states.add(to_s)
                        transitions.append(
                            StateTransition(
                                from_state=from_s,
                                to_state=to_s,
                                trigger=trigger,
                                action=None,
                            )
                        )

                return StateMachine(states=list(states), transitions=transitions)

        return StateMachine()

    def _extract_nfrs(self, content: str) -> list[NFR]:
        """提取 NFR Markdown 表格（向后兼容）"""
        nfrs = []

        # 查找 NFR 表格
        table_match = re.search(
            r"##\s*非功能需求.*?\n\|(.+?)\|\n\|[-| ]+\|\n(.*?)(?=\n##|\Z)",
            content,
            re.DOTALL,
        )

        if table_match:
            rows_text = table_match.group(2)
            for row in rows_text.strip().split("\n"):
                row = row.strip()
                if not row.startswith("|"):
                    continue
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) >= 4:
                    try:
                        nfrs.append(
                            NFR(
                                id=cells[0],
                                metric=cells[1],
                                threshold=float(cells[2]),
                                unit=cells[3],
                            )
                        )
                    except (ValueError, IndexError):
                        continue

        return nfrs

    def _extract_components_from_headings(self, content: str) -> list[ComponentSpec]:
        """从 Markdown 标题中提取组件（兜底）。

        适用于 bounded-contexts.md 这类用 ## User Center 标题描述 BC 的文档。
        通过上下文关键词过滤，避免把普通章节标题识别为组件。
        """
        components: list[ComponentSpec] = []
        positive_kws = (
            "Bounded Context",
            "职责",
            "Responsibility",
            "Aggregate Roots",
            "聚合根",
            "Component",
            "组件",
        )
        negative_kws = {
            "Overview",
            "Scope",
            "Introduction",
            "Conclusion",
            "References",
            "Summary",
            "Flow",
            "Flows",
            "Characteristics",
            "NFR",
            "Interface",
            "Interfaces",
            "Contract",
            "Contracts",
            "Technology",
            "Deployment",
            "Data Model",
            "Domain Events",
            "ADR",
            "Constraints",
            "Architecture",
            "Diagram",
            "Bounded Contexts",
            "Context Map",
            "Aggregate Roots and Boundaries",
            "Data Ownership Rules",
            "QAS Traceability",
            "FR Coverage",
            "Consistency Check",
            "C4 System Context",
            "映射",
            "Mapping",
        }

        for match in re.finditer(r"^#{2,3}\s+([A-Z][\w\s/]+?)(?:\s*\n)", content, re.MULTILINE):
            name = match.group(1).strip()
            if name in negative_kws or any(nw in name for nw in negative_kws):
                continue
            # 只看标题后一小段，避免跨章节误匹配
            snippet = content[match.start() : match.start() + 300]
            if not any(kw in snippet for kw in positive_kws):
                continue
            # 尝试提取职责
            resp_match = re.search(
                r"[-*]\s*\*\*Responsibility\*\*[:：]\s*(.+?)(?:\n|$)", snippet
            ) or re.search(r"[-*]\s*\*\*职责\*\*[:：]\s*(.+?)(?:\n|$)", snippet)
            responsibility = (
                resp_match.group(1).strip() if resp_match else f"Bounded Context: {name}"
            )
            components.append(ComponentSpec(name=name, responsibility=responsibility))

        # 中文限界上下文/运行时元素表格兜底
        components.extend(self._extract_components_from_chinese_tables(content))
        # 通用模块清单表 / BC→Module 映射表兜底
        components.extend(self._extract_components_from_module_tables(content))
        return components

    def _extract_components_from_module_tables(self, content: str) -> list[ComponentSpec]:
        """从「模块清单」表与「BC→Module 映射」表中提取组件。

        覆盖形如 ``| Module | Responsibility | … |`` 与 ``| Bounded Context | Module | … |``
        的表格，不依赖特定章节标题，按表头签名匹配。
        """
        components: list[ComponentSpec] = []
        for table in self.table_extractor.extract_all(content):
            headers = [h.strip() for h in table["headers"]]
            headers_lower = [h.lower() for h in headers]
            has_module = any("module" in h or "模块" in h for h in headers_lower + headers)
            has_resp = any("responsibility" in h or "职责" in h for h in headers_lower + headers)
            has_bc = any("bounded context" in h for h in headers_lower)

            def cell(row: dict[str, Any], *candidates: str) -> str:
                for key in candidates:
                    value = row.get(key)
                    if value:
                        return str(value)
                # 大小写不敏感回退
                lower_map = {k.lower(): v for k, v in row.items()}
                for key in candidates:
                    value = lower_map.get(key.lower())
                    if value:
                        return str(value)
                return ""

            if has_module and has_resp:
                # 模块清单表：Module + Responsibility
                for row in table["rows"]:
                    name = cell(row, "Module", "模块")
                    resp = cell(row, "Responsibility", "职责", "一句话职责")
                    if name:
                        components.append(
                            ComponentSpec(
                                name=name.strip(),
                                responsibility=resp.strip() or f"Module: {name.strip()}",
                            )
                        )
            elif has_bc and has_module:
                # BC→Module 映射表：取 Module 作为组件名，BC 作为职责上下文
                for row in table["rows"]:
                    name = cell(row, "Module", "模块")
                    bc = cell(row, "Bounded Context", "限界上下文")
                    rationale = cell(row, "Mapping Rationale", "Rationale", "映射理由")
                    if name:
                        resp = f"BC: {bc} → {name}" if bc else rationale or f"Module: {name}"
                        components.append(
                            ComponentSpec(name=name.strip(), responsibility=resp.strip())
                        )
        return components

    def _extract_components_from_chinese_tables(self, content: str) -> list[ComponentSpec]:
        """从中文架构文档的限界上下文表、运行时元素表中提取组件。"""
        components: list[ComponentSpec] = []

        # 限界上下文表：表头通常包含 BC（中文）/BC（英文）/Responsibility
        bc_match = re.search(
            r"^#{2,3}\s+(?:\d+(?:\.\d+)*\s+)?限界上下文.*?\n\|(.+?)\|\n\|[-\| ]+\|\n(.*?)(?=\n#{1,3}\s|\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )
        if bc_match:
            headers = [c.strip() for c in bc_match.group(1).split("|") if c.strip()]
            # 优先用英文 BC 列，否则用中文 BC 列
            bc_en_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "BC（英文）" in h or "BC(English)" in h or h.strip().lower() == "bc"
                ),
                None,
            )
            bc_cn_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "BC（中文）" in h or "BC(中文)" in h or h.strip() == "BC"
                ),
                None,
            )
            resp_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "职责" in h or "Responsibility" in h or "一句话职责" in h
                ),
                None,
            )
            for row in bc_match.group(2).strip().split("\n"):
                if not row.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if not cells:
                    continue
                name = None
                if bc_en_idx is not None and bc_en_idx < len(cells) and cells[bc_en_idx]:
                    name = cells[bc_en_idx]
                elif bc_cn_idx is not None and bc_cn_idx < len(cells) and cells[bc_cn_idx]:
                    name = cells[bc_cn_idx]
                elif len(cells) >= 2:
                    name = cells[1] if cells[1] else cells[0]
                if not name or name.lower() in ("bc", "bc（英文）", "bc（中文）"):
                    continue
                responsibility = (
                    cells[resp_idx]
                    if resp_idx is not None and resp_idx < len(cells)
                    else f"Bounded Context: {name}"
                )
                components.append(ComponentSpec(name=name, responsibility=responsibility))

        # 运行时元素表：表头通常包含 Element/Type/Responsibility
        rt_match = re.search(
            r"^#{2,3}\s+(?:\d+(?:\.\d+)*\s+)?运行时元素.*?\n\|(.+?)\|\n\|[-\| ]+\|\n(.*?)(?=\n#{1,3}\s|\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )
        if rt_match:
            headers = [c.strip() for c in rt_match.group(1).split("|") if c.strip()]
            element_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if h.strip().lower() in ("element", "元素", "组件", "container", "容器")
                ),
                0,
            )
            type_idx = next(
                (i for i, h in enumerate(headers) if h.strip().lower() in ("type", "类型")),
                None,
            )
            resp_idx = next(
                (
                    i
                    for i, h in enumerate(headers)
                    if "职责" in h or "Responsibility" in h or "responsibility" in h.lower()
                ),
                None,
            )
            for row in rt_match.group(2).strip().split("\n"):
                if not row.strip().startswith("|"):
                    continue
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if not cells or element_idx >= len(cells) or not cells[element_idx]:
                    continue
                name = cells[element_idx]
                comp_type = (
                    cells[type_idx] if type_idx is not None and type_idx < len(cells) else ""
                )
                responsibility = (
                    cells[resp_idx]
                    if resp_idx is not None and resp_idx < len(cells)
                    else f"{comp_type}: {name}" if comp_type else name
                )
                components.append(
                    ComponentSpec(name=name, responsibility=responsibility, tech_stack=None)
                )

        return components

    def _extract_components(self, content: str) -> list[ComponentSpec]:
        """提取组件职责表（向后兼容）"""
        components = []

        # 查找组件表格
        table_match = re.search(
            r"##\s*组件职责.*?\n\|(.+?)\|\n\|[-| ]+\|\n(.*?)(?=\n##|\Z)",
            content,
            re.DOTALL,
        )

        if table_match:
            rows_text = table_match.group(2)
            for row in rows_text.strip().split("\n"):
                row = row.strip()
                if not row.startswith("|"):
                    continue
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) >= 2:
                    components.append(
                        ComponentSpec(
                            name=cells[0],
                            responsibility=cells[1],
                            tech_stack=cells[2] if len(cells) > 2 else None,
                        )
                    )

        return components
