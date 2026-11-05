# The contract between the platform stack and the release stack. The platform
# stack writes non-secret IDs and ARNs here; the release stack and the app
# pipeline read them. That keeps the two stacks (and their IAM roles)
# decoupled: the app pipeline never needs platform permissions or remote-state
# access, only read access to /fernbrook/config.
#
# Nothing secret goes in these parameters. They hold identifiers.
locals {
  config_parameters = {
    memory_id         = aws_bedrockagentcore_memory.agent.id
    gateway_url       = aws_bedrockagentcore_gateway.agent.gateway_url
    guardrail_id      = aws_bedrock_guardrail.agent.guardrail_id
    guardrail_version = aws_bedrock_guardrail_version.agent.version
    user_pool_id      = aws_cognito_user_pool.customers.id
    app_client_id     = aws_cognito_user_pool_client.support_app.id
    runtime_role_arn  = aws_iam_role.agent_runtime.arn
    code_bucket       = aws_s3_bucket.code.bucket
    model_id          = var.model_id
  }
}

resource "aws_ssm_parameter" "config" {
  for_each = local.config_parameters

  name        = "/fernbrook/config/${each.key}"
  description = "Platform output consumed by the release stack and app pipeline."
  type        = "String"
  value       = each.value
}
