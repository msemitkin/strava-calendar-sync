data "external" "build" {
  program = ["bash", "${path.module}/../scripts/terraform-build.sh"]
}

resource "random_password" "webhook_verify_token" {
  length  = 40
  special = false
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "events" {
  name                       = "${var.project_name}-events"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 1209600
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = 5
  })
}

resource "aws_iam_role" "webhook" {
  name               = "${var.project_name}-webhook"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role" "worker" {
  name               = "${var.project_name}-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service", identifiers = ["lambda.amazonaws.com"] }
  }
}

resource "aws_iam_role_policy_attachment" "webhook_logs" {
  role       = aws_iam_role.webhook.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "worker_logs" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "webhook_queue" {
  role = aws_iam_role.webhook.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sqs:SendMessage", Resource = aws_sqs_queue.events.arn
  }] })
}

resource "aws_iam_role_policy" "worker_access" {
  role = aws_iam_role.worker.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.events.arn },
    { Effect = "Allow", Action = ["ssm:GetParametersByPath"], Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.parameter_prefix}/*" }
  ] })
}

data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "webhook" {
  name              = "/aws/lambda/${var.project_name}-webhook"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${var.project_name}-worker"
  retention_in_days = 14
}

resource "aws_lambda_function" "webhook" {
  function_name    = "${var.project_name}-webhook"
  role             = aws_iam_role.webhook.arn
  runtime          = "java21"
  handler          = "dev.msemitkin.stravacalendar.WebhookHandler::handleRequest"
  filename         = data.external.build.result.artifact_path
  source_code_hash = data.external.build.result.source_code_hash
  memory_size      = 512
  timeout          = 10
  environment { variables = { QUEUE_URL = aws_sqs_queue.events.url, WEBHOOK_VERIFY_TOKEN = random_password.webhook_verify_token.result } }
  depends_on = [aws_iam_role_policy_attachment.webhook_logs, aws_cloudwatch_log_group.webhook]
}

resource "aws_lambda_function" "worker" {
  function_name    = "${var.project_name}-worker"
  role             = aws_iam_role.worker.arn
  runtime          = "java21"
  handler          = "dev.msemitkin.stravacalendar.SyncWorkerHandler::handleRequest"
  filename         = data.external.build.result.artifact_path
  source_code_hash = data.external.build.result.source_code_hash
  memory_size      = 768
  timeout          = 60
  environment { variables = { PARAMETER_PREFIX = var.parameter_prefix } }
  depends_on = [aws_iam_role_policy_attachment.worker_logs, aws_cloudwatch_log_group.worker]
}

resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn = aws_sqs_queue.events.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
}

resource "aws_lambda_function_url" "webhook" {
  function_name      = aws_lambda_function.webhook.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "public_url" {
  statement_id           = "PublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.webhook.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "public_invoke" {
  statement_id           = "PublicInvokeViaUrl"
  action                 = "lambda:InvokeFunction"
  function_name          = aws_lambda_function.webhook.function_name
  principal              = "*"
  invoked_via_function_url = true
}

