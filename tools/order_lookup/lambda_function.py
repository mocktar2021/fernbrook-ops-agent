"""
Lambda handler for the order-lookup tool. AgentCore Gateway invokes this
function when the agent calls the get_order_status tool; see
tool_schema.json for the schema the model actually sees.

This function only reads. It cannot modify an order. Read/write is a
distinction Design Note 10 asked you to make before building any tool; this
one is a read tool, and stays one.

As of Design Note 23, the response includes customer_id. That field exists
so the agent's own code (agent.py's get_order_status wrapper) can check
the returned order actually belongs to the verified customer on the
conversation, something this Lambda itself has no way to know, since it
has no visibility into who's asking, only what was asked. The wrapper
strips customer_id before anything reaches the model or the customer.
"""

import boto3

REGION = "us-east-1"
TABLE_NAME = "fernbrook-orders"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    """Look up one order by ID and return its status.

    `event` is the tool input Gateway forwards, matching tool_schema.json:
    a single "order_id" field. Returns a plain dict; Gateway translates
    it back into the MCP tool result the agent sees.
    """
    order_id = event.get("order_id", "").strip()

    if not order_id:
        return {"found": False, "error": "order_id was not provided."}

    response = table.get_item(Key={"order_id": order_id})
    item = response.get("Item")

    if item is None:
        return {
            "found": False,
            "error": f"No order found with ID {order_id}.",
        }

    return {
        "found": True,
        "order_id": item["order_id"],
        "customer_id": item["customer_id"],
        "status": item["status"],
        "order_type": item["order_type"],
        "order_date": item["order_date"],
        "estimated_delivery_date": item["estimated_delivery_date"],
        "items": item["items"],
    }
