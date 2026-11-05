# Short-term (session-scoped) AgentCore Memory only. No long-term strategies,
# deliberately (Design Note 8). Replaces memory/create_memory.py.
#
# Name rule: letters, digits, underscores (no hyphens).
resource "aws_bedrockagentcore_memory" "agent" {
  name                  = "FernbrookOpsAgentShortTermMemory"
  description           = "Short-term, session-scoped memory for the Fernbrook Ops Agent. No long-term strategies enabled."
  event_expiry_duration = var.memory_event_expiry_days
}
