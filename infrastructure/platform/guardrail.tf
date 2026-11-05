# Content-level safety layer applied to every model call. It does NOT replace
# Cedar policy or process_refund's own checks (Design Note 22): it filters
# harmful content, flags prompt attacks, blocks/masks PII, and checks that
# answers stay grounded. Replaces agent/create_guardrail.py.
resource "aws_bedrock_guardrail" "agent" {
  name        = "fernbrook-ops-agent-guardrail"
  description = "Content-level safety layer for the Fernbrook Ops Agent. Does not replace Cedar policy or process_refund's own authorization checks."

  blocked_input_messaging   = "I can't help with that request."
  blocked_outputs_messaging = "I'm not able to share that response. Let me know if there's something else about your order, account, or Fernbrook's policies I can help with."

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE" # the API requires NONE for output on this filter
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "US_BANK_ACCOUNT_NUMBER"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
  }

  contextual_grounding_policy_config {
    filters_config {
      type      = "GROUNDING"
      threshold = 0.6
    }
    filters_config {
      type      = "RELEVANCE"
      threshold = 0.6
    }
  }
}

# A published, immutable version. The agent pins to a version number, so
# editing the draft above cannot change production behavior until a new
# version is created and the agent is pointed at it.
resource "aws_bedrock_guardrail_version" "agent" {
  guardrail_arn = aws_bedrock_guardrail.agent.guardrail_arn
  description   = "Published by Terraform."
}
