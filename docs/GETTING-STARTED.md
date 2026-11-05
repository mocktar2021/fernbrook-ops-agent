# Getting started: deploy it, understand it, delete it, redeploy it

This guide takes you from an empty folder to a running agent in your own AWS account, using your own GitHub repository, and ends with everything deleted and a clear path to redeploy later.

Work through it in order. Every phase ends with a **Check** (how you know it worked) and a **Why** (what you should be able to explain in an interview). If a command fails, stop and read the **If it fails** notes before retrying.

| Phase | What you do | Time |
|---|---|---|
| 1 | Prepare tools, AWS sign-in, model access, GitHub repo | 30 to 45 min |
| 2 | Bootstrap: state bucket, GitHub-to-AWS trust, pipeline roles (once, from your laptop) | 15 min |
| 3 | Give GitHub the role ARNs and set approval gates | 5 min |
| 4 | Pipeline deploys the platform (identity, tools, memory, gateway, policy) | 15 to 20 min |
| 5 | Pipeline deploys the agent | 10 to 15 min |
| 6 | Use it, look inside it, break it on purpose | 30 min |
| 7 | Tear everything down | 15 min |
| 8 | Redeploy later | 30 min |

**Cost.** Everything is pay-per-use, and idle cost is low, but model calls and a few services bill while deployed. Do not leave it running for weeks. Set the budget alert in Phase 2. Check current AWS pricing yourself before relying on any number.

**Commands** are for a bash shell (Git Bash, MSYS2, macOS, Linux). Windows PowerShell users: the `aws`, `terraform`, `git` and `gh` commands are the same; only line continuations and `export` differ.

---

## The mental model (read this once)

```
Your laptop (once)                 GitHub Actions (every change)               AWS
-------------------                -----------------------------               ---
bootstrap stack  ----creates---->  OIDC trust + 3 narrow roles
                                   Infra Plan  (PR)      -> read-only role
                                   Infra Apply (main)    -> infra role  ----> platform stack
                                   App Deploy  (main)    -> app role    ----> release stack (runtime)
```

- **Bootstrap** creates the things a pipeline cannot create for itself: the place Terraform keeps its state, and the permission for GitHub to act in AWS. A human runs it once.
- **Platform** is the long-lived infrastructure the agent needs.
- **Release** is just the agent runtime, pinned to one code artifact. It changes often, so it has its own stack and its own role.

No AWS access keys are stored in GitHub. GitHub proves who it is with a short-lived signed token (OIDC), and AWS hands back temporary credentials only to the right repository and the right environment.

---

## Phase 1: Prepare

### 1.1 Tools

You need: Terraform 1.10 or newer, AWS CLI v2, Git, and the GitHub CLI (`gh`). Python is optional (only for running the tests locally).

```bash
terraform -version     # 1.10 or newer
aws --version          # aws-cli/2.x
git --version
gh --version
```

### 1.2 Sign in to AWS

```bash
aws login
aws sts get-caller-identity
```

**Check:** the second command prints your account ID and your user ARN.

`aws login` sessions expire (up to 12 hours). When commands start failing with credential errors, run `aws login` again.

**On Windows (Git Bash or MSYS2),** three settings avoid confusing errors later:

```bash
python -m pip install "botocore[crt]"   # Python scripts need it to read aws login sessions
export MSYS2_ARG_CONV_EXCL='*'           # stop MSYS2 rewriting /aws/... and /fernbrook/... into Windows paths (Git Bash: MSYS_NO_PATHCONV=1)
export PYTHONUTF8=1                      # the AWS CLI otherwise crashes printing some log characters
```

With path conversion off, the Windows AWS CLI cannot see `/tmp`. Write output files to the current folder instead.

Terraform's AWS provider 6.23 or newer reads `aws login` sessions directly. Do **not** add a `credential_process` line to your default profile: that stops `aws login` from working.

**Use an account you can safely experiment in.** This guide creates IAM roles and a permissions boundary. Prefer a personal or sandbox account. Do not use the root user for daily work.

### 1.3 Confirm the model works in your account

The agent uses Claude Sonnet 4.6 through the US cross-region inference profile. Test it directly before involving any pipeline:

```bash
aws bedrock-runtime converse \
  --region us-east-1 \
  --model-id us.anthropic.claude-sonnet-4-6 \
  --messages '[{"role":"user","content":[{"text":"Say hello in five words."}]}]' \
  --query 'output.message.content[].text' --output text
```

**Check:** it prints a short greeting.

**If it fails:**
- `ResourceNotFoundException: Model use case details have not been submitted`: Anthropic requires a one-time use-case form per AWS account. Complete it from the Anthropic page under **Providers** in the Bedrock console (`us-east-1`), wait a few minutes, and retry.
- `AccessDeniedException` mentioning `aws-marketplace:Subscribe`: the account has no Marketplace subscription for the model yet. The first successful call from an identity allowed to subscribe creates it. Your admin user is allowed; the agent's runtime role deliberately is not. Retry this command, or send one message in the Bedrock playground, until it replies.

**Do not skip this check.** It is the one setup step Terraform cannot do for you. If you skip it, everything deploys and the smoke test fails at the first model call.
- `ValidationException` or "model not found": the model ID may have changed. Check the Bedrock model catalog for the current Claude ID and pass it later as `model_id` (see Phase 4).
- Models have a lifecycle (Active, Legacy, end of life). AWS states that new customers cannot start using Legacy models. This is why the repository does not default to an older model.

### 1.4 Get the code and check it locally

Unzip the project to a folder you control (for example `C:\dev\fernbrook-ops-agent`), then:

```bash
cd /c/dev/fernbrook-ops-agent       # adjust to your path
terraform fmt -recursive infrastructure

for s in bootstrap platform release; do
  echo "=== $s ==="
  terraform -chdir=infrastructure/$s init -backend=false -input=false && \
  terraform -chdir=infrastructure/$s validate
done
```

`init -backend=false` downloads the providers without touching AWS. `validate` checks that the Terraform is internally consistent and matches the provider schemas.

**Check:** each stack prints `Success! The configuration is valid.`

**If it fails:** the Terraform in this repository was written from the provider documentation and has not been run end to end by its author. A validate error is expected sometimes and cheap to fix. Copy the error output (not any secrets) and fix the named file. This is the best place to find those mistakes: before anything exists in AWS.

Then record provider checksums for every platform the team and the CI runners use, so builds are reproducible:

```bash
for s in bootstrap platform release; do
  terraform -chdir=infrastructure/$s providers lock \
    -platform=linux_amd64 -platform=windows_amd64 -platform=darwin_arm64 -platform=darwin_amd64
done
```

This writes a `.terraform.lock.hcl` into each stack. Commit those files.

Optional, to run the Python tests:

```bash
python -m venv .venv && source .venv/Scripts/activate    # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q
```

### 1.5 Create your public GitHub repository

```bash
git config user.name  "Your Name"
git config user.email "YOUR-ID+YOUR-USERNAME@users.noreply.github.com"   # keeps your real email private

git init -b main
git add .
git status        # read this list: there must be no .env, no *.tfvars, no *.tfstate
git commit -m "Initial commit [skip ci]"
gh repo create YOUR-USERNAME/fernbrook-ops-agent --public --source . --remote origin --push
```

`[skip ci]` stops GitHub from running the pipelines on this first push. You will start them deliberately in Phases 4 and 5.

Then, in the GitHub web UI for the new repository: **Settings, Actions, General, Fork pull request workflows**, choose **Require approval for all outside collaborators**. Because the repository is public, this stops strangers' pull requests from running workflows in your account without your review.

**Check:** `gh repo view --web` opens your repository, and the files are there.

**Why:** a public repository is safe here because it contains no secrets and no account IDs. The pipelines get everything account-specific from GitHub secrets and from SSM at run time.

---

## Phase 2: Bootstrap (run once, from your laptop)

```bash
cd infrastructure/bootstrap
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` (it is gitignored). Set `github_owner` to your GitHub username, `github_repo` to `fernbrook-ops-agent`, and optionally `budget_email` to get a cost alert.

Then add your repository's numeric IDs. GitHub puts them in the OIDC token it sends to AWS (`repo:OWNER@OWNER_ID/REPO@REPO_ID:...`), and the role trust policies must match. The repository must exist first (Phase 1.5):

```bash
gh api repos/YOUR-GITHUB-USERNAME/fernbrook-ops-agent --jq '"github_owner_id = \"\(.owner.id)\"", "github_repo_id  = \"\(.id)\""' >> terraform.tfvars
tail -2 terraform.tfvars
```

```bash
terraform init
terraform plan
terraform apply
```

Read the plan before typing `yes`. Expect to create: a state bucket, the GitHub OIDC provider, a permissions-boundary policy, three roles with their policies, and (if you set an email) a budget.

**Check:**

```bash
terraform output
aws s3 ls | grep fernbrook
aws iam list-roles --query "Roles[?starts_with(RoleName,'fernbrook-gha')].RoleName" --output text
```

You should see the state bucket, and three roles: `fernbrook-gha-plan`, `fernbrook-gha-infra-apply`, `fernbrook-gha-app-deploy`.

Commit the lock file if it changed: `git add -A && git commit -m "Lock bootstrap providers" && git push` (this push runs only the CI workflow, which has no AWS access, because bootstrap files are not in the deploy workflows' path filters).

**If it fails:**
- `EntityAlreadyExists` for the OIDC provider: your account already trusts GitHub. Find its ARN with `aws iam list-open-id-connect-providers` and set `existing_github_oidc_provider_arn` in `terraform.tfvars`.
- `No valid credential sources found`: re-run `aws login`. If Terraform still cannot see the session, export temporary credentials for this shell only: `eval "$(aws configure export-credentials --format env)"`. (This is a documented fallback; it has not been verified against `aws login` sessions by the author.)
- Budget errors: leave `budget_email` empty and apply again.

**Important:** the bootstrap stack keeps its state in a local file (`terraform.tfstate`, gitignored) because it creates the bucket that would otherwise hold it. Do not delete that file until you have run the teardown. If you lose it, `docs/TEARDOWN.md` lists what to delete by hand.

**Why:**
- *Why two kinds of state?* You cannot store state in a bucket that does not exist yet. Bootstrap uses local state; everything else uses the S3 bucket.
- *Why S3 locking and no DynamoDB table?* Terraform 1.10 added native S3 state locking, so one less resource to manage.
- *Why three roles?* A pull request preview only needs to read. Deploying the agent does not need to create databases. Splitting them limits what a stolen or abused token can do.
- *What is the permissions boundary?* A ceiling. The infra role can create only three named workload roles, and only if they carry this boundary. Even if someone edits the pipeline, the roles it creates cannot exceed the ceiling, and the pipeline cannot edit its own roles or the boundary.

---

## Phase 3: Connect GitHub to AWS

Back at the repository root:

```bash
cd ../..
./scripts/setup_github.sh
```

It sets two repository secrets, creates the `infra-dev` and `app-dev` environments restricted to the `main` branch with you as the required reviewer, and sets a different `AWS_ROLE_ARN` secret in each. It pipes values straight to GitHub and never prints them.

**Check:**

```bash
gh secret list
gh secret list --env infra-dev
gh secret list --env app-dev
```

Expected: `AWS_PLAN_ROLE_ARN` and `TF_STATE_BUCKET` at repository level, and `AWS_ROLE_ARN` in each environment.

**If it fails:** if the branch-restriction step reports an API error, you can set it in the UI: **Settings, Environments, (name), Deployment branches and tags, Selected branches, add `main`**. Required reviewers on a private repository need a paid GitHub plan; your public repository is fine.

**Why:** the AWS role trusts only `repo:YOU/fernbrook-ops-agent` from the matching environment. The environment is the gate: it is limited to `main` and needs your approval, so a branch or a pull request cannot assume the powerful roles.

---

## Phase 4: Deploy the platform

Go to the **Actions** tab, choose **Infra Apply**, and click **Run workflow** on `main`. When the job pauses, click **Review deployments**, tick `infra-dev`, and approve.

The job runs `terraform plan`, applies exactly that plan, then runs two scripts: one creates the demo customer and stores a generated password straight into Secrets Manager (it never appears in Terraform state or logs), and one seeds six synthetic orders.

**Check:** the run is green, then:

```bash
aws ssm get-parameters-by-path --path /fernbrook/config --query "Parameters[].Name" --output text
aws bedrock-agentcore-control list-gateways --region us-east-1 --query "items[].name" --output text
aws dynamodb list-tables --query "TableNames" --output text
aws cognito-idp list-user-pools --max-results 20 --query "UserPools[].Name" --output text
```

You should see nine `/fernbrook/config/*` parameters, a gateway named `fernbrook-gateway`, three `fernbrook-*` tables, and a Cognito pool. (If the gateway command prints nothing, run it again without `--query` to see the raw response.)

**If it fails:** this is the most likely place for a first-run error. Open the failed step, read the error, and fix it in the named `.tf` file. Typical causes:
- A provider argument that differs from the documentation: fix the argument and push a change.
- `AccessDenied` for the infra role: the pipeline role is missing a permission. Add the action to `infrastructure/bootstrap/role-infra-apply.tf`, then run `terraform apply` in the bootstrap directory **from your laptop**, then re-run the workflow. The pipeline cannot widen its own permissions, by design.
- The Gateway or Cedar policy complaining about a role that does not exist yet: re-run the workflow. A short wait (`time_sleep`) is built in for IAM propagation, and it occasionally needs another run.

To use a different model, set `model_id` in a repository-level change to `infrastructure/platform/variables.tf` (or a `*.auto.tfvars` file you commit) and let Infra Apply run again.

**Why:**
- *Why a plan, then apply that exact plan?* So what ran is what was reviewed.
- *Why concurrency control and no auto-cancel?* Two applies at once, or one cut off halfway, corrupt state.
- *Why is the demo password not in Terraform?* State files store resource arguments in plain text. A secret that passes through Terraform ends up in state. This one never does.
- *What did the Cedar policy do?* It runs at the Gateway in enforce mode and allows tool calls only from the agent's own runtime role, in addition to the ownership check in the agent code.

---

## Phase 5: Deploy the agent

Go to **Actions**, choose **App Deploy**, **Run workflow**, then approve `app-dev`.

What it does, in order: runs the tests; builds an arm64 Linux package (the runtime is arm64); uploads it to the versioned code bucket; applies the release stack, which creates the AgentCore Runtime pinned to that exact file and version; runs the smoke test; and either records this build as "last good" or redeploys the previous good one.

**Check:** the run is green. Then:

```bash
aws ssm get-parameter --name /fernbrook/release/runtime_arn --query Parameter.Value --output text
aws ssm get-parameter --name /fernbrook/release/last_good_key --query Parameter.Value --output text
```

**If it fails:** first deploys are where unverified assumptions show up. See [Known unknowns](#known-unknowns). The most common ones:
- Packaging fails on a dependency with no arm64 wheel: the error names the package; pin a version that has one in `requirements-runtime.txt`.
- The Runtime starts but every call errors: the container start command is `opentelemetry-instrument app.py`. If the logs show it failing to start, change `entry_point` in `infrastructure/release/runtime.tf` to `["app.py"]` and push.
- Smoke test times out on the first call: a new runtime can take a minute or two. The test retries for about three minutes. Re-run the workflow.
- Smoke test check 2 fails because the model answered but did not say "shipped": read the printed reply. If the model access in Phase 1.3 worked, adjust the wording the test looks for.

**Why:**
- *Why a smoke test, when unit tests passed?* Unit tests prove the code. The smoke test proves the deployed system: real identity, real Gateway, real policy, real model. Passing tests is not the same as safe to ship.
- *Why pin the runtime to an S3 object version?* A release is one immutable artifact, so a rollback is just pointing back at the previous one.
- *Why is the pipeline red after a rollback?* Because the release failed. The system recovering is good; hiding the failure would not be.

---

## Phase 6: Use it, look inside it, break it on purpose

### 6.1 Talk to your agent

```bash
pip install boto3 "botocore[crt]" "python-jose[cryptography]"     # once, if you skipped the local venv
python scripts/chat.py "What is the status of order FB-10293?"
python scripts/chat.py "What is the status of order FB-10318 and what is in it?"
```

The first order belongs to the demo customer and should come back as shipped. The second belongs to someone else and should be refused. The code, not the model, makes that decision.

Read the refusal closely. On the first deployment the model added that the order "may be associated with a different account", although the prompt tells it not to speculate. Nothing leaked, because the code returns the same `found: false` for someone else's order as for one that does not exist. That is the point of keeping authorization in code: the model does not always follow the prompt.

For a conversation: `python scripts/chat.py`.

### 6.2 Look at the evidence

Lambda logs for the tool call:

```bash
aws logs tail /aws/lambda/fernbrook-order-lookup --since 15m
```

For traces of the model and tool calls, enable **CloudWatch Transaction Search** once per account (CloudWatch console, Settings, Transaction Search; it can take about ten minutes before spans are searchable). Then open the GenAI observability area of CloudWatch and find the `fernbrook-ops-agent` service.

### 6.3 Break it on purpose

This is the best way to see why the pipeline exists.

1. Create a branch: `git switch -c break-it`.
2. In `agent/app.py`, add `raise RuntimeError("boom")` as the first line inside `invoke`.
3. Commit, push, open a pull request, and read the CI result. Merge it.
4. App Deploy runs; approve it. The new version is deployed, the smoke test fails, and the pipeline redeploys the previous good version automatically.
5. Run `python scripts/chat.py "What is the status of order FB-10293?"` again. It still works.
6. Revert the change.

### 6.4 See a plan before it happens

Change something harmless in `infrastructure/platform` (for example, `log_retention_days`), open a pull request, and open the **Infra Plan** run. The summary shows exactly what Terraform would change, using a role that can only read.

---

## Phase 7: Tear everything down

Full details and a manual fallback are in [`TEARDOWN.md`](TEARDOWN.md). In short:

1. **Actions, Destroy, Run workflow**, type `destroy-fernbrook`, approve `app-dev`, then approve `infra-dev`. It removes the runtime, then the platform.
2. From your laptop, remove the bootstrap stack:
   ```bash
   cd infrastructure/bootstrap
   terraform destroy
   ```
3. Run the verification commands in `TEARDOWN.md` to confirm nothing named `fernbrook` is left.

Do not delete the bootstrap folder's `terraform.tfstate` before step 2.

---

## Phase 8: Redeploy later

Your repository is the recipe; nothing else needs to survive.

1. `aws login`, and confirm the model works (Phase 1.3). **Check the model is still Active**: models are retired over time. If it is not, set a current `model_id`.
2. Update tool versions if you like, then re-run Phase 1.4 (validate locally).
3. Phase 2 (bootstrap), Phase 3 (setup script), Phase 4 (Infra Apply), Phase 5 (App Deploy).

If you only ran the Destroy workflow and kept the bootstrap stack, start at Phase 4.

---

## Known unknowns

Status after the first end-to-end deployment (November 2026, AWS provider 6.72.0, Terraform 1.16).

| Area | Status | If it bites |
|---|---|---|
| Terraform code | Deployed end to end. The first-run fixes are in [What broke on the first deploy](#what-broke-on-the-first-deploy). | Fix the error in the named `.tf` file. |
| Provider version floor | Works on 6.72.0. Lower versions are not tested. | Keep the `~> 6.72` constraint. |
| Runtime start command | `opentelemetry-instrument app.py` works. | Nothing to do. |
| arm64 dependencies | Every pinned package builds for arm64 (about 47 MB zip). | Pin a version with an arm64 wheel. |
| Gateway tool names | Confirmed against a live Gateway: Cedar accepts `OrderLookup___get_order_status` and the agent resolves it at run time. | Nothing to do. |
| Cedar validation | The policy engine runs with `validation_mode = IGNORE_ALL_FINDINGS`, which skips only the semantic checks. The schema check always runs, so the policy names only the deployed order-lookup tool. | Try `FAIL_ON_ANY_FINDINGS`; add the wholesale and knowledge actions together with their targets. |
| Infra role breadth | `bedrock-agentcore:*` is deliberately broad on the infra role. | Tighten it using CloudTrail or IAM Access Analyzer. |
| Model | Sonnet 4.6 was chosen because Sonnet 5.5 and Haiku 5.5 showed `agreementAvailability: NOT_AVAILABLE` on the author's account. It is Active, with end of life no sooner than 2027-02-17, so a redeploy after that date needs a newer model. | Set a different `model_id`; if you pick a pre-5 model, you may set `FERNBROOK_TEMPERATURE`. |
| Auth | Terraform reads `aws login` sessions directly. Python scripts need `botocore[crt]`. | `pip install "botocore[crt]"`. |

---

## What broke on the first deploy

The repository was written from documentation and then deployed for the first time. These are the failures, in the order they appeared. All are fixed in the code; the account-level step (6) is in Phase 1.3.

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | Infra Apply: `Not authorized to perform sts:AssumeRoleWithWebIdentity` | GitHub now sends an immutable OIDC subject with numeric IDs: `repo:OWNER@OWNER_ID/REPO@REPO_ID:environment:NAME`. The trust policies expected names only. | `github_owner_id` and `github_repo_id` in bootstrap. Found by reading the failed event in CloudTrail. |
| 2 | `aws_bedrockagentcore_policy`: `CREATE_FAILED`, "unrecognized action" | AgentCore Policy checks every action against the attached gateways' schema in every validation mode. The policy named two tools with no target yet. | Name only deployed tools; a test now checks every permitted action has a Gateway target. |
| 3 | Demo-user script: `AccessDenied` on `ssm:GetParametersByPath` | That call is authorized against the path itself, and the role only allowed `/fernbrook/config/*`. | Grant `/fernbrook/config` as well. |
| 4 | Packaging: pip `ResolutionImpossible` | `mcp` 2.x pinned, while Strands and AgentCore require `mcp<2`. CI did not install the full requirements, so it passed. | Pin `mcp` 1.30.0; CI now installs `requirements.txt`. |
| 5 | Release stack: "Failed creating service linked role" | The first AgentCore Runtime in an account creates `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity` as the caller. | Scoped `iam:CreateServiceLinkedRole` on the app-deploy role. |
| 6 | Smoke test: Runtime returns 500 on every model call | Anthropic use-case form not submitted, then no Marketplace subscription. Account-level, not code. | Phase 1.3. |
| 7 | Smoke test: "own order not returned" | The Gateway timeout was passed as the int `10`; the MCP client sends the request, then fails computing the timeout. The tool ran but its result was lost, and a bare `except` turned that into "not found". | `timedelta(seconds=10)`, errors now logged, and a test that rejects numeric timeouts. |

Two habits made each fix fast: read the full error (in CloudWatch for the Runtime, in CloudTrail for IAM), and test each layer on its own (DynamoDB item, direct Lambda invoke, Cognito attribute) before changing code.

---

## What to do next

- Read [`INTERVIEW-GUIDE.md`](INTERVIEW-GUIDE.md) and be able to draw the diagram in the README from memory.
- Pick a license for the repository (a `LICENSE` file). It is your decision; without one, others have no permission to reuse the code.
- Work through [`DESIGN-NOTES.md`](DESIGN-NOTES.md) for the reasoning behind each part.
- Milestone 2 ideas: deploy the wholesale OpenAPI target with an API-key credential provider, add the Knowledge Base, tighten the infra role from CloudTrail, add an alarm on the smoke-test failure path.
