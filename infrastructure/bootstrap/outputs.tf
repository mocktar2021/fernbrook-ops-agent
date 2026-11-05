output "state_bucket" {
  description = "Remote-state bucket for the platform and release stacks."
  value       = aws_s3_bucket.state.bucket
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

output "infra_apply_role_arn" {
  value = aws_iam_role.infra_apply.arn
}

output "app_deploy_role_arn" {
  value = aws_iam_role.app_deploy.arn
}

output "permissions_boundary_arn" {
  value = aws_iam_policy.boundary.arn
}

output "next_steps" {
  description = "What to do after apply."
  value       = <<-EOT
    Bootstrap complete. Next, store these in GitHub (see docs/GETTING-STARTED.md, phase 3):
      repository secret   AWS_PLAN_ROLE_ARN       <- terraform output -raw plan_role_arn
      repository secret   TF_STATE_BUCKET         <- terraform output -raw state_bucket
      environment infra-dev, secret AWS_ROLE_ARN  <- terraform output -raw infra_apply_role_arn
      environment app-dev,   secret AWS_ROLE_ARN  <- terraform output -raw app_deploy_role_arn
    Or run scripts/setup_github.sh from the repo root to do it with the gh CLI.
  EOT
}
