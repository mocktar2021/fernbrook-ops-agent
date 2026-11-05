"""
Compares two saved evaluation result files (see run_evaluations.py) and
flags regressions: any scenario whose status changed for the worse, any
evaluator score that dropped, or the authorization-correctness check
flipping from PASS to FAIL. Exits with a nonzero status if it finds
one, so this is safe to wire into a CI step, even though this project
doesn't gate on anything outside .github/workflows.

Run:

    python3 evaluations/compare_results.py \
        evaluations/results/results-<baseline>.json \
        evaluations/results/results-<new>.json
"""

import json
import sys

SCORE_REGRESSION_THRESHOLD = 0.05  # ignore noise smaller than this


def compare(baseline_path: str, new_path: str) -> bool:
    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(new_path) as f:
        new = json.load(f)

    regressions = []

    for scenario_id, baseline_scenario in baseline["scenarios"].items():
        new_scenario = new["scenarios"].get(scenario_id)
        if new_scenario is None:
            regressions.append(f"{scenario_id}: missing from new results entirely")
            continue

        if baseline_scenario["status"] == "COMPLETED" and new_scenario["status"] != "COMPLETED":
            regressions.append(
                f"{scenario_id}: status changed {baseline_scenario['status']} -> {new_scenario['status']}"
            )

        for evaluator_id, old_score in baseline_scenario["scores"].items():
            new_score = new_scenario["scores"].get(evaluator_id)
            if new_score is None:
                continue
            if (old_score - new_score) > SCORE_REGRESSION_THRESHOLD:
                regressions.append(
                    f"{scenario_id} / {evaluator_id}: score dropped {old_score:.2f} -> {new_score:.2f}"
                )

    if baseline["authorization_correctness"] == "PASS" and new["authorization_correctness"] != "PASS":
        regressions.append("authorization-correctness: PASS -> FAIL (see this immediately, do not ship)")

    if regressions:
        print(f"Found {len(regressions)} regression(s) vs {baseline_path}:")
        for r in regressions:
            print(f"  - {r}")
        return False

    print(f"No regressions vs {baseline_path}.")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 evaluations/compare_results.py <baseline.json> <new.json>")
        sys.exit(2)

    passed = compare(sys.argv[1], sys.argv[2])
    sys.exit(0 if passed else 1)
