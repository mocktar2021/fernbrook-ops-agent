"""Unit tests for agent/gateway_names.py (pure functions, no AWS needed)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from gateway_names import base_tool_name, resolve_gateway_tool_names  # noqa: E402


def test_base_name_strips_target_prefix():
    assert base_tool_name("OrderLookup___get_order_status") == "get_order_status"


def test_base_name_without_prefix_is_unchanged():
    assert base_tool_name("get_order_status") == "get_order_status"


def test_only_first_delimiter_is_split():
    assert base_tool_name("Target___tool___v2") == "tool___v2"


def test_resolve_maps_base_to_full_name():
    tools = [
        SimpleNamespace(tool_name="OrderLookup___get_order_status"),
        SimpleNamespace(tool_name="PolicyKnowledge___Retrieve"),
    ]
    assert resolve_gateway_tool_names(tools) == {
        "get_order_status": "OrderLookup___get_order_status",
        "Retrieve": "PolicyKnowledge___Retrieve",
    }


def test_resolve_skips_objects_without_names():
    tools = [SimpleNamespace(tool_name=None), SimpleNamespace(), SimpleNamespace(tool_name="A___b")]
    assert resolve_gateway_tool_names(tools) == {"b": "A___b"}
