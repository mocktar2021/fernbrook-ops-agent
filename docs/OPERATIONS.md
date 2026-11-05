# Operating the Fernbrook Ops Agent

Design Note 38 covers the reasoning. This file is quick reference for what to actually do once the pilot is live.

## If `LookupOwnershipDenied` is nonzero

Treat as a security event, not routine noise (Design Note 25). Pull the specific session from CloudWatch Traces View (Design Note 24), confirm whether it was a genuine attempt to access another customer's data or an honest mistake (a mistyped order ID a customer then corrected), and escalate to a human review if it looks deliberate or repeated from the same identity.

## If `RefundEscalated` spikes

Not automatically a problem (Design Note 25); check `scripts/review_pending_refunds.py list` first, then correlate against anything else happening, a promotion, a product issue, before assuming something is wrong.

## If a cost alert fires

Run `evaluations/estimate_cost.py` with current real rates against recent traffic patterns (Design Note 30) to find which driver actually moved, rather than guessing. Check agent step count trends first; a spike there usually means something is causing more tool calls per request than expected.

## Rolling back a bad deployment

Application/agent code: redeploy the previous git commit through the same pipeline (Design Note 29); nothing about the deployment mechanism changes for a rollback versus a forward deploy.

Infrastructure managed by Terraform: `terraform plan` against the previous commit's configuration before applying, exactly as cautious as any other apply (Design Note 28).

AgentCore-native resources (Runtime, Gateway, Policy): check the current `agentcore` CLI's own rollback or version history support before assuming a redeploy alone reverts a bad change; this project has not verified exactly how much history the CLI retains (Design Note 29).

## Before merging a change to Cedar policy, `refund_logic.py`, or identity verification

These files deserve a human reviewer every time, regardless of CI status (Design Note 29, Design Note 37). No technical enforcement for this exists yet in this repository; until it does, treat this as a manual, non-negotiable step in your own review process.

## Before updating the model, the framework, or the prompt

Run the full evaluation suite before and after, save both results, and diff them with `evaluations/compare_results.py` (Design Note 27). Do not ship a model or prompt change on a green CI run alone; Design Note 29 was explicit that a green pipeline does not prove production safety.

## Before re-ingesting the knowledge base

Confirm the source documents were reviewed by someone who understands what's changed; this project has no automated content review process for `knowledge/policies/` (a gap named in Design Note 37), which makes a human check the only check that currently exists.
