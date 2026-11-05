> **Note:** the setup steps below describe the original manual path and are kept to explain the design. In this repository the telemetry packages are already in `requirements-runtime.txt` and the runtime entry point enables them. Enabling CloudWatch Transaction Search is still a one-time manual step per account. Follow `docs/GETTING-STARTED.md` to deploy.

# Enabling AgentCore Observability

Design Note 24 covers the reasoning. This file covers the one-time setup.

## 1. Enable CloudWatch Transaction Search (once per account, per region)

This is a one-time account-level setting, not something `agentcore deploy` handles for you.

1. Open the CloudWatch console.
2. In the navigation pane, expand **Application Signals (APM)** and choose **Transaction search**.
3. Choose **Enable Transaction Search**.
4. Select the checkbox to **ingest spans as structured logs**.
5. Choose **Save**.

An API path exists too (`PutResourcePolicy` against X-Ray, granting CloudWatch permission to ingest spans), worth using if you're scripting a repeatable account setup; the console path above is simpler for a one-time action on a single account. Spans can take about ten minutes to become searchable after enabling this.

## 2. Dependencies

Already reflected in `requirements.txt`: `strands-agents[otel]` (Strands' own OpenTelemetry instrumentation) and `aws-opentelemetry-distro` (ADOT, which actually ships the spans to CloudWatch). Both are required together; Strands' instrumentation alone doesn't get data to CloudWatch, and ADOT alone has nothing Strands-specific to ship.

## 3. No agent code changes required

Because the Fernbrook Ops Agent already runs on AgentCore Runtime (Design Note 7, via `BedrockAgentCoreApp`), Runtime handles session tracking automatically through its own session ID, the same `session_id` this project has threaded through every payload since Design Note 9. Redeploy after updating `requirements.txt`, and traces begin flowing with no changes to `agent.py` or `app.py` at all.

```bash
agentcore deploy
```

## 4. Viewing traces

In the CloudWatch console, open **GenAI Observability** under Application Signals. Three views matter:

- **Agents View**: every deployed agent, the Fernbrook Ops Agent among them, with runtime-level metrics.
- **Sessions View**: every session, matching this project's own `session_id` values, so a specific customer conversation can be found and inspected directly.
- **Traces View**: the individual spans within a session, one per model call, per tool call, per Gateway round trip, each with its own latency and status.

## 5. Correlating traces with this project's own identifiers

By default, a trace is findable by AgentCore Runtime's own session ID. To make a trace additionally searchable by something specific to this project's domain, a request ID your own logging already generates, for instance, set a resource attribute before the agent process starts:

```bash
export OTEL_RESOURCE_ATTRIBUTES="service.name=fernbrook-ops-agent"
```

Extend this with additional key-value pairs as your own correlation needs grow; anything set here becomes a searchable attribute on every span the process emits, not just the session ID Runtime already tracks automatically.

## 6. Custom operational metrics

AgentCore's built-in tracing (Sections 1-5 above) is excellent for investigating one specific session after the fact. It doesn't, on its own, give you a running count of business and security signals worth watching continuously. `agent/emit_metric.py` emits two of those, in CloudWatch's Embedded Metric Format, no new IAM permission required since it's ordinary log output:

- `RefundEscalated`, incremented every time `process_refund` queues a refund for human review (`agent/refund_logic.py`).
- `LookupOwnershipDenied`, incremented every time `get_order_status` or `get_wholesale_account_status` denies a request because the record belongs to someone other than the verified caller (`agent/agent.py`), tagged with which tool triggered it. This one specifically only counts genuine ownership mismatches, not simple not-found cases, so it stays a meaningful security signal instead of noise from ordinary typos.

Build a CloudWatch dashboard from these, alongside AgentCore's own built-in metrics (request volume and latency, visible directly in the Agents View from Section 4), through the CloudWatch console's dashboard editor: add a metric widget, select the `FernbrookOpsAgent` namespace, and choose `RefundEscalated` or `LookupOwnershipDenied`. Design Note 25 explains why these two signals specifically, and what "avoid decorative dashboards" means in practice.
