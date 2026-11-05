# Customer identity. In a real deployment the support application's own login
# would issue these tokens; this pool exists so the agent's identity check
# (identity/verify_customer_token.py) has something real to verify against.
#
# Terraform creates the pool and app client only. The demo *user* and its
# password are created by scripts/set_demo_user_password.py after apply, so
# the password never enters Terraform state (state stores resource arguments
# in plain text).
resource "aws_cognito_user_pool" "customers" {
  name = "fernbrook-customers"

  # Customers are created by administrators (or by the support app's backend);
  # there is no public self-service sign-up on this pool.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  schema {
    name                = "customer_id"
    attribute_data_type = "String"
    mutable             = true
    required            = false

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
  }
}

resource "aws_cognito_user_pool_client" "support_app" {
  name         = "fernbrook-support-app"
  user_pool_id = aws_cognito_user_pool.customers.id

  generate_secret = false

  # Admin-initiated password auth: used by scripts and the smoke test, which
  # call it with IAM credentials. Not exposed to browsers.
  explicit_auth_flows = [
    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}
