# GitHub Actions authenticates to AWS with short-lived OIDC tokens, so there
# are no long-lived access keys anywhere: not in GitHub secrets, not in the
# repository, not on a laptop. AWS validates the token against GitHub's
# published signing keys; the roles below decide *which* workflow runs may
# use the token, by matching the token's `sub` claim exactly.
#
# thumbprint_list is omitted on purpose: for GitHub's OIDC endpoint AWS uses
# its own library of trusted root CAs instead of a configured thumbprint.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.existing_github_oidc_provider_arn == "" ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  oidc_aud_condition = {
    test     = "StringEquals"
    variable = "token.actions.githubusercontent.com:aud"
    values   = ["sts.amazonaws.com"]
  }
}

# Three trust policies, three different `sub` values. This is the main
# control: a workflow run can only assume the role whose subject it matches.
data "aws_iam_policy_document" "trust_plan" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = local.oidc_aud_condition.test
      variable = local.oidc_aud_condition.variable
      values   = local.oidc_aud_condition.values
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:pull_request"]
    }
  }
}

data "aws_iam_policy_document" "trust_infra" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = local.oidc_aud_condition.test
      variable = local.oidc_aud_condition.variable
      values   = local.oidc_aud_condition.values
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:environment:${var.infra_environment}"]
    }
  }
}

data "aws_iam_policy_document" "trust_app" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = local.oidc_aud_condition.test
      variable = local.oidc_aud_condition.variable
      values   = local.oidc_aud_condition.values
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.repo}:environment:${var.app_environment}"]
    }
  }
}
