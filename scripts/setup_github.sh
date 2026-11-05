#!/usr/bin/env bash
# Wires GitHub to the AWS roles created by infrastructure/bootstrap.
#
#   - repository secrets:   AWS_PLAN_ROLE_ARN, TF_STATE_BUCKET
#   - environments:         infra-dev, app-dev (main branch only, you as required reviewer)
#   - environment secrets:  AWS_ROLE_ARN in each (a different role per environment)
#
# Run from the repo root after `terraform apply` in infrastructure/bootstrap
# and after `gh auth login`. Safe to re-run. Secret values are piped to `gh`
# on stdin and never printed.
#
#   ./scripts/setup_github.sh              # with you as required reviewer
#   ./scripts/setup_github.sh --no-reviewer
set -euo pipefail

BOOTSTRAP_DIR="infrastructure/bootstrap"
REVIEWER=true
[[ "${1:-}" == "--no-reviewer" ]] && REVIEWER=false

command -v gh >/dev/null        || { echo "gh (GitHub CLI) not found. Install it, then run: gh auth login"; exit 1; }
command -v terraform >/dev/null || { echo "terraform not found."; exit 1; }
gh auth status >/dev/null 2>&1  || { echo "Not logged in to GitHub. Run: gh auth login"; exit 1; }
[[ -d "$BOOTSTRAP_DIR" ]]       || { echo "Run this from the repository root."; exit 1; }

tf_out() { terraform -chdir="$BOOTSTRAP_DIR" output -raw "$1"; }

REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
echo "Repository: $REPO"

PLAN_ROLE=$(tf_out plan_role_arn)
INFRA_ROLE=$(tf_out infra_apply_role_arn)
APP_ROLE=$(tf_out app_deploy_role_arn)
STATE_BUCKET=$(tf_out state_bucket)

echo "Setting repository secrets..."
printf %s "$PLAN_ROLE"    | gh secret set AWS_PLAN_ROLE_ARN --repo "$REPO"
printf %s "$STATE_BUCKET" | gh secret set TF_STATE_BUCKET   --repo "$REPO"

USER_ID=$(gh api user --jq .id)

create_environment() {
  local env="$1"
  echo "Configuring environment $env..."
  if $REVIEWER; then
    printf '{"reviewers":[{"type":"User","id":%s}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}' "$USER_ID" \
      | gh api -X PUT "repos/$REPO/environments/$env" --input - >/dev/null
  else
    printf '{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}' \
      | gh api -X PUT "repos/$REPO/environments/$env" --input - >/dev/null
  fi
  # Only the main branch may use this environment, and therefore its AWS role.
  printf '{"name":"main","type":"branch"}' \
    | gh api -X POST "repos/$REPO/environments/$env/deployment-branch-policies" --input - >/dev/null 2>&1 \
    || echo "  (branch policy for $env may already exist, or the API refused it; check Settings > Environments)"
}

create_environment infra-dev
create_environment app-dev

echo "Setting environment secrets..."
printf %s "$INFRA_ROLE" | gh secret set AWS_ROLE_ARN --env infra-dev --repo "$REPO"
printf %s "$APP_ROLE"   | gh secret set AWS_ROLE_ARN --env app-dev   --repo "$REPO"

echo
echo "Done. Verify with:  gh secret list --repo $REPO ; gh secret list --env infra-dev --repo $REPO"
