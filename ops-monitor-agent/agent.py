"""
The Fernbrook Operations Monitor: a second, deliberately separate
agent, built for Design Note 35 to make Design Note 34's tradeoffs concrete,
not to replace anything about the Fernbrook Ops Agent itself.

This agent answers a genuinely different question, for a genuinely
different audience: not "what's my order status," but "is the Ops
Agent healthy right now," asked by Fernbrook's internal support and
engineering staff, not customers. It has its own system prompt, its
own single tool, and lives in its own top-level directory, on purpose;
a second agent that shared agent/ with the first wouldn't actually
demonstrate the separation Design Note 34 described.

Deliberately not built here, and named honestly rather than glossed
over: real staff identity verification (this agent currently trusts
whoever can invoke it, exactly the gap Design Notes 9 through 15 spent six
notes closing for customers, not yet repeated here), and real A2A
wiring to let the Fernbrook Ops Agent delegate to this one directly.
Both are real, sensible next steps, not completed in this design note,
which is about the shape of a justified second agent, not a second
full production build.
"""

from datetime import datetime, timedelta, timezone

import boto3
from strands import Agent, tool
from strands.models import BedrockModel

REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
METRICS_NAMESPACE = "FernbrookOpsAgent"

cloudwatch = boto3.client("cloudwatch", region_name=REGION)

SYSTEM_PROMPT = """
You are the Fernbrook Operations Monitor, used by Fernbrook's internal
support and engineering staff to check the health of the Fernbrook Ops
Agent. You are not customer-facing, and you have no access to any
customer's order, account, or refund data directly; you only summarize
operational metrics that were already recorded, in aggregate.

Use query_operational_metric to answer questions about the Ops Agent's
recent behavior: how many refunds were escalated, how many ownership
checks were denied, how often memory degraded, and similar operational
signals. Report actual numbers from the tool, never estimates. If a
metric name isn't recognized, say so rather than guessing which metric
the person meant.

A nonzero LookupOwnershipDenied count deserves being flagged as worth
investigating, not just reported neutrally; see Design Note 25 for why that
specific metric is treated differently from the others.
"""


@tool
def query_operational_metric(metric_name: str, hours: int = 24) -> dict:
    """Return the total count of a Fernbrook Ops Agent metric over a
    recent time window.

    metric_name must be one already emitted by the Ops Agent, for
    example RefundEscalated, LookupOwnershipDenied,
    RefundIdempotentReplay, or MemoryUnavailableDegraded (see
    agent/emit_metric.py and Design Notes 25, 32, and 33 for the full set).
    hours is how far back to look, 24 by default.
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    response = cloudwatch.get_metric_statistics(
        Namespace=METRICS_NAMESPACE,
        MetricName=metric_name,
        StartTime=start_time,
        EndTime=end_time,
        Period=hours * 3600,
        Statistics=["Sum"],
    )

    datapoints = response.get("Datapoints", [])
    total = sum(d["Sum"] for d in datapoints) if datapoints else 0

    return {
        "metric_name": metric_name,
        "hours": hours,
        "total": total,
    }


def run_ops_monitor(prompt: str) -> str:
    """Run one turn of the Ops Monitor agent and return its reply.

    No actor_id, no session scoping, no customer memory: this agent's
    entire input and output space is aggregate operational numbers,
    not anything tied to an individual customer, which is exactly why
    it doesn't need most of the identity machinery the earlier design notes
    built for the customer-facing agent.
    """
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[query_operational_metric],
    )
    result = agent(prompt)
    return result.message


if __name__ == "__main__":
    import sys

    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "How many refunds were escalated for manager review in the last 24 hours?"
    )
    print(run_ops_monitor(prompt))
