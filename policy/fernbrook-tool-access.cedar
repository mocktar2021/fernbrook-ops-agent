// Default-deny is Cedar's own posture: nothing is permitted unless an
// explicit permit policy matches. This file is that explicit allow
// list, and nothing more. If a new tool is ever registered on the
// Gateway without a matching permit statement added here, Policy denies
// it automatically, regardless of what the agent's own reasoning
// concludes it should be allowed to do.
//
// Only name tools whose Gateway targets are deployed. AgentCore Policy
// checks every action below against the schema of the gateways attached
// to the policy engine, in every validation mode, and rejects the policy
// (CREATE_FAILED) if an action does not exist there. Milestone 2 adds
// WholesaleAccountLookup___getWholesaleAccountStatus and
// PolicyKnowledge___Retrieve to this list, in the same change that adds
// their Gateway targets.
//
// get_order_status is called through Gateway and authorized here at the
// tool level. The agent's local wrapper functions check each result
// against the verified actor_id before anything reaches the model. This
// policy answers "is this tool callable at all." The wrapper answers the
// question Cedar cannot: "does this specific record belong to this
// specific caller."
//
// process_refund still sidesteps Gateway entirely.

permit(
  principal is AgentCore::IamEntity,
  action in [
    AgentCore::Action::"OrderLookup___get_order_status"
  ],
  resource == AgentCore::Gateway::"REPLACE_WITH_YOUR_FERNBROOK_GATEWAY_ARN"
) when {
  principal.id like "*assumed-role/fernbrook-agent-runtime*"
};
