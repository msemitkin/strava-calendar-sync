terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws      = { source = "hashicorp/aws", version = "~> 6.0" }
    external = { source = "hashicorp/external", version = "~> 2.3" }
    random   = { source = "hashicorp/random", version = "~> 3.7" }
  }
}

provider "aws" { region = var.aws_region }

