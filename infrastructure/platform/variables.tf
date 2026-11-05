variable "aws_region" {
  description = "AWS region. The Python code hardcodes us-east-1, so this repo supports only that region."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This repository hardcodes us-east-1 in its Python code. Changing the region needs code changes too; see README."
  }
}

variable "environment" {
  description = "Environment label used in tags. Resource names are fixed (one environment per AWS account)."
  type        = string
  default     = "dev"
}

variable "model_id" {
  description = <<-EOT
    Bedrock model or inference-profile ID the agent calls. Passed to the
    agent as FERNBROOK_MODEL_ID. Claude Sonnet 4.6 was listed as Active by
    AWS on 2026-11-05 (end of life no sooner than 2027-02-17). Models have
    a lifecycle and new accounts cannot start using Legacy ones, so before
    you redeploy months from now, check the Bedrock model catalog and set a
    current model here. The agent sends no temperature/top_p/top_k, because
    Sonnet 5 and later models reject them.
  EOT
  type        = string
  default     = "us.anthropic.claude-sonnet-4-6"
}

variable "memory_event_expiry_days" {
  description = "How long AgentCore Memory keeps conversation events. Provider allows 7 to 365."
  type        = number
  default     = 30

  validation {
    condition     = var.memory_event_expiry_days >= 7 && var.memory_event_expiry_days <= 365
    error_message = "memory_event_expiry_days must be between 7 and 365."
  }
}

variable "log_retention_days" {
  description = "Retention for Lambda log groups managed here."
  type        = number
  default     = 14
}
