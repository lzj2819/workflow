"""L12 CMP-ASSESSMENT-ENGINE：五维评估装配、缺失材料影响说明。Phase 3 (W2) 实现。"""
from .engine import AssessmentEngine, AssessmentOutcome
from .errors import (
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MATERIAL_UNREADABLE,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    ERROR_PROMPT_ASSEMBLY_FAILED,
    MaterialUnreadableError,
    PromptAssemblyFailedError,
    ResponseValidationError,
)
from .impact import build_missing_materials_impact
from .ports import MaterialReadPort, PromptComposerPort
from .validator import validate_model_response

__all__ = [
    "ERROR_INVALID_RESPONSE_SCHEMA",
    "ERROR_MATERIAL_UNREADABLE",
    "ERROR_MODEL_ERROR",
    "ERROR_MODEL_TIMEOUT",
    "ERROR_PROMPT_ASSEMBLY_FAILED",
    "AssessmentEngine",
    "AssessmentOutcome",
    "MaterialReadPort",
    "MaterialUnreadableError",
    "PromptAssemblyFailedError",
    "PromptComposerPort",
    "ResponseValidationError",
    "build_missing_materials_impact",
    "validate_model_response",
]
