# Terraform owns the tables' existence and schema. tools/order_lookup/seed_data.py
# still loads the synthetic orders (it skips table creation when the table
# exists). Replaces the table-creation steps of seed_data.py and
# agent/setup_refund_approvals_table.py.
#
# deletion_protection stays off and there is no point-in-time recovery: this
# is synthetic demo data you will destroy and recreate. A real deployment
# would turn both on (named as an open gap in the readiness review).

resource "aws_dynamodb_table" "orders" {
  name         = "fernbrook-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

}

resource "aws_dynamodb_table" "refund_approvals" {
  name         = "fernbrook-refund-approvals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "approval_id"

  attribute {
    name = "approval_id"
    type = "S"
  }

}

# Design Note 32: backs request_refund()'s idempotency check. TTL means a
# retried request within the idempotency window returns the cached
# result instead of processing twice, and old entries expire on their
# own instead of growing this table forever.
resource "aws_dynamodb_table" "refund_idempotency" {
  name         = "fernbrook-refund-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idempotency_key"

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

}
