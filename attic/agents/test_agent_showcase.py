"""
Tests for the GLYPH agent showcase payload generator.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "agent_showcase.py"


spec = importlib.util.spec_from_file_location("agent_showcase", MODULE_PATH)
agent_showcase = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = agent_showcase
spec.loader.exec_module(agent_showcase)


def test_showcase_payload_contains_expected_sections():
    payload = agent_showcase.build_showcase_payload()

    assert payload["meta"]["title"] == "GLYPH Agent Control Room"
    assert payload["metrics"]["tool_call_count"] == 3
    assert len(payload["personas"]) == 4
    assert payload["personas"][0]["artifact"]["output_type"] == "Explanation"
    assert payload["planning"]["phases"][0]["owner"] == "Feynman"
    assert payload["patches"]
    assert "session_id" in payload["checkpoint"]["json"]


def test_showcase_payload_reflects_settings_toggles():
    payload = agent_showcase.build_showcase_payload(
        {"enable_tools": False, "include_arbiter": False}
    )

    assert payload["metrics"]["tool_call_count"] == 0
    assert len(payload["personas"]) == 3
    assert payload["settings"]["include_arbiter"] is False
