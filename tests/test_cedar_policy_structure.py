"""
A lightweight structural check on policy/fernbrook-tool-access.cedar,
the "policy test" category Design Note 26 named as a testing layer distinct
from agent behavior evaluation. This is not a substitute for the Cedar
CLI's own validator or a real `cedar validate` / `cedar authorize` run
against a schema; it's a fast, dependency-free guard against the two
specific mistakes Design Note 16 and Design Note 29 warned about by name:
an accidentally over-broad `action` clause, and a new Gateway tool
shipping with no matching permit statement at all.

Run:

    python3 -m pytest tests/test_cedar_policy_structure.py -v
"""

from pathlib import Path

POLICY_PATH = (
    Path(__file__).parent.parent / "policy" / "fernbrook-tool-access.cedar"
)

# The exact set of Gateway actions this project's agent.py is written to
# call, as of the final completion pass that wrapped
# Retrieve alongside the two lookup tools. If this list and the Cedar
# file's permitted actions ever drift apart, either a real tool call
# will be silently denied, or a tool was added to Gateway without a
# matching permit statement, exactly Design Note 16's default-deny warning.
#
# Milestone 2 adds WholesaleAccountLookup___getWholesaleAccountStatus and
# PolicyKnowledge___Retrieve here and to the Cedar file, together with their
# Gateway targets. AgentCore Policy rejects a policy that names an action no
# attached gateway defines, so they must not be listed earlier.
EXPECTED_ACTIONS = {
    'AgentCore::Action::"OrderLookup___get_order_status"',
}


def _read_policy() -> str:
    return POLICY_PATH.read_text()


def test_every_permitted_action_has_a_gateway_target_in_terraform():
    """AgentCore Policy checks each action against the schema of the gateways
    attached to the policy engine in every validation mode, and rejects the
    policy (CREATE_FAILED) if an action has no matching target. Catch that
    here instead of in the middle of an apply.
    """
    import re

    active = "\n".join(
        line for line in _read_policy().splitlines()
        if not line.lstrip().startswith("//")
    )
    actions = re.findall(r'AgentCore::Action::"([^"]+)"', active)
    assert actions, "No actions found in the Cedar policy."

    platform_dir = POLICY_PATH.parent.parent / "infrastructure" / "platform"
    terraform = "\n".join(p.read_text() for p in platform_dir.glob("*.tf"))
    targets = set(
        re.findall(
            r'resource "aws_bedrockagentcore_gateway_target" "[^"]+" \{\s*name\s*=\s*"([^"]+)"',
            terraform,
        )
    )
    assert targets, "No Gateway targets found in the platform Terraform."

    missing = [a for a in actions if a.split("___")[0] not in targets]
    assert not missing, (
        f"Cedar permits action(s) with no Gateway target in Terraform: {missing}. "
        f"Targets defined: {sorted(targets)}"
    )


def test_policy_file_exists():
    assert POLICY_PATH.exists(), "Cedar policy file is missing entirely."


def test_expected_actions_are_all_present():
    text = _read_policy()
    missing = [a for a in EXPECTED_ACTIONS if a not in text]
    assert not missing, f"Cedar policy is missing expected action(s): {missing}"


def test_no_unscoped_action_clause():
    """Guard against exactly the mistake Design Note 16 named: an `action`
    clause with no `in [...]` list, which would permit every current
    and future Gateway tool rather than an explicit, reviewed list.
    """
    text = _read_policy()
    # A bare `action,` or `action ==` with no `in [` anywhere nearby
    # would indicate the allow-list pattern was abandoned.
    assert "action in [" in text, (
        "Expected an explicit `action in [...]` allow-list; found "
        "something else, which may be an over-broad grant."
    )


def test_policy_is_a_permit_not_a_forbid_only_file():
    """This project's policy is an explicit allow-list built on Cedar's
    own default-deny behavior; it should contain a permit statement,
    not rely solely on forbid statements layered over an assumed-open
    default that Cedar doesn't actually have.
    """
    text = _read_policy()
    assert "permit(" in text


def test_gateway_arn_placeholder_is_visible_not_silently_filled():
    """A real deployment must replace this placeholder with the actual
    Gateway ARN. This test doesn't fail a real deployment (that
    placeholder is expected to be replaced there); it exists so a fresh
    clone of this repository fails loudly if someone runs it against
    this file unmodified, rather than silently matching nothing.
    """
    text = _read_policy()
    assert (
        "REPLACE_WITH_YOUR_FERNBROOK_GATEWAY_ARN" in text
        or "arn:aws:bedrock-agentcore:" in text
    ), "Expected either the documented placeholder or a real Gateway ARN."
