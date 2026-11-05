"""
The Fernbrook Ops Agent. Order and wholesale account lookups, and now
retrieval, are backed by AgentCore Gateway targets (Design Notes 12, 13,
19), but as of Design Note 23 (lookups) and a final repository
completion pass (retrieval) are no longer exposed to the model as raw Gateway
tools; they're wrapped in local functions that call the underlying
Gateway tool directly. The two lookups check the result against the
verified actor_id before returning anything, closing a cross-user data
leakage gap Design Note 21 found and Design Note 16 explained the root cause
of. Retrieve has no ownership check to make, but gets the same
graceful-degradation wrapping the two lookups already had, closing a
gap Design Note 33 claimed was closed project-wide and, until this pass,
wasn't quite. Refunds (Design Note 17) remain a fully local tool for a
related but distinct reason: verified actor_id has to reach the check,
and Gateway's current AWS_IAM authorization has no per-customer
identity to hand it directly.

Because Gateway tools come from a remote MCP connection, the connection
needs to stay open for the whole time the agent might use it, not just
while listing available tools. That's why this file doesn't expose a
build_agent() that hands back a ready-to-use Agent; instead, run_agent()
does the whole thing, model, memory, tools, and the actual call, inside
one open connection. See Design Note 12 for why.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from refund_logic import request_refund
from emit_metric import emit_metric
from gateway_names import resolve_gateway_tool_names, base_tool_name

REGION = "us-east-1"

# Claude Sonnet 4.6 through the US cross-region inference profile. AWS lists it
# as Active (checked 2026-11-05). Check the Bedrock model catalog before you
# build; model IDs have a lifecycle and this one will not last forever.
# Overridable via FERNBROOK_MODEL_ID (set from Terraform's model_id variable) so a
# model retirement is a one-line config change, not a code change.
MODEL_ID = os.environ.get("FERNBROOK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

# Claude Sonnet 5 and later reject temperature, top_p and top_k with a 400
# error, so none is sent by default. Set FERNBROOK_TEMPERATURE only if you switch
# to a model that accepts it (for example Sonnet 4.6).
_TEMPERATURE = os.environ.get("FERNBROOK_TEMPERATURE")

# Created once by memory/create_memory.py (Design Note 9).
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID")
if not MEMORY_ID:
    raise RuntimeError(
        "AGENTCORE_MEMORY_ID is not set. Run memory/create_memory.py "
        "once, then export the memory ID it prints. See memory/README.md."
    )

# Printed after `agentcore deploy` when the FernbrookGateway target was
# created; see tools/order_lookup/README.md.
GATEWAY_URL = os.environ.get("FERNBROOK_GATEWAY_URL")
if not GATEWAY_URL:
    raise RuntimeError(
        "FERNBROOK_GATEWAY_URL is not set. Deploy the Gateway described "
        "in tools/order_lookup/README.md, then export its MCP endpoint "
        "URL before running this agent."
    )

# Created once by agent/create_guardrail.py (Design Note 22). A second,
# independent safety layer; does not replace Cedar policy or
# process_refund's own authorization checks.
GUARDRAIL_ID = os.environ.get("FERNBROOK_GUARDRAIL_ID")
GUARDRAIL_VERSION = os.environ.get("FERNBROOK_GUARDRAIL_VERSION")
if not GUARDRAIL_ID or not GUARDRAIL_VERSION:
    raise RuntimeError(
        "FERNBROOK_GUARDRAIL_ID and FERNBROOK_GUARDRAIL_VERSION must both "
        "be set. Run agent/create_guardrail.py once, then export the "
        "values it prints."
    )

SYSTEM_PROMPT = """
You are an early, internal-only prototype of the Fernbrook Ops Agent.

You have a tool, current_utc_time, for the current date and time; a
tool, get_order_status, for looking up a Fernbrook order by its order
ID; a tool, get_wholesale_account_status, for looking up a Fernbrook
wholesale partner account by its account ID; a tool, process_refund,
for requesting a refund on an order; and a Retrieve tool for searching
Fernbrook's return, warranty, and shipping policy documents. Use
get_order_status whenever a customer asks about an order's status,
delivery date, or contents. Use get_wholesale_account_status whenever a
wholesale partner asks about their account's tier or approval status.
Both lookup tools only return records belonging to the verified
customer on this conversation; if either reports found: false, tell
the person plainly that you couldn't find that record, without
speculating about whether it exists under someone else's account.
Use Retrieve whenever a customer asks about a policy, a return window,
a warranty, or shipping terms, and answer using only what the
retrieved passages actually say. Do not guess or invent order,
account, or policy information.

Use process_refund only when a customer explicitly asks for a refund
on a specific order, with a specific dollar amount. You do not decide
whether a refund is approved; the tool does, deterministically. Refunds
of $100 or less are approved automatically. Refunds above that amount
are queued for manager review and are not processed immediately; tell
the customer plainly that their refund needs manager approval and has
not been issued yet. process_refund will deny any order that does not
belong to the verified customer on this conversation; if that happens,
tell the customer plainly that you couldn't process that request,
without speculating about why.

If any tool reports that it is temporarily unavailable, tell the
customer plainly and suggest trying again shortly. Do not guess at an
answer to fill the gap, and do not claim an action succeeded when a
tool has told you it could not complete.

You do not have access to any tool that can modify an account or
change approval status. If asked to do either of those things, say
plainly that you cannot yet do that.

You may recall earlier parts of this specific conversation, but you
have no memory of any other conversation with any other customer.
"""


@tool
def current_utc_time() -> str:
    """Return the current date and time in UTC, ISO 8601 format.

    Use this whenever a question depends on knowing what time or date
    it is right now. Do not guess the current time on your own.
    """
    return datetime.now(timezone.utc).isoformat()


def _parse_gateway_result(raw_result: dict) -> dict:
    """Extract the JSON payload Gateway wraps every tool result in."""
    content = raw_result.get("content") or []
    if not content:
        return {"found": False, "error": "No response from tool."}
    try:
        return json.loads(content[0].get("text", "{}"))
    except json.JSONDecodeError:
        return {"found": False, "error": "Malformed tool response."}


def run_agent(actor_id: str, session_id: str, prompt: str) -> str:
    """Run one turn of the Fernbrook Ops Agent and return its reply.

    actor_id identifies the customer; session_id identifies this one
    conversation with them, exactly as in Design Note 9. The connection to
    AgentCore Gateway is opened for the duration of this call only,
    long enough to discover and, if needed, invoke Gateway-hosted
    tools, including the two ownership-checked wrappers below.
    """
    model_kwargs = {}
    if _TEMPERATURE:
        model_kwargs["temperature"] = float(_TEMPERATURE)
    model = BedrockModel(
        model_id=MODEL_ID,
        region_name=REGION,
        guardrail_id=GUARDRAIL_ID,
        guardrail_version=GUARDRAIL_VERSION,
        guardrail_trace="enabled",
        **model_kwargs,
    )

    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        actor_id=actor_id,
        session_id=session_id,
    )
    # Design Note 33: memory is a real dependency that can be unreachable,
    # a question Design Note 8 raised and deferred. The answer: degrade,
    # don't fail the whole turn. A customer who has to repeat something
    # they already said is a worse experience than usual, not a broken
    # one; a request that fails outright because a memory backend
    # hiccuped is a worse outcome than that, for a read-heavy support
    # agent with nothing irreversible riding on memory specifically.
    try:
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config,
            region_name=REGION,
        )
    except Exception:
        emit_metric("MemoryUnavailableDegraded")
        session_manager = None

    # Design Note 17: process_refund is defined here, inside run_agent(),
    # deliberately not as a Gateway target like the two lookup tools.
    # It needs access to the verified actor_id from this specific,
    # authenticated request, and closing over it here means the model
    # never sees actor_id as a parameter it could supply or override;
    # Python's own function signature enforces that, not a system
    # prompt instruction the model is merely asked to follow.
    @tool
    def process_refund(order_id: str, amount: float, reason: str) -> dict:
        """Request a refund for a Fernbrook order.

        Refunds of $100 or less are approved automatically. Refunds
        above that amount are queued for manager review and are not
        processed immediately. This tool can only refund orders
        belonging to the verified customer on this conversation; any
        other order_id is denied.
        """
        try:
            return request_refund(
                actor_id=actor_id, order_id=order_id, amount=amount, reason=reason
            )
        except Exception:
            # Design Note 33: stop, don't guess. Unlike the two read tools
            # below, this touches money; if something failed in a way
            # this code didn't anticipate, the safe response is "try
            # again," not a best-effort answer about whether a refund
            # went through. Design Note 32 made this call idempotent
            # specifically so telling the customer to retry is now
            # actually safe advice, not a duplicate-refund risk.
            emit_metric("RefundToolUnavailable")
            return {
                "status": "unavailable",
                "reason": (
                    "Refund processing is temporarily unavailable. "
                    "Please try again in a moment."
                ),
            }

    # Gateway exposes tools as "<target>___<tool>". Filled in from the live
    # tool listing below, before the agent can call any wrapper.
    gateway_tool_names: dict = {}

    def _gateway_name(base: str) -> str:
        return gateway_tool_names.get(base, base)

    # Design Note 15: SigV4-signed, using this Runtime's own execution role,
    # not an unauthenticated connection. FernbrookGateway now requires
    # AWS_IAM inbound authorization; see identity/README.md.
    gateway_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_region=REGION,
            aws_service="bedrock-agentcore",
        )
    )

    # Design Note 23: get_order_status and getWholesaleAccountStatus are no
    # longer exposed to the model as raw Gateway tools. Cedar (Design Note
    # 16) still authorizes the underlying tool call, exactly as before;
    # what Cedar cannot do, given FernbrookGateway's AWS_IAM inbound
    # authorization, is check whether the specific order or account
    # requested actually belongs to this conversation's verified
    # actor_id. These wrappers close that gap the same way
    # process_refund already does: the check happens in code the model
    # cannot see or influence, using an actor_id it was never given as
    # a parameter.
    @tool
    def get_order_status(order_id: str) -> dict:
        """Look up the status of a Fernbrook order by its order ID.

        Only returns orders belonging to the verified customer on this
        conversation. Any other order_id returns found: false, the
        same response as an order_id that doesn't exist at all.
        """
        try:
            raw = gateway_client.call_tool_sync(
                tool_use_id=str(uuid.uuid4()),
                name=_gateway_name("get_order_status"),
                arguments={"order_id": order_id},
                read_timeout_seconds=10,  # Design Note 31: bound the Gateway round trip
            )
        except Exception:
            # Design Note 33: a read failure is safe to surface plainly and
            # safe to retry, unlike a write failure. No ownership
            # ambiguity here either way, since nothing was returned.
            emit_metric("LookupToolUnavailable", dimensions={"tool": "get_order_status"})
            return {
                "found": False,
                "error": "Order lookup is temporarily unavailable. Please try again shortly.",
            }
        order = _parse_gateway_result(raw)

        if not order.get("found") or order.get("customer_id") != actor_id:
            if order.get("found"):
                emit_metric("LookupOwnershipDenied", dimensions={"tool": "get_order_status"})
            return {"found": False, "error": f"No order found with ID {order_id}."}

        order.pop("customer_id", None)
        return order

    @tool
    def get_wholesale_account_status(account_id: str) -> dict:
        """Look up a Fernbrook wholesale account by its account ID.

        Only returns the account belonging to the verified wholesale
        customer on this conversation. Any other account_id returns
        found: false, the same response as an account_id that doesn't
        exist at all.
        """
        try:
            raw = gateway_client.call_tool_sync(
                tool_use_id=str(uuid.uuid4()),
                name=_gateway_name("getWholesaleAccountStatus"),
                arguments={"account_id": account_id},
                read_timeout_seconds=10,
            )
        except Exception:
            emit_metric(
                "LookupToolUnavailable",
                dimensions={"tool": "get_wholesale_account_status"},
            )
            return {
                "found": False,
                "error": "Account lookup is temporarily unavailable. Please try again shortly.",
            }
        account = _parse_gateway_result(raw)

        if not account.get("found") or account_id != actor_id:
            if account.get("found"):
                emit_metric(
                    "LookupOwnershipDenied",
                    dimensions={"tool": "get_wholesale_account_status"},
                )
            return {
                "found": False,
                "error": f"No wholesale account found with ID {account_id}.",
            }

        return account

    # Final completion pass: Retrieve has no per-customer
    # ownership concept (Design Note 23's reasoning for wrapping the two
    # tools above doesn't apply here), but it's still a Gateway call
    # that can fail, and until now nothing caught that. Design Note 33
    # claimed every dependency in this project degrades gracefully;
    # this was the one place that claim was incomplete. Wrapped the
    # same way as the two lookup tools, minus the ownership check.
    @tool
    def Retrieve(query: str) -> dict:
        """Search Fernbrook's return, warranty, and shipping policy
        documents for passages relevant to a customer's question.

        Returns the retrieved passages, or a message that retrieval is
        temporarily unavailable. Never answer a policy question from
        general knowledge if this tool reports unavailable; say so
        plainly instead.
        """
        try:
            raw = gateway_client.call_tool_sync(
                tool_use_id=str(uuid.uuid4()),
                name=_gateway_name("Retrieve"),
                arguments={"query": query},
                read_timeout_seconds=10,
            )
        except Exception:
            emit_metric("RetrievalToolUnavailable")
            return {
                "found": False,
                "error": "Policy lookup is temporarily unavailable. Please try again shortly.",
            }
        return _parse_gateway_result(raw)

    with gateway_client:
        gateway_tools = gateway_client.list_tools_sync()
        gateway_tool_names.update(resolve_gateway_tool_names(gateway_tools))
        # The order lookup, wholesale lookup, and retrieval tools are
        # all replaced above with wrapped versions; every other Gateway
        # tool this project doesn't yet have a reason to wrap is
        # exposed as-is. Verify `tool_name` against the current Strands
        # MCP tool object API before you build; if it's moved,
        # list_tools_sync()'s return objects will tell you the right
        # attribute via their own repr.
        other_gateway_tools = [
            t
            for t in gateway_tools
            if base_tool_name(getattr(t, "tool_name", "") or "")
            not in ("get_order_status", "getWholesaleAccountStatus", "Retrieve")
        ]

        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                current_utc_time,
                process_refund,
                get_order_status,
                get_wholesale_account_status,
                Retrieve,
            ]
            + other_gateway_tools,
            # Design Note 33: omitted entirely, not passed as None, when
            # memory setup failed above; Agent() without a
            # session_manager still works, just without persistence
            # across a restart, which is exactly the degraded-not-dead
            # behavior this design note argues for.
            **({"session_manager": session_manager} if session_manager else {}),
        )

        result = agent(prompt)
        return result.message


if __name__ == "__main__":
    import sys

    # For direct local testing of run_agent() only, bypassing app.py's
    # token verification. CUST-4471 matches the demo customer created
    # by scripts/set_demo_user_password.py, and is also the customer on
    # order FB-10293 in tools/order_lookup/seed_data.py.
    demo_actor_id = "CUST-4471"
    demo_session_id = "demo-session-1"
    demo_prompt = (
        sys.argv[1] if len(sys.argv) > 1 else "What's the status of order FB-10293?"
    )

    print(run_agent(demo_actor_id, demo_session_id, demo_prompt))
