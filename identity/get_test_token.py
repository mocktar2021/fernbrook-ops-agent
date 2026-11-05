"""
Development helper: obtain a real Cognito ID token for the demo customer,
so you can test the deployed agent's identity verification.

The demo customer is created by scripts/set_demo_user_password.py (run by
the infra pipeline after each apply). Its password is generated randomly
and lives only in AWS Secrets Manager (fernbrook/demo-user-password). It
is never in this repository, in Terraform state, or in CI logs.

Pool and client IDs come from SSM Parameter Store (written by Terraform),
so there is nothing to export by hand. The environment variables
FERNBROOK_USER_POOL_ID / FERNBROOK_APP_CLIENT_ID still win when set.

Usage:

    python3 identity/get_test_token.py          # prints the ID token
    TOKEN=$(python3 identity/get_test_token.py)

A real support application would issue this token through its own login
flow. This script exists only so a developer can exercise the agent.
"""

import os

import boto3

REGION = "us-east-1"
CONFIG_PATH = "/fernbrook/config"
SECRET_ID = "fernbrook/demo-user-password"
DEMO_USERNAME = "demo-customer@example.com"
DEMO_CUSTOMER_ID = "CUST-4471"  # the customer on synthetic order FB-10293


def load_config() -> dict:
    """Read the platform stack's non-secret config from SSM, keyed by leaf name."""
    ssm = boto3.client("ssm", region_name=REGION)
    config = {}
    paginator = ssm.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=CONFIG_PATH):
        for parameter in page["Parameters"]:
            config[parameter["Name"].rsplit("/", 1)[-1]] = parameter["Value"]
    return config


def get_id_token() -> str:
    config = load_config()
    user_pool_id = os.environ.get("FERNBROOK_USER_POOL_ID") or config["user_pool_id"]
    app_client_id = os.environ.get("FERNBROOK_APP_CLIENT_ID") or config["app_client_id"]

    secrets = boto3.client("secretsmanager", region_name=REGION)
    password = secrets.get_secret_value(SecretId=SECRET_ID)["SecretString"]

    cognito = boto3.client("cognito-idp", region_name=REGION)
    response = cognito.admin_initiate_auth(
        UserPoolId=user_pool_id,
        ClientId=app_client_id,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": DEMO_USERNAME, "PASSWORD": password},
    )
    return response["AuthenticationResult"]["IdToken"]


def main() -> None:
    print(get_id_token())


if __name__ == "__main__":
    main()
