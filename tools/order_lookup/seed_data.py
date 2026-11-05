"""
One-time setup: create the DynamoDB table backing Fernbrook's order data
and seed it with a small set of synthetic orders.

Run this once:

    python3 tools/order_lookup/seed_data.py

Every order below is invented for this project. It does not represent a
real company, a real customer, or a real transaction.
"""

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
TABLE_NAME = "fernbrook-orders"

SYNTHETIC_ORDERS = [
    {
        "order_id": "FB-10293",
        "customer_id": "CUST-4471",
        "order_type": "retail",
        "status": "shipped",
        "order_date": "2026-08-20",
        "estimated_delivery_date": "2026-08-27",
        "items": "Trailhead Hiking Boots (size 10)",
    },
    {
        "order_id": "FB-10318",
        "customer_id": "CUST-5502",
        "order_type": "retail",
        "status": "processing",
        "order_date": "2026-08-28",
        "estimated_delivery_date": "2026-09-05",
        "items": "Ridgeline 4-Person Tent",
    },
    {
        "order_id": "FB-10402",
        "customer_id": "CUST-WHS-118",
        "order_type": "wholesale",
        "status": "delivered",
        "order_date": "2026-08-01",
        "estimated_delivery_date": "2026-08-10",
        "items": "Bulk order: 48x assorted trail socks",
    },
    {
        "order_id": "FB-10455",
        "customer_id": "CUST-6190",
        "order_type": "retail",
        "status": "delayed",
        "order_date": "2026-08-22",
        "estimated_delivery_date": "2026-08-29",
        "items": "Summit Shell Jacket (size M)",
    },
    {
        "order_id": "FB-10510",
        "customer_id": "CUST-6304",
        "order_type": "retail",
        "status": "delivered",
        "order_date": "2026-08-15",
        "estimated_delivery_date": "2026-08-21",
        "items": "Cascade 45L Backpack",
    },
    {
        "order_id": "FB-10577",
        "customer_id": "CUST-WHS-204",
        "order_type": "wholesale",
        "status": "processing",
        "order_date": "2026-08-30",
        "estimated_delivery_date": "2026-09-08",
        "items": "Bulk order: 24x Ridgeline Tent",
    },
]


def create_table_if_missing(dynamodb) -> None:
    try:
        dynamodb.meta.client.describe_table(TableName=TABLE_NAME)
        print(f"Table {TABLE_NAME} already exists; skipping creation.")
        return
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    print(f"Creating table {TABLE_NAME}...")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "order_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print("Table created.")


def seed_orders(dynamodb) -> None:
    table = dynamodb.Table(TABLE_NAME)
    with table.batch_writer() as batch:
        for order in SYNTHETIC_ORDERS:
            batch.put_item(Item=order)
    print(f"Seeded {len(SYNTHETIC_ORDERS)} synthetic orders.")


def main() -> None:
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    create_table_if_missing(dynamodb)
    seed_orders(dynamodb)


if __name__ == "__main__":
    main()
