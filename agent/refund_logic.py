"""
Core refund logic for the Fernbrook Ops Agent's process_refund tool.
Deliberately separated from the Strands @tool wrapper in agent.py so
this function can be tested directly, with no framework involved, and
so the ownership check, threshold decision, and idempotency check are
all visible as plain Python, not buried inside tool-calling machinery.
"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from emit_metric import emit_metric

REGION = "us-east-1"
ORDERS_TABLE = "fernbrook-orders"
APPROVALS_TABLE = "fernbrook-refund-approvals"
IDEMPOTENCY_TABLE = "fernbrook-refund-idempotency"
AUTO_APPROVAL_THRESHOLD_USD = 100.00

# Design Note 32: how wide a window counts two calls with identical
# arguments as "the same request retried" rather than "two separate,
# genuinely intended requests." Wide enough to absorb a real network
# retry (seconds, not minutes); narrow enough that a customer asking
# for the same refund again an hour later, because the first one
# genuinely never went through, isn't silently swallowed.
IDEMPOTENCY_WINDOW_SECONDS = 60
IDEMPOTENCY_RECORD_TTL_SECONDS = 24 * 60 * 60

dynamodb = boto3.resource("dynamodb", region_name=REGION)
orders_table = dynamodb.Table(ORDERS_TABLE)
approvals_table = dynamodb.Table(APPROVALS_TABLE)
idempotency_table = dynamodb.Table(IDEMPOTENCY_TABLE)


def _idempotency_key(actor_id: str, order_id: str, amount: float, reason: str) -> str:
    """A content-and-time-window hash, not a client-generated token.

    A textbook idempotency key is generated once by the calling client
    and reused across every retry of that same logical request. This
    project's caller is a model deciding, turn by turn, whether to call
    a tool, with no natural mechanism to generate and consistently
    replay such a token across a retry. This hash is the honest
    alternative: identical arguments, within a short time window, are
    treated as the same request. See Design Note 32 for the tradeoff this
    accepts.
    """
    time_bucket = int(time.time() // IDEMPOTENCY_WINDOW_SECONDS)
    raw = f"{actor_id}:{order_id}:{amount}:{reason}:{time_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


def request_refund(actor_id: str, order_id: str, amount: float, reason: str) -> dict:
    """Process or queue a refund request, exactly once per idempotency
    window for a given actor, order, amount, and reason.

    actor_id is the verified customer identity established by
    identity/verify_customer_token.py and passed in by run_agent()'s
    own code. This function never receives, and would not trust, a
    customer identity supplied by the model itself; the tool wrapper in
    agent.py does not expose actor_id as a parameter the model can set.
    """
    idempotency_key = _idempotency_key(actor_id, order_id, amount, reason)
    existing = idempotency_table.get_item(Key={"idempotency_key": idempotency_key}).get("Item")
    if existing is not None:
        emit_metric("RefundIdempotentReplay")
        # DynamoDB returns Decimal for stored numbers; convert back to
        # plain float/int so a replayed result has the same shape as a
        # freshly processed one.
        return json.loads(json.dumps(existing["result"], default=float))

    result = _process_refund(actor_id, order_id, amount, reason)

    # boto3's DynamoDB resource rejects Python float directly (it
    # requires Decimal for numeric types); result's "amount" field is a
    # plain float, since that's the natural type for a caller reading
    # the return value directly, so it gets converted only for storage,
    # not in what this function actually returns.
    storable_result = json.loads(json.dumps(result), parse_float=Decimal)
    idempotency_table.put_item(
        Item={
            "idempotency_key": idempotency_key,
            "result": storable_result,
            "expires_at": int(time.time()) + IDEMPOTENCY_RECORD_TTL_SECONDS,
        }
    )
    return result


def _process_refund(actor_id: str, order_id: str, amount: float, reason: str) -> dict:
    """The original decision logic from Design Note 17, unchanged. Split
    out from request_refund() so the idempotency wrapper above and the
    actual refund decision stay two separate, individually readable
    concerns.
    """
    order = orders_table.get_item(Key={"order_id": order_id}).get("Item")

    if order is None:
        return {"status": "denied", "reason": f"No order found with ID {order_id}."}

    if order["customer_id"] != actor_id:
        emit_metric("RefundOwnershipDenied")
        return {
            "status": "denied",
            "reason": (
                "This order does not belong to the verified customer on "
                "this conversation."
            ),
        }

    if amount <= AUTO_APPROVAL_THRESHOLD_USD:
        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET refund_status = :s, refund_amount = :a",
            ExpressionAttributeValues={":s": "approved_automatic", ":a": str(amount)},
        )
        return {
            "status": "approved",
            "order_id": order_id,
            "amount": amount,
            "approval": "automatic",
        }

    approval_id = str(uuid.uuid4())
    approvals_table.put_item(
        Item={
            "approval_id": approval_id,
            "order_id": order_id,
            "customer_id": actor_id,
            "amount": str(amount),
            "reason": reason,
            "status": "pending_human_review",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    emit_metric("RefundEscalated")
    return {
        "status": "pending_approval",
        "approval_id": approval_id,
        "order_id": order_id,
        "amount": amount,
        "message": (
            f"This refund exceeds ${AUTO_APPROVAL_THRESHOLD_USD:.2f} and has "
            "been queued for manager review. It has not been processed yet."
        ),
    }
