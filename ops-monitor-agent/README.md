# Fernbrook Operations Monitor

A second, deliberately separate agent, built in Design Note 35 to make Design Note 34's multi-agent tradeoffs concrete. Not a replacement for anything in `agent/`, and not wired to it.

## What it does

Answers questions about the Fernbrook Ops Agent's own operational health, using the EMF metrics `agent/emit_metric.py` has been emitting since Design Note 25: how many refunds were escalated, how many ownership checks were denied, how often memory degraded. One tool, `query_operational_metric`, reads directly from the `FernbrookOpsAgent` CloudWatch namespace.

## Running it locally

```bash
python3 ops-monitor-agent/agent.py "How many refunds were escalated in the last 24 hours?"
python3 ops-monitor-agent/agent.py "Were there any ownership violations in the last week?"
```

## Why this counts as a genuinely separate agent, not just another tool

Design Note 34's test: does this need to share context, identity, or ownership with the customer-facing agent? No. It has no customer conversation, no `actor_id`, no session, and answers a completely different kind of question, for a completely different audience, Fernbrook's internal staff, not customers. That's the real justification; it isn't here because two agents are more impressive than one.

## What's deliberately not built

- **Staff identity verification.** This agent currently trusts whoever can invoke it. Design Notes 9 through 15 spent six design notes closing exactly this kind of gap for customers; repeating that work for internal staff access is real, sensible next work, not done here.
- **A2A wiring to the Fernbrook Ops Agent.** Design Note 34 described AgentCore Gateway's Agent Target category as the current path for exactly this kind of delegation. Building it is real, available work; this design note's job was demonstrating why a second agent is justified here, not shipping the full integration.
- **A deployment.** This agent runs locally in this repository. It has no Runtime deployment, no execution role, no Terraform of its own.
