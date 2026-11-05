> **Note: not deployed by the pipelines yet (milestone 2).** The wholesale lookup needs an OpenAPI Gateway target and an API-key credential provider, neither of which is deployed. The agent treats this capability as unavailable and says so. The code and notes here are kept for when it is added.

# Wholesale account lookup tool

Fernbrook's second tool, and the first built against an already-running HTTP endpoint instead of a Gateway-invoked Lambda. Design Note 13 covers the reasoning; this file covers the steps.

## 1. Store the API key in Secrets Manager

```bash
python3 tools/wholesale_lookup/create_api_key_secret.py
```

Prints the generated key once. Note it down; you'll need it in Step 3.

## 2. Deploy the Lambda behind a Function URL

```bash
zip -j tools/wholesale_lookup/function.zip tools/wholesale_lookup/lambda_function.py

aws lambda create-function \
  --function-name fernbrook-wholesale-lookup \
  --runtime python3.12 \
  --handler lambda_function.handler \
  --role arn:aws:iam::<YOUR_ACCOUNT_ID>:role/fernbrook-wholesale-lookup-lambda-role \
  --zip-file fileb://tools/wholesale_lookup/function.zip

aws lambda create-function-url-config \
  --function-name fernbrook-wholesale-lookup \
  --auth-type NONE

aws lambda add-permission \
  --function-name fernbrook-wholesale-lookup \
  --statement-id AllowPublicFunctionUrl \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE
```

`--auth-type NONE` on the function URL does not mean this endpoint is unprotected; it means Lambda itself doesn't check an IAM signature, and the handler enforces its own check instead, the `x-api-key` header comparison in `lambda_function.py`, checked against the value now stored in Secrets Manager rather than a plain environment variable. Anyone without that key gets a 401 with no access to account data.

Note the Function URL printed in the `create-function-url-config` output; it goes in `openapi.json`'s `servers` block, replacing the placeholder host.

## 3. Store the API key as an AgentCore credential provider

Follow the current AgentCore Gateway documentation for creating an API-key credential provider; the exact CLI or console steps are worth checking fresh, since this is newer surface area than the Lambda-target path from Design Note 12. The credential provider stores the same value `create_api_key_secret.py` generated in Step 1; Gateway attaches it to every outbound call to this target automatically.

## 4. Register the OpenAPI target

```bash
agentcore add gateway-target \
  --name WholesaleAccountLookup \
  --type open-api-schema \
  --schema tools/wholesale_lookup/openapi.json \
  --outbound-auth api-key \
  --credential-name WholesaleLookupApiKey \
  --gateway FernbrookGateway
agentcore deploy
```

No hand-written tool schema this time. Gateway derives the tool's name, description, and input shape from `openapi.json` directly, the payoff of describing this tool with a specification instead of a schema file.

## No agent code changes required

`agent/agent.py` calls `gateway_client.list_tools_sync()` against the same `FernbrookGateway` used in Design Note 12. Once this target is deployed, that call returns both tools, `get_order_status` and `getWholesaleAccountStatus`, with no change to `run_agent()` at all. Adding a Gateway target is not the same operation as adding a directly imported tool, and Design Note 13 explains why that difference is the entire point of building on Gateway in the first place.
