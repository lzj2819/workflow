from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT.parent
for path in (
    ROOT / "scripts",
    WORKFLOW_ROOT / "prd-generation" / "scripts",
    WORKFLOW_ROOT / "mocktest" / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from architecture_flow.bundle import FIXED_BUNDLE, write_bundle
from architecture_flow.canonical import (
    SECTION_ORDER,
    build_canonical_architecture,
    canonical_json_text,
    render_canonical_architecture,
    validate_canonical_architecture,
)
from architecture_flow.consumer_profiles import validate_consumer_profile
from mock_framework.loader.arch_doc_parser import ArchDocParser
from prd_flow.canonical import build_canonical_prd
from prd_flow.derive.parser import extract_module_context


def prd_source(*, node_id: str = "root", parent_node_id: str | None = None, depth: int = 0) -> dict:
    return {
        "P1": {
            "doc_id": f"ORDER-{node_id}-v1.0",
            "project_name": "Order Service",
            "version": "1.0.0",
            "layer": "root" if depth == 0 else "module",
            "author": "Product Owner",
            "priority": "P0",
            "status": "approved",
            "release_scope_frozen": True,
            "ready_for_test_generation": True,
            "agent_review_passed": True,
            "run_id": "run-arch-001",
            "project_id": "project-order",
            "node_id": node_id,
            "parent_node_id": parent_node_id,
            "artifact_id": f"prd:project-order:{node_id}:run-arch-001",
            "created_at": "2026-08-02T00:00:00Z",
            "generator": "prd-generation",
            "input_artifacts": ["inputs/request.json"],
            "depth": depth,
            "max_depth": 4,
            "node_history": [] if depth == 0 else ["root"],
            "_review": {
                "status": "passed",
                "reviewer": "architecture-test-reviewer",
                "model": "test-model",
                "reviewed_at": "2026-08-02T00:01:00Z",
                "input_hash": "a" * 64,
                "findings": [],
            },
        },
        "P2": {
            "summary": "Record an order reliably",
            "target_users": "Order operators",
            "pain_points": "Manual order recording",
            "desired_outcomes": "A durable order identifier",
            "current_release_boundary": "Single order recording",
            "in_scope": ["Create one order"],
            "dependencies": ["Identity provider"],
            "data_availability": ["Synthetic order data"],
            "risks": ["Identity provider unavailable"],
        },
        "P3": {
            "functional": [{
                "id": "REQ-001",
                "text": "The system records an order and returns its identifier.",
                "priority": "Must Have",
                "release_scope": "current",
                "scope_reason": None,
                "requirement_kind": "atomic",
                "source_kind": "explicit",
                "evidence_refs": ["decision:001"],
            }],
            "non_functional": [],
            "non_goals": ["Bulk import"],
            "retired_requirement_ids": [],
        },
        "P4": {"contracts": [{
            "id": "AC-REQ-001-01",
            "type": "functional",
            "verifies": ["REQ-001"],
            "release_scope": "current",
            "actor": "operator",
            "preconditions": ["operator is authenticated"],
            "trigger": "operator submits a valid order",
            "response": ["system persists the order"],
            "observable_oracles": ["response contains the order identifier"],
            "boundaries": [{"condition": "identifier available", "response": "allocate it"}],
            "exceptions": [{"condition": "store unavailable", "response": "reject without success"}],
            "evidence_refs": ["decision:002"],
        }]},
        "P5": {"metrics": [{
            "id": "METRIC-001",
            "name": "Persisted accepted orders",
            "target": "100%",
            "method": "Compare responses to stored records",
            "verifies": ["REQ-001"],
            "evidence_refs": ["decision:003"],
        }]},
        "P6": {
            "system_boundary": ["Own order write consistency"],
            "external_dependencies": ["Identity provider"],
            "data_and_storage_constraints": [],
            "runtime_and_capacity_constraints": [],
            "security_and_privacy_constraints": ["Do not expose credentials"],
            "deployment_constraints": [],
            "open_decisions": [],
        },
    }


def artifact_refs() -> list[dict]:
    return [{
        "artifact_id": "prd:project-order:root:run-arch-001",
        "artifact_type": "prd",
        "artifact_schema_version": "prd/v3",
        "path": "inputs/prd.json",
        "sha256": "b" * 64,
    }]


def top_design(*, name: str = "Order Module", node_id: str = "MOD-ORDER") -> dict:
    return {
        "design_context": {
            "summary": "Order system architecture",
            "scope": "Order recording system",
            "goals": ["Reliable writes"],
            "non_goals": ["Bulk imports"],
            "responsibility": "Define the system boundary and first-level modules",
            "exclusions": ["Implementation code"],
            "external_systems": [{
                "id": "EXT-IDP", "name": "Identity Provider",
                "responsibility": "Authenticate operators", "source_refs": ["REQ-001"],
            }],
        },
        "requirement_allocations": [{
            "requirement_id": "REQ-001", "classification": "allocated",
            "owner_node_ids": [node_id], "source_refs": ["REQ-001"], "reason": "Write owner",
        }],
        "nodes": [{
            "id": node_id, "name": name, "kind": "module",
            "responsibility": "Own order recording", "exclusions": ["Identity storage"],
            "requirement_ids": ["REQ-001"], "state_ids": ["STATE-ORDER"],
            "dependency_ids": [], "source_refs": ["REQ-001"], "rationale": "Single write owner",
        }],
        "state_ownership": [{
            "id": "STATE-ORDER", "name": "Order", "owner_node_id": node_id,
            "reader_node_ids": [node_id], "writer_node_ids": [node_id],
            "lifecycle": "created to retained", "consistency_boundary": "one transaction",
            "retention_and_privacy": "retain 30 days", "source_refs": ["REQ-001"],
        }],
        "contracts": [{
            "id": "API-ORDER-CREATE", "type": "api", "provider_id": node_id,
            "consumer_ids": ["EXT-IDP"], "trigger": "valid request", "protocol": "HTTPS",
            "interaction_style": "sync", "schema_fields": ["operator_id", "order_id"],
            "side_effects": "creates order", "dependency_ids": [],
            "error_semantics": "typed 4xx/5xx", "timeout": "2s", "retry": "none",
            "idempotency": "Idempotency-Key", "version": "1", "requirement_ids": ["REQ-001"],
            "source_refs": ["REQ-001"],
        }],
        "runtime_flows": [{
            "id": "FLOW-ORDER-CREATE", "name": "Create order", "kind": "success",
            "requirement_ids": ["REQ-001"], "source_refs": ["REQ-001"],
            "steps": [{
                "order": 1, "from_id": "EXT-IDP", "to_id": node_id,
                "contract_id": "API-ORDER-CREATE", "action": "submit authenticated order",
                "failure_behavior": "return typed error",
            }],
        }],
        "technology_decisions": [{
            "id": "TECH-RUNTIME", "choice": "Python service", "affected_node_ids": [node_id],
            "driver_refs": ["REQ-001"], "rationale": "Team support", "status": "accepted",
        }],
        "deployment_units": [{
            "id": "DEPLOY-ORDER", "name": "Order deployment", "node_ids": [node_id],
            "scaling": "horizontal", "isolation": "process", "operations": "health checks",
            "source_refs": ["REQ-001"],
        }],
        "decisions": [{
            "id": "AD-ORDER-BOUNDARY", "classification": "decide_now",
            "question": "Who owns order writes?", "decision": node_id,
            "alternatives": ["shared ownership"], "consequences": ["single owner"],
            "affected_node_ids": [node_id], "source_refs": ["REQ-001"], "status": "decided",
        }],
        "risks": [{
            "id": "RISK-IDP", "description": "Identity provider outage", "severity": "high",
            "mitigation": "fail closed", "status": "open", "source_refs": ["REQ-001"],
        }],
        "assumptions": ["Identity tokens are verifiable"],
        "open_questions": [],
        "traceability": [{
            "source_id": "REQ-001", "target_ids": [node_id, "API-ORDER-CREATE"],
            "relation": "allocated_to", "evidence_refs": ["REQ-001"],
        }],
        "child_handoff": {
            "recommended_target_ids": [node_id],
            "required_ancestor_context": ["system boundary", "public contracts"],
        },
        "review": {"status": "approved", "reviewer": "architect", "evidence_ref": "review:001"},
    }


def child_design() -> dict:
    return {
        "design_context": {
            "summary": "Order Module", "scope": "Internal order realization",
            "goals": ["Separate orchestration and storage"], "non_goals": ["Change public API"],
            "responsibility": "Refine only MOD-ORDER", "exclusions": ["Sibling redesign"],
            "external_systems": [{
                "id": "EXT-IDP", "name": "Identity Provider",
                "responsibility": "Authenticate operators", "source_refs": ["REQ-001"],
            }],
        },
        "requirement_allocations": [{
            "requirement_id": "REQ-001", "classification": "inherited",
            "owner_node_ids": ["CMP-HANDLER", "CMP-STORE"], "source_refs": ["REQ-001"],
            "reason": "Realizes parent allocation",
        }],
        "nodes": [
            {
                "id": "CMP-HANDLER", "name": "Order Handler", "kind": "component",
                "responsibility": "Validate and coordinate order creation", "exclusions": ["Persist data"],
                "requirement_ids": ["REQ-001"], "state_ids": [], "dependency_ids": ["CMP-STORE"],
                "source_refs": ["REQ-001"], "rationale": "Separate orchestration",
            },
            {
                "id": "CMP-STORE", "name": "Order Store", "kind": "component",
                "responsibility": "Persist orders", "exclusions": ["Authenticate operators"],
                "requirement_ids": ["REQ-001"], "state_ids": ["STATE-ORDER-LOCAL"],
                "dependency_ids": [], "source_refs": ["REQ-001"], "rationale": "Single data owner",
            },
        ],
        "state_ownership": [{
            "id": "STATE-ORDER-LOCAL", "name": "Order record", "owner_node_id": "CMP-STORE",
            "reader_node_ids": ["CMP-HANDLER"], "writer_node_ids": ["CMP-STORE"],
            "lifecycle": "created to retained", "consistency_boundary": "store transaction",
            "retention_and_privacy": "inherit parent", "source_refs": ["REQ-001"],
        }],
        "contracts": [{
            "id": "INT-ORDER-SAVE", "type": "internal", "provider_id": "CMP-STORE",
            "consumer_ids": ["CMP-HANDLER"], "trigger": "validated order", "protocol": "in-process",
            "interaction_style": "sync", "schema_fields": ["order_id"], "side_effects": "persists order",
            "dependency_ids": [], "error_semantics": "typed storage error", "timeout": "1s",
            "retry": "none", "idempotency": "order_id", "version": "1",
            "requirement_ids": ["REQ-001"], "source_refs": ["REQ-001"],
        }],
        "contract_realizations": [{
            "contract_id": "API-ORDER-CREATE", "realizing_node_ids": ["CMP-HANDLER"],
            "notes": "Handler preserves the inherited API",
        }],
        "runtime_flows": [{
            "id": "FLOW-ORDER-INTERNAL", "name": "Persist order", "kind": "success",
            "requirement_ids": ["REQ-001"], "source_refs": ["REQ-001"],
            "steps": [{
                "order": 1, "from_id": "CMP-HANDLER", "to_id": "CMP-STORE",
                "contract_id": "INT-ORDER-SAVE", "action": "persist validated order",
                "failure_behavior": "propagate typed error",
            }],
        }],
        "technology_decisions": [], "deployment_units": [],
        "decisions": [{
            "id": "LAD-ORDER-COMPONENTS", "classification": "decide_now",
            "question": "How is MOD-ORDER split?", "decision": "handler plus store",
            "alternatives": ["single component"], "consequences": ["clear state owner"],
            "affected_node_ids": ["CMP-HANDLER", "CMP-STORE"],
            "source_refs": ["REQ-001"], "status": "decided",
        }],
        "risks": [], "assumptions": ["Parent API remains fixed"], "open_questions": [],
        "traceability": [{
            "source_id": "REQ-001", "target_ids": ["CMP-HANDLER", "CMP-STORE"],
            "relation": "realized_by", "evidence_refs": ["REQ-001"],
        }],
        "child_handoff": {"recommended_target_ids": ["CMP-STORE"], "required_ancestor_context": ["MOD-ORDER boundary"]},
        "review": {"status": "approved", "reviewer": "module-architect", "evidence_ref": "review:002"},
    }


def component_design() -> dict:
    return {
        "design_context": {
            "summary": "Order Handler", "scope": "Internal handler realization",
            "goals": ["Separate validation and coordination"],
            "non_goals": ["Change module contracts"],
            "responsibility": "Refine only CMP-HANDLER", "exclusions": ["Store redesign"],
            "external_systems": [],
        },
        "requirement_allocations": [{
            "requirement_id": "REQ-001", "classification": "inherited",
            "owner_node_ids": ["SUB-VALIDATOR", "SUB-COORDINATOR"],
            "source_refs": ["REQ-001"], "reason": "Realizes the component allocation",
        }],
        "nodes": [
            {
                "id": "SUB-VALIDATOR", "name": "Order Validator", "kind": "subcomponent",
                "responsibility": "Validate order input", "exclusions": ["Persistence"],
                "requirement_ids": ["REQ-001"], "state_ids": [],
                "dependency_ids": [], "source_refs": ["REQ-001"],
                "rationale": "Isolate validation rules",
            },
            {
                "id": "SUB-COORDINATOR", "name": "Order Coordinator", "kind": "subcomponent",
                "responsibility": "Coordinate validated writes", "exclusions": ["Own order state"],
                "requirement_ids": ["REQ-001"], "state_ids": [],
                "dependency_ids": ["SUB-VALIDATOR"], "source_refs": ["REQ-001"],
                "rationale": "Preserve orchestration boundary",
            },
        ],
        "state_ownership": [],
        "contracts": [{
            "id": "INT-HANDLER-VALIDATE", "type": "internal",
            "provider_id": "SUB-VALIDATOR", "consumer_ids": ["SUB-COORDINATOR"],
            "trigger": "order input", "protocol": "in-process", "interaction_style": "sync",
            "schema_fields": ["order_id"], "side_effects": "None; read-only",
            "dependency_ids": [], "error_semantics": "validation result", "timeout": "100ms",
            "retry": "none", "idempotency": "pure validation", "version": "1",
            "requirement_ids": ["REQ-001"], "source_refs": ["REQ-001"],
        }],
        "contract_realizations": [
            {
                "contract_id": "API-ORDER-CREATE",
                "realizing_node_ids": ["SUB-COORDINATOR"],
                "notes": "Preserve the ancestor public API",
            },
            {
                "contract_id": "INT-ORDER-SAVE",
                "realizing_node_ids": ["SUB-COORDINATOR"],
                "notes": "Preserve the parent internal save contract",
            },
        ],
        "runtime_flows": [{
            "id": "FLOW-HANDLER-INTERNAL", "name": "Validate then coordinate", "kind": "success",
            "requirement_ids": ["REQ-001"], "source_refs": ["REQ-001"],
            "steps": [{
                "order": 1, "from_id": "SUB-COORDINATOR", "to_id": "SUB-VALIDATOR",
                "contract_id": "INT-HANDLER-VALIDATE", "action": "validate order",
                "failure_behavior": "stop before persistence",
            }],
        }],
        "technology_decisions": [], "deployment_units": [], "decisions": [], "risks": [],
        "assumptions": ["Ancestor contracts remain fixed"], "open_questions": [],
        "traceability": [{
            "source_id": "REQ-001", "target_ids": ["SUB-VALIDATOR", "SUB-COORDINATOR"],
            "relation": "realized_by", "evidence_refs": ["REQ-001"],
        }],
        "child_handoff": {
            "recommended_target_ids": ["SUB-COORDINATOR"],
            "required_ancestor_context": ["MOD-ORDER", "CMP-HANDLER"],
        },
        "review": {
            "status": "approved", "reviewer": "component-architect",
            "evidence_ref": "review:003",
        },
    }


def build_top(name: str = "Order Module", node_id: str = "MOD-ORDER") -> dict:
    return build_canonical_architecture(
        top_design(name=name, node_id=node_id),
        build_canonical_prd(prd_source()),
        architecture_mode="top_level",
        input_artifacts=artifact_refs(),
    )


class CanonicalArchitectureTests(unittest.TestCase):
    def test_cli_two_modes_emit_the_same_public_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            root_prd_path = temporary_root / "root-prd.json"
            child_prd_path = temporary_root / "child-prd.json"
            root_prd_path.write_text(
                canonical_json_text(build_canonical_prd(prd_source())), encoding="utf-8"
            )
            child_prd_path.write_text(
                canonical_json_text(
                    build_canonical_prd(
                        prd_source(node_id="MOD-ORDER", parent_node_id="root", depth=1)
                    )
                ),
                encoding="utf-8",
            )
            root_output = temporary_root / "root-architecture"
            child_output = temporary_root / "child-architecture"
            top = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_architecture_flow.py"),
                    "top-level",
                    "--prd", str(root_prd_path),
                    "--design", str(ROOT / "templates" / "top-level-design-input.json"),
                    "--output-dir", str(root_output),
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertEqual(top.returncode, 0, top.stdout + top.stderr)
            child = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_architecture_flow.py"),
                    "decompose",
                    "--prd", str(child_prd_path),
                    "--parent-architecture", str(root_output / "architecture.json"),
                    "--target-node-id", "MOD-ORDER",
                    "--design", str(ROOT / "templates" / "decompose-design-input.json"),
                    "--output-dir", str(child_output),
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertEqual(
                {item.name for item in root_output.iterdir()},
                {item.name for item in child_output.iterdir()},
            )
            root_model = json.loads((root_output / "architecture.json").read_text(encoding="utf-8"))
            child_model = json.loads((child_output / "architecture.json").read_text(encoding="utf-8"))
            self.assertEqual(tuple(root_model), tuple(child_model))
            self.assertEqual(tuple(root_model["payload"]), tuple(child_model["payload"]))
            self.assertEqual(root_model["architecture_mode"], "top_level")
            self.assertEqual(child_model["architecture_mode"], "decompose")

    def test_different_content_has_identical_shape_and_section_order(self) -> None:
        first = build_top()
        second = build_top("Profile Module", "MOD-PROFILE")
        self.assertEqual(tuple(first), tuple(second))
        self.assertEqual(tuple(first["payload"]), tuple(second["payload"]))
        self.assertEqual(first["section_order"], list(SECTION_ORDER))
        first_headings = [line.split(". ", 1)[1] for line in render_canonical_architecture(first).splitlines() if line.startswith("## ")]
        second_headings = [line.split(". ", 1)[1] for line in render_canonical_architecture(second).splitlines() if line.startswith("## ")]
        self.assertEqual(first_headings, list(SECTION_ORDER))
        self.assertEqual(first_headings, second_headings)

    def test_input_array_order_is_canonical(self) -> None:
        draft = top_design()
        extra = copy.deepcopy(draft["risks"][0])
        extra.update({"id": "RISK-STORE", "description": "Store outage"})
        draft["risks"].append(extra)
        shuffled = copy.deepcopy(draft)
        shuffled["risks"].reverse()
        self.assertEqual(
            canonical_json_text(build_canonical_architecture(draft, build_canonical_prd(prd_source()), architecture_mode="top_level", input_artifacts=artifact_refs())),
            canonical_json_text(build_canonical_architecture(shuffled, build_canonical_prd(prd_source()), architecture_mode="top_level", input_artifacts=artifact_refs())),
        )

    def test_schema_semantics_profiles_and_fixed_bundle(self) -> None:
        model = build_top()
        self.assertEqual(validate_canonical_architecture(model, require_ready=True), [])
        for consumer in ("canonical", "decompose", "mocktest", "leaf", "vibe_adapter"):
            self.assertEqual(validate_consumer_profile(model, consumer), [], consumer)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "architecture"
            errors = write_bundle(model, output, schema_path=ROOT / "schemas" / "canonical-architecture.schema.json")
            self.assertEqual(errors, [])
            self.assertEqual({item.name for item in output.iterdir()}, set(FIXED_BUNDLE))
            headings = [line.split(". ", 1)[1] for line in (output / "architecture.md").read_text(encoding="utf-8").splitlines() if line.startswith("## ")]
            self.assertEqual(headings, list(SECTION_ORDER))

    def test_fail_closed_for_mutated_allocations_and_projections(self) -> None:
        model = build_top()
        model["payload"]["requirement_allocations"] = []
        model["components"] = []
        errors = validate_canonical_architecture(model, require_ready=True)
        self.assertTrue(any("without allocation" in item for item in errors))
        self.assertTrue(any("components projection" in item for item in errors))
        self.assertTrue(any("content_sha256" in item for item in errors))

    def test_top_to_decompose_exact_binding_and_parent_immutability(self) -> None:
        parent = build_top()
        child_prd = build_canonical_prd(prd_source(node_id="MOD-ORDER", parent_node_id="root", depth=1))
        child = build_canonical_architecture(
            child_design(), child_prd, architecture_mode="decompose",
            parent_architecture=parent, target_node_id="MOD-ORDER",
            input_artifacts=[*artifact_refs(), {
                "artifact_id": parent["artifact_id"], "artifact_type": "architecture",
                "artifact_schema_version": parent["artifact_schema_version"],
                "path": "inputs/parent-architecture.json", "sha256": "c" * 64,
            }],
        )
        self.assertEqual(validate_canonical_architecture(child, require_ready=True, parent_architecture=parent), [])
        self.assertTrue(all(item["inherited"] for item in child["payload"]["inherited_contracts"]))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "child"
            self.assertEqual(write_bundle(child, output, schema_path=ROOT / "schemas" / "canonical-architecture.schema.json", parent_architecture=parent), [])
            self.assertEqual({item.name for item in output.iterdir()}, set(FIXED_BUNDLE))
        mutated_parent = copy.deepcopy(parent)
        mutated_parent["payload"]["nodes"][0]["responsibility"] = "Changed after child approval"
        errors = validate_canonical_architecture(child, require_ready=True, parent_architecture=mutated_parent)
        self.assertTrue(any("immutable_snapshot" in item or "fingerprint" in item for item in errors))

    def test_component_level_decompose_preserves_ancestor_contracts(self) -> None:
        top = build_top()
        module_prd = build_canonical_prd(
            prd_source(node_id="MOD-ORDER", parent_node_id="root", depth=1)
        )
        module = build_canonical_architecture(
            child_design(), module_prd, architecture_mode="decompose",
            parent_architecture=top, target_node_id="MOD-ORDER",
            input_artifacts=artifact_refs(),
        )
        component_prd = build_canonical_prd(
            prd_source(node_id="CMP-HANDLER", parent_node_id="MOD-ORDER", depth=2)
        )
        component = build_canonical_architecture(
            component_design(), component_prd, architecture_mode="decompose",
            parent_architecture=module, target_node_id="CMP-HANDLER",
            input_artifacts=artifact_refs(),
        )
        self.assertEqual(
            validate_canonical_architecture(
                component, require_ready=True, parent_architecture=module
            ),
            [],
        )
        inherited_ids = {
            item["id"] for item in component["payload"]["inherited_contracts"]
        }
        self.assertEqual(
            inherited_ids,
            {"API-ORDER-CREATE", "INT-ORDER-SAVE"},
        )

    def test_real_prd_derive_and_mocktest_markdown_parsers(self) -> None:
        model = build_top()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "architecture"
            self.assertEqual(write_bundle(model, output, schema_path=ROOT / "schemas" / "canonical-architecture.schema.json"), [])
            module = extract_module_context(output / "architecture.json", "Order Module")
            self.assertTrue(module["found"], module)
            self.assertEqual(module["module"]["id"], "MOD-ORDER")
            parsed = ArchDocParser().parse(str(output))
            self.assertIn("MOD-ORDER", {item.name for item in parsed.components})

    def test_real_leaf_gate_accepts_generated_architecture(self) -> None:
        model = build_top()
        prd = build_canonical_prd(prd_source())
        common = {
            key: model[key]
            for key in (
                "schema_version", "run_id", "project_id", "node_id", "parent_node_id",
                "created_at", "generator", "status", "input_artifacts", "requirement_ids",
            )
        }
        with tempfile.TemporaryDirectory() as temporary:
            node = Path(temporary)
            (node / "architecture.json").write_text(canonical_json_text(model), encoding="utf-8")
            (node / "prd.json").write_text(canonical_json_text(prd), encoding="utf-8")
            (node / "testcases.json").write_text(json.dumps(common | {
                "artifact_id": "testcases:project-order:root:run-arch-001", "artifact_type": "testcases",
                "testcases": [{"id": "TC-001", "requirement_ids": ["REQ-001"], "status": "PASS"}],
            }), encoding="utf-8")
            (node / "mocktest_report.json").write_text(json.dumps(common | {
                "artifact_id": "mocktest:project-order:root:run-arch-001", "artifact_type": "mocktest_report",
                "defects": [],
            }), encoding="utf-8")
            output = node / "leaf_gate_decision.json"
            result = subprocess.run(
                [sys.executable, str(WORKFLOW_ROOT / "leaf-gate" / "scripts" / "run_leaf_gate.py"), str(node), "--output", str(output)],
                text=True, capture_output=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(json.loads(output.read_text(encoding="utf-8"))["decision"], {"STOP_LAYERING", "CONTINUE_LAYERING"})

    def test_blocked_decompose_emits_explicit_parent_change_request(self) -> None:
        parent = build_top()
        child_prd = build_canonical_prd(prd_source(node_id="MOD-ORDER", parent_node_id="root", depth=1))
        draft = child_design()
        draft["change_requests"] = [{
            "id": "PCR-ORDER-API", "trigger_requirement_id": "REQ-001",
            "affected_parent_field": "contracts.API-ORDER-CREATE",
            "current_rule": "synchronous", "proposed_change": "asynchronous",
            "impact": "requires parent approval", "blocked_decision_ids": ["LAD-ORDER-COMPONENTS"],
        }]
        draft["review"] = {"status": "pending", "reviewer": "", "evidence_ref": ""}
        child = build_canonical_architecture(
            draft, child_prd, architecture_mode="decompose",
            parent_architecture=parent, target_node_id="MOD-ORDER", input_artifacts=artifact_refs(),
        )
        self.assertEqual(child["status"], "FAIL")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "child"
            errors = write_bundle(child, output, schema_path=ROOT / "schemas" / "canonical-architecture.schema.json", parent_architecture=parent)
            self.assertEqual(errors, [])
            self.assertTrue((output / "parent-change-request.md").is_file())


if __name__ == "__main__":
    unittest.main()
