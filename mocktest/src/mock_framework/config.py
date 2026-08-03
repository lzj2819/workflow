"""配置加载"""

from pathlib import Path
from typing import Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class FrameworkConfig(BaseModel):
    """框架配置"""

    name: str = Field(default="Mocktest")
    version: str = Field(default="2.0.0")


class GapDetectorConfig(BaseModel):
    """GapDetector 配置"""

    non_component_words: list[str] = Field(
        default_factory=list,
        description="额外需要过滤的非组件词",
    )
    chinese_mode_threshold: float = Field(
        default=0.5,
        description="中文字符占比超过此阈值时启用中文模式",
    )


class LoaderConfig(BaseModel):
    """Loader 配置"""

    gherkin_parser: str = Field(default="official")
    mapping_confidence_threshold: str = Field(default="medium")
    gap_detector: GapDetectorConfig = Field(default_factory=GapDetectorConfig)


class LatencyModelConfig(BaseModel):
    """延迟模型配置"""

    components: dict = Field(default_factory=dict)
    network_overhead: dict = Field(default_factory=dict)
    concurrency_penalty: dict = Field(default_factory=dict)


class SimulatorConfig(BaseModel):
    """Simulator 配置"""

    latency_model: LatencyModelConfig = Field(default_factory=LatencyModelConfig)
    token_budget: int = Field(default=4000)


class ValidatorConfig(BaseModel):
    """Validator 配置"""

    dimensions: list[str] = Field(
        default_factory=lambda: [
            "structure",
            "flow",
            "state",
            "contract",
            "performance",
        ]
    )
    token_budget: int = Field(default=2000)


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO")
    format: str = Field(default="structured")
    output: str = Field(default="console")


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""

    provider: str = Field(default="codex", description="configured by the strict driver")
    model: str = Field(default="configured-by-strict-driver")
    token_budget: int = Field(default=4000)
    timeout_seconds: float = Field(default=60.0, description="单次 API 请求超时（秒）")
    max_retries: int = Field(default=3, description="瞬态错误最大重试次数")
    retry_backoff_seconds: float = Field(default=1.0, description="重试基础退避（秒）")


class LLMConfig(BaseModel):
    """LLM 配置"""

    api_key: str = Field(default="", description="支持 ${ENV_VAR} 语法")
    base_url: Optional[str] = Field(default=None)
    simulator: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    validator: LLMProviderConfig = Field(default_factory=LLMProviderConfig)


class ExecutionConfig(BaseModel):
    """执行模式配置"""

    mode: str = Field(default="strict", description="strict | legacy")


class SkillConfig(BaseModel):
    """Skill 模式配置"""

    max_modify_rounds: int = Field(default=0)
    auto_modify: bool = Field(default=False)
    pause_on_high_severity: bool = Field(default=True)
    show_reasoning: bool = Field(default=False)
    show_modification_diff: bool = Field(default=False)
    enable_modification_history: bool = Field(default=False)
    max_history_versions: int = Field(default=0)
    cache_file_path: str = Field(
        default=".work/validate-arch/cache/prompt_cache.json",
        description="Skill Gateway prompt cache 持久化路径",
    )
    cache_ttl_seconds: int = Field(
        default=86400,
        ge=1,
        description="缓存条目 TTL（秒），默认 24 小时",
    )
    batch_size: int = Field(
        default=1,
        ge=1,
        description="Skill 模式下次 LLM 调用处理的测试用例数，1 表示不批量",
    )


class ValidatorDimensionConfig(BaseModel):
    """验证维度配置"""

    base_dimensions: list[str] = Field(
        default_factory=lambda: [
            "structure",
            "flow",
            "state",
            "contract",
            "performance",
        ]
    )
    component_dimensions: list[str] = Field(
        default_factory=lambda: [
            "error_handling",
            "concurrency",
            "observability",
        ]
    )
    strictness: str = Field(default="normal")


class Config(BaseModel):
    """总配置（更新版）"""

    framework: FrameworkConfig = Field(default_factory=FrameworkConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    skill: SkillConfig = Field(default_factory=SkillConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    validator: ValidatorConfig = Field(default_factory=ValidatorConfig)
    validator_dimensions: ValidatorDimensionConfig = Field(default_factory=ValidatorDimensionConfig)
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    loader: LoaderConfig = Field(default_factory=LoaderConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(path: Optional[str] = None) -> Config:
    """加载配置文件

    Args:
        path: 配置文件路径，默认 config/default.yaml

    Returns:
        Config 实例
    """
    config_path: Path
    if path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    else:
        config_path = Path(path)

    if not config_path.exists():
        return Config()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(**data)
