# Everything the platform stack decided (memory ID, gateway URL, guardrail,
# identity pool) arrives through SSM, not through shared Terraform state.
data "aws_ssm_parameters_by_path" "config" {
  path      = "/fernbrook/config"
  recursive = false
}

locals {
  # The provider marks `values` sensitive unconditionally. These are
  # identifiers and ARNs, not secrets, and the runtime's environment
  # variables are not sensitive either, so the marking is removed.
  config = nonsensitive(zipmap(
    data.aws_ssm_parameters_by_path.config.names,
    data.aws_ssm_parameters_by_path.config.values,
  ))

  cfg = { for path, value in local.config : element(split("/", path), length(split("/", path)) - 1) => value }
}

# The agent itself. Direct code deployment: AgentCore pulls a zip from S3 and
# runs it on managed arm64 compute; there is no container image to build.
#
# Every change to the artifact below creates a NEW Runtime version. The
# DEFAULT endpoint (created automatically by the service) always follows the
# latest version, which is what the smoke test and evaluations invoke.
resource "aws_bedrockagentcore_agent_runtime" "agent" {
  # Letters, digits, underscores only.
  agent_runtime_name = "fernbrook_ops_agent"
  description        = "Fernbrook Ops Agent (Strands) on AgentCore Runtime."
  role_arn           = local.cfg["runtime_role_arn"]

  agent_runtime_artifact {
    code_configuration {
      runtime = var.python_runtime

      # opentelemetry-instrument wraps the process so Strands + ADOT ship
      # traces to CloudWatch (GenAI Observability) with no agent code change.
      entry_point = ["opentelemetry-instrument", "app.py"]

      code {
        s3 {
          bucket     = local.cfg["code_bucket"]
          prefix     = var.code_key
          version_id = var.code_version_id
        }
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  # Configuration only. No secrets: the agent authenticates to AWS with its
  # execution role, and customers with Cognito tokens.
  environment_variables = {
    AGENTCORE_MEMORY_ID         = local.cfg["memory_id"]
    FERNBROOK_GATEWAY_URL       = local.cfg["gateway_url"]
    FERNBROOK_GUARDRAIL_ID      = local.cfg["guardrail_id"]
    FERNBROOK_GUARDRAIL_VERSION = local.cfg["guardrail_version"]
    FERNBROOK_USER_POOL_ID      = local.cfg["user_pool_id"]
    FERNBROOK_APP_CLIENT_ID     = local.cfg["app_client_id"]
    FERNBROOK_MODEL_ID          = local.cfg["model_id"]
    OTEL_RESOURCE_ATTRIBUTES    = "service.name=fernbrook-ops-agent"
  }
}

# Published for the smoke test, evaluations and anything that needs to invoke
# the agent. Managed here so it is removed with the Runtime.
resource "aws_ssm_parameter" "runtime_arn" {
  name        = "/fernbrook/release/runtime_arn"
  description = "ARN of the deployed AgentCore Runtime."
  type        = "String"
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}
