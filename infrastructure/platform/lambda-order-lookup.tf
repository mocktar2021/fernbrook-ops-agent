# The read-only order lookup tool. AgentCore Gateway invokes this Lambda
# when the agent calls get_order_status. Same function, role, and policy
# documents as the manual setup in tools/order_lookup/README.md; Terraform
# makes it reproducible.

data "archive_file" "order_lookup" {
  type        = "zip"
  source_file = "${path.module}/../../tools/order_lookup/lambda_function.py"
  output_path = "${path.module}/build/order_lookup.zip"
}

resource "aws_iam_role" "order_lookup_lambda" {
  name                 = "fernbrook-order-lookup-lambda-role"
  assume_role_policy   = file("${path.module}/../../tools/order_lookup/lambda-trust-policy.json")
  permissions_boundary = local.boundary_arn
}

resource "aws_iam_role_policy" "order_lookup_lambda" {
  name   = "ReadFernbrookOrdersTable"
  role   = aws_iam_role.order_lookup_lambda.id
  policy = file("${path.module}/../../tools/order_lookup/lambda-dynamodb-policy.json")
}

# Managed here (not auto-created by Lambda) so retention is bounded and
# `terraform destroy` removes it. Otherwise it would outlive the stack.
resource "aws_cloudwatch_log_group" "order_lookup" {
  name              = "/aws/lambda/fernbrook-order-lookup"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "order_lookup" {
  function_name    = "fernbrook-order-lookup"
  runtime          = "python3.12"
  handler          = "lambda_function.handler"
  role             = aws_iam_role.order_lookup_lambda.arn
  filename         = data.archive_file.order_lookup.output_path
  source_code_hash = data.archive_file.order_lookup.output_base64sha256

  # Design Note 31: explicit, not AWS's 3-second default left unexamined.
  # A single DynamoDB GetItem should complete in well under a second;
  # 5 seconds leaves room for a slow cold start without letting a
  # genuinely stuck request hang the whole agent turn waiting on it.
  timeout = 5

  depends_on = [
    aws_dynamodb_table.orders,
    aws_iam_role_policy.order_lookup_lambda,
    aws_cloudwatch_log_group.order_lookup,
  ]
}
