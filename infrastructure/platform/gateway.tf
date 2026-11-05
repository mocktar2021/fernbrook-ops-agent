# AgentCore Gateway: the one door through which the agent reaches tools. It
# speaks MCP to the agent and invokes the Lambda on the agent's behalf.
#
# Inbound authorization is AWS_IAM: only SigV4-signed callers with
# bedrock-agentcore:InvokeGateway on this gateway get in, and the only such
# caller is the agent's execution role (see iam-runtime.tf). On top of that,
# the attached policy engine (policy.tf) evaluates Cedar default-deny on every
# tool call.

# ---- The Gateway's own service role: what Gateway may do on our behalf ----
resource "aws_iam_role" "gateway" {
  name                 = "fernbrook-gateway-role"
  description          = "Assumed by AgentCore Gateway to invoke tool Lambdas and evaluate policy."
  assume_role_policy   = local.agentcore_trust_policy
  permissions_boundary = local.boundary_arn
}

resource "aws_iam_role_policy" "gateway" {
  name = "InvokeToolsAndEvaluatePolicy"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeOrderLookupLambda"
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.order_lookup.arn
      },
      {
        # Per the AgentCore Policy docs, AuthorizeAction and
        # PartiallyAuthorizeActions need BOTH the policy engine and the
        # gateway as resources. The gateway ID is not known until the gateway
        # exists (and the gateway needs this role), so the gateway resource
        # is scoped to this account and region instead of one ID.
        Sid    = "EvaluateCedarPolicy"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetPolicyEngine", "bedrock-agentcore:AuthorizeAction", "bedrock-agentcore:PartiallyAuthorizeActions"]
        Resource = [
          aws_bedrockagentcore_policy_engine.agent.policy_engine_arn,
          "arn:${local.partition}:bedrock-agentcore:${local.region}:${local.account_id}:gateway/*",
        ]
      },
    ]
  })
}

# IAM is eventually consistent. Creating a Gateway the instant its role
# exists can fail with "role cannot be assumed". A short pause is the
# standard, boring fix.
resource "time_sleep" "iam_propagation" {
  create_duration = "20s"

  depends_on = [
    aws_iam_role.gateway,
    aws_iam_role_policy.gateway,
  ]
}

resource "aws_bedrockagentcore_gateway" "agent" {
  name            = "fernbrook-gateway"
  description     = "Fernbrook tool gateway: approved tools only, default-deny Cedar policy."
  role_arn        = aws_iam_role.gateway.arn
  authorizer_type = "AWS_IAM"
  protocol_type   = "MCP"

  policy_engine_configuration {
    arn  = aws_bedrockagentcore_policy_engine.agent.policy_engine_arn
    mode = "ENFORCE"
  }

  depends_on = [time_sleep.iam_propagation]
}

# The tool the model sees. Name, description and input schema come from
# tools/order_lookup/tool_schema.json, so the JSON stays the single source of
# truth (it is also what the manual setup in tools/order_lookup/README.md uses).
#
# Gateway exposes this as `OrderLookup___get_order_status` (target name, three
# underscores, tool name). The Cedar policy references that exact string.
locals {
  order_tool = jsondecode(file("${path.module}/../../tools/order_lookup/tool_schema.json"))[0]
}

resource "aws_bedrockagentcore_gateway_target" "order_lookup" {
  name               = "OrderLookup"
  gateway_identifier = aws_bedrockagentcore_gateway.agent.gateway_id
  description        = "Read-only order status lookup (Lambda + DynamoDB)."

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.order_lookup.arn

        tool_schema {
          inline_payload {
            name        = local.order_tool.name
            description = local.order_tool.description

            input_schema {
              type = "object"

              property {
                name        = "order_id"
                type        = "string"
                description = local.order_tool.inputSchema.properties.order_id.description
                required    = true
              }
            }
          }
        }
      }
    }
  }
}
