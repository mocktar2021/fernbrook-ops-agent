# Permissions boundary for every role the pipeline creates.
#
# The infra-apply role must be able to create IAM roles (the agent's
# execution role, the Gateway's service role, a Lambda role). Without a
# guardrail, "can create roles" means "can mint an admin role and use it".
# So the apply role may only create roles that carry THIS boundary, and
# the boundary lists the most those roles can ever do, whatever policy is
# attached to them later. A role's effective permissions are the
# intersection of its own policies and its boundary.
data "aws_iam_policy_document" "boundary" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:DescribeLogGroups"]
    resources = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:*"]
  }

  statement {
    # AgentCore lets X-Ray deliver the agent's spans into the agent's own
    # log group. Only the Fernbrook agent's runtime log groups.
    sid       = "AgentSpanDelivery"
    actions   = ["logs:PutResourcePolicy"]
    resources = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/fernbrook_ops_agent-*"]
  }

  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }

  statement {
    sid       = "AgentCoreMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  statement {
    sid     = "InvokeModelsAndGuardrail"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail"]
    resources = [
      "arn:${local.partition}:bedrock:*::foundation-model/*",
      "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:inference-profile/*",
      "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:guardrail/*",
    ]
  }

  statement {
    sid = "AgentCoreDataPlane"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
      "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
      "bedrock-agentcore:InvokeGateway",
      "bedrock-agentcore:CreateEvent",
      "bedrock-agentcore:GetEvent",
      "bedrock-agentcore:ListEvents",
      "bedrock-agentcore:ListActors",
      "bedrock-agentcore:ListSessions",
      "bedrock-agentcore:GetPolicyEngine",
      "bedrock-agentcore:AuthorizeAction",
      "bedrock-agentcore:PartiallyAuthorizeActions",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "FernbrookTables"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = ["arn:${local.partition}:dynamodb:${local.region}:${local.account_id}:table/fernbrook-*"]
  }

  statement {
    sid       = "InvokeFernbrookLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:${local.partition}:lambda:${local.region}:${local.account_id}:function:fernbrook-*"]
  }

  statement {
    sid       = "ReadFernbrookSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:${local.partition}:secretsmanager:${local.region}:${local.account_id}:secret:fernbrook/*"]
  }

  statement {
    sid       = "ReadAgentCode"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["arn:${local.partition}:s3:::${local.code_bucket_name}/*"]
  }
}

resource "aws_iam_policy" "boundary" {
  name        = local.boundary_policy_name
  description = "Upper limit on every role the Fernbrook pipelines create."
  policy      = data.aws_iam_policy_document.boundary.json
}
