"""CMP-AE-EVALUATION-COORDINATOR + RESULT-ASSEMBLER + OUTCOME-CLASSIFIER（L12）。

单次评估尝试的装配流水线：

1. ICT-002：经注入的 PromptComposerPort 组装 evaluation_prompt（含 prompt/rubric 版本）；
2. ICT-003：经注入的 MaterialReadPort 只读加载材料内容（MOD-02 所有权，不转移）；
3. ICT-004：组装 CT-010 请求（数据最小化，KD-001：不含 submission_id/姓名/小组/
   课程等任何业务标识），调用注入的 ModelProvider（Phase 1 仅 FakeModelProvider，
   禁止真实供应商与任何网络调用）；
4. L2-AE-001：按 CT-010 response schema 校验应答；
5. L2-AE-002：装配 ICT-005 成功载荷（与 L03 complete_assessment 关键字参数兼容）；
6. L2-AE-003：失败三分类 + 端口失败分类，装配 ICT-006 载荷
   （与 L03 fail_assessment 兼容；重试/终态决策归编排器，本节点不决定）。

fake 可追溯性：FakeModelProvider 的输出仅用于链路测试，不表达真实评估能力；
结果 model_meta 与日志均标注 provider=fake 来源，绝不假扮真实评估。
日志仅含 task_id/request_id/耗时/版本/错误分类，不含材料内容与业务标识。
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..model_provider import (
    FakeModelProvider,
    ModelProvider,
    ModelProviderError,
    validate_request,
)

from .errors import (
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MATERIAL_UNREADABLE,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    ERROR_PROMPT_ASSEMBLY_FAILED,
    MODEL_ERROR_KINDS,
    MaterialUnreadableError,
    PromptAssemblyFailedError,
    ResponseValidationError,
)
from .impact import build_missing_materials_impact
from .ports import MaterialReadPort, PromptComposerPort
from .validator import validate_model_response

logger = logging.getLogger(__name__)

# CT-010 materials 三个最小化桶 ← CT-004 材料类别的映射（LCD-005 细化归 backfill；
# 未识别类别折叠进 result_description 并带类别标签，不外发类别以外的标识）。
_BUCKET_BY_CATEGORY = {
    "对话": "dialogue_summary",
    "对话摘要": "dialogue_summary",
    "dialogue": "dialogue_summary",
    "dialogue_summary": "dialogue_summary",
    "代码": "code",
    "code": "code",
    "结果描述": "result_description",
    "result": "result_description",
    "result_description": "result_description",
}
_CT010_MATERIAL_BUCKETS = ("dialogue_summary", "code", "result_description")

_FAKE_PROVIDER_TRACE = (
    "deterministic fake output for pipeline testing only; not a real assessment"
)


@dataclass(frozen=True)
class AssessmentOutcome:
    """一次评估尝试的装配结果。

    ok=True：payload 为 ICT-005 载荷，键为 L03 complete_assessment 的关键字参数
    （task_id/owner 由调用方自 ClaimedTask 补充）。
    ok=False：payload 为 ICT-006 载荷 {error_kind, attempt_no, at}，与
    L03 fail_assessment 兼容（at 对应其 now 参数）。
    """

    ok: bool
    attempt_no: int
    payload: dict
    error_kind: str | None = None


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AssessmentEngine:
    """五维评估装配执行器（无持久状态；一次 attempt 一个调用）。"""

    def __init__(
        self,
        prompt_composer: PromptComposerPort,
        material_reader: MaterialReadPort,
        model_provider: ModelProvider,
    ) -> None:
        self._prompt_composer = prompt_composer
        self._material_reader = material_reader
        self._model_provider = model_provider

    # ------------------------------------------------------------------ API

    def run(self, task: Any) -> AssessmentOutcome:
        """执行一次评估尝试；task 为 L03 ClaimedTask 形状（duck-typed）。

        需要的属性：task_id, assignment, material_refs, missing_items, attempt_no。
        任何失败均返回分类后的 AssessmentOutcome，不抛出、不伪造等级。
        """
        attempt_no = task.attempt_no
        try:
            composed = self._compose_prompt(task)
            materials = self._load_materials(task)
            return self._invoke_and_assemble(task, attempt_no, composed, materials)
        except PromptAssemblyFailedError as exc:
            return self._fail(task, attempt_no, ERROR_PROMPT_ASSEMBLY_FAILED, exc)
        except MaterialUnreadableError as exc:
            return self._fail(task, attempt_no, ERROR_MATERIAL_UNREADABLE, exc)

    # ------------------------------------------------------------- pipeline

    def _compose_prompt(self, task: Any) -> dict:
        composed = self._prompt_composer.compose(
            assignment=task.assignment,
            material_refs=task.material_refs,
            missing_items=task.missing_items,
        )
        if (
            not isinstance(composed, dict)
            or not isinstance(composed.get("evaluation_prompt"), str)
            or not composed.get("evaluation_prompt")
            or not isinstance(composed.get("prompt_version"), str)
            or not composed.get("prompt_version")
            or not isinstance(composed.get("rubric_version"), str)
            or not composed.get("rubric_version")
        ):
            raise PromptAssemblyFailedError(
                "ICT-002 output must carry evaluation_prompt/prompt_version/rubric_version"
            )
        return composed

    def _load_materials(self, task: Any) -> dict:
        loaded = self._material_reader.load(task.material_refs)
        if not isinstance(loaded, dict) or not isinstance(loaded.get("materials"), dict):
            raise MaterialUnreadableError(
                "ICT-003 output must carry a materials mapping of category to content"
            )
        contents = loaded["materials"]
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in contents.items()):
            raise MaterialUnreadableError("ICT-003 materials must map str category to str content")
        return contents

    def _invoke_and_assemble(
        self, task: Any, attempt_no: int, composed: dict, contents: dict
    ) -> AssessmentOutcome:
        request_id = uuid.uuid4().hex  # 每次尝试新值；不携带任何业务标识
        request = {
            "evaluation_prompt": composed["evaluation_prompt"],
            "materials": self._minimize_materials(contents),
            "request_id": request_id,
        }
        problems = validate_request(request)
        if problems:
            # 本地组装缺陷（绝不应外发）：不外发、归类 MODEL_ERROR。
            logger.error(
                "L12 ct010 request assembly defect task_id=%s problems=%s",
                task.task_id,
                problems,
            )
            return self._fail(task, attempt_no, ERROR_MODEL_ERROR, problems)

        is_fake = isinstance(self._model_provider, FakeModelProvider)
        provider_name = type(self._model_provider).__name__
        started = time.perf_counter()
        try:
            response = self._model_provider.evaluate(request)
        except TimeoutError as exc:
            return self._fail(task, attempt_no, ERROR_MODEL_TIMEOUT, exc)
        except ModelProviderError as exc:
            kind = getattr(exc, "error_kind", None)
            if kind not in MODEL_ERROR_KINDS:
                kind = ERROR_MODEL_ERROR
            return self._fail(task, attempt_no, kind, exc)
        except Exception as exc:  # noqa: BLE001 — 未知异常不得静默转成功
            logger.exception(
                "L12 unexpected provider error task_id=%s attempt_no=%d",
                task.task_id,
                attempt_no,
            )
            return self._fail(task, attempt_no, ERROR_MODEL_ERROR, exc)
        duration_ms = int((time.perf_counter() - started) * 1000)

        try:
            validated = validate_model_response(response)
        except ResponseValidationError as exc:
            return self._fail(task, attempt_no, ERROR_INVALID_RESPONSE_SCHEMA, exc)

        payload = {
            "attempt_no": attempt_no,
            "original_grade": validated["grade"],
            "dimension_rationales": validated["dimension_rationales"],
            "teacher_suggestions": validated["suggestions"],
            "scored_at": _utcnow_naive(),
            "missing_materials_impact": build_missing_materials_impact(task.missing_items),
            "prompt_version": composed["prompt_version"],
            "rubric_version": composed["rubric_version"],
            "model_meta": {
                "request_id": request_id,
                "duration_ms": duration_ms,
                "attempt_no": attempt_no,
                "provider": provider_name,
                "is_fake_provider": is_fake,
                "provider_trace": (
                    _FAKE_PROVIDER_TRACE if is_fake else "model provider via ICT-004 ACL port"
                ),
            },
        }
        logger.info(
            "L12 assessment assembled task_id=%s attempt_no=%d request_id=%s "
            "provider=%s fake=%s duration_ms=%d prompt_version=%s rubric_version=%s",
            task.task_id,
            attempt_no,
            request_id,
            provider_name,
            is_fake,
            duration_ms,
            composed["prompt_version"],
            composed["rubric_version"],
        )
        return AssessmentOutcome(ok=True, attempt_no=attempt_no, payload=payload)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _minimize_materials(contents: dict) -> dict:
        """按类别把材料内容折叠进 CT-010 三个最小化桶（KD-001 数据最小化）。"""
        buckets: dict[str, list[str]] = {name: [] for name in _CT010_MATERIAL_BUCKETS}
        for category, content in contents.items():
            bucket = _BUCKET_BY_CATEGORY.get(category)
            if bucket is None:
                buckets["result_description"].append(f"[{category}]\n{content}")
            else:
                buckets[bucket].append(content)
        return {name: "\n".join(parts) for name, parts in buckets.items()}

    def _fail(
        self, task: Any, attempt_no: int, error_kind: str, detail: Any
    ) -> AssessmentOutcome:
        at = _utcnow_naive()
        logger.warning(
            "L12 assessment failed task_id=%s attempt_no=%d error_kind=%s detail=%s",
            task.task_id,
            attempt_no,
            error_kind,
            detail,
        )
        return AssessmentOutcome(
            ok=False,
            attempt_no=attempt_no,
            error_kind=error_kind,
            payload={"error_kind": error_kind, "attempt_no": attempt_no, "at": at},
        )
