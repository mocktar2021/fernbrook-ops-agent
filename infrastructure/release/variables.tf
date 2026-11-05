variable "aws_region" {
  description = "AWS region. The Python code hardcodes us-east-1, so this repo supports only that region."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This repository hardcodes us-east-1 in its Python code. Changing the region needs code changes too; see README."
  }
}

# The two inputs below change on every release. The app pipeline supplies them
# (TF_VAR_code_key / TF_VAR_code_version_id) after uploading the zip.
variable "code_key" {
  description = "S3 key of the agent zip inside the code bucket, e.g. agent/<git sha>.zip."
  type        = string
}

variable "code_version_id" {
  description = "S3 version ID of that exact upload. Pins the Runtime to one immutable artifact."
  type        = string
}

variable "python_runtime" {
  description = "AgentCore Runtime Python version. scripts/package_agent.py builds wheels for the same version; change both together."
  type        = string
  default     = "PYTHON_3_13"
}
