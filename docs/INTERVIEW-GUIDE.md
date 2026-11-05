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
AWS models move through Active, Legacy and end-of-life stages, and new accounts cannot start using Legacy models. I checked the lifecycle documentation, moved off a Legacy model to an Active one, and then found that the newest generation was not offered to my account at all: `get-foundation-model-availability` reported the Marketplace agreement as NOT_AVAILABLE. So I tested what the account could actually call, chose Claude Sonnet 4.6, and kept the model ID as configuration so changing it is a one-line change, not a code change. The code sends no sampling parameters, so it also works on newer models that reject them.

**Why Strands?**
It is one of the frameworks the AgentCore documentation supports, it is small, and it keeps the agent loop readable. The architecture does not depend on it: AgentCore Runtime hosts any framework.

**What does Guardrails protect against, and what does it not?**
Content filtering, prompt-attack patterns and PII masking at the model boundary. It is one layer. It does not replace authorization, because a guardrail evaluates text, not who is allowed to do what.

## Honest gaps (say these before they ask)

- The wholesale lookup and Knowledge Base are not deployed yet; the agent degrades gracefully when those tools are unavailable.
- `us-east-1` only and one environment per account, because names are fixed. A real platform would parameterize both.
- The infra role has one deliberately broad statement for AgentCore control-plane actions. The next step is to tighten it from CloudTrail or IAM Access Analyzer after a few applies.
- The Cedar policy runs with the relaxed `IGNORE_ALL_FINDINGS` mode, which skips only the semantic checks. Schema validation always runs, which I learned when my first apply failed because the policy named two tools with no Gateway target yet. The fix was to name only deployed tools and add the rest with their targets.
- The idempotency window is time-based because the caller is a model. A production system would move more of this to the order system itself.
- The evaluation suite exists and runs on demand, but is not part of the deployment gate yet. The gate is a three-check smoke test.
- The Terraform was written from documentation and debugged on first deployment. Be ready to describe what broke and how you fixed it. That is a good story, not a weakness.

## The first-deploy story

Eight failures, each a different layer. Pick two or three and tell them as symptom, how you found the cause, fix, and what now prevents it. The full table is in `docs/GETTING-STARTED.md`.

- **Identity:** GitHub's OIDC token used an immutable subject with numeric IDs. CloudTrail showed the exact subject; the trust policy now pins the IDs, which also stops someone re-creating the repo name from inheriting access.
- **Policy:** Cedar rejected actions for tools not deployed yet. The schema check always runs. A test now fails if the policy names a tool with no Gateway target.
- **IAM details:** `GetParametersByPath` is authorized on the path itself, and the first Runtime needs a service-linked role. Both fixed with scoped grants applied by a human from bootstrap, because the pipeline cannot widen its own permissions.
- **Dependencies:** a pin conflict CI missed because it did not install everything. CI now installs the full requirements.
- **Account setup:** the model needed a one-time form and a Marketplace subscription. Everything deployed, then the first model call failed. The lesson: any step not in code is what breaks a fresh account.
- **A silent bug:** the agent said "not found" for an order that existed. Testing each layer alone (DynamoDB, Lambda, Cognito) proved they all worked, which left the client code: a timeout passed as an int, and a bare `except` hiding the crash. Fixed the type, logged the exception, added a test.
- **Observability that failed silently:** after the deploy was green, traces never appeared. No error anywhere. Narrowing it down (the stream existed, nothing in it, nothing in the shared group) led to a missing `logs:PutResourcePolicy` in the documented execution-role policy. Lesson: a monitoring gap does not page you; check that the telemetry exists, not just that the app works.
- **Bonus observation:** for another customer's order the model hinted it "may be associated with a different account", against the prompt. Nothing leaked, because the decision is in code. That is the argument for authorization outside the model, shown live.

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
