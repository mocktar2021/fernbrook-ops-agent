"""
Human-facing review tool for refunds queued above process_refund's
automatic-approval threshold. Run by a Fernbrook support manager, not
by the agent. Nothing in this project lets the agent approve its own
high-value refund requests; this script is the entire mechanism by
which one actually gets approved once it's above that line.
"""

import sys

import boto3

REGION = "us-east-1"
APPROVALS_TABLE = "fernbrook-refund-approvals"
ORDERS_TABLE = "fernbrook-orders"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
approvals_table = dynamodb.Table(APPROVALS_TABLE)
orders_table = dynamodb.Table(ORDERS_TABLE)


def list_pending() -> None:
    response = approvals_table.scan(
        FilterExpression="#s = :pending",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":pending": "pending_human_review"},
    )
    items = response.get("Items", [])
    if not items:
        print("No refunds pending review.")
        return

    for item in items:
        print(
            f"[{item['approval_id']}] order {item['order_id']}, "
            f"customer {item['customer_id']}, ${item['amount']}, "
            f"reason: {item['reason']}"
        )


def decide(approval_id: str, approve: bool) -> None:
    item = approvals_table.get_item(Key={"approval_id": approval_id}).get("Item")
    if item is None:
        print("No such pending approval.")
        return

    new_status = "approved_by_manager" if approve else "denied_by_manager"
    approvals_table.update_item(
        Key={"approval_id": approval_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": new_status},
    )

    if approve:
        orders_table.update_item(
            Key={"order_id": item["order_id"]},
            UpdateExpression="SET refund_status = :s, refund_amount = :a",
            ExpressionAttributeValues={":s": "approved_manual", ":a": item["amount"]},
        )

    print(f"Approval {approval_id} marked {new_status}.")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "list":
        list_pending()
    elif len(sys.argv) == 3 and sys.argv[1] in ("approve", "deny"):
        decide(sys.argv[2], approve=(sys.argv[1] == "approve"))
    else:
        print("Usage:")
        print("  python3 scripts/review_pending_refunds.py list")
        print("  python3 scripts/review_pending_refunds.py approve <approval_id>")
        print("  python3 scripts/review_pending_refunds.py deny <approval_id>")
