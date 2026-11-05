"""
Lambda handler for Fernbrook's wholesale account lookup, exposed
through a Lambda Function URL and described to AgentCore Gateway as an
OpenAPI target (see openapi.json). Unlike the order-lookup Lambda in
Design Note 12, Gateway reaches this one over plain HTTPS, not a direct
Lambda invocation, and authenticates to it with a shared API key rather
than an IAM execution role.

The API key itself lives in AWS Secrets Manager (Design Note 22), not in a
Lambda environment variable. It's fetched once per warm execution
environment, at module load time, and reused across invocations that
land on the same warm container, rather than fetched fresh on every
request.

Account data below is a small in-memory dictionary, not a database.
For six synthetic accounts that's an honest simplification, not a
shortcut worth hiding; a real implementation would query Fernbrook's
actual partner database the way Design Note 12's order lookup queries
DynamoDB.
"""

import json

import boto3

REGION = "us-east-1"
SECRET_NAME = "fernbrook/wholesale-lookup-api-key"

_secrets_client = boto3.client("secretsmanager", region_name=REGION)
API_KEY = _secrets_client.get_secret_value(SecretId=SECRET_NAME)["SecretString"]

WHOLESALE_ACCOUNTS = {
    "CUST-WHS-118": {
        "business_name": "Trailhead Outfitters Co-op",
        "tier": "Preferred",
        "status": "active",
    },
    "CUST-WHS-204": {
        "business_name": "Cascade Basin Supply",
        "tier": "Standard",
        "status": "active",
    },
    "CUST-WHS-267": {
        "business_name": "Blue Ridge Trail Goods",
        "tier": "Standard",
        "status": "pending_approval",
    },
    "CUST-WHS-311": {
        "business_name": "Northfork Camp & Trail",
        "tier": "Preferred",
        "status": "on_hold",
    },
}


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if headers.get("x-api-key") != API_KEY:
        return _response(401, {"error": "Invalid or missing API key."})

    query = event.get("queryStringParameters") or {}
    account_id = (query.get("account_id") or "").strip()

    if not account_id:
        return _response(400, {"error": "account_id is required."})

    account = WHOLESALE_ACCOUNTS.get(account_id)
    if account is None:
        return _response(
            404, {"found": False, "error": f"No wholesale account found with ID {account_id}."}
        )

    return _response(200, {"found": True, "account_id": account_id, **account})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
