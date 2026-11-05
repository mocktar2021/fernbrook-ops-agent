variable "aws_region" {
  description = "AWS region. The Python code hardcodes us-east-1, so this repo supports only that region."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This repository hardcodes us-east-1 in its Python code. Changing the region needs code changes too; see README."
  }
}

variable "github_owner" {
  description = "GitHub user or organization that owns the repository, e.g. \"octocat\". Case-sensitive in the OIDC subject claim."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name, e.g. \"fernbrook-ops-agent\"."
  type        = string
}

variable "existing_github_oidc_provider_arn" {
  description = <<-EOT
    An AWS account can hold only one OIDC provider per URL. If this account
    already has token.actions.githubusercontent.com registered, pass its ARN
    here and this stack will reuse it instead of trying to create a second one.
  EOT
  type        = string
  default     = ""
}

variable "state_bucket_force_destroy" {
  description = "Allow `terraform destroy` to delete the state bucket even though it holds state files. True suits a demo; set false for anything you care about."
  type        = bool
  default     = true
}

variable "infra_environment" {
  description = "GitHub environment name whose jobs may assume the infrastructure-apply role."
  type        = string
  default     = "infra-dev"
}

variable "app_environment" {
  description = "GitHub environment name whose jobs may assume the app-deploy role."
  type        = string
  default     = "app-dev"
}

variable "budget_email" {
  description = "Email address for a monthly cost alert. Leave empty to skip creating the budget."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  description = "Monthly budget in USD. An email is sent at 80% of actual spend and at 100% of forecasted spend."
  type        = number
  default     = 25
}

variable "github_owner_id" {
  description = <<-EOT
    Numeric ID of the GitHub account that owns the repository. GitHub puts the
    owner and repository IDs into the OIDC subject claim of repositories that use
    its immutable subject format, so the trust policy must match them. Find them with:
      gh api repos/OWNER/REPO --jq '.owner.id, .id'
    Leave both IDs empty only if your repository still uses the older name-only format.
  EOT
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[0-9]*$", var.github_owner_id))
    error_message = "github_owner_id must be digits only."
  }
}

variable "github_repo_id" {
  description = "Numeric ID of the GitHub repository. Set together with github_owner_id."
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[0-9]*$", var.github_repo_id)) && ((var.github_repo_id == "") == (var.github_owner_id == ""))
    error_message = "github_repo_id must be digits only, and must be set together with github_owner_id (both or neither)."
  }
}
