"""SkillPromptGateway — 抽象基类，用于在 Skill 模式下执行 Agent Prompt.

定义了 Simulator、Validator、Modifier 三个角色的 prompt 执行接口，
以及相关的异常类型。
"""

import asyncio
import hashlib
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from mock_framework.agents.local_auto_responder import LocalAutoResponder
from mock_framework.logger import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger("skill_gateway")


class PromptExecutionError(Exception):
    """Prompt 执行失败时抛出的异常."""

    pass


class SchemaValidationError(Exception):
    """返回结果不符合预期 Schema 时抛出的异常."""

    pass


class SkillPromptGateway(ABC):
    """Skill 模式下的 Prompt 执行网关抽象基类.

    子类需要实现三个抽象方法，分别对应 Simulator、Validator、Modifier
    的 prompt 执行逻辑。所有方法均为异步，返回经 schema 验证后的结构化对象.
    """

    @abstractmethod
    async def execute_simulator_prompt(
        self,
        prompt: str,
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 60,
    ) -> T:
        """执行 Simulator 的 prompt.

        Args:
            prompt: 发送给 LLM 的完整 prompt 文本.
            schema: 期望返回的 Pydantic BaseModel 子类.
            max_retries: 执行失败时的最大重试次数.
            timeout_seconds: 单次执行的超时时间（秒）.

        Returns:
            经 schema 验证后的结构化对象.

        Raises:
            PromptExecutionError: prompt 执行失败（如网络错误、超时）.
            SchemaValidationError: 返回结果无法通过 schema 验证.
        """
        ...

    @abstractmethod
    async def execute_validator_prompt(
        self,
        prompt: str,
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 60,
    ) -> T:
        """执行 Validator 的 prompt.

        Args:
            prompt: 发送给 LLM 的完整 prompt 文本.
            schema: 期望返回的 Pydantic BaseModel 子类.
            max_retries: 执行失败时的最大重试次数.
            timeout_seconds: 单次执行的超时时间（秒）.

        Returns:
            经 schema 验证后的结构化对象.

        Raises:
            PromptExecutionError: prompt 执行失败（如网络错误、超时）.
            SchemaValidationError: 返回结果无法通过 schema 验证.
        """
        ...

    @abstractmethod
    async def execute_modifier_prompt(
        self,
        prompt: str,
        schema: Type[T],
        auto_modify: bool = False,
    ) -> T:
        """执行 Modifier 的 prompt.

        Args:
            prompt: 发送给 LLM 的完整 prompt 文本.
            schema: 期望返回的 Pydantic BaseModel 子类.
            auto_modify: 是否自动将修改写入架构文档.

        Returns:
            经 schema 验证后的结构化对象.

        Raises:
            PromptExecutionError: prompt 执行失败（如网络错误、超时）.
            SchemaValidationError: 返回结果无法通过 schema 验证.
        """
        ...

    @abstractmethod
    async def execute_simulator_prompts_batch(
        self,
        prompts: list[str],
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> list[T]:
        """批量执行 Simulator prompt.

        Args:
            prompts: 多个 prompt 文本.
            schema: 期望返回的 Pydantic BaseModel 子类.
            max_retries: 执行失败时的最大重试次数.
            timeout_seconds: 单次执行的超时时间（秒）.

        Returns:
            与 prompts 顺序一致的结构化对象列表.

        Raises:
            PromptExecutionError: prompt 执行失败.
            SchemaValidationError: 返回结果无法通过 schema 验证.
        """
        ...

    @abstractmethod
    async def execute_validator_prompts_batch(
        self,
        prompts: list[str],
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> list[T]:
        """批量执行 Validator prompt."""
        ...


class ClaudeCodeSkillGateway(SkillPromptGateway):
    """Claude Code Skill 模式下的 Prompt 执行网关.

    通过文件 IPC 与 Claude Code 进行通信：
    1. 将 prompt 写入临时文件
    2. 通过 stdout 打印标记通知 Claude Code
    3. 轮询等待结果文件
    4. 读取结果后清理临时文件
    """

    TMP_DIR = Path(".claude/skills/validate-arch/.tmp")

    def __init__(self, cache_size: int = 128) -> None:
        """初始化网关，创建临时目录并清理旧文件."""
        self._logger = get_logger("ClaudeCodeSkillGateway")
        self.TMP_DIR.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_files()
        self._local_responder: Optional[LocalAutoResponder] = None
        if os.environ.get("MOCK_FRAMEWORK_LOCAL_AUTO_RESPOND") == "1":
            self._local_responder = LocalAutoResponder()
            self._logger.info("LocalAutoResponder enabled via MOCK_FRAMEWORK_LOCAL_AUTO_RESPOND=1")

        # Prompt 级 LRU 缓存：只缓存通过文件 IPC 的成功响应
        self._cache_size = cache_size
        self._prompt_cache: dict[str, Any] = {}
        self._cache_order: list[str] = []
        self._cache_hits = 0
        self._cache_misses = 0

        # 从磁盘恢复缓存（在内存 LRU 限制内）
        self._load_cache_entries_into_memory()

    def _cache_key(self, agent_type: str, prompt: str, schema: Type[T]) -> str:
        """基于 agent 类型、prompt 内容和 schema 生成缓存键."""
        schema_name = getattr(schema, "__name__", str(schema))
        content = f"{agent_type}:{schema_name}:{prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def _get_cached(self, key: str) -> Optional[Any]:
        """读取缓存并更新 LRU 顺序."""
        if key not in self._prompt_cache:
            return None
        self._cache_order.remove(key)
        self._cache_order.append(key)
        self._cache_hits += 1
        return self._prompt_cache[key]

    def _set_cached(self, key: str, value: Any) -> None:
        """写入缓存并维护 LRU 淘汰."""
        if key in self._prompt_cache:
            self._cache_order.remove(key)
        elif len(self._prompt_cache) >= self._cache_size:
            lru_key = self._cache_order.pop(0)
            del self._prompt_cache[lru_key]
        self._prompt_cache[key] = value
        self._cache_order.append(key)
        self._cache_misses += 1
        self._save_cache_to_disk()

    def get_cache_stats(self) -> dict[str, int]:
        """返回缓存统计信息."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._prompt_cache),
            "max_size": self._cache_size,
        }

    async def execute_simulator_prompt(
        self,
        prompt: str,
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> T:
        """执行 Simulator 的 prompt."""
        if self._local_responder is not None:
            result_data = await self._local_responder.execute_simulator_prompt(prompt, schema)
            return self._validate_schema(result_data, schema)
        return await self._execute_prompt("simulator", prompt, schema, max_retries, timeout_seconds)

    async def execute_validator_prompt(
        self,
        prompt: str,
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> T:
        """执行 Validator 的 prompt."""
        if self._local_responder is not None:
            result_data = await self._local_responder.execute_validator_prompt(prompt, schema)
            return self._validate_schema(result_data, schema)
        return await self._execute_prompt("validator", prompt, schema, max_retries, timeout_seconds)

    async def execute_modifier_prompt(
        self,
        prompt: str,
        schema: Type[T],
        auto_modify: bool = False,
    ) -> T:
        """执行 Modifier 的 prompt.

        Args:
            prompt: 发送给 LLM 的完整 prompt 文本.
            schema: 期望返回的结构化对象类型.
            auto_modify: 是否自动将修改写入架构文档.

        Returns:
            经 schema 验证后的结构化对象.
        """
        if self._local_responder is not None:
            result_data = await self._local_responder.execute_modifier_prompt(prompt, schema)
            return self._validate_schema(result_data, schema)
        uid = self._write_prompt_file("modifier", prompt)
        mode = "auto" if auto_modify else "interactive"
        print(f"[SKILL_PROMPT:modifier:{mode}:{uid}]", flush=True)
        result_data = await self._wait_for_result(uid, timeout_seconds=300)
        return self._validate_schema(result_data, schema)

    def _build_batched_prompt(self, agent_type: str, prompts: list[str]) -> str:
        """将多个 prompt 合并为一个."""
        delimiter = "\n---BATCH_ITEM---\n"
        combined = delimiter.join(f"[ITEM {i}]\n{p}" for i, p in enumerate(prompts))
        instructions = (
            f"You are processing {len(prompts)} {agent_type} prompts. "
            "Return a single JSON object with key 'results' containing an array "
            "of JSON objects, one per item, in the same order. "
            "Do not add markdown code blocks."
        )
        return f"{instructions}\n{delimiter}{combined}"

    async def _execute_prompt_batch(
        self,
        agent_type: str,
        prompts: list[str],
        schema: Type[T],
        max_retries: int,
        timeout_seconds: int,
    ) -> list[T]:
        """执行批量 prompt 的核心逻辑."""
        if not prompts:
            return []

        batched_prompt = self._build_batched_prompt(agent_type, prompts)
        current_prompt = batched_prompt
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                uid = self._write_prompt_file(agent_type, current_prompt)
                print(f"[SKILL_PROMPT:{agent_type}:batch:{uid}]", flush=True)
                result_data = await self._wait_for_result(uid, timeout_seconds)
                items = result_data.get("results", [])
                if len(items) != len(prompts):
                    raise SchemaValidationError(
                        f"Expected {len(prompts)} results, got {len(items)}"
                    )
                return [self._validate_schema(item, schema) for item in items]
            except (PromptExecutionError, SchemaValidationError) as exc:
                last_error = exc
                self._logger.warning(
                    "Batch prompt execution failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    current_prompt = self._refine_prompt(current_prompt, str(exc))
                    await asyncio.sleep(0.1)

        raise PromptExecutionError(
            f"Batch prompt execution failed after {max_retries} attempts: {last_error}"
        )

    async def execute_simulator_prompts_batch(
        self,
        prompts: list[str],
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> list[T]:
        if self._local_responder is not None:
            results = []
            for prompt in prompts:
                result_data = await self._local_responder.execute_simulator_prompt(prompt, schema)
                results.append(self._validate_schema(result_data, schema))
            return results
        return await self._execute_prompt_batch(
            "simulator", prompts, schema, max_retries, timeout_seconds
        )

    async def execute_validator_prompts_batch(
        self,
        prompts: list[str],
        schema: Type[T],
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> list[T]:
        if self._local_responder is not None:
            results = []
            for prompt in prompts:
                result_data = await self._local_responder.execute_validator_prompt(prompt, schema)
                results.append(self._validate_schema(result_data, schema))
            return results
        return await self._execute_prompt_batch(
            "validator", prompts, schema, max_retries, timeout_seconds
        )

    async def _execute_prompt(
        self,
        agent_type: str,
        prompt: str,
        schema: Type[T],
        max_retries: int,
        timeout_seconds: int,
    ) -> T:
        """执行 prompt 的核心逻辑，支持重试和缓存.

        Args:
            agent_type: Agent 类型 (simulator/validator/modifier).
            prompt: 发送给 LLM 的完整 prompt 文本.
            schema: 期望返回的 Pydantic BaseModel 子类.
            max_retries: 最大重试次数.
            timeout_seconds: 单次执行的超时时间（秒）.

        Returns:
            经 schema 验证后的结构化对象.

        Raises:
            PromptExecutionError: 所有重试均失败.
            SchemaValidationError: 返回结果无法通过 schema 验证.
        """
        cache_key = self._cache_key(agent_type, prompt, schema)
        cached = self._get_cached(cache_key)
        if cached is not None:
            self._logger.debug("Cache hit for %s prompt", agent_type)
            return self._validate_schema(cached, schema)

        current_prompt = prompt
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                uid = self._write_prompt_file(agent_type, current_prompt)
                print(f"[SKILL_PROMPT:{agent_type}:{uid}]", flush=True)
                result_data = await self._wait_for_result(uid, timeout_seconds)
                validated = self._validate_schema(result_data, schema)
                self._set_cached(cache_key, result_data)
                return validated
            except (PromptExecutionError, SchemaValidationError) as exc:
                last_error = exc
                self._logger.warning(
                    "Prompt execution failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    current_prompt = self._refine_prompt(current_prompt, str(exc))
                    await asyncio.sleep(0.1)

        raise PromptExecutionError(
            f"Prompt execution failed after {max_retries} attempts: {last_error}"
        )

    def _write_prompt_file(self, agent_type: str, prompt: str) -> str:
        """将 prompt 写入临时文件.

        Args:
            agent_type: Agent 类型.
            prompt: Prompt 文本.

        Returns:
            生成的 UUID 字符串.
        """
        uid = str(uuid.uuid4())
        prompt_file = self.TMP_DIR / f"{uid}_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        self._logger.debug("Wrote prompt file: %s", prompt_file)
        return uid

    async def _wait_for_result(self, uid: str, timeout_seconds: float) -> dict[str, Any]:
        """轮询等待结果文件.

        Args:
            uid: Prompt 的唯一标识.
            timeout_seconds: 超时时间（秒）.

        Returns:
            结果文件的 JSON 内容.

        Raises:
            PromptExecutionError: 超时或结果文件读取失败.
        """
        result_file = self.TMP_DIR / f"{uid}_result.json"
        prompt_file = self.TMP_DIR / f"{uid}_prompt.md"
        elapsed = 0.0
        poll_interval = 0.1

        try:
            while elapsed < timeout_seconds:
                if result_file.exists():
                    try:
                        result_text = result_file.read_text(encoding="utf-8")
                        result_data: dict[str, Any] = json.loads(result_text)
                        self._logger.debug("Read result file: %s", result_file)
                        return result_data
                    except (OSError, json.JSONDecodeError) as exc:
                        raise PromptExecutionError(f"Failed to read result file: {exc}") from exc
                    finally:
                        result_file.unlink(missing_ok=True)
                        prompt_file.unlink(missing_ok=True)
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            raise PromptExecutionError(f"Timeout waiting for result file: {result_file}")
        finally:
            prompt_file.unlink(missing_ok=True)
            result_file.unlink(missing_ok=True)

    def _refine_prompt(self, prompt: str, error: str) -> str:
        """根据错误信息修正 prompt.

        Args:
            prompt: 原始 prompt.
            error: 错误信息.

        Returns:
            修正后的 prompt.
        """
        refinement = f"\n\n---\n" f"[修正要求] 上次执行出现错误，请修正后重试:\n" f"{error}\n"
        return prompt + refinement

    def _validate_schema(self, data: dict[str, Any], schema: Type[T]) -> T:
        """验证数据是否符合 schema.

        Args:
            data: 待验证的数据.
            schema: Pydantic BaseModel 子类.

        Returns:
            验证后的模型实例.

        Raises:
            SchemaValidationError: 验证失败.
        """
        try:
            return schema(**data)
        except ValidationError as exc:
            raise SchemaValidationError(f"Schema validation failed: {exc}") from exc

    def _cleanup_old_files(self, max_age_hours: int = 1) -> None:
        """清理超过指定时间的临时文件.

        Args:
            max_age_hours: 文件最大存活时间（小时）.
        """
        if not self.TMP_DIR.exists():
            return

        max_age_seconds = max_age_hours * 3600
        now = time.time()

        for file_path in self.TMP_DIR.iterdir():
            if file_path.is_file():
                try:
                    mtime = file_path.stat().st_mtime
                    if now - mtime > max_age_seconds:
                        file_path.unlink(missing_ok=True)
                        self._logger.debug("Cleaned up stale file: %s", file_path)
                except OSError:
                    pass

    def _cache_file_path(self) -> Path:
        """返回缓存文件路径（可由环境变量覆盖）."""
        env_path = os.environ.get("MOCK_FRAMEWORK_SKILL_CACHE_PATH")
        if env_path:
            return Path(env_path)
        return self.TMP_DIR / "prompt_cache.json"

    def _load_cache_from_disk(self) -> dict[str, tuple[Any, float]]:
        """从磁盘加载未过期的缓存条目.

        Returns:
            {cache_key: (value, timestamp)} 的字典.
        """
        cache_file = self._cache_file_path()
        if not cache_file.exists():
            return {}
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

        try:
            ttl = float(os.environ.get("MOCK_FRAMEWORK_SKILL_CACHE_TTL", "86400"))
        except ValueError:
            ttl = 86400.0
        now = time.time()
        entries = data.get("entries", {})
        result: dict[str, tuple[Any, float]] = {}
        for key, item in entries.items():
            if not isinstance(item, dict):
                continue
            ts = item.get("ts", 0)
            value = item.get("value")
            if value is None or now - ts > ttl:
                continue
            result[key] = (value, ts)
        return result

    def _save_cache_to_disk(self) -> None:
        """将当前内存缓存原子写入磁盘."""
        cache_file = self._cache_file_path()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        entries = {key: {"value": value, "ts": now} for key, value in self._prompt_cache.items()}
        suffix = os.urandom(16).hex()
        tmp_file = cache_file.with_suffix(f".tmp.{suffix}")
        try:
            with tmp_file.open("w", encoding="utf-8") as f:
                json.dump({"entries": entries}, f, ensure_ascii=False)
            tmp_file.replace(cache_file)
        except OSError as exc:
            self._logger.warning("Failed to save prompt cache to disk: %s", exc)

    def _load_cache_entries_into_memory(self) -> None:
        """将磁盘缓存加载到内存 LRU，受 cache_size 限制."""
        disk_entries = self._load_cache_from_disk()
        for key, (value, _ts) in disk_entries.items():
            self._set_cached(key, value)
