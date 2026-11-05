// Default-deny is Cedar's own posture: nothing is permitted unless an
// explicit permit policy matches. This file is that explicit allow
// list, and nothing more. If a new tool is ever registered on
// FernbrookGateway without a matching permit policy added here, Policy
// denies it automatically, regardless of what the agent's own
// reasoning concludes it should be allowed to do.
//
// As of Design Note 23, get_order_status and getWholesaleAccountStatus are
// still called through Gateway, still authorized by this policy at the
// tool level, exactly as before. What changed is upstream, in
// agent.py: the model no longer calls these Gateway tools directly:
// local wrapper functions call them via call_tool_sync and check the
// result against the verified actor_id before anything reaches the
// model. This policy still answers "is this tool callable at all."
// The wrapper answers the question Cedar cannot: "does this specific
// record belong to this specific caller."
//
// process_refund (Design Note 17) still sidesteps Gateway entirely.

permit(
  principal is AgentCore::IamEntity,
  action in [
    AgentCore::Action::"OrderLookup___get_order_status",
    AgentCore::Action::"WholesaleAccountLookup___getWholesaleAccountStatus",
    AgentCore::Action::"PolicyKnowledge___Retrieve"
  ],
  resource == AgentCore::Gateway::"REPLACE_WITH_YOUR_FERNBROOK_GATEWAY_ARN"
) when {
  principal.id like "*assumed-role/fernbrook-agent-runtime*"
};
