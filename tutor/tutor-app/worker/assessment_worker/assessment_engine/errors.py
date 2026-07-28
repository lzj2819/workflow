"""L12 CMP-ASSESSMENT-ENGINE 本地错误与 ICT-006 失败分类。

错误分类与 L03 orchestrator 的 ERROR_TAXONOMY 一致（只读引用其语义，不重定义）：
- MODEL_TIMEOUT / MODEL_ERROR / INVALID_RESPONSE_SCHEMA：CT-010 模型类三分类（REQ-012）；
- MATERIAL_UNREADABLE / PROMPT_ASSEMBLY_FAILED：ICT-003 / ICT-002 端口失败的本层扩展分类。
"""
from __future__ import annotations

ERROR_MODEL_TIMEOUT = "MODEL_TIMEOUT"
ERROR_MODEL_ERROR = "MODEL_ERROR"
ERROR_INVALID_RESPONSE_SCHEMA = "INVALID_RESPONSE_SCHEMA"
ERROR_MATERIAL_UNREADABLE = "MATERIAL_UNREADABLE"
ERROR_PROMPT_ASSEMBLY_FAILED = "PROMPT_ASSEMBLY_FAILED"

MODEL_ERROR_KINDS = (
    ERROR_MODEL_TIMEOUT,
    ERROR_MODEL_ERROR,
    ERROR_INVALID_RESPONSE_SCHEMA,
)


class PromptAssemblyFailedError(RuntimeError):
    """ICT-002 提示组装失败（准则/模板缺失或端口输出非法）。"""


class MaterialUnreadableError(RuntimeError):
    """ICT-003 材料只读端口 IO 失败（声明缺失的 missing_items 不属于此错误）。"""


class ResponseValidationError(RuntimeError):
    """模型应答未通过 CT-010 response schema / 领域校验；映射 INVALID_RESPONSE_SCHEMA。"""
