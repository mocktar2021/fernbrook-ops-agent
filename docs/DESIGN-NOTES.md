# Design notes index

Comments, READMEs and tests in this repository refer to numbered **Design Notes** (for example "Design Note 15"). They are the design reasoning behind each part of the system, written while the project was built up step by step. This page maps each number to its topic and to where that topic lives in the repository.

The notes themselves are not included here. The repository's own READMEs, comments and the documents in this folder carry the decisions that matter; use this table to find the right file when a comment cites a number.

| # | Topic | Where to look |
|---|---|---|
| 1 | From chatbots to production agents | `README.md` (what it does) |
| 2 | Understanding Amazon Bedrock AgentCore | `README.md` (architecture) |
| 3 | Designing the production agent | `docs/diagrams/fig-03-01-fernbrook-architecture-preview.svg` |
| 4 | Preparing the AWS environment | `docs/GETTING-STARTED.md` (Phase 1), `infrastructure/bootstrap/` |
| 5 | Calling a foundation model | `agent/model_call_test.py` |
| 6 | Building the first agent with Strands | `agent/agent.py` |
| 7 | Running the agent on AgentCore Runtime | `agent/app.py`, `infrastructure/release/` |
| 8 | Designing safe agent memory | `memory/README.md` |
| 9 | Building with AgentCore Memory | `infrastructure/platform/memory.tf`, `memory/` |
| 10 | Giving agents tools | `agent/agent.py` |
| 11 | MCP and AgentCore Gateway | `infrastructure/platform/gateway.tf` |
| 12 | Building tools: read-only, Lambda, external APIs | `tools/order_lookup/`, `tools/wholesale_lookup/` |
| 13 | Designing a multi-tool toolkit | `tools/`, `agent/agent.py` |
| 14 | Identity for AI agents | `identity/README.md` |
| 15 | AgentCore identity in practice | `identity/verify_customer_token.py`, `infrastructure/platform/cognito.tf` |
| 16 | Least privilege and AgentCore Policy | `policy/`, `infrastructure/platform/policy.tf` |
| 17 | Human approval for sensitive actions | `agent/refund_logic.py`, `scripts/review_pending_refunds.py` |
| 18 | Knowledge vs. memory, and RAG | `knowledge/README.md` |
| 19 | Building the knowledge layer | `knowledge/` (not deployed yet) |
| 20 | Retrieval quality and malicious content | `knowledge/README.md` |
| 21 | Threat modeling AI agents | `docs/INTERVIEW-GUIDE.md` (decisions), `tests/` |
| 22 | Guardrails, secrets and data protection | `infrastructure/platform/guardrail.tf`, `infrastructure/platform/secrets.tf` |
| 23 | Securing MCP and tools | `agent/agent.py` (ownership-checked wrappers), `agent/gateway_names.py` |
| 24 | Observability for AI agents | `observability/README.md`, `agent/emit_metric.py` |
| 25 | Building an operations view | `docs/OPERATIONS.md` |
| 26 | Testing and evaluating agent behavior | `tests/`, `evaluations/` |
| 27 | Regression testing and continuous evaluation | `evaluations/compare_results.py` |
| 28 | Infrastructure as code | `infrastructure/` |
| 29 | CI/CD and versioning | `.github/workflows/`, `docs/GETTING-STARTED.md` (Phases 4 and 5) |
| 30 | Understanding and reducing agent cost | `evaluations/estimate_cost.py` |
| 31 | Performance and latency | `docs/OPERATIONS.md` |
| 32 | Failure modes and idempotent retries | `agent/refund_logic.py` |
| 33 | Graceful degradation | `agent/agent.py` |
| 34 | When one agent is not enough | `ops-monitor-agent/README.md` |
| 35 | Designing specialized agents | `ops-monitor-agent/` |
| 36 | Reviewing the final architecture | `docs/diagrams/fig-36-01-final-architecture.svg` |
| 37 | Production readiness review | `README.md` (current scope and known limits) |
| 38 | Deploying and operating the complete agent | `docs/GETTING-STARTED.md`, `docs/TEARDOWN.md`, `docs/OPERATIONS.md` |

Notes 39 to 41 covered next projects, careers and a learning roadmap; they have no code in this repository.

Two things have changed since some of those notes were written, so comments that cite them may be out of date:

- **Deployment.** Early notes describe setting AgentCore resources up with the CLI and scripts. The Terraform stacks and GitHub Actions workflows now do that. The old scripts remain for reference and are marked as such at the top of their READMEs.
- **Model.** Early notes use Claude Sonnet 4.5. The project now defaults to Claude Sonnet 4.6 because Sonnet 4.5 entered AWS's Legacy stage. Sonnet 5.5 is the better long-term choice but was not offered to the author's account (its Marketplace agreement showed NOT_AVAILABLE). The agent sends no sampling parameters, so it also runs on Sonnet 5.x.
