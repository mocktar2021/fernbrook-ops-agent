"""
Estimates the cost of one Fernbrook Ops Agent request, broken down by
the same cost drivers this project has flagged since Design Note 5: model
tokens, tool calls, memory operations, retrieval, and guardrail
evaluation.

The RATES dictionary below is a template, not a source of truth. Every
value in it needs to be checked against the current Bedrock, AgentCore,
and Lambda pricing pages before you trust a number this script
produces; this project teaches the shape of the calculation, not a
permanent table of prices, because those prices will have changed by
the time you read this. Fill in real values in your own environment.

Usage:

    python3 evaluations/estimate_cost.py \
        --input-tokens 850 --output-tokens 220 \
        --tool-calls 2 --memory-events 4 \
        --retrieval-calls 1 --guardrail-units 1
"""

import argparse

# TEMPLATE VALUES ONLY. Verify at:
#   https://aws.amazon.com/bedrock/pricing/
#   https://aws.amazon.com/bedrock/agentcore/pricing/
#   https://aws.amazon.com/lambda/pricing/
# before using this script to make a real budgeting decision.
RATES = {
    "model_input_per_1k_tokens": 0.0,   # USD, fill in for your model
    "model_output_per_1k_tokens": 0.0,  # USD, fill in for your model
    "gateway_per_invocation": 0.0,      # USD per tool call through Gateway
    "memory_per_event": 0.0,            # USD per short-term memory event
    "retrieval_per_query": 0.0,         # USD per Knowledge Base query
    "guardrail_per_unit": 0.0,          # USD per guardrail content unit
}


def estimate(
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    memory_events: int,
    retrieval_calls: int,
    guardrail_units: int,
) -> dict:
    """Break down estimated cost by driver, not just a single total.

    A single total number invites the exact mistake this design note warns
    against: treating cost as one line to shrug at instead of several
    distinct levers, each with its own reduction strategy.
    """
    breakdown = {
        "model_input": (input_tokens / 1000) * RATES["model_input_per_1k_tokens"],
        "model_output": (output_tokens / 1000) * RATES["model_output_per_1k_tokens"],
        "gateway_invocations": tool_calls * RATES["gateway_per_invocation"],
        "memory_events": memory_events * RATES["memory_per_event"],
        "retrieval": retrieval_calls * RATES["retrieval_per_query"],
        "guardrails": guardrail_units * RATES["guardrail_per_unit"],
    }
    breakdown["total"] = sum(breakdown.values())
    return breakdown


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-tokens", type=int, required=True)
    parser.add_argument("--output-tokens", type=int, required=True)
    parser.add_argument("--tool-calls", type=int, default=0)
    parser.add_argument("--memory-events", type=int, default=0)
    parser.add_argument("--retrieval-calls", type=int, default=0)
    parser.add_argument("--guardrail-units", type=int, default=0)
    args = parser.parse_args()

    result = estimate(
        args.input_tokens,
        args.output_tokens,
        args.tool_calls,
        args.memory_events,
        args.retrieval_calls,
        args.guardrail_units,
    )

    for driver, cost in result.items():
        print(f"{driver:20s} ${cost:.6f}")
