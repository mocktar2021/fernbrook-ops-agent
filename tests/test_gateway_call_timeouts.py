"""
Guard against passing a number as the MCP read timeout.

Strands' MCPClient.call_tool_sync expects read_timeout_seconds to be a
datetime.timedelta. An int is accepted by Python, the request is sent, and
then the client fails computing the timeout. The tool runs, but the agent
loses its result and reports "not found". This test reads agent/agent.py
without importing it, so it needs no SDKs or AWS access.
"""

import ast
from pathlib import Path

AGENT = Path(__file__).parent.parent / "agent" / "agent.py"


def _tree():
    return ast.parse(AGENT.read_text(encoding="utf-8"))


def test_gateway_calls_never_pass_a_number_as_timeout():
    calls = [
        node for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "call_tool_sync"
    ]
    assert calls, "Expected call_tool_sync calls in agent/agent.py."
    for call in calls:
        for kw in call.keywords:
            if kw.arg == "read_timeout_seconds":
                assert not (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, (int, float))
                ), f"line {call.lineno}: read_timeout_seconds must be a timedelta, not a number"


def test_gateway_read_timeout_is_a_timedelta():
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "GATEWAY_READ_TIMEOUT" for t in node.targets
        ):
            value = node.value
            assert isinstance(value, ast.Call) and getattr(value.func, "id", "") == "timedelta"
            return
    raise AssertionError("GATEWAY_READ_TIMEOUT is not defined in agent/agent.py")
