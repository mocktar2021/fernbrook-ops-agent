> **Note:** the setup steps below describe the original manual path and are kept to explain the design. In this repository Terraform (`infrastructure/platform/lambda-order-lookup.tf`) creates the Lambda, its role and the Gateway target, and the Infra Apply workflow seeds the data with `seed_data.py`. Follow `docs/GETTING-STARTED.md` to deploy.

# Order lookup tool

Fernbrook's first real, business-connected tool: a read-only lookup against synthetic order data. Design Note 12 covers the reasoning behind every step below.

## 1. Create and seed the orders table

```bash
python3 tools/order_lookup/seed_data.py
```

Creates the `fernbrook-orders` DynamoDB table (if it doesn't already exist) and loads six synthetic orders. Safe to re-run; it won't duplicate the table, and re-seeding just overwrites the same items with the same values.

## 2. Create the Lambda function's execution role

```bash
aws iam create-role \
  --role-name fernbrook-order-lookup-lambda-role \
  --assume-role-policy-document file://tools/order_lookup/lambda-trust-policy.json

aws iam put-role-policy \
  --role-name fernbrook-order-lookup-lambda-role \
  --policy-name ReadFernbrookOrdersTable \
  --policy-document file://tools/order_lookup/lambda-dynamodb-policy.json
```

This role can read the orders table and write its own CloudWatch logs. Nothing else.

## 3. Package and deploy the Lambda function

```bash
cd tools/order_lookup
zip function.zip lambda_function.py
aws lambda create-function \
  --function-name fernbrook-order-lookup \
  --runtime python3.12 \
  --handler lambda_function.handler \
  --role arn:aws:iam::<YOUR_ACCOUNT_ID>:role/fernbrook-order-lookup-lambda-role \
  --zip-file fileb://function.zip
cd ../..
```

Replace `<YOUR_ACCOUNT_ID>` with your account ID (from `aws sts get-caller-identity`, per Design Note 4).

## 4. Create the Gateway and register this Lambda as a target

```bash
agentcore add gateway --name FernbrookGateway --authorizer-type NONE
agentcore add gateway-target \
  --name OrderLookup \
  --type lambda-function-arn \
  --lambda-arn arn:aws:lambda:us-east-1:<YOUR_ACCOUNT_ID>:function:fernbrook-order-lookup \
  --tool-schema-file tools/order_lookup/tool_schema.json \
  --gateway FernbrookGateway
agentcore deploy
```

`--authorizer-type NONE` is a deliberate, temporary simplification, not an oversight; Design Note 12 explains exactly why it's acceptable for now and what closes the gap in a later design note.

Note the Gateway's MCP endpoint URL printed after deployment (or retrieve it later with `agentcore status`); `agent/agent.py` needs it.

## Isolation reminder

This tool is read-only by design (Design Note 10's read/write distinction). It cannot modify an order, issue a refund, or touch any data outside the `fernbrook-orders` table. Write tools arrive in a later design note, behind AgentCore Policy and human approval, not here.
