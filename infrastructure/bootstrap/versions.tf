terraform {
  # >= 1.10 is required for the S3 backend's native state locking
  # (use_lockfile) used by the platform and release stacks. No DynamoDB
  # lock table needed.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }

  # Deliberately local state. This stack creates the bucket that holds every
  # other stack's state, so it cannot live there itself (chicken and egg).
  # It contains no secrets. Keep terraform.tfstate until you destroy this
  # stack. See docs/TEARDOWN.md for what to do if you lose it.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "fernbrook-ops-agent"
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}
