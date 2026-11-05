"""
One-time setup: create the DynamoDB table that holds refund requests
queued for human review, above process_refund's automatic-approval
threshold. Run once:

    python3 agent/setup_refund_approvals_table.py
"""

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
TABLE_NAME = "fernbrook-refund-approvals"


def main() -> None:
    dynamodb = boto3.resource("dynamodb", region_name=REGION)

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
        KeySchema=[{"AttributeName": "approval_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "approval_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print("Table created.")


if __name__ == "__main__":
    main()
