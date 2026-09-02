output "webhook_url" {
  value = aws_lambda_function_url.webhook.function_url
}

output "webhook_callback_url" {
  value     = "${aws_lambda_function_url.webhook.function_url}${random_password.webhook_verify_token.result}"
  sensitive = true
}

output "webhook_verify_token" {
  value     = random_password.webhook_verify_token.result
  sensitive = true
}

output "parameter_prefix" {
  value = var.parameter_prefix
}
