from __future__ import annotations

import hashlib
import json

from vibecode.artifact_contract import canonical_json_bytes, validate_content_hash


def test_json_artifact_hash_omits_only_its_top_level_hash(tmp_path):
    artifact = {
        "schema_version": "verilayer-artifact/v0.2",
        "artifact_id": "r1:n1:prd",
        "nested": {"content_sha256": "must-remain"},
    }
    digest = hashlib.sha256(canonical_json_bytes(artifact)).hexdigest()
    artifact["content_sha256"] = digest
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")
    envelope = {"content_path": "artifact.json", "content_sha256": digest}
    assert validate_content_hash(envelope, tmp_path) == []
