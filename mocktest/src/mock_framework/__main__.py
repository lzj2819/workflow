"""CLI 入口"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional


def _resolve_api_key(value: str) -> str:
    """解析 API Key，支持 ${ENV_VAR} 环境变量语法.

    Args:
        value: 配置值，可能是普通字符串或 ${ENV_VAR} 格式.

    Returns:
        解析后的 API Key.
    """
    match = re.match(r"^\$\{(.+)\}$", value)
    if match:
        env_var = match.group(1)
        return os.environ.get(env_var, value)
    return value


from mock_framework.config import load_config
from mock_framework.improvement.report_renderer import ReportRenderer
from mock_framework.logger import get_logger, setup_logging
from mock_framework.models.validator import ValidationReport
from mock_framework.pipeline import Pipeline
from mock_framework.simulator.llm_client import LLMClient
from mock_framework.simulator.simulator import Simulator
from mock_framework.validator.validator import Validator


def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    parser = argparse.ArgumentParser(
        prog="mock-test",
        description="Mock测试框架 - 消费Gherkin场景进行架构验证",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m mock_framework --help
  python -m mock_framework run --feature tests/fixtures/auth.feature --arch tests/fixtures/auth-arch.md
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        default="config/default.yaml",
        help="配置文件路径 (默认: config/default.yaml)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出 (DEBUG 级别)",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="显示版本号",
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="执行 Mock 测试")
    run_parser.add_argument(
        "--feature",
        "-f",
        required=True,
        help="Gherkin feature 文件路径",
    )
    run_parser.add_argument(
        "--arch",
        "-a",
        required=True,
        help="架构文档路径",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        default="report.md",
        help="报告输出路径 (默认: report.md)",
    )
    run_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="报告输出格式 (默认: markdown)",
    )

    # layer-check 命令
    layer_parser = subparsers.add_parser("layer-check", help="Cross-layer consistency check")
    layer_parser.add_argument("--parent", "-p", required=True, help="Parent architecture document")
    layer_parser.add_argument(
        "--children", "-c", nargs="+", required=True, help="Child architecture documents"
    )

    return parser


def _is_claude_code_environment() -> bool:
    """检测是否在支持 Skill IPC 的 Claude Code 环境中运行。

    多因子检测：
    1. MOCK_FRAMEWORK_FORCE_SKILL_IPC=1 强制启用 Skill IPC
    2. MOCK_FRAMEWORK_FORCE_API=1 强制禁用 Skill IPC
    3. CLAUDE_CODE_CHILD_SESSION=1 表示 VS Code 扩展子会话，stdout markers
       不会被当前 Claude 会话捕获，因此不走 Skill IPC
    4. CLAUDE_CODE / CLAUDECODE 环境变量 == "1"
    5. .claude 目录存在于当前工作目录
    6. CLAUDE_SESSION 环境变量存在

    可通过设置 MOCK_FRAMEWORK_FORCE_API=1 强制使用 API 模式，
    或 MOCK_FRAMEWORK_FORCE_SKILL_IPC=1 强制使用 Skill IPC 模式。
    """
    if os.environ.get("MOCK_FRAMEWORK_FORCE_API") == "1":
        return False
    if os.environ.get("MOCK_FRAMEWORK_FORCE_SKILL_IPC") == "1":
        return True
    if os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1":
        return False
    if os.environ.get("CLAUDE_CODE") == "1":
        return True
    if os.environ.get("CLAUDECODE") == "1":
        return True
    if Path(".claude").exists():
        return True
    if os.environ.get("CLAUDE_SESSION") is not None:
        return True
    return False


def _build_pipeline(config_path: str) -> Pipeline:
    """从配置构建 Pipeline.

    LLM 后端选择优先级（真实验证时禁止 mock 数据）：
    1. 显式启用本地自动响应器（MOCK_FRAMEWORK_LOCAL_AUTO_RESPOND=1）——仅用于调试/回归
    2. Claude Code Skill IPC 模式（检测到 .claude/CLAUDE_CODE/CLAUDE_SESSION）
    3. 真实 LLM API 模式（需要配置有效 api_key）
    4. 以上都不可用时抛出异常

    Args:
        config_path: 配置文件路径.

    Returns:
        配置好的 Pipeline 实例.

    Raises:
        RuntimeError: 没有可用的真实 LLM 后端且未显式启用本地自动响应器.
    """
    config = load_config(config_path)

    # 解析 API Key（支持环境变量）
    api_key = _resolve_api_key(config.llm.api_key)
    base_url = config.llm.base_url

    simulator_llm: LLMClient
    validator_llm: LLMClient

    if os.environ.get("MOCK_FRAMEWORK_LOCAL_AUTO_RESPOND") == "1":
        # 显式本地自动响应器（调试/批量回归）
        from mock_framework.agents.local_auto_responder import LocalAutoResponderLLMClient

        simulator_llm = LocalAutoResponderLLMClient(token_budget=config.simulator.token_budget)
        validator_llm = LocalAutoResponderLLMClient(token_budget=config.validator.token_budget)
    elif _is_claude_code_environment():
        # 优先使用真实 Skill 文件 IPC 模式
        from mock_framework.agents.skill_gateway import ClaudeCodeSkillGateway
        from mock_framework.skills.skill_llm_client import SkillLLMClient

        gateway = ClaudeCodeSkillGateway()
        simulator_llm = SkillLLMClient(gateway=gateway, agent_type="simulator")
        validator_llm = SkillLLMClient(gateway=gateway, agent_type="validator")
    elif api_key:
        # 真实 LLM API 模式
        from mock_framework.simulator.llm_client import LLMClientFactory

        sim_cfg = config.llm.simulator
        simulator_llm = LLMClientFactory.create(
            provider=sim_cfg.provider,
            api_key=api_key,
            model=sim_cfg.model,
            token_budget=sim_cfg.token_budget,
            base_url=base_url,
            timeout_seconds=sim_cfg.timeout_seconds,
            max_retries=sim_cfg.max_retries,
            retry_backoff_seconds=sim_cfg.retry_backoff_seconds,
        )

        val_cfg = config.llm.validator
        validator_llm = LLMClientFactory.create(
            provider=val_cfg.provider,
            api_key=api_key,
            model=val_cfg.model,
            token_budget=val_cfg.token_budget,
            base_url=base_url,
            timeout_seconds=val_cfg.timeout_seconds,
            max_retries=val_cfg.max_retries,
            retry_backoff_seconds=val_cfg.retry_backoff_seconds,
        )
    else:
        raise RuntimeError(
            "未配置可用的真实 LLM 后端。请满足以下任一条件：\n"
            "1. 在 Claude Code 中运行以使用 Skill 文件 IPC 模式；\n"
            "2. 在配置文件中设置有效的 llm.api_key 以使用真实 API 模式；\n"
            "3. 显式设置 MOCK_FRAMEWORK_LOCAL_AUTO_RESPOND=1 以启用本地自动响应器（仅用于调试/回归）。"
        )

    from mock_framework.loader import Loader

    loader = Loader(config.loader)
    simulator = Simulator(simulator_llm, config_path)
    validator = Validator(validator_llm, config_path)

    return Pipeline(loader, simulator, validator, retry_count=3)


def _write_report(report: ValidationReport, output_path: str, format: str = "markdown") -> None:
    """将验证报告写入文件.

    Args:
        report: 验证报告.
        output_path: 输出文件路径.
        format: 输出格式，markdown 或 json.
    """
    renderer: ReportRenderer | JsonReportRenderer
    if format == "json":
        from mock_framework.improvement.json_report_renderer import JsonReportRenderer

        renderer = JsonReportRenderer()
    else:
        renderer = ReportRenderer()
    content = renderer.render(report)
    Path(output_path).write_text(content, encoding="utf-8")


def _run_command(args: argparse.Namespace) -> int:
    """执行 run 命令.

    Args:
        args: 解析后的命令行参数.

    Returns:
        退出码 0=成功, 1=存在失败.
    """
    logger = get_logger("cli")
    logger.info("开始执行: feature=%s arch=%s", args.feature, args.arch)

    pipeline = _build_pipeline(args.config)
    report = pipeline.run(args.feature, args.arch)

    _write_report(report, args.output, args.format)
    logger.info("报告已写入: %s", args.output)

    failed = report.summary.get("failed", 0)
    warnings = report.summary.get("warnings", 0)
    missing = report.summary.get("missing", 0)

    if failed > 0:
        logger.error("验证失败: %d 个场景未通过", failed)
        return 1
    if warnings > 0:
        logger.warning("验证警告: %d 个场景存在警告", warnings)
        return 1
    if missing > 0:
        logger.warning("验证缺失: %d 个场景缺失", missing)
        return 1

    logger.info("所有场景验证通过")
    return 0


def main(args: Optional[list[str]] = None) -> int:
    """主入口函数

    Args:
        args: 命令行参数，None 时自动解析 sys.argv

    Returns:
        退出码 0=成功, 1=错误
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if parsed.version:
        from mock_framework import __version__

        print(f"Mock测试框架 v{__version__}")
        return 0

    # 加载配置
    config = load_config(parsed.config)

    # 设置日志
    log_level = "DEBUG" if parsed.verbose else config.logging.level
    setup_logging(
        level=log_level,
        format_type=config.logging.format,
        output=config.logging.output,
    )
    logger = get_logger("cli")

    logger.info("启动 %s v%s", config.framework.name, config.framework.version)
    logger.debug("配置文件: %s", parsed.config)

    if parsed.command == "run":
        return _run_command(parsed)

    if parsed.command == "layer-check":
        from .cli.layer_check import layer_check_command

        return layer_check_command(parsed.parent, parsed.children)

    # 无子命令时显示帮助
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
