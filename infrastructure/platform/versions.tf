terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }

  # Remote state in the S3 bucket the bootstrap stack created. The bucket
  # name and region are not hardcoded (they contain your account ID); pass
  # them at init time:
  #
  #   terraform init -backend-config="bucket=<state bucket>" -backend-config="region=us-east-1"
  #
  # The workflows do exactly that from the TF_STATE_BUCKET secret.
  backend "s3" {
    key          = "platform/terraform.tfstate"
    use_lockfile = true # native S3 locking, Terraform >= 1.10; no DynamoDB table
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "fernbrook-ops-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
      Stack       = "platform"
    }
  }
}
