"""SI-CORE-INTEGRITY：材料清单与完整性报告（SIC-ST-02/03）。

规则（SIC-INV-03/04）：
- 报告只基于声明类别与 SI-STORE 已登记元数据，不解析文件内容；
- `missing_items[]` 是显式报告而非拒绝条件：空目录仍可 received 并发布 CT-004；
- 同一输入快照生成同一报告（确定性）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence

from .errors import MaterialMetadataUnavailableError, ValidationError

#: 材料类别值域（CT-004 schema 冻结枚举）。
CATEGORIES = ("对话", "代码", "截图", "结果")


@dataclass(frozen=True)
class MaterialMetadata:
    """SI-STORE 已登记的材料元数据（IC-SI-02 read_metadata 输出）。"""

    material_ref: str
    category: str
    size_bytes: int | None = None
    declared: bool = True
    filename: str | None = None


class MaterialMetadataReader(Protocol):
    """SI-STORE 元数据端口（抽象注入；实现归 SI-STORE/backfill）。

    实现抛出的任何异常都会被归一为 MATERIAL_METADATA_UNAVAILABLE，
    使当前事务整体回滚，由上游按父错误/重试策略处理。
    """

    def read_metadata(self, material_ref: str) -> MaterialMetadata: ...


@dataclass(frozen=True)
class IntegrityReportData:
    """SIC-ST-03 值对象：expected/received/missing 类别快照。"""

    expected_categories: tuple[str, ...]
    received_categories: tuple[str, ...]
    missing_items: tuple[str, ...]
    generated_at: datetime
    report_version: int = 1


@dataclass(frozen=True)
class ManifestAndReport:
    entries: tuple[MaterialMetadata, ...] = field(default_factory=tuple)
    report: IntegrityReportData | None = None


def _validate_categories(categories: Sequence[str], field_name: str) -> tuple[str, ...]:
    result: list[str] = []
    for category in categories:
        if category not in CATEGORIES:
            raise ValidationError(f"{field_name}: unknown category {category!r}")
        if category not in result:
            result.append(category)
    return tuple(result)


def build_manifest_and_report(
    material_refs: Sequence[str],
    expected_categories: Sequence[str],
    reader: MaterialMetadataReader,
    now: datetime,
) -> ManifestAndReport:
    """按声明类别与 SI-STORE 元数据生成清单与完整性报告。

    - `expected_categories` 为空表示未声明（报告 missing_items 为空，不臆造缺失）；
    - 缺失 = 声明类别中无任何已登记材料的类别，按 CATEGORIES 固定顺序输出；
    - 元数据读取失败抛 MATERIAL_METADATA_UNAVAILABLE（事务回滚）。
    """
    expected = _validate_categories(expected_categories, "expected_categories")
    entries: list[MaterialMetadata] = []
    for ref in material_refs:
        try:
            meta = reader.read_metadata(ref)
        except MaterialMetadataUnavailableError:
            raise
        except Exception as exc:  # 端口实现异常归一为契约错误码
            raise MaterialMetadataUnavailableError(f"read_metadata({ref!r}) failed") from exc
        _validate_categories([meta.category], "material category")
        entries.append(meta)
    received = tuple(c for c in CATEGORIES if any(e.category == c for e in entries))
    missing = tuple(c for c in CATEGORIES if c in expected and c not in received)
    report = IntegrityReportData(
        expected_categories=expected,
        received_categories=received,
        missing_items=missing,
        generated_at=now,
    )
    return ManifestAndReport(entries=tuple(entries), report=report)
