"""Phase 1 契约测试：contracts/ 机器可读 schema 的完整性、错误码、版本与幂等要求。

期望值逐字段对齐 tutor/L0-root/architecture/04-interface-contracts.md 的
contract_fields（冻结源）；任何不一致即失败。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from course_app.contracts_registry import ContractRegistryError, load_registry  # noqa: E402

CONTRACTS_DIR = ROOT / "contracts"

EXPECTED_IDS = {
    "CT-001", "CT-002", "CT-003", "CT-004", "CT-005", "CT-006", "CT-007",
    "CT-008", "CT-009", "CT-010", "CT-011", "CT-012", "CT-013", "CT-014",
    "CT-015",  # CCR-001 方案 A（用户批准 2026-07-22）：AssessmentPurgeCompleted
    "AUTH-TOKEN", "FLOW-011",
}
EVENT_IDS = {"CT-004", "CT-005", "CT-006", "CT-012", "CT-014", "CT-015"}

EXPECTED_ERROR_CODES = {
    "CT-001": {"AUTH_INVALID", "VALIDATION_FAILED", "PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE", "REJECTED_MEMBERSHIP"},
    "CT-002": {"AUTH_INVALID", "NOT_FOUND"},
    "CT-003": {"ROSTER_UNAVAILABLE"},
    "CT-007": {"AUTH_INVALID", "FORBIDDEN"},
    "CT-008": {"AUTH_INVALID", "FORBIDDEN", "NOT_FOUND", "VALIDATION_FAILED", "NO_ORIGINAL_GRADE"},
    "CT-009": {"AUTH_INVALID", "FORBIDDEN", "VALIDATION_FAILED", "NO_AVAILABLE_SUBMISSION"},
    "CT-010": {"MODEL_TIMEOUT", "MODEL_ERROR", "INVALID_RESPONSE_SCHEMA"},
    "CT-011": {"AUTH_INVALID", "FORBIDDEN", "NOT_FOUND", "BATCH_NOT_EXPIRED"},
    "CT-013": {"AUTH_INVALID", "FORBIDDEN", "NOT_FOUND", "VALIDATION_FAILED"},
    "AUTH-TOKEN": {"AUTH_INVALID"},
    "CT-004": set(), "CT-005": set(), "CT-006": set(), "CT-012": set(), "CT-014": set(),
    "CT-015": set(),
    "FLOW-011": set(),
}

REQUIRED_FIELDS = {
    "CT-001": ("request", ["submission_uuid", "invite_code", "student_name", "group_name", "assignment", "material_chunks"]),
    "CT-003": ("request", ["invite_code", "student_name", "group_name"]),
    "CT-004": ("event", ["submission_id", "course_id", "assignment", "student_name", "group_name", "material_refs", "missing_items", "received_at", "v"]),
    "CT-005": ("event", ["submission_id", "outcome", "v"]),
    "CT-006": ("event", ["submission_id", "course_id", "assignment", "student_name", "group_name", "status", "missing_items", "received_at", "v"]),
    "CT-008": ("request", ["submission_id", "request_id"]),
    "CT-009": ("request", ["group_ids"]),
    "CT-010": ("request", ["evaluation_prompt", "materials"]),
    "CT-011": ("request", ["batch_id", "confirm"]),
    "CT-012": ("event", ["batch_id", "submission_ids", "scope", "operator", "executed_at", "audit_record_id", "v"]),
    "CT-013": ("request", ["course_id", "roster_entries"]),
    "CT-014": ("event", ["batch_id", "purged_submission_ids", "failed_items", "purged_at", "v"]),
    "CT-015": ("event", ["batch_id", "purged_submission_ids", "failed_items", "purged_at", "v"]),
    "AUTH-TOKEN": ("request", ["invite_code", "student_name", "group_name"]),
}

CT010_FORBIDDEN_REQUEST_FIELDS = {"submission_id", "student_name", "group_name", "invite_code", "course_id"}


class TestContractFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(CONTRACTS_DIR)

    def test_all_expected_contracts_present(self):
        self.assertEqual(set(self.registry.ids()), EXPECTED_IDS)
        self.assertEqual(len(self.registry), 17)

    def test_error_codes_match_frozen_design(self):
        for cid, expected in EXPECTED_ERROR_CODES.items():
            contract = self.registry.get(cid)
            self.assertEqual(set(contract.error_codes), expected, cid)

    def test_required_fields_match_frozen_design(self):
        for cid, (schema_key, required) in REQUIRED_FIELDS.items():
            schema = self.registry.get(cid).schemas[schema_key]
            self.assertEqual(schema["required"], required, cid)

    def test_events_require_v_const_1(self):
        for cid in EVENT_IDS:
            event = self.registry.get(cid).schemas["event"]
            self.assertIn("v", event["required"], cid)
            self.assertEqual(event["properties"]["v"]["const"], 1, cid)

    def test_idempotency_declared_for_every_contract(self):
        for cid in EXPECTED_IDS:
            idem = self.registry.get(cid).idempotency
            self.assertTrue(idem and idem.strip(), cid)

    def test_api_contracts_declare_version_prefix(self):
        for cid in EXPECTED_IDS - {"FLOW-011"}:
            contract = self.registry.get(cid)
            if contract.contract_type == "api":
                self.assertIn("/api/v1", contract.versioning, cid)
            elif contract.contract_type == "external_api":
                self.assertIn("ACL", contract.versioning, cid)  # 供应商版本由 ACL 封装
            else:  # 事件契约经 v 字段版本化
                self.assertIn("v", contract.versioning, cid)

    def test_ct001_limits_and_categories(self):
        raw = self.registry.get("CT-001").raw
        self.assertEqual(raw["limits"]["max_submission_bytes"], 500 * 1024 * 1024)
        categories = raw["schemas"]["request"]["properties"]["material_chunks"]["items"]["properties"]["category"]["enum"]
        self.assertEqual(categories, ["对话", "代码", "截图", "结果"])

    def test_ct003_response_conditional_fields(self):
        response = self.registry.get("CT-003").schemas["response"]
        self.assertEqual(response["required"], ["verified"])
        self.assertIn("course_id", response["properties"])
        self.assertIn("reason", response["properties"])

    def test_ct005_outcome_and_retry_bounds(self):
        event = self.registry.get("CT-005").schemas["event"]
        self.assertEqual(event["properties"]["outcome"]["enum"], ["scored", "scoring_failed"])
        self.assertEqual(event["properties"]["retry_record"]["properties"]["attempts"]["maximum"], 2)
        dims = event["properties"]["dimension_rationales"]
        self.assertEqual((dims["minItems"], dims["maxItems"]), (5, 5))

    def test_ct010_data_minimization(self):
        request = self.registry.get("CT-010").schemas["request"]
        props = set(request["properties"])
        self.assertTrue(CT010_FORBIDDEN_REQUEST_FIELDS.isdisjoint(props))
        materials = request["properties"]["materials"]
        self.assertEqual(materials["required"], ["dialogue_summary", "code", "result_description"])

    def test_ct012_consumers_post_ccr001(self):
        # CCR-001 方案 A（用户批准 2026-07-22）：CT-012 消费者扩展为 [MOD-02, MOD-04, MOD-05]
        contract = self.registry.get("CT-012")
        self.assertEqual(contract.consumer, ["MOD-02", "MOD-04", "MOD-05"])

    def test_ct015_mirrors_ct014_shape(self):
        # CCR-001：CT-015 AssessmentPurgeCompleted 语义镜像 CT-014（MOD-04 → MOD-05）
        ct015 = self.registry.get("CT-015")
        self.assertEqual(ct015.provider, "MOD-04")
        self.assertEqual(ct015.consumer, "MOD-05")
        event = ct015.schemas["event"]
        item = event["properties"]["failed_items"]["items"]
        self.assertEqual(item["required"], ["submission_id", "reason"])
        self.assertFalse(event.get("additionalProperties", True))

    def test_auth_token_response_shape(self):
        response = self.registry.get("AUTH-TOKEN").schemas["response"]
        self.assertEqual(response["required"], ["access_token", "token_type", "expires_in"])
        self.assertEqual(response["properties"]["token_type"]["const"], "Bearer")

    def test_flow_011_is_internal_read(self):
        contract = self.registry.get("FLOW-011")
        self.assertEqual(contract.contract_type, "internal_read")
        self.assertIsNone(contract.raw["endpoint"])
        self.assertEqual(contract.schemas["response"]["required"], ["course_end_time"])

    def test_registry_rejects_bad_dir(self):
        with self.assertRaises(ContractRegistryError):
            load_registry(ROOT / "does-not-exist")

    def test_internal_contracts_index(self):
        internal = json.loads((CONTRACTS_DIR / "internal-contracts.json").read_text(encoding="utf-8"))
        modules = internal["modules"]
        self.assertEqual(set(modules), {"MOD-01", "MOD-02", "MOD-03", "MOD-04", "MOD-05"})
        counts = {m: len(modules[m]["contracts"]) for m in modules}
        self.assertEqual(counts, {"MOD-01": 5, "MOD-02": 6, "MOD-03": 2, "MOD-04": 9, "MOD-05": 7})
        ids = [c["id"] for m in modules.values() for c in m["contracts"]]
        self.assertEqual(len(ids), len(set(ids)))
        for m in modules.values():
            for c in m["contracts"]:
                self.assertTrue(c["owner"] and c["consumer"], c["id"])


if __name__ == "__main__":
    unittest.main()
