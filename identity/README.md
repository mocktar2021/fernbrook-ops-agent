> **Note:** the setup steps below describe the original manual path and are kept to explain the design. In this repository Terraform (`infrastructure/platform/cognito.tf`) creates the user pool and app client, and `scripts/set_demo_user_password.py` creates the demo customer with a generated password stored in Secrets Manager. Follow `docs/GETTING-STARTED.md` to deploy.

# Closing the identity gaps

This folder and this design note close two separate gaps, on purpose kept separate, per Design Note 14: a user identity gap (Design Note 9's trusted `actor_id`) and a service/agent identity gap (Design Note 12's `NONE` Gateway authorization).

## 1. Verified customer identity

```bash
# Pool and client are created by Terraform (infrastructure/platform/cognito.tf).
# The demo customer is created by scripts/set_demo_user_password.py.
# Get a token for it (IDs are read from SSM, the password from Secrets Manager):
python3 identity/get_test_token.py
```

Terraform creates a Cognito User Pool and an app client; the script creates one test customer (`demo-customer@example.com`, mapped via a custom attribute to `CUST-4471`, the customer on synthetic order `FB-10293`).

Get a real token for that test customer whenever you need one to test with:

```bash
python3 identity/get_test_token.py
```

`app.py` now requires a `customer_token` field in every invocation payload (in place of the old, trusted `actor_id` field) and verifies it with `identity/verify_customer_token.py` before doing anything else. A missing, expired, or invalid token gets a plain "could not verify customer identity" response, not a guess.

**If the verified claim comes back empty:** confirm the app client's read attributes include `custom:customer_id`; newer Cognito pools don't always expose custom attributes to a client by default.

## 2. Real Gateway inbound authorization

`FernbrookGateway` was created in Design Note 12 with `--authorizer-type NONE`. Recreate it with `AWS_IAM` authorization, then reattach both existing targets:

```bash
agentcore add gateway --name FernbrookGateway --authorizer-type AWS_IAM
agentcore add gateway-target \
  --name OrderLookup \
  --type lambda-function-arn \
  --lambda-arn arn:aws:lambda:us-east-1:<YOUR_ACCOUNT_ID>:function:fernbrook-order-lookup \
  --tool-schema-file tools/order_lookup/tool_schema.json \
  --gateway FernbrookGateway
agentcore add gateway-target \
  --name WholesaleAccountLookup \
  --type open-api-schema \
  --schema tools/wholesale_lookup/openapi.json \
  --outbound-auth api-key \
  --credential-name WholesaleLookupApiKey \
  --gateway FernbrookGateway
agentcore deploy
```

With `AWS_IAM` authorization, Gateway only accepts SigV4-signed requests, meaning only callers with valid AWS credentials, checked against an IAM policy granting `bedrock-agentcore:InvokeGateway` on this specific Gateway, can reach it at all.

Grant that permission to the deployed agent's own execution role (not `fernbrook-agent-builder`; see `infrastructure/iam/README.md`), using `infrastructure/iam/runtime-execution-role-gateway-invoke-statement.json` as the statement to add, with the Gateway ID filled in.

`agent/agent.py`'s Gateway connection now uses `aws_iam_streamablehttp_client` from the `mcp-proxy-for-aws` package instead of a plain, unauthenticated connection, so this change is already reflected in the agent's own code, not just the Gateway's configuration.

## What's still open

Design Note 14 named four identity categories: user, agent, service, and tool. This folder closes the user identity gap (verified customer tokens) and the service/agent identity gap at Gateway's inbound boundary (SigV4). Tool identity, what a downstream system sees when the agent calls it on a specific customer's behalf, remains unaddressed; every tool call still presents as "the Fernbrook Ops Agent," not "the Fernbrook Ops Agent, acting for CUST-4471." For two read-only tools against synthetic data, that's a tolerable, named gap. It will not be tolerable once a later design note reaches a write action, which is exactly why Design Note 16's authorization work and Design Note 17's human approval step both exist.
