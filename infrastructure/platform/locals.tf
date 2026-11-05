data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = var.aws_region

  # Every role this stack creates must carry this boundary (created by the
  # bootstrap stack). The infra-apply pipeline role cannot create a role
  # without it. See infrastructure/bootstrap/boundary.tf.
  boundary_arn = "arn:${local.partition}:iam::${local.account_id}:policy/fernbrook-workload-boundary"

  code_bucket_name = "fernbrook-agent-code-${local.account_id}-${local.region}"

  # Trust policy shared by the roles AgentCore assumes (Runtime and Gateway).
  # The SourceAccount/SourceArn conditions stop another account's AgentCore
  # resources from borrowing these roles (confused-deputy protection).
  agentcore_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AssumeByAgentCore"
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:${local.partition}:bedrock-agentcore:${local.region}:${local.account_id}:*" }
      }
    }]
  })
}
