# Role 2 of 3: "infra-apply". Assumed only by jobs that run in the
# `infra-dev` GitHub environment (which you protect with a required
# reviewer). Creates and destroys the platform stack.
#
# Three managed policies keep each under IAM's size limit and make the
# review easier: data/compute, IAM+identity, and the AI services.
resource "aws_iam_role" "infra_apply" {
  name                 = "fernbrook-gha-infra-apply"
  description          = "GitHub Actions: apply/destroy the platform stack (infra-dev environment only)."
  assume_role_policy   = data.aws_iam_policy_document.trust_infra.json
  max_session_duration = 3600
}

resource "aws_iam_policy" "infra_apply_data" {
  name        = "fernbrook-gha-infra-apply-data"
  description = "Platform stack: state, code bucket, DynamoDB, Lambda, logs, SSM, Secrets Manager."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PlatformStateObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.state.arn}/platform/*"
      },
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.state.arn
      },
      {
        Sid      = "CodeBucketAll"
        Effect   = "Allow"
        Action   = ["s3:*"]
        Resource = ["arn:${local.partition}:s3:::${local.code_bucket_name}", "arn:${local.partition}:s3:::${local.code_bucket_name}/*"]
      },
      {
        Sid      = "FernbrookTables"
        Effect   = "Allow"
        Action   = ["dynamodb:*"]
        Resource = "arn:${local.partition}:dynamodb:${local.region}:${local.account_id}:table/fernbrook-*"
      },
      {
        Sid      = "FernbrookFunctions"
        Effect   = "Allow"
        Action   = ["lambda:*"]
        Resource = "arn:${local.partition}:lambda:${local.region}:${local.account_id}:function:fernbrook-*"
      },
      {
        Sid      = "FernbrookLambdaLogGroups"
        Effect   = "Allow"
        Action   = ["logs:*"]
        Resource = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/fernbrook-*", "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/fernbrook-*:*"]
      },
      {
        Sid      = "DescribeLogGroupsNoResourceScope"
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups", "logs:ListTagsForResource"]
        Resource = "*"
      },
      {
        Sid    = "FernbrookConfigParameters"
        Effect = "Allow"
        Action = ["ssm:PutParameter", "ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath", "ssm:DeleteParameter", "ssm:DeleteParameters", "ssm:AddTagsToResource", "ssm:RemoveTagsFromResource", "ssm:ListTagsForResource"]
        # GetParametersByPath is authorized against the path itself, so the
        # bare path is listed as well as the parameters under it.
        Resource = [
          "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/fernbrook/config",
          "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/fernbrook/config/*",
        ]
      },
      {
        Sid      = "DescribeParametersNoResourceScope"
        Effect   = "Allow"
        Action   = ["ssm:DescribeParameters"]
        Resource = "*"
      },
      {
        Sid      = "DemoUserSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:*"]
        Resource = "arn:${local.partition}:secretsmanager:${local.region}:${local.account_id}:secret:fernbrook/demo-user-password-*"
      },
    ]
  })
}

resource "aws_iam_policy" "infra_apply_iam" {
  name        = "fernbrook-gha-infra-apply-iam"
  description = "Platform stack: create bounded workload roles; manage the Cognito pool."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # The key control. CreateRole succeeds only when the new role carries
        # the permissions boundary, so a compromised pipeline cannot mint an
        # unbounded (admin) role.
        Sid      = "CreateOnlyBoundedWorkloadRoles"
        Effect   = "Allow"
        Action   = ["iam:CreateRole"]
        Resource = local.workload_role_arns
        Condition = {
          StringEquals = { "iam:PermissionsBoundary" = local.boundary_policy_arn }
        }
      },
      {
        Sid    = "ManageWorkloadRoles"
        Effect = "Allow"
        Action = [
          "iam:GetRole", "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateAssumeRolePolicy",
          "iam:TagRole", "iam:UntagRole", "iam:ListRoleTags",
          "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy",
          "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole",
        ]
        Resource = local.workload_role_arns
      },
      {
        Sid      = "PassWorkloadRolesToTheirServices"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = local.workload_role_arns
        Condition = {
          StringEquals = { "iam:PassedToService" = ["bedrock-agentcore.amazonaws.com", "lambda.amazonaws.com"] }
        }
      },
      {
        Sid      = "NeverTouchPipelineRolesOrBoundary"
        Effect   = "Deny"
        Action   = ["iam:*"]
        Resource = ["arn:${local.partition}:iam::${local.account_id}:role/fernbrook-gha-*", local.boundary_policy_arn]
      },
      {
        Sid      = "CognitoCreateAndList"
        Effect   = "Allow"
        Action   = ["cognito-idp:CreateUserPool", "cognito-idp:ListUserPools"]
        Resource = "*"
      },
      {
        Sid      = "CognitoManagePools"
        Effect   = "Allow"
        Action   = ["cognito-idp:*"]
        Resource = "arn:${local.partition}:cognito-idp:${local.region}:${local.account_id}:userpool/*"
      },
    ]
  })
}

resource "aws_iam_policy" "infra_apply_ai" {
  name        = "fernbrook-gha-infra-apply-ai"
  description = "Platform stack: Bedrock Guardrails and AgentCore Memory/Gateway/Policy."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Guardrails"
        Effect   = "Allow"
        Action   = ["bedrock:CreateGuardrail", "bedrock:CreateGuardrailVersion", "bedrock:GetGuardrail", "bedrock:UpdateGuardrail", "bedrock:DeleteGuardrail", "bedrock:ListGuardrails", "bedrock:ListTagsForResource", "bedrock:TagResource", "bedrock:UntagResource"]
        Resource = "*"
      },
      {
        # AgentCore create-APIs do not support resource-level scoping, and
        # the exact action set the provider needs for gateways and policy
        # engines is not fully documented. This is the one deliberately broad
        # statement. Tighten it from CloudTrail / IAM Access Analyzer after a
        # few successful applies (see docs/INTERVIEW-GUIDE.md).
        Sid      = "AgentCoreControlPlane"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:*"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "infra_apply" {
  for_each = {
    data = aws_iam_policy.infra_apply_data.arn
    iam  = aws_iam_policy.infra_apply_iam.arn
    ai   = aws_iam_policy.infra_apply_ai.arn
  }

  role       = aws_iam_role.infra_apply.name
  policy_arn = each.value
}
