# Where the app pipeline uploads the agent's code zip. Versioned: every upload
# gets an S3 version ID, and the Runtime is pinned to (key, version ID), so a
# release is exactly one immutable artifact and a rollback is just pointing
# back at the previous one.
resource "aws_s3_bucket" "code" {
  bucket = local.code_bucket_name

  # Lets `terraform destroy` delete the bucket even though it holds object
  # versions. Fine for build artifacts you can always rebuild from git.
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "code" {
  bucket = aws_s3_bucket.code.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "code" {
  bucket = aws_s3_bucket.code.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "code" {
  bucket                  = aws_s3_bucket.code.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "code" {
  bucket = aws_s3_bucket.code.id

  rule {
    id     = "expire-old-agent-builds"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  depends_on = [aws_s3_bucket_versioning.code]
}
