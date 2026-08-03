"""Real consumer contract probe for the sibling Mocktest Gherkin loader."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tests/mocktest_loader_contract.py <testcases.feature>")
    repository = Path(__file__).resolve().parents[1]
    mocktest_src = repository.parent / "mocktest" / "src"
    sys.path.insert(0, str(mocktest_src))

    from mock_framework.loader.gherkin_parser import GherkinParser

    feature = GherkinParser().parse(sys.argv[1])
    assert feature.background is None
    assert feature.scenarios
    assert [item.id for item in feature.scenarios] == [
        f"SCENARIO-{index:03d}" for index in range(1, len(feature.scenarios) + 1)
    ]
    for scenario in feature.scenarios:
        assert scenario.examples is None
        assert sum(tag.startswith("@TC-") for tag in scenario.tags) == 1
        assert any(tag.startswith("@REQ-") or tag.startswith("@NFR-") for tag in scenario.tags)
        keywords = [step.keyword for step in scenario.steps]
        assert keywords[0] == "Given"
        assert keywords.count("When") == 1
        assert "Then" in keywords
    print(json.dumps({"status": "PASS", "loader": "mock_framework.loader.GherkinParser", "scenarios": len(feature.scenarios)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
