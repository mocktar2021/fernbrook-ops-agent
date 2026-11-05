"""
One-time setup: create the Bedrock Guardrail this agent applies to
every model call. Run once:

    python3 agent/create_guardrail.py

Prints the guardrail ID and version; export both before running or
deploying the agent.

This guardrail is a second, independent layer, not a replacement for
anything the earlier design notes already built. process_refund's threshold and
ownership checks (Design Note 17) and Cedar's default-deny tool policy
(Design Note 16) still do the actual authorization work; nothing here
changes what the agent is allowed to do. What this adds is content-level
filtering the agent code alone never attempted: blocking harmful
categories, catching prompt-attack patterns, masking PII a customer
might paste unnecessarily, and checking that knowledge-base-grounded
answers actually stay grounded in what was retrieved.
"""

import boto3

REGION = "us-east-1"


def main() -> None:
    client = boto3.client("bedrock", region_name=REGION)

    response = client.create_guardrail(
        name="fernbrook-ops-agent-guardrail",
        description=(
            "Content-level safety layer for the Fernbrook Ops Agent. "
            "Does not replace Cedar policy or process_refund's own "
            "authorization checks; see Design Note 22."
        ),
        contentPolicyConfig={
            "filtersConfig": [
                {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "INSULTS", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
                {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "VIOLENCE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "MISCONDUCT", "inputStrength": "HIGH", "outputStrength": "HIGH"},
                {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
            ]
        },
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": [
                {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "BLOCK"},
                {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "BLOCK"},
                {"type": "US_BANK_ACCOUNT_NUMBER", "action": "BLOCK"},
                {"type": "EMAIL", "action": "ANONYMIZE"},
                {"type": "PHONE", "action": "ANONYMIZE"},
            ]
        },
        contextualGroundingPolicyConfig={
            "filtersConfig": [
                {"type": "GROUNDING", "threshold": 0.6},
                {"type": "RELEVANCE", "threshold": 0.6},
            ]
        },
        blockedInputMessaging=(
            "I can't help with that request."
        ),
        blockedOutputsMessaging=(
            "I'm not able to share that response. Let me know if there's "
            "something else about your order, account, or Fernbrook's "
            "policies I can help with."
        ),
    )

    guardrail_id = response["guardrailId"]

    version_response = client.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="Initial published version.",
    )
    guardrail_version = version_response["version"]

    print(f"Created guardrail: {guardrail_id}")
    print(f"Published version: {guardrail_version}")
    print()
    print("Export before running or deploying the agent:")
    print(f"  export FERNBROOK_GUARDRAIL_ID={guardrail_id}")
    print(f"  export FERNBROOK_GUARDRAIL_VERSION={guardrail_version}")


if __name__ == "__main__":
    main()
