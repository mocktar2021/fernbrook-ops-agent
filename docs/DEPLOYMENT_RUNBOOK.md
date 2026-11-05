# Deployment runbook: Fernbrook Ops Agent

The setup sequence is automated by Terraform and GitHub Actions. Follow [`GETTING-STARTED.md`](GETTING-STARTED.md) to deploy, and [`TEARDOWN.md`](TEARDOWN.md) to delete. The manual, CLI-driven steps that older versions of this runbook listed are replaced by:

| Old manual step | Now done by |
|---|---|
| Seed the orders table | Infra Apply workflow (`tools/order_lookup/seed_data.py`) |
| Create AgentCore Memory | `infrastructure/platform/memory.tf` |
| Create the Cognito pool and demo user | `infrastructure/platform/cognito.tf` plus `scripts/set_demo_user_password.py` |
| Create the Guardrail | `infrastructure/platform/guardrail.tf` |
| Create the Gateway, target, policy engine and Cedar policy | `infrastructure/platform/gateway.tf` and `policy.tf` |
| Grant the execution role its permissions | `infrastructure/platform/iam-runtime.tf` |
| Deploy the Runtime | App Deploy workflow and `infrastructure/release/` |

Still manual, once per account: enable CloudWatch Transaction Search so traces become searchable.

## Scope

This deploys the **order-lookup, memory, guardrail, identity, policy and refund** milestone. The wholesale lookup and the Knowledge Base are not deployed; the agent reports those tools as unavailable. Wholesale traffic must stay disabled until its identity path is verified with the same rigor as the retail path.

## End-to-end verification, before any real traffic

Verify each item against the deployed agent, not just locally. The smoke test in the App Deploy workflow automates the three that must never regress (marked with an asterisk).

- [ ] **Authentication\***: an invalid `customer_token` is rejected
- [ ] **Runtime**: the agent responds to a basic invocation (`python scripts/chat.py "hello"`)
- [ ] **Model interaction**: a direct question gets a coherent answer
- [ ] **Memory**: a fact stated in turn one is recalled in turn two of the same session (use `python scripts/chat.py` for a multi-turn session)
- [ ] **Gateway and tool invocation\***: `get_order_status` returns real data for the customer's own order
- [ ] **Authorization\***: the same verified customer is denied when asking about a different customer's order. This is the most important check in the list.
- [ ] **Human approval**: a refund above $100 is queued, not auto-approved
- [ ] **Logging**: the session is findable in CloudWatch (needs Transaction Search enabled)
- [ ] **Evaluation**: `python evaluations/run_evaluations.py` (see `evaluations/README.md` for the required environment variables)
- [ ] **Failure handling**: temporarily break one dependency (for example, deny a permission) and confirm the agent degrades gracefully rather than crashing
- [ ] **Retrieval** (milestone 2): a policy question returns a grounded answer

## Go / no-go

Do not proceed to real traffic until every box is checked against the actual deployed system, not assumed from earlier local testing.
