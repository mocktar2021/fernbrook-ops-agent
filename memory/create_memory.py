"""
One-time setup: create the AgentCore Memory resource the Fernbrook Ops
Agent uses for short-term, session-scoped memory.

Run this once. It prints the new memory resource's ID; set that as the
AGENTCORE_MEMORY_ID environment variable before running or deploying the
agent (see this folder's README). Running this script again creates a
second, separate memory resource. It does not update the existing one,
and it does not delete anything.

This resource is created with no long-term memory strategies. That's
deliberate, not a placeholder to fill in later: Design Note 8 makes the case
that short-term, session-scoped memory matches what Fernbrook's support
use case actually needs, and that long-term, cross-session consolidation
is a decision that deserves its own explicit justification. If that
justification shows up in a later design note, this script is where a
strategy would be added, visibly, not silently.
"""

from bedrock_agentcore.memory import MemoryClient

REGION = "us-east-1"


def main() -> None:
    client = MemoryClient(region_name=REGION)

    memory = client.create_memory(
        name="FernbrookOpsAgentShortTermMemory",
        description=(
            "Short-term, session-scoped memory for the Fernbrook Ops "
            "Agent. No long-term strategies enabled; see Design Note 8 and "
            "Design Note 9 for why."
        ),
    )

    memory_id = memory.get("id")
    print(f"Created memory resource: {memory_id}")
    print()
    print("Set this before running or deploying the agent:")
    print(f"  export AGENTCORE_MEMORY_ID={memory_id}")


if __name__ == "__main__":
    main()
