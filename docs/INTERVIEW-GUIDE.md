# Interview guide

How to talk about this project: a short pitch, a whiteboard walkthrough, the decisions behind it, the honest gaps, and likely questions with answers you can say in your own words.

Be ready to explain every part in your own words, including how you built it and which tools helped. Interviewers reward clear reasoning and honesty about trade-offs far more than polish.

## The 60-second pitch

> I built a customer-support AI agent on Amazon Bedrock AgentCore and deployed it the way I would deploy any production service: Terraform for all infrastructure, GitHub Actions for two pipelines, and no long-lived AWS keys. The agent looks up orders through a Gateway, remembers conversations, and refuses to show one customer another customer's data. The interesting part is the engineering around the model: authorization lives in code and policy, not in the prompt; the pipelines have narrow roles and can't escalate their own permissions; deploys are gated on a behavioral smoke test and roll back automatically; and the whole thing can be destroyed and redeployed from the repository.

## Draw this on a whiteboard

```
Customer app --(Cognito ID token)--> AgentCore Runtime (Strands agent)
                                          |-- verifies token in code (never trusts the model)
                                          |-- Bedrock model + Guardrail
                                          |-- AgentCore Memory (session context)
                                          |-- AgentCore Gateway --(Cedar policy)--> Lambda --> DynamoDB
                                          '-- refund tool (local) --> DynamoDB (+ idempotency table)

GitHub --(OIDC)--> 3 roles: plan (read-only) | infra apply | app deploy
                   bootstrap (local, once) -> platform (infra pipeline) -> release (app pipeline)
```

Then say the one sentence that ties it together: **models decide what might be useful; application policy decides what is allowed.**

## Decisions and the reasoning behind them

**Why OIDC instead of access keys in GitHub secrets?**
Static keys leak, never expire and are hard to scope. OIDC gives short-lived credentials, and the AWS role's trust policy names the exact repository and environment allowed to assume it.

**Why three pipeline roles?**
Least privilege by job. A pull request preview only needs to read, so it gets a read-only role. Deploying new agent code does not need to create databases, so the app role is narrow. Only the infra role can create platform resources, and only from the protected `main` branch after an approval.

**What is the permissions boundary for?**
It is the ceiling that stops privilege escalation. The infra role may create only three named workload roles, and only if each carries the boundary. It is also explicitly denied from editing the pipeline roles and the boundary itself. A compromised or careless pipeline cannot mint a more powerful role or loosen its own limits.

**Why can the pipeline not update its own permissions?**
That is deliberate. Changing what the pipeline may do is a human action, done from a laptop through the bootstrap stack. If the pipeline hits `AccessDenied`, the fix is a reviewed change to the role policy, not a wider default.

**Why are secrets kept out of Terraform state?**
State stores resource arguments in plain text. If a password passes through a Terraform resource, it lands in state. Terraform creates an empty Secrets Manager container; a script generates the password and writes it directly to Secrets Manager.

**Why does authorization not live in the prompt?**
A prompt is a request, not a control. Prompt injection, a retrieved document, or an odd model output can change behavior. So identity is verified in code from a signed token, ownership is checked in code on every record, and Cedar policy at the Gateway independently decides which tool calls are allowed. Even a fully compromised model can only ask; it cannot authorize.

**Why Cedar at the Gateway as well as an ownership check in code?**
They answer different questions. Cedar answers "may this caller invoke this tool at all?" The code check answers "does this specific record belong to this specific user?" Cedar cannot see inside the tool's data, so the second check has to live in code.

**Why a smoke test on top of unit tests?**
Unit tests show the code is right. The smoke test shows the deployed system behaves safely: real identity, real Gateway, real policy, real model. It checks properties that must never regress: a bad token is rejected, a customer can read their own order, and cannot read someone else's.

**How does rollback work?**
Each release is an immutable S3 object version and the runtime is pinned to it. After a deploy, if the smoke test passes, the pipeline records that build as "last good" in SSM. If it fails, the pipeline re-applies the stored last-good artifact. First deploy has nothing to roll back to, and the pipeline says so.

**Why split platform and release into separate stacks?**
Different rates of change and different blast radius. The runtime changes on every code push; the database and identity layer change rarely. Separate state files and roles mean a bad app deploy cannot touch platform resources, and the app pipeline never needs platform permissions. SSM Parameter Store is the contract between them.

**Why S3 native state locking and no DynamoDB lock table?**
Terraform 1.10 introduced it. It removes a resource and a cost, and it is enough for one team.

**Why a human-approved environment gate?**
Deployments change a real account. The environment is restricted to `main` and requires approval, and the AWS role trust requires that environment, so a branch or a pull request cannot assume the powerful roles.

**How are refunds made safe?**
A refund is a write action, the riskiest kind. Small refunds auto-approve under a threshold; larger ones are queued for human approval. An idempotency record keyed on actor, order, amount and reason within a short window stops a retry from refunding twice. It is a documented trade-off: the caller is a model, so it cannot hold a client-generated idempotency token.

**Why did you change the model?**
AWS models move through Active, Legacy and end-of-life stages, and new accounts cannot start using Legacy models. I checked the lifecycle documentation before deploying, moved to a model listed as Active, and made the model ID a configuration value so retirement is a one-line change, not a code change. The newer model also rejects `temperature`, so the code no longer sends it.

**Why Strands?**
It is one of the frameworks the AgentCore documentation supports, it is small, and it keeps the agent loop readable. The architecture does not depend on it: AgentCore Runtime hosts any framework.

**What does Guardrails protect against, and what does it not?**
Content filtering, prompt-attack patterns and PII masking at the model boundary. It is one layer. It does not replace authorization, because a guardrail evaluates text, not who is allowed to do what.

## Honest gaps (say these before they ask)

- The wholesale lookup and Knowledge Base are not deployed yet; the agent degrades gracefully when those tools are unavailable.
- `us-east-1` only and one environment per account, because names are fixed. A real platform would parameterize both.
- The infra role has one deliberately broad statement for AgentCore control-plane actions. The next step is to tighten it from CloudTrail or IAM Access Analyzer after a few applies.
- The Cedar validation mode is relaxed until all the actions in the policy have deployed targets.
- The idempotency window is time-based because the caller is a model. A production system would move more of this to the order system itself.
- The evaluation suite exists and runs on demand, but is not part of the deployment gate yet. The gate is a three-check smoke test.
- The Terraform was written from documentation and debugged on first deployment. Be ready to describe what broke and how you fixed it. That is a good story, not a weakness.

## Questions to expect, with a short answer

| Question | Short answer |
|---|---|
| What is AgentCore, and how is it different from Bedrock Agents? | A set of managed building blocks for running agents in production (Runtime, Memory, Gateway, Identity, Policy, Observability) that work with any framework and model. |
| Where does the agent run? | AgentCore Runtime, as an arm64 Python package from a versioned S3 object, started with a managed session per conversation. |
| How do tools get exposed? | Through Gateway, over MCP, with a Lambda target. The Gateway authenticates callers with IAM and Cedar decides which calls are allowed. |
| What is MCP? | A protocol for exposing tools to agents in a standard way. It is a protocol, not a capability by itself. |
| How do you stop prompt injection? | Layers: identity and ownership in code, policy at the Gateway, least-privilege tools, guardrails, treating tool and retrieved content as untrusted data. No single control is enough. |
| How do you know it works after a deploy? | A smoke test against the deployed runtime that must pass before the build is marked good. |
| How do you debug a bad answer? | Traces for the session (model calls and tool calls), Lambda logs, and the evaluation dataset to reproduce. |
| What would you change at scale? | Per-environment parameterization, multi-region, a proper approval and audit flow for sensitive actions, evaluation in the release gate, cost dashboards and alarms. |
| What did you learn from teardown and redeploy? | That every manual step is a liability: anything not in code (an account setting, a console click) is what breaks the redeploy. |

## Demo script (5 minutes)

1. Show the README diagram and say the one-sentence principle.
2. Open the Actions tab: point to the five workflows and the two approval gates.
3. Run `python scripts/chat.py "What is the status of order FB-10293?"`, then ask for `FB-10318` and show the refusal.
4. Show `infrastructure/bootstrap/boundary.tf` and the explicit deny in the infra role.
5. Show the break-it-on-purpose run (Phase 6.3 of the getting-started guide): red pipeline, working agent.
6. Show the Destroy workflow and the verification commands in `TEARDOWN.md`.

## Practice

- Draw the architecture and both pipelines from memory in under two minutes.
- Explain what happens, step by step, when a customer asks about someone else's order.
- Explain what would happen if the infra role were compromised, and why the boundary limits it.
