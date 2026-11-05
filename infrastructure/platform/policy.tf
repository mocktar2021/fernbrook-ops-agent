# AgentCore Policy: Cedar, default-deny. If a tool is registered on the Gateway
# and no permit statement names it, calls to it are denied, whatever the
# model decides. "Models decide what might be useful. Policy decides what is
# allowed."
resource "aws_bedrockagentcore_policy_engine" "agent" {
  # Letters, digits, underscores only; max 48 characters.
  name        = "fernbrook_policy_engine"
  description = "Default-deny Cedar policy for the Fernbrook Gateway."
}

locals {
  # policy/fernbrook-tool-access.cedar is the single source of truth (it is
  # also what tests/test_cedar_policy_structure.py checks). Only the Gateway
  # ARN placeholder is filled in here.
  cedar_statement = replace(
    file("${path.module}/../../policy/fernbrook-tool-access.cedar"),
    "REPLACE_WITH_YOUR_FERNBROOK_GATEWAY_ARN",
    aws_bedrockagentcore_gateway.agent.gateway_arn,
  )
}

resource "aws_bedrockagentcore_policy" "tool_access" {
  name             = "fernbrook_tool_access"
  description      = "Permit the agent's execution role to call the approved Gateway tools. Everything else is denied."
  policy_engine_id = aws_bedrockagentcore_policy_engine.agent.policy_engine_id

  # The Cedar file also permits the wholesale and knowledge-base tools, whose
  # Gateway targets are not deployed in this milestone. Strict validation
  # would reject a permit for an action that does not exist yet, so findings
  # are ignored here. A permit for a missing tool grants nothing: default-deny
  # still applies. When those targets are added, switch this to
  # FAIL_ON_ANY_FINDINGS so the policy is checked against the real schema.
  validation_mode = "IGNORE_ALL_FINDINGS"

  definition {
    cedar {
      statement = local.cedar_statement
    }
  }

  depends_on = [aws_bedrockagentcore_gateway_target.order_lookup]
}
