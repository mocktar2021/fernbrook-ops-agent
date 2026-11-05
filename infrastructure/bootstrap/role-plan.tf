# Role 1 of 3: "plan" (read-only). Assumed by pull_request workflow runs.
#
# It can read the account and read the platform state file, nothing else.
# Even a hostile pull request that rewrites the workflow can only look; it
# cannot create, change, or delete anything. Plans run with -lock=false
# because this role deliberately cannot write the lock file.
resource "aws_iam_role" "plan" {
  name                 = "fernbrook-gha-plan"
  description          = "GitHub Actions: terraform plan on pull requests (read-only)."
  assume_role_policy   = data.aws_iam_policy_document.trust_plan.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "plan_extra" {
  name = "ReadAgentCoreAndState"
  role = aws_iam_role.plan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadAgentCoreAndBedrock"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:Get*", "bedrock-agentcore:List*", "bedrock:Get*", "bedrock:List*"]
        Resource = "*"
      },
      {
        Sid      = "ReadPlatformState"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.state.arn}/platform/*"
      },
      {
        Sid      = "ListStateBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.state.arn
      },
    ]
  })
}
