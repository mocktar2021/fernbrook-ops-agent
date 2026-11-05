"""
Small, dependency-free helpers for AgentCore Gateway tool names.

AgentCore Gateway exposes every tool to MCP clients as
`<target name>___<tool name>` (three underscores), for example
`OrderLookup___get_order_status`. Cedar policy actions use that same
prefixed form. The agent's code, though, thinks in base tool names
(`get_order_status`). Resolving one to the other at runtime, from the
live tool listing, means the agent keeps working whichever target name
is configured, and a rename in Terraform cannot silently break a call.

Kept separate from agent.py so it can be unit tested without the
Strands/AgentCore SDKs or any environment variables.
"""

GATEWAY_TOOL_DELIMITER = "___"


def base_tool_name(full_name: str) -> str:
    """Strip the `<target>___` prefix, if there is one."""
    return full_name.split(GATEWAY_TOOL_DELIMITER, 1)[-1]


def resolve_gateway_tool_names(tools) -> dict:
    """Map base tool name -> full Gateway tool name for a tool listing.

    `tools` is any iterable of objects exposing `tool_name`, which is what
    Strands' MCP client returns from list_tools_sync(). Objects without a
    usable name are skipped.
    """
    mapping = {}
    for tool in tools:
        full_name = getattr(tool, "tool_name", None)
        if full_name:
            mapping[base_tool_name(full_name)] = full_name
    return mapping
