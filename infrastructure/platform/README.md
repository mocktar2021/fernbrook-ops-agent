# Platform stack

The long-lived infrastructure the agent needs. It is applied by the **Infra Apply** workflow (`.github/workflows/infra-apply.yml`) after a required reviewer approves, and previewed on pull requests by **Infra Plan**. You normally do not run Terraform in this folder by hand.

State lives in the S3 bucket created by `infrastructure/bootstrap` (key `platform/terraform.tfstate`, native S3 locking). The bucket name contains your account ID, so it is passed at init time instead of being committed:

```bash
terraform init -backend-config="bucket=<state bucket>" -backend-config="region=us-east-1"
```

`backend.hcl.example` shows the shape. The workflows read the bucket from the `TF_STATE_BUCKET` secret.

## What it manages

| File | Resources |
|---|---|
| `dynamodb.tf` | Orders table, refund-approvals table, refund-idempotency table (with TTL) |
| `lambda-order-lookup.tf` | The order-lookup Lambda, its role (boundary attached) and log group |
| `cognito.tf` | Customer user pool and app client |
| `secrets.tf` | An empty Secrets Manager container for the demo password. The value is written by `scripts/set_demo_user_password.py`, never by Terraform. |
| `guardrail.tf` | Bedrock Guardrail and a published version |
| `memory.tf` | AgentCore Memory (short-term) |
| `gateway.tf` | Gateway role, the Gateway (AWS_IAM authorizer, MCP) and the Lambda target |
| `policy.tf` | Policy engine (enforce mode) and the Cedar policy, with the Gateway ARN filled in |
| `iam-runtime.tf` | The runtime execution role (boundary attached) and its grants |
| `code-bucket.tf` | Versioned bucket for agent code artifacts |
| `ssm.tf` | Publishes IDs under `/fernbrook/config/*` for the release stack and app pipeline |

## What it does not manage

- The AgentCore **Runtime** itself: that is the `release` stack, so it can change on every code push without touching anything here.
- The wholesale target and the Knowledge Base (milestone 2).
- The demo user's password (kept out of state on purpose).

## Variables

| Variable | Default | Notes |
|---|---|---|
| `aws_region` | `us-east-1` | Must be `us-east-1`; the Python code hardcodes it |
| `environment` | `dev` | Tag only. Resource names are fixed, so run one environment per AWS account |
| `model_id` | `us.anthropic.claude-sonnet-4-6` | Passed to the agent through SSM. Check the model is still Active before you redeploy |
| `memory_event_expiry_days` | `30` | Provider allows 7 to 365 |
| `log_retention_days` | `14` | |

## Ordering notes

- IAM roles are eventually consistent, so a short `time_sleep` sits between the roles and the Gateway. If an apply fails complaining that a role cannot be assumed, run it again.
- The Cedar policy is templated: `policy/fernbrook-tool-access.cedar` contains a placeholder that Terraform replaces with the Gateway's ARN.
- The Cedar file may only name tools whose Gateway targets exist. AgentCore Policy checks every action against the attached gateways' schema in every validation mode, and a policy naming a missing tool ends in `CREATE_FAILED`. Milestone 2 adds the wholesale and knowledge actions together with their targets. `validation_mode = "IGNORE_ALL_FINDINGS"` skips only the semantic checks; try `FAIL_ON_ANY_FINDINGS` once the apply is green.

## Permissions

The pipeline role that runs this stack (`fernbrook-gha-infra-apply`, defined in `infrastructure/bootstrap/role-infra-apply.tf`) is scoped to these resources and can only create the three workload roles, each with the permissions boundary. If an apply fails with `AccessDenied`, add the missing action to that role in the bootstrap stack and apply bootstrap from your laptop. The pipeline cannot edit its own permissions, on purpose.
