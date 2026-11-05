> **Note:** the setup steps below describe the original manual path and are kept to explain the design. In this repository Terraform (`infrastructure/platform/memory.tf`) creates the memory resource; `create_memory.py` is the older script version. Follow `docs/GETTING-STARTED.md` to deploy.

# AgentCore Memory setup

This folder holds the one-time setup for the Fernbrook Ops Agent's memory, not the agent's own code (that's still in `agent/`).

## Setup

```bash
python3 memory/create_memory.py
```

This creates one AgentCore Memory resource, scoped to short-term, session-based memory only, and prints its ID. Export that ID before running or deploying the agent:

```bash
export AGENTCORE_MEMORY_ID=<the-id-printed-above>
```

`agent/agent.py` reads this from the environment; it does not create the memory resource itself, and it will raise a clear error if the variable isn't set.

## Why short-term only

Design Note 8 makes the full argument. In short: Fernbrook's actual requirement is that a customer shouldn't have to repeat themselves within one conversation. It is not a requirement that the agent remember a customer across separate conversations, and cross-session memory carries privacy and correctness obligations, retention, deletion, staleness, that this project isn't taking on without a specific reason to. If a real need for long-term memory shows up later, it gets added here, deliberately and visibly, with those obligations answered first.

## Isolation

Every memory record is scoped by two identifiers: `actor_id` (the customer) and `session_id` (the specific conversation). AgentCore enforces that a request scoped to one actor and session cannot retrieve another's records. Design Note 9 covers what currently establishes `actor_id` in this project (the caller-supplied value in the request payload) and why that's an honest, temporary simplification that a later design note's Identity work replaces with something a caller can't simply assert.
