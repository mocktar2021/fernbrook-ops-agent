> **Note:** the setup steps below describe the original manual path and are kept to explain the design. In this repository Terraform (`infrastructure/platform/policy.tf`) creates the policy engine and this Cedar policy, filling in the Gateway ARN. Follow `docs/GETTING-STARTED.md` to deploy.

# AgentCore Policy: default-deny, explicit allow list

## Setup

```bash
agentcore add policy-engine \
  --name FernbrookPolicyEngine \
  --attach-to-gateways FernbrookGateway \
  --attach-mode ENFORCE

agentcore add policy \
  --name AllowApprovedReadTools \
  --source policy/fernbrook-tool-access.cedar \
  --policy-engine FernbrookPolicyEngine

agentcore deploy
```

Before running this, replace the placeholder Gateway ARN in `fernbrook-tool-access.cedar` with `FernbrookGateway`'s real ARN (`agentcore status` prints it), and replace `fernbrook-agent-runtime` in the `principal.id like` condition with whatever your deployed Runtime execution role is actually named, if it differs.

`--attach-mode ENFORCE` matters: AgentCore Policy also supports a monitor-only mode that logs what *would* have been denied without actually blocking anything, useful for testing a new policy against real traffic before it can affect a live agent. This project goes straight to enforcement because both tools are already well understood and the risk of an unexpected denial is low; a project adding policy to an established, less predictable toolkit might reasonably start in monitor mode instead.

## What this policy does and does not do

**Does:** enforces default-deny at the Gateway boundary. Only `get_order_status` and `getWholesaleAccountStatus`, called by this project's own Runtime execution role, are permitted. Anything else, a tool this policy doesn't name, a caller this policy doesn't recognize, is denied automatically, independent of anything the agent's own reasoning concludes.

**Does not:** restrict a customer to their own order or account. `AgentCore::IamEntity` here is the Runtime execution role, the same principal for every conversation this agent ever has, because Gateway authenticates inbound calls with AWS_IAM (Design Note 15), not per-customer OAuth tokens. Cedar has no visibility into Fernbrook's business data, which customer owns which order, unless that information reaches it through the principal's identity or the call's context, and right now, neither does. Design Note 16 explains this limitation in full and what actually closing it would require.
