# Role 3 of 3: "app-deploy". Assumed only by jobs in the `app-dev` GitHub
# environment. Ships a new agent version: uploads the code zip, updates the
# Runtime, runs the smoke test, records the last known good version.
#
# It cannot create IAM roles, DynamoDB tables, Gateways or Cognito pools.
# The people (or workflow) who can change application code are therefore not
# the same ones who can change the platform.
resource "aws_iam_role" "app_deploy" {
  name                 = "fernbrook-gha-app-deploy"
  description          = "GitHub Actions: ship a new agent version (app-dev environment only)."
  assume_role_policy   = data.aws_iam_policy_document.trust_app.json
  max_session_duration = 3600
}

resource "aws_iam_policy" "app_deploy" {
  name        = "fernbrook-gha-app-deploy"
  description = "Ship agent code: code bucket, Runtime, release SSM params, smoke test."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReleaseStateObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.state.arn}/release/*"
      },
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.state.arn
      },
      {
        Sid      = "UploadAgentZips"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:GetObjectVersion"]
        Resource = "arn:${local.partition}:s3:::${local.code_bucket_name}/agent/*"
      },
      {
        Sid      = "ListCodeBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:ListBucketVersions", "s3:GetBucketVersioning"]
        Resource = "arn:${local.partition}:s3:::${local.code_bucket_name}"
      },
      {
        Sid      = "RuntimeAndItsWorkloadIdentity"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:*AgentRuntime*", "bedrock-agentcore:*WorkloadIdentity*", "bedrock-agentcore:TagResource", "bedrock-agentcore:UntagResource", "bedrock-agentcore:ListTagsForResource"]
        Resource = "*"
      },
      {
        Sid      = "PassOnlyTheRuntimeRole"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = "arn:${local.partition}:iam::${local.account_id}:role/fernbrook-agent-runtime-role"
        Condition = {
          StringEquals = { "iam:PassedToService" = "bedrock-agentcore.amazonaws.com" }
        }
      },
      {
        Sid      = "ReadPlatformConfig"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/fernbrook/config*"
      },
      {
        Sid      = "ManageReleaseParameters"
        Effect   = "Allow"
        Action   = ["ssm:PutParameter", "ssm:GetParameter", "ssm:GetParameters", "ssm:DeleteParameter", "ssm:DeleteParameters", "ssm:AddTagsToResource", "ssm:RemoveTagsFromResource", "ssm:ListTagsForResource"]
        Resource = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/fernbrook/release/*"
      },
      {
        Sid      = "DescribeParametersNoResourceScope"
        Effect   = "Allow"
        Action   = ["ssm:DescribeParameters"]
        Resource = "*"
      },
      {
        Sid      = "SmokeTestCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:${local.partition}:secretsmanager:${local.region}:${local.account_id}:secret:fernbrook/demo-user-password-*"
      },
      {
        Sid      = "SmokeTestLogin"
        Effect   = "Allow"
        Action   = ["cognito-idp:AdminInitiateAuth"]
        Resource = "arn:${local.partition}:cognito-idp:${local.region}:${local.account_id}:userpool/*"
      },
      {
        Sid      = "RuntimeLogsReadAndCleanup"
        Effect   = "Allow"
        Action   = ["logs:DescribeLogStreams", "logs:GetLogEvents", "logs:FilterLogEvents", "logs:DeleteLogGroup", "logs:ListTagsForResource"]
        Resource = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/fernbrook_ops_agent-*", "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/fernbrook_ops_agent-*:*"]
      },
      {
        Sid      = "DescribeLogGroupsNoResourceScope"
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app_deploy" {
  role       = aws_iam_role.app_deploy.name
  policy_arn = aws_iam_policy.app_deploy.arn
}
