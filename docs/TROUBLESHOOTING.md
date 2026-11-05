# Troubleshooting

Symptom-first, collected from the failure modes met while building this project. If something here doesn't resolve your issue, the design note referenced has more detail than fits in this quick-reference format (see `DESIGN-NOTES.md`).

## Setup and environment

**`ModuleNotFoundError` running `agent.py`, `app.py`, or `refund_logic.py`.** These files import each other as siblings (`from refund_logic import request_refund`, `from agent import run_agent`), a pattern that only resolves correctly when the script is run from the repository root as `python3 agent/agent.py`, not from inside the `agent/` directory, and not via `python3 -m agent.agent`. See Design Note 7's note on this exact pattern.

**`RuntimeError: AGENTCORE_MEMORY_ID is not set`** (or the equivalent for `FERNBROOK_GATEWAY_URL`, `FERNBROOK_GUARDRAIL_ID`, `FERNBROOK_USER_POOL_ID`, etc.). These are deliberately loud, fail-fast checks (Design Note 9's design choice), not bugs. Run the one-time setup script named in the error message, export the value it prints, and re-run.

**Tests fail to import `cryptography` or `jose`.** Run `pip install -r requirements.txt` again; `python-jose[cryptography]` (Design Note 15) brings in both.

## Bedrock and the model

**`AccessDeniedException` calling the model (Design Note 5).** Check two things, in order: model access requested and granted in the Bedrock console for your region, and your IAM policy's resource ARNs matching `MODEL_ID` exactly, including the inference-profile ARN (the one starting `arn:aws:bedrock:...:inference-profile/...`) if you're using a cross-region profile ID (one starting `us.`). The inference-profile ARN is the single most common thing people forget; see Design Note 5's explanation of why it's a separate resource from the model itself.

**Responses vary between runs.** Expected. Claude Sonnet 5 and later reject `temperature`, `top_p` and `top_k`, so the agent sends none and uses the model's default sampling. If you switch to a model that accepts it, set `FERNBROOK_TEMPERATURE`. Assert on properties (was the order refused, was a tool called), not exact wording.

**`ValidationException` mentioning `temperature` is deprecated.** Something is sending a sampling parameter to a Sonnet 5 or later model. Remove it from the call. The agent code already omits it unless `FERNBROOK_TEMPERATURE` is set.

**`ValidationException` or "model not found" after a long gap.** Models have a lifecycle. AWS states that new customers cannot start using Legacy models, and models reach end of life. Check the Bedrock model catalog for a current Claude ID and set `model_id` in `infrastructure/platform/variables.tf` (or a committed `*.auto.tfvars`), then let Infra Apply run.

**`AccessDeniedException: ... is not available for this account`.** The model is not offered to your account. Run `aws bedrock get-foundation-model-availability --region us-east-1 --model-id <model>`. `agreementAvailability: NOT_AVAILABLE` means the AWS Marketplace agreement for that model is not offered to your account (seen with Claude Sonnet 5.5 and Haiku 5.5 on one account, while Sonnet 4.6 worked). Test other Active models with a direct `converse` call and set `model_id` to one that replies.

**`KeyError: 'text'` or empty replies from your own model code.** Newer models can return a reasoning block before the text block. Collect every block that has a `text` key instead of reading `content[0]`.

## Gateway, Policy, and tools

**A tool call fails with an authorization error after switching Gateway to `AWS_IAM` (Design Note 15).** The deployed agent's execution role needs `bedrock-agentcore:InvokeGateway`, scoped to your specific Gateway ID; see `infrastructure/iam/runtime-execution-role-gateway-invoke-statement.json`. This is a different identity than your local `fernbrook-agent-builder` user; granting the local identity more access does nothing for this error.

**Infra Apply fails creating `aws_bedrockagentcore_policy` (status `CREATE_FAILED`, error echoes your Cedar statement with line numbers).** AgentCore Policy checks every action against the schema of the gateways attached to the policy engine, in every validation mode, and rejects an action that no Gateway target defines. Name only tools whose targets are deployed. `tests/test_cedar_policy_structure.py` checks this before you push.

**Cedar denies a call you expect to be permitted.** Two likely causes: the Gateway ARN placeholder in `policy/fernbrook-tool-access.cedar` was never replaced with your real Gateway ARN, or `principal.id like "*assumed-role/fernbrook-agent-runtime*"` doesn't match your actual Runtime execution role's name. Run `tests/test_cedar_policy_structure.py` first; it catches the placeholder case directly.

**`get_order_status` or `get_wholesale_account_status` return `found: false` for an order or account you know exists.** This is almost always correct behavior, not a bug: either the record genuinely belongs to a different `actor_id` (Design Note 23's ownership check working as designed), or the token verification (Design Note 15) resolved to a different `actor_id` than you expected. Confirm which `actor_id` your token actually verifies to before assuming the lookup is wrong.

**If a lookup ever returns another customer's data:** stop and treat this as a critical finding, not a minor bug. As of this repository's final completion pass, `get_order_status`, `get_wholesale_account_status`, and `Retrieve` are all wrapped with the checks described in Design Notes 23 and 33. If you're seeing cross-customer data, you are very likely working from a version of `agent.py` predating Design Note 23's fix, or a local edit has removed the ownership check. Compare against this repository's current `agent/agent.py` directly.

**The wholesale Lambda returns 401 for a request you believe has the right API key.** The key stored in Secrets Manager (`tools/wholesale_lookup/create_api_key_secret.py`) and the key configured on the Gateway's API-key credential provider (Design Note 13's setup) have to be the same value; if the credential provider was configured before the secret was last rotated, they've drifted apart. Recreate the credential provider with the secret's current value.

## Memory

**A session doesn't recall something said earlier in the same conversation.** Confirm you're testing across a genuine process or session boundary the way Design Note 9's verification described, not relying on Strands' own in-process conversation history to look like durable memory when it isn't. If memory genuinely failed, check for a `MemoryUnavailableDegraded` metric (Design Note 33); the agent is designed to keep working without memory rather than fail the request, which means a memory outage won't necessarily be obvious from the response alone.

## Deployment pipelines

**Infra Apply or App Deploy sits at "Waiting".** It is waiting for you to approve the environment. Open the run and choose **Review deployments**.

**"Could not assume role" / "Not authorized to perform sts:AssumeRoleWithWebIdentity".** The role's trust policy did not match the token. Check, in order: the `AWS_ROLE_ARN` secret exists in the *environment* the job names (not only at repository level); `github_owner` and `github_repo` in your bootstrap `terraform.tfvars` match your repository exactly, including capitalization; the workflow ran on `main`, because the environments are restricted to it.

**Infra Plan is skipped on a pull request.** It only runs when files under `infrastructure/platform`, `policy` or `tools` change, and never for pull requests from forks.

**Infra role `AccessDenied` during apply.** The role is missing an action. Add it to `infrastructure/bootstrap/role-infra-apply.tf` and run `terraform apply` in the bootstrap folder from your laptop. The pipeline cannot widen its own permissions.

**App Deploy fails with a message that platform configuration is missing.** The platform stack has not been applied yet, or its SSM parameters were deleted. Run Infra Apply first.

**App Deploy is red but the agent still works.** That is the rollback doing its job: the smoke test failed and the previous good version was redeployed. Read the smoke-test step to see which check failed.

**Packaging fails on a dependency.** `scripts/package_agent.py` builds arm64 Linux wheels only (`--only-binary`). Pin a version of the named package that publishes an arm64 wheel in `requirements-runtime.txt`.

**The Runtime starts but calls fail.** Check the runtime's CloudWatch log group (`/aws/bedrock-agentcore/runtimes/fernbrook_ops_agent-*`). If startup fails on `opentelemetry-instrument`, change `entry_point` in `infrastructure/release/runtime.tf` to `["app.py"]`.

**`terraform init` on your laptop complains about credentials after `aws login`.** Use provider 6.23 or newer (this repository does), keep `credential_process` out of the default profile, and as a fallback run `eval "$(aws configure export-credentials --format env)"` for that shell.

**Destroy fails.** See `docs/TEARDOWN.md`, including the manual fallback.

## Terraform

**`terraform plan` wants to recreate a resource you created by hand.** Terraform's state file doesn't know about resources it didn't create. Either import the existing resource (`terraform import`) or, for a fresh environment, let Terraform create it from scratch rather than mixing manual and Terraform-managed creation for the same resource.

**A Terraform apply fails on a permission.** Check `infrastructure/iam/README.md`'s change log for the statement that's supposed to cover the action that failed; if it's missing, that's a real gap worth fixing in the policy file directly, following the same one-scoped-statement-per-need pattern the rest of the file uses.

## Evaluation and CI

**`run_evaluations.py` returns no data or empty traces.** Confirm CloudWatch Transaction Search is actually enabled (Design Note 24); it's a one-time, account-level setting that `agentcore deploy` does not turn on for you, and spans can take about ten minutes to become searchable after enabling it.

**`retrieval-failure-knowledge-base-unreachable` fails in `evaluations/dataset.json`.** As of this repository's final completion pass, this should pass; `Retrieve` now has the same graceful-degradation wrapping as the two lookup tools. If you're working from an earlier snapshot of `agent/agent.py`, this is a known, documented gap (see the scenario's own notes in the dataset file), not a new bug.

**CI's `agent-evaluation` job fails on the `compare_results.py` step with a "file not found" error.** You need an accepted baseline file at `evaluations/results/baseline.json` before comparisons can run; see Design Note 27 for how a baseline gets established and accepted in the first place.

## Still stuck

Check the referenced design note and the folder README; this file collects the highest-frequency issues across the whole project, not every issue any single part anticipated.
