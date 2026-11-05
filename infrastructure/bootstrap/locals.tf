data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = var.aws_region
  repo       = "${var.github_owner}/${var.github_repo}"

  # S3 bucket names are global; the account ID and region make them unique
  # and recognizable. The code bucket is created by the platform stack; its
  # name is computed here (not referenced) so the app-deploy role can be
  # scoped to it without a dependency between stacks.
  state_bucket_name = "fernbrook-tfstate-${local.account_id}-${local.region}"
  code_bucket_name  = "fernbrook-agent-code-${local.account_id}-${local.region}"

  oidc_provider_arn = (
    var.existing_github_oidc_provider_arn != ""
    ? var.existing_github_oidc_provider_arn
    : aws_iam_openid_connect_provider.github[0].arn
  )

  # Workload roles the platform stack creates. Listed explicitly (not as a
  # wildcard) so the pipeline roles named fernbrook-gha-* can never match.
  workload_role_names = [
    "fernbrook-agent-runtime-role",
    "fernbrook-gateway-role",
    "fernbrook-order-lookup-lambda-role",
  ]
  workload_role_arns = [
    for name in local.workload_role_names : "arn:${local.partition}:iam::${local.account_id}:role/${name}"
  ]

  boundary_policy_name = "fernbrook-workload-boundary"
  boundary_policy_arn  = "arn:${local.partition}:iam::${local.account_id}:policy/${local.boundary_policy_name}"
}
