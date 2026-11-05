output "gateway_url" {
  description = "MCP endpoint of the Fernbrook Gateway."
  value       = aws_bedrockagentcore_gateway.agent.gateway_url
}

output "gateway_arn" {
  value = aws_bedrockagentcore_gateway.agent.gateway_arn
}

output "memory_id" {
  value = aws_bedrockagentcore_memory.agent.id
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.agent.guardrail_id
}

output "guardrail_version" {
  value = aws_bedrock_guardrail_version.agent.version
}

output "user_pool_id" {
  value = aws_cognito_user_pool.customers.id
}

output "app_client_id" {
  value = aws_cognito_user_pool_client.support_app.id
}

output "runtime_role_arn" {
  value = aws_iam_role.agent_runtime.arn
}

output "code_bucket" {
  value = aws_s3_bucket.code.bucket
}

output "order_lookup_function_arn" {
  description = "ARN of the order-lookup Lambda behind the Gateway target."
  value       = aws_lambda_function.order_lookup.arn
}

output "orders_table_name" {
  value = aws_dynamodb_table.orders.name
}

output "refund_approvals_table_name" {
  value = aws_dynamodb_table.refund_approvals.name
}
