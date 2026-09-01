variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  type    = string
  default = "strava-calendar-sync"
}

variable "parameter_prefix" {
  type    = string
  default = "/strava-calendar-sync"
}

