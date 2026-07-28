"""RubricPromptComposer：ICT-002 ComposeEvaluationPrompt 的真实实现。

从 PG（单测 SQLite）读取 ST-004 唯一 active RubricPolicy，纯组装
evaluation_prompt：模板正文的 {{assignment}} / {{material_manifest}} /
{{missing_declaration}} 占位符按固定顺序逐一替换。无副作用、无 IO（除
策略只读查询）、同版本同输入同输出（ICT-002 幂等口径）。

失败（无 active 策略 / 多 active / 模板缺占位符 / 维度存证缺失）抛
L12 `PromptAssemblyFailedError`，由引擎映射 ICT-006 PROMPT_ASSEMBLY_FAILED。
数据最小化（KD-001）：材料清单仅取类别标注，不取 filename/ref 等标识；
缺失声明口径与 assessment_engine.impact.build_missing_materials_impact 一致。
"""
from __future__ import annotations

import sqlalchemy as sa

from assessment_worker.assessment_engine.errors import PromptAssemblyFailedError

from .models import STATUS_ACTIVE, RubricPolicy

# 模板占位符（与迁移 0011 种子 v1 模板一致；按此固定顺序逐一替换）
TOKEN_ASSIGNMENT = "{{assignment}}"
TOKEN_MATERIAL_MANIFEST = "{{material_manifest}}"
TOKEN_MISSING_DECLARATION = "{{missing_declaration}}"
REQUIRED_TOKENS = (
    TOKEN_ASSIGNMENT,
    TOKEN_MATERIAL_MANIFEST,
    TOKEN_MISSING_DECLARATION,
)

_NO_MATERIALS_LINE = "- （未声明材料）"
_NO_MISSING_LINE = "本次提交材料完整，无缺失类别。"
_MISSING_HEADER = "本次评估缺少以下材料类别："
_MISSING_ITEM_LINE = "- {item}：该类别材料缺失，对应维度仅能依据其余已提供材料推断"


def build_material_manifest(material_refs: list) -> str:
    """材料清单：仅类别标注（KD-001），保持输入顺序（确定性）。"""
    lines: list[str] = []
    for ref in material_refs:
        category = ref.get("category") if isinstance(ref, dict) else None
        if isinstance(category, str) and category:
            lines.append(f"- 类别：{category}")
        else:
            raise PromptAssemblyFailedError(
                "material_refs entries must carry a non-empty category"
            )
    return "\n".join(lines) if lines else _NO_MATERIALS_LINE


def build_missing_declaration(missing_items: list) -> str:
    """缺失材料声明：口径与 L12 build_missing_materials_impact 一致。"""
    if not missing_items:
        return _NO_MISSING_LINE
    lines = [_MISSING_HEADER]
    for item in missing_items:
        if not isinstance(item, str) or not item:
            raise PromptAssemblyFailedError("missing_items entries must be non-empty strings")
        lines.append(_MISSING_ITEM_LINE.format(item=item))
    return "\n".join(lines)


class RubricPromptComposer:
    """ICT-002 端口实现（PromptComposerPort 形状）；构造接收既有 Session。

    事务边界归调用方：本类只读查询，不 commit/rollback。
    """

    def __init__(self, session) -> None:
        self._session = session

    # ------------------------------------------------------------------ API

    def compose(self, assignment: str, material_refs: list, missing_items: list) -> dict:
        """组装 evaluation_prompt；返回 {evaluation_prompt, prompt_version, rubric_version}。"""
        if not isinstance(assignment, str) or not assignment:
            raise PromptAssemblyFailedError("assignment must be a non-empty string")
        policy = self._load_active_policy()

        prompt = policy.template_body
        replacements = (
            (TOKEN_ASSIGNMENT, assignment),
            (TOKEN_MATERIAL_MANIFEST, build_material_manifest(material_refs)),
            (TOKEN_MISSING_DECLARATION, build_missing_declaration(missing_items)),
        )
        for token, value in replacements:
            prompt = prompt.replace(token, value)
        return {
            "evaluation_prompt": prompt,
            "prompt_version": policy.prompt_version,
            "rubric_version": policy.rubric_version,
        }

    # -------------------------------------------------------------- helpers

    def _load_active_policy(self) -> RubricPolicy:
        """读取唯一 active 策略（ST-004 单版本一致读取）。"""
        rows = (
            self._session.execute(
                sa.select(RubricPolicy)
                .where(RubricPolicy.status == STATUS_ACTIVE)
                .order_by(RubricPolicy.id)
            )
            .scalars()
            .all()
        )
        if not rows:
            raise PromptAssemblyFailedError("no active rubric policy (ST-004 missing)")
        if len(rows) > 1:
            # 同库 active 唯一由迁移部分唯一索引保证；此处仅为防御性兜底。
            raise PromptAssemblyFailedError("multiple active rubric policies")
        policy = rows[0]
        for token in REQUIRED_TOKENS:
            if token not in policy.template_body:
                raise PromptAssemblyFailedError(
                    f"rubric template missing required token {token}"
                )
        if not isinstance(policy.dimensions, list) or not policy.dimensions:
            raise PromptAssemblyFailedError("rubric policy dimensions missing")
        return policy
