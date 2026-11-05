"""
One-time setup: create the Secrets Manager secret backing the
wholesale-lookup API key, closing the credential-hygiene gap Design Note 21
named (the key previously lived in a plain Lambda environment variable).

Run once:

    python3 tools/wholesale_lookup/create_api_key_secret.py

Generates a random key, stores it, and prints it once so you can
configure the Gateway's credential provider (see this folder's
README). The key is never printed again after this run; retrieve it
from Secrets Manager directly if you need it again.
"""

import secrets as secrets_module

import boto3

REGION = "us-east-1"
SECRET_NAME = "fernbrook/wholesale-lookup-api-key"


def main() -> None:
    api_key = secrets_module.token_urlsafe(32)

    client = boto3.client("secretsmanager", region_name=REGION)
    client.create_secret(
        Name=SECRET_NAME,
        Description="API key the wholesale-lookup Lambda checks against.",
        SecretString=api_key,
    )

    print(f"Created secret: {SECRET_NAME}")
    print(f"API key (shown once): {api_key}")
    print()
    print("Use this value when configuring the Gateway's API-key")
    print("credential provider for the WholesaleAccountLookup target.")


if __name__ == "__main__":
    main()
