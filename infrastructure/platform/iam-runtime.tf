# The execution role the agent runs as inside AgentCore Runtime. This is the
# agent's identity: every AWS call the agent code makes is made as this role.
#
# The name MUST contain "fernbrook-agent-runtime": the Cedar policy permits
# only principals whose id matches "*assumed-role/fernbrook-agent-runtime*".
#
# Statements follow the AWS-documented Runtime execution role, plus the
# project's own grants (infrastructure/iam/runtime-execution-role-*.json),
# each scoped to the one resource it needs. The permissions boundary caps the
# role even if someone later attaches a broader policy.
resource "aws_iam_role" "agent_runtime" {
  name                 = "fernbrook-agent-runtime-role"
  description          = "Execution role for the Fernbrook Ops Agent on AgentCore Runtime."
  assume_role_policy   = local.agentcore_trust_policy
  permissions_boundary = local.boundary_arn
}

resource "aws_iam_role_policy" "agent_runtime" {
  name = "FernbrookAgentRuntime"
  role = aws_iam_role.agent_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "LogGroups"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:DescribeLogStreams"]
        Resource = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
      },
      {
        # Spans go to the agent's own log group. AgentCore uses this to allow
        # X-Ray to write there. Without it, spans are silently dropped.
        Sid      = "AgentSpanDelivery"
        Effect   = "Allow"
        Action   = ["logs:PutResourcePolicy"]
        Resource = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/fernbrook_ops_agent-*"
      },
      {
        Sid      = "DescribeLogGroups"
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups"]
        Resource = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:*"
      },
      {
        Sid      = "LogStreams"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
      },
      {
        Sid      = "Tracing"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
        Resource = "*"
      },
      {
        Sid       = "AgentCoreMetrics"
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" } }
      },
      {
        Sid    = "WorkloadAccessToken"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
        Resource = [
          "arn:${local.partition}:bedrock-agentcore:${local.region}:${local.account_id}:workload-identity-directory/default",
          "arn:${local.partition}:bedrock-agentcore:${local.region}:${local.account_id}:workload-identity-directory/default/workload-identity/fernbrook_ops_agent-*",
        ]
      },
      {
        # Foundation-model ARNs are listed for every region because a
        # cross-region inference profile (us.*) can route to any region in
        # its geography.
        Sid    = "InvokeModel"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = [
          "arn:${local.partition}:bedrock:*::foundation-model/*",
          "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:inference-profile/*",
        ]
      },
      {
        Sid      = "ApplyFernbrookGuardrail"
        Effect   = "Allow"
        Action   = ["bedrock:ApplyGuardrail"]
        Resource = aws_bedrock_guardrail.agent.guardrail_arn
      },
      {
        Sid      = "UseFernbrookShortTermMemory"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:CreateEvent", "bedrock-agentcore:GetEvent", "bedrock-agentcore:ListEvents", "bedrock-agentcore:ListActors", "bedrock-agentcore:ListSessions"]
        Resource = aws_bedrockagentcore_memory.agent.arn
      },
      {
        Sid      = "InvokeFernbrookGateway"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:InvokeGateway"]
        Resource = aws_bedrockagentcore_gateway.agent.gateway_arn
      },
      {
        Sid      = "ProcessFernbrookRefunds"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Sid      = "QueueRefundApprovals"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.refund_approvals.arn
      },
      {
        Sid      = "CheckRefundIdempotency"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.refund_idempotency.arn
      },
    ]
  })
}
