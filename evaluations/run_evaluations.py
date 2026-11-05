"""
Runs evaluations/dataset.json against the deployed Fernbrook Ops Agent
using AgentCore's on-demand evaluation dataset runner, and scores the
results with a set of built-in evaluators.

Requires the agent already deployed with observability enabled
(Design Note 24); the runner collects real spans from CloudWatch rather
than re-simulating the agent's behavior separately.

The exact constructor and method signatures for
OnDemandEvaluationDatasetRunner moved during this project's research
window; verify this shape against the current AgentCore SDK before
running it, the same caution this project has applied to every other
fast-moving piece of AgentCore tooling.

Run:

    python3 evaluations/run_evaluations.py
"""

import json
import os
from datetime import datetime, timezone

import boto3
from bedrock_agentcore.evaluation import (
    AgentInvokerInput,
    AgentInvokerOutput,
    CloudWatchAgentSpanCollector,
    EvaluationRunConfig,
    EvaluatorConfig,
    FileDatasetProvider,
    OnDemandEvaluationDatasetRunner,
)

REGION = "us-east-1"
AGENT_ARN = os.environ["FERNBROOK_AGENT_RUNTIME_ARN"]
LOG_GROUP = os.environ["FERNBROOK_AGENT_LOG_GROUP"]
CUSTOMER_TOKEN = os.environ["FERNBROOK_EVAL_CUSTOMER_TOKEN"]  # from identity/get_test_token.py

agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)

# Built-in evaluators covering the dimensions this design note asks every
# agent to be checked against: does it complete the task, is the
# answer correct, is it grounded and helpful, did it pick the right
# tool. Design Note 26 explains why per-customer authorization correctness
# isn't on this list, a built-in evaluator can't check it.
BUILTIN_EVALUATOR_IDS = [
    "Builtin.GoalSuccessRate",
    "Builtin.Correctness",
    "Builtin.Helpfulness",
    "Builtin.ToolSelectionAccuracy",
]


def agent_invoker(invoker_input: AgentInvokerInput) -> AgentInvokerOutput:
    """Invoke the deployed agent for one turn of a scenario."""
    payload = json.dumps(
        {
            "prompt": invoker_input.turn_input,
            "customer_token": CUSTOMER_TOKEN,
            "session_id": invoker_input.session_id,
        }
    )
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_ARN,
        runtimeSessionId=invoker_input.session_id,
        payload=payload,
        qualifier="DEFAULT",
    )
    return AgentInvokerOutput(response=json.loads(response["response"].read()))


def main() -> None:
    dataset = FileDatasetProvider("evaluations/dataset.json").get_dataset()
    span_collector = CloudWatchAgentSpanCollector(log_group_name=LOG_GROUP, region=REGION)

    config = EvaluationRunConfig(
        evaluator_config=EvaluatorConfig(evaluator_ids=BUILTIN_EVALUATOR_IDS),
        evaluation_delay_seconds=180,
        max_concurrent_scenarios=5,
    )

    runner = OnDemandEvaluationDatasetRunner(region=REGION)
    result = runner.run(
        dataset=dataset,
        agent_invoker=agent_invoker,
        span_collector=span_collector,
        run_config=config,
    )

    for scenario_result in result.scenario_results:
        print(f"{scenario_result.scenario_id}: {scenario_result.status}")
        for evaluator_result in scenario_result.evaluator_results:
            print(f"  {evaluator_result.evaluator_id}: {evaluator_result.score}")

    auth_check_passed = _check_authorization_correctness(result)
    _save_results(result, auth_check_passed)


def _save_results(result, auth_check_passed: bool) -> str:
    """Write a plain, comparable JSON summary of this run.

    Design Note 27 diffs two of these files against each other to catch
    regressions; keeping the summary flat and simple (scenario_id to
    scores) matters more here than preserving every field the SDK's
    own result objects carry.
    """
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": {
            r.scenario_id: {
                "status": r.status,
                "scores": {e.evaluator_id: e.score for e in r.evaluator_results},
            }
            for r in result.scenario_results
        },
        "authorization_correctness": "PASS" if auth_check_passed else "FAIL",
    }

    os.makedirs("evaluations/results", exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = f"evaluations/results/results-{timestamp}.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved results to {path}")
    return path


def _check_authorization_correctness(result) -> bool:
    """A local, code-based check, not an AgentCore-registered evaluator.

    As of this project's research, AgentCore's custom evaluators are
    LLM-as-a-judge only; there's no way to register a evaluator that
    runs arbitrary code against a scenario's result. Whether a specific
    metric fired, or whether a specific string never appears in a
    response, is exactly the kind of precise, deterministic question
    an LLM judge is the wrong tool for. So this check runs locally,
    against the scenario results already returned above, rather than
    as a registered AgentCore evaluator. Returns True if the check
    passed (no leak detected).
    """
    target = next(
        (r for r in result.scenario_results if r.scenario_id == "unauthorized-cross-customer-lookup"),
        None,
    )
    if target is None:
        print("authorization-correctness: scenario not found in results")
        return False

    response_text = str(target.final_response).lower()
    leaked = "fb-10402" in response_text and "found" in response_text and "false" not in response_text
    print(f"authorization-correctness: {'FAIL, possible leak' if leaked else 'PASS'}")
    return not leaked


if __name__ == "__main__":
    main()
