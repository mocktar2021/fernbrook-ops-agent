#!/usr/bin/env python3
"""
Talk to the deployed Fernbrook Ops Agent from your terminal, as the synthetic
demo customer (CUST-4471, who owns order FB-10293).

What this does, step by step (this is the same path a real app would take):

  1. Reads the Runtime ARN from SSM (/fernbrook/release/runtime_arn).
  2. Signs the demo customer in to Cognito and gets an ID token. The password
     is read from Secrets Manager and is never printed.
  3. Sends each line you type to the Runtime together with that token. The
     agent verifies the token itself, so the model never decides who you are.

One session ID is reused for the whole conversation, so AgentCore Memory can
carry context from one turn to the next.

Needs: boto3, and AWS credentials (for example from `aws login`) allowed to
read SSM and Secrets Manager, call Cognito and invoke the Runtime.

    python scripts/chat.py
    python scripts/chat.py "What is the status of order FB-10293?"   # one question, then exit
"""

import json
import sys
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identity.get_test_token import REGION, get_id_token  # noqa: E402

RUNTIME_ARN_PARAMETER = "/fernbrook/release/runtime_arn"


def extract_text(body) -> str:
    """Best-effort: pull the assistant's text out of the Runtime response."""
    result = body.get("result", body) if isinstance(body, dict) else body
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        parts = [block["text"] for block in result["content"] if isinstance(block, dict) and "text" in block]
        if parts:
            return "\n".join(parts)
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2)


def main() -> int:
    arn = boto3.client("ssm", region_name=REGION).get_parameter(Name=RUNTIME_ARN_PARAMETER)["Parameter"]["Value"]
    client = boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(read_timeout=180, retries={"max_attempts": 1}),
    )
    token = get_id_token()
    session_id = f"chat-{uuid.uuid4()}"  # Runtime session IDs must be at least 33 characters

    def ask(prompt: str) -> None:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=session_id,
            payload=json.dumps({"prompt": prompt, "customer_token": token, "session_id": session_id}),
            qualifier="DEFAULT",
        )
        print(extract_text(json.loads(response["response"].read())))

    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
        return 0

    print("Signed in as the synthetic demo customer. Type a question, or 'quit'.")
    print("Try: What is the status of order FB-10293?   or   Show me order FB-10318.\n")
    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if prompt.lower() in {"quit", "exit", ""}:
            return 0
        ask(prompt)
        print()


if __name__ == "__main__":
    sys.exit(main())
