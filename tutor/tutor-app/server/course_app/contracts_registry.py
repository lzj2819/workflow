"""冻结契约注册表：加载 contracts/*.json 并做结构校验。

用途：运行时请求/事件校验、契约测试、任务包边界检查。
仅 Integration Owner 可修改 contracts/；本模块只读。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from course_app.settings import DEFAULT_CONTRACTS_DIR

REQUIRED_TOP_KEYS = {
    "contract_id",
    "contract_type",
    "direction",
    "provider",
    "consumer",
    "versioning",
    "idempotency",
    "error_codes",
    "publishes_events",
    "schemas",
    "source",
}

EVENT_TYPES = {"event"}
API_TYPES = {"api", "external_api", "internal_read"}


class ContractRegistryError(RuntimeError):
    """契约注册表结构非法。"""


@dataclass(frozen=True)
class Contract:
    contract_id: str
    contract_type: str
    direction: str
    provider: str
    consumer: object
    error_codes: tuple[str, ...]
    publishes_events: tuple[str, ...]
    idempotency: str
    versioning: str
    schemas: dict
    raw: dict

    @property
    def is_event(self) -> bool:
        return self.contract_type in EVENT_TYPES


class ContractRegistry:
    def __init__(self, contracts: dict[str, Contract], internal: dict) -> None:
        self._contracts = contracts
        self.internal = internal

    def get(self, contract_id: str) -> Contract:
        try:
            return self._contracts[contract_id]
        except KeyError:
            raise ContractRegistryError(f"unknown contract_id: {contract_id}") from None

    def ids(self) -> list[str]:
        return sorted(self._contracts)

    def __len__(self) -> int:
        return len(self._contracts)


def _validate_one(path: Path, data: dict) -> list[str]:
    problems: list[str] = []
    missing = REQUIRED_TOP_KEYS - data.keys()
    if missing:
        problems.append(f"{path.name}: missing keys {sorted(missing)}")
        return problems
    if data["contract_type"] not in EVENT_TYPES | API_TYPES:
        problems.append(f"{path.name}: bad contract_type {data['contract_type']!r}")
    if data["contract_type"] in ("api", "external_api") and not data["error_codes"]:
        problems.append(f"{path.name}: api contract must declare error_codes")
    if data["contract_type"] in EVENT_TYPES:
        event = data["schemas"].get("event")
        if not isinstance(event, dict):
            problems.append(f"{path.name}: event contract missing schemas.event")
        else:
            required = event.get("required", [])
            version_prop = event.get("properties", {}).get("v", {})
            if "v" not in required or version_prop.get("const") != 1:
                problems.append(f"{path.name}: event schema must require v with const 1")
    for name, schema in data.get("schemas", {}).items():
        if not isinstance(schema, dict) or ("type" not in schema and name != "event"):
            problems.append(f"{path.name}: schemas.{name} is not a schema object")
    return problems


def load_registry(contracts_dir: Path | str = DEFAULT_CONTRACTS_DIR) -> ContractRegistry:
    contracts_dir = Path(contracts_dir)
    problems: list[str] = []
    if not contracts_dir.is_dir():
        raise ContractRegistryError(f"contracts dir not found: {contracts_dir}")
    contracts: dict[str, Contract] = {}
    for path in sorted(contracts_dir.glob("*.json")):
        if path.name == "internal-contracts.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: unreadable ({exc})")
            continue
        file_problems = _validate_one(path, data)
        problems.extend(file_problems)
        cid = data.get("contract_id")
        if file_problems:
            continue  # 有问题文件不构造 Contract，统一经 problems 报告
        if cid in contracts:
            problems.append(f"{path.name}: duplicate contract_id {cid}")
        else:
            contracts[cid] = Contract(
                contract_id=cid,
                contract_type=data["contract_type"],
                direction=data["direction"],
                provider=data["provider"],
                consumer=data["consumer"],
                error_codes=tuple(data["error_codes"]),
                publishes_events=tuple(data["publishes_events"]),
                idempotency=data["idempotency"],
                versioning=data["versioning"],
                schemas=data["schemas"],
                raw=data,
            )
    internal_path = contracts_dir / "internal-contracts.json"
    internal = json.loads(internal_path.read_text(encoding="utf-8")) if internal_path.exists() else {}
    if problems:
        raise ContractRegistryError("; ".join(problems))
    return ContractRegistry(contracts, internal)
