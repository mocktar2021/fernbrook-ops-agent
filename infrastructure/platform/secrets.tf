# A container for the demo user's password, with NO secret value. The value is
# generated and written by scripts/set_demo_user_password.py, so it never
# appears in Terraform state, plan output, or CI logs.
#
# recovery_window_in_days = 0 deletes immediately on destroy. Without it, AWS
# keeps a deleted secret for 7 to 30 days and blocks reusing the name, which
# would break "destroy and redeploy tomorrow".
resource "aws_secretsmanager_secret" "demo_user_password" {
  name                    = "fernbrook/demo-user-password"
  description             = "Password for the synthetic demo customer. Written by scripts/set_demo_user_password.py."
  recovery_window_in_days = 0
}
