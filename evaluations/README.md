# Fernbrook Ops Agent evaluation dataset

Ten scenarios in `dataset.json`, covering normal requests, ambiguous requests, unsupported requests, an unauthorized cross-customer lookup, missing information, a prompt injection attempt, both sides of the refund threshold, and both a covered and an uncovered retrieval question. Design Note 26 explains the reasoning behind each one and what "good" looks like for each.

## Running

```bash
export FERNBROOK_AGENT_RUNTIME_ARN=<from `agentcore status`>
export FERNBROOK_AGENT_LOG_GROUP=<from the CloudWatch console; see Design Note 24>
export FERNBROOK_EVAL_CUSTOMER_TOKEN=$(python3 identity/get_test_token.py)

python3 evaluations/run_evaluations.py
```

Each run saves a timestamped summary to `evaluations/results/`. Before making a change, run this once and keep the resulting file as your baseline. After the change, run it again and compare:

```bash
python3 evaluations/compare_results.py \
  evaluations/results/results-<before>.json \
  evaluations/results/results-<after>.json
```

Exits nonzero if anything regressed, safe to use as a gate in a CI step via the workflows in .github/workflows.

## Scope

All eleven scenario categories from the original evaluation design are now represented: normal, ambiguous, unsupported, unauthorized, missing information, prompt injection, tool correctness, retrieval (grounded and not-covered), invalid tool arguments, conflicting information, tool failure, retrieval failure, and stale information, fifteen scenarios in total. Three of them, tool failure, retrieval failure, and stale information, aren't runnable as a normal conversational turn; each carries a `test_procedure` field describing the manual setup required (temporarily breaking a dependency, or editing and re-ingesting a policy document) since the on-demand dataset runner alone can't induce those conditions.

One of those three is worth flagging directly: `retrieval-failure-knowledge-base-unreachable` is expected to **fail** as of this repository's current state. Design Note 33's graceful-degradation wrapping now covers `get_order_status`, `get_wholesale_account_status`, and `Retrieve` (the last one added in a final repository completion pass), so as of that pass this scenario should pass too. If you're working from an earlier snapshot of this repository, before that pass, treat a failure here as expected and consistent with the honest gap this dataset was designed to catch, not a bug in the test.
