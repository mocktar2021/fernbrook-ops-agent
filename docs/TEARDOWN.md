# Teardown and redeploy

You should be able to delete everything this project created and bring it back later from the repository alone. This page is the deletion half. The redeploy half is Phase 8 of [`GETTING-STARTED.md`](GETTING-STARTED.md).

## Order matters

Delete in the reverse order of creation, because each layer depends on the one below it:

1. The agent runtime (release stack), then the platform (platform stack): the **Destroy** workflow does both.
2. The bootstrap stack (state bucket, GitHub trust, pipeline roles): you do this from your laptop. It has to be last, because the Destroy workflow needs the state bucket and the pipeline roles to run at all.

## Step 1: run the Destroy workflow

**Actions, Destroy, Run workflow.** Type `destroy-fernbrook` exactly. The workflow fails immediately on any other input and destroys nothing.

You approve twice: first `app-dev` (removes the runtime, the `last_good` parameters and the runtime log groups), then `infra-dev` (removes the platform: gateway, policy, memory, guardrail, Cognito, tables, functions, the code bucket and the execution roles).

**Check:** the run is green. If a step fails, read the error before re-running. Common causes:
- A resource was changed by hand outside Terraform and no longer matches state. Fix or delete it by hand, then re-run.
- A non-empty bucket. The code bucket is created with `force_destroy`, so this should not happen; if it does, empty it in the console (include object versions) and re-run.

## Step 2: destroy the bootstrap stack

```bash
cd infrastructure/bootstrap
terraform destroy
```

This removes the pipeline roles, the permissions boundary, the GitHub OIDC provider (if this stack created it), the budget, and the state bucket. The bucket is created with `force_destroy = true` so it deletes even though it holds state files. That is appropriate for a demo. For anything you care about, set `state_bucket_force_destroy = false` first.

You need the local `terraform.tfstate` file in this folder for this step. If you lost it, use the manual list below.

## Step 3: verify nothing is left

Catch-all by tag (not every resource type is returned, so also run the specific checks):

```bash
aws resourcegroupstaggingapi get-resources --region us-east-1 \
  --tag-filters Key=Project,Values=fernbrook-ops-agent --query "ResourceTagMappingList[].ResourceARN" --output text
```

Specific checks (each should print nothing):

```bash
aws iam list-roles --query "Roles[?contains(RoleName,'fernbrook')].RoleName" --output text
aws iam list-policies --scope Local --query "Policies[?contains(PolicyName,'fernbrook')].PolicyName" --output text
aws iam list-open-id-connect-providers --query "OpenIDConnectProviderList[].Arn" --output text   # your GitHub provider should be gone unless you pointed bootstrap at a pre-existing one
aws s3 ls | grep -i fernbrook
aws dynamodb list-tables --query "TableNames[?contains(@,'fernbrook')]" --output text
aws lambda list-functions --query "Functions[?contains(FunctionName,'fernbrook')].FunctionName" --output text
aws cognito-idp list-user-pools --max-results 60 --query "UserPools[?contains(Name,'ernbrook')].Name" --output text
aws secretsmanager list-secrets --query "SecretList[?contains(Name,'fernbrook')].Name" --output text
aws ssm get-parameters-by-path --path /fernbrook --recursive --query "Parameters[].Name" --output text
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fernbrook --query "logGroups[].logGroupName" --output text
aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore --query "logGroups[].logGroupName" --output text
aws bedrock list-guardrails --region us-east-1 --query "guardrails[?contains(name,'ernbrook')].name" --output text
aws bedrock-agentcore-control list-agent-runtimes --region us-east-1
aws bedrock-agentcore-control list-gateways --region us-east-1
aws bedrock-agentcore-control list-memories --region us-east-1
```

A day later, glance at **Billing, Cost Explorer** to confirm spend has stopped.

## What teardown deliberately leaves behind

| Left behind | Why it is fine |
|---|---|
| CloudWatch Transaction Search setting and the `aws/spans` log group | Account-level setting shared with anything else you build. It costs only when spans are ingested. Turn it off in CloudWatch settings if you want. |
| Bedrock model access or Marketplace subscription for Claude | Pay-per-use. No usage, no charge. |
| GitHub secrets and environments | They hold role ARNs that no longer exist. Re-running `scripts/setup_github.sh` after the next bootstrap overwrites them. |
| CloudTrail history | Read-only record of what happened. |

## If the Destroy workflow or the bootstrap state is unavailable

Use this only when the normal path is broken. It needs an identity with broad permissions (your admin user).

**Platform and release, from your laptop** (works only if the state bucket still exists):

```bash
BUCKET=$(terraform -chdir=infrastructure/bootstrap output -raw state_bucket)

cd infrastructure/release
terraform init -backend-config="bucket=$BUCKET" -backend-config="region=us-east-1"
terraform destroy -var code_key=unused -var code_version_id=unused

cd ../platform
terraform init -backend-config="bucket=$BUCKET" -backend-config="region=us-east-1"
terraform destroy
```

**Everything lost (no state anywhere).** Delete by hand, in this order, using the console or CLI. Everything is named `fernbrook`-something, and the verification commands above find each type:

1. AgentCore runtime, then gateway target(s), then gateway, then policy engine and policy, then memory. Check `aws bedrock-agentcore-control help` for the exact `delete-*` commands and delete targets before their gateway.
2. Guardrail (`aws bedrock delete-guardrail`).
3. Lambda function and its log group; DynamoDB tables; Cognito user pool; Secrets Manager secret `fernbrook/demo-user-password` (use `--force-delete-without-recovery`); SSM parameters under `/fernbrook`.
4. S3 buckets: empty them **including all object versions** (console "Empty" does this), then delete.
5. IAM: roles `fernbrook-agent-runtime-role`, `fernbrook-gateway-role`, `fernbrook-order-lookup-lambda-role`, then `fernbrook-gha-plan`, `fernbrook-gha-infra-apply`, `fernbrook-gha-app-deploy`, then the customer-managed `fernbrook-*` policies and the permissions boundary. Detach policies from a role before deleting it.
6. The GitHub OIDC provider, only if nothing else in the account uses it.
7. The budget `fernbrook-monthly`.

## Redeploy

See Phase 8 of [`GETTING-STARTED.md`](GETTING-STARTED.md). The short version: sign in, confirm the model is still Active, bootstrap, run `scripts/setup_github.sh`, run Infra Apply, run App Deploy.

If you destroyed only the platform and runtime and kept bootstrap, skip bootstrap and run Infra Apply, then App Deploy.
