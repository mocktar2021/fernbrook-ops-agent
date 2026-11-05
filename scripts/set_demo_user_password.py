#!/usr/bin/env python3
"""
Ensure the synthetic demo customer exists in the Cognito pool, with a random
password that lives only in AWS Secrets Manager.

Why this is a script and not Terraform: Terraform stores resource arguments
in its state file in plain text. A password passed to a Terraform resource
would sit in state. Here the password is generated in memory, written to
Secrets Manager, set on the Cognito user, and never printed or logged.

Idempotent. Safe to run after every platform apply, including the first apply
after a destroy (when the secret container is new and empty):

    python3 scripts/set_demo_user_password.py

Needs: ssm:GetParametersByPath on /fernbrook/config, secretsmanager
Get/PutSecretValue on fernbrook/demo-user-password, and Cognito
AdminGetUser / AdminCreateUser / AdminSetUserPassword on the pool. The
infra-apply pipeline role has exactly these.
"""

import secrets
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identity.get_test_token import (  # noqa: E402
    DEMO_CUSTOMER_ID,
    DEMO_USERNAME,
    REGION,
    SECRET_ID,
    load_config,
)


def new_password() -> str:
    # token_urlsafe supplies letters, digits, "-" and "_"; the suffix
    # guarantees every Cognito default-policy character class is present.
    return secrets.token_urlsafe(24) + "Aa1!"


def get_or_create_secret_value(secrets_client) -> str:
    try:
        value = secrets_client.get_secret_value(SecretId=SECRET_ID)["SecretString"]
        if value:
            return value
    except ClientError as error:
        # ResourceNotFoundException is raised both when the secret is missing
        # and when it exists but has no value yet (a fresh Terraform container).
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    value = new_password()
    secrets_client.put_secret_value(SecretId=SECRET_ID, SecretString=value)
    print("Generated a new demo password and stored it in Secrets Manager.")
    return value


def ensure_user(cognito, user_pool_id: str) -> None:
    try:
        cognito.admin_get_user(UserPoolId=user_pool_id, Username=DEMO_USERNAME)
        print(f"Demo user {DEMO_USERNAME} already exists.")
        return
    except ClientError as error:
        if error.response["Error"]["Code"] != "UserNotFoundException":
            raise

    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=DEMO_USERNAME,
        UserAttributes=[
            {"Name": "email", "Value": DEMO_USERNAME},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:customer_id", "Value": DEMO_CUSTOMER_ID},
        ],
        MessageAction="SUPPRESS",
    )
    print(f"Created demo user {DEMO_USERNAME} mapped to {DEMO_CUSTOMER_ID}.")


def main() -> None:
    config = load_config()
    user_pool_id = config["user_pool_id"]

    secrets_client = boto3.client("secretsmanager", region_name=REGION)
    cognito = boto3.client("cognito-idp", region_name=REGION)

    password = get_or_create_secret_value(secrets_client)
    ensure_user(cognito, user_pool_id)
    cognito.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=DEMO_USERNAME,
        Password=password,
        Permanent=True,
    )
    print("Demo user password is in sync with Secrets Manager.")


if __name__ == "__main__":
    main()
