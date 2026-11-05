#!/usr/bin/env python3
"""
Post-deploy smoke test for the deployed Runtime. Exit code 0 means "safe to
call this release good"; nonzero makes the app pipeline roll back.

It is deliberately small, deterministic, and about the properties that must
never regress, not about answer quality (the evaluation suite does that):

  1. Authentication: a bad customer token is rejected before any model runs.
  2. Happy path: the demo customer can read THEIR order (FB-10293).
  3. Authorization: the same customer asks for someone else's order
     (FB-10318, owned by CUST-5502) and nothing from that record leaks.
     The ownership check runs in code, not in the model's judgment.

Usage (needs AWS credentials able to read SSM, Secrets Manager, Cognito and
invoke the Runtime; the app-deploy pipeline role has these):

    python3 scripts/smoke_test.py
"""

import json
import sys
import time
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identity.get_test_token import REGION, get_id_token  # noqa: E402

RUNTIME_ARN_PARAMETER = "/fernbrook/release/runtime_arn"

# A new Runtime version can take a little while to start serving. Retry the
# FIRST call generously; once it works, later calls should too.
FIRST_CALL_ATTEMPTS = 8
FIRST_CALL_WAIT_SECONDS = 20


def runtime_arn() -> str:
    ssm = boto3.client("ssm", region_name=REGION)
    return ssm.get_parameter(Name=RUNTIME_ARN_PARAMETER)["Parameter"]["Value"]


def invoke(client, arn: str, token: str, prompt: str) -> str:
    session_id = f"smoke-{uuid.uuid4()}"  # Runtime needs a session ID of 33+ characters
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt, "customer_token": token, "session_id": session_id}),
        qualifier="DEFAULT",
    )
    body = json.loads(response["response"].read())
    return json.dumps(body)  # flatten whatever shape "result" has into searchable text


def invoke_with_retry(client, arn: str, token: str, prompt: str) -> str:
    for attempt in range(1, FIRST_CALL_ATTEMPTS + 1):
        try:
            return invoke(client, arn, token, prompt)
        except (ClientError, json.JSONDecodeError) as error:
            print(f"  attempt {attempt}/{FIRST_CALL_ATTEMPTS} failed: {type(error).__name__}: {error}")
            if attempt == FIRST_CALL_ATTEMPTS:
                raise
            time.sleep(FIRST_CALL_WAIT_SECONDS)
    raise AssertionError("unreachable")


def main() -> int:
    arn = runtime_arn()
    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(read_timeout=180, retries={"max_attempts": 1}),
    )
    token = get_id_token()
    failures = []

    print("1/3 rejects an invalid customer token")
    text = invoke_with_retry(client, arn, "not-a-real-token", "What is the status of order FB-10293?").lower()
    if "could not verify customer identity" not in text:
        failures.append(f"invalid token was not rejected. Reply: {text[:300]}")

    print("2/3 demo customer can read their own order")
    text = invoke_with_retry(client, arn, token, "What is the status of order FB-10293?").lower()
    if "shipped" not in text:
        failures.append(f"own order not returned. Reply: {text[:300]}")

    print("3/3 demo customer cannot read another customer's order")
    text = invoke_with_retry(client, arn, token, "What is the status of order FB-10318 and what items are in it?").lower()
    leaked = [marker for marker in ("ridgeline", "2026-09-05") if marker in text]
    if leaked:
        failures.append(f"another customer's order leaked markers {leaked}. Reply: {text[:300]}")

    if failures:
        print("\nSMOKE TEST FAILED")
        for failure in failures:
            print(" -", failure)
        return 1

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
