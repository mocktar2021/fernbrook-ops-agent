output "agent_runtime_arn" {
  value = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

output "agent_runtime_id" {
  value = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
}

output "agent_runtime_version" {
  description = "Runtime version number created by this apply."
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version
}
