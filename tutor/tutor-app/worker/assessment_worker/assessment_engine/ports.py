"""L12 端口协议：ICT-002（rubric composer）与 ICT-003（材料只读加载）。

两端口均以依赖注入方式提供；本叶子不实现其真实逻辑（归 backfill / MOD-02），
测试中注入 stub。模型调用（ICT-004）直接使用
`assessment_worker.model_provider.ModelProvider` 协议（Phase 1 仅 FakeModelProvider）。
"""
from __future__ import annotations

from typing import Protocol


class PromptComposerPort(Protocol):
    """ICT-002 ComposeEvaluationPrompt：纯组装、无副作用、同版本同输入同输出。

    返回 {"evaluation_prompt": str, "prompt_version": str, "rubric_version": str}；
    失败抛 `PromptAssemblyFailedError`（映射 ICT-006 PROMPT_ASSEMBLY_FAILED）。
    """

    def compose(
        self,
        assignment: str,
        material_refs: list,
        missing_items: list,
    ) -> dict:
        ...


class MaterialReadPort(Protocol):
    """ICT-003 LoadMaterialContents：MOD-02 所有的材料只读端口。

    返回 {"materials": {类别: 内容文本}, "readability": [...]}；
    IO 失败抛 `MaterialUnreadableError`（映射 ICT-006 MATERIAL_UNREADABLE）。
    只读：不得修改或转移材料所有权。
    """

    def load(self, material_refs: list) -> dict:
        ...
