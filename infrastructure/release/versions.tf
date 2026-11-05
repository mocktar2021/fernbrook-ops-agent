terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }

  # Same bucket as the platform stack, different key: the release stack has its
  # own state, its own pipeline, and its own (narrower) IAM role.
  #
  #   terraform init -backend-config="bucket=<state bucket>" -backend-config="region=us-east-1"
  backend "s3" {
    key          = "release/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "fernbrook-ops-agent"
      Environment = "dev"
      ManagedBy   = "terraform"
      Stack       = "release"
    }
  }
}
