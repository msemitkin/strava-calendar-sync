# Strava Calendar Sync

Serverless synchronization of private and public Strava activities to a dedicated Google Calendar.

## What it does

- Receives Strava `create`, `update`, and `delete` webhooks.
- Reads private activities with the `activity:read_all` scope.
- Creates an event at the real activity start time with elapsed duration, distance, elevation, and Strava URL.
- Uses stable event IDs, so webhook retries do not create duplicates.
- Responds to Strava quickly and processes API calls asynchronously through SQS.
- Sends repeatedly failing messages to a dead-letter queue.

## Architecture

```text
Strava -> Lambda Function URL -> webhook Lambda -> SQS -> worker Lambda
                                                       |-> Strava API
                                                       |-> Google Calendar API
                                                       `-> SSM Parameter Store
```

## Prerequisites

- AWS account and AWS CLI credentials.
- Terraform 1.8+.
- Python 3, `curl`, `unzip`, `tar`, and `openssl`.
- A Strava API application. Set its Authorization Callback Domain to `localhost`.
- A Google Cloud project with Google Calendar API enabled and an OAuth client of type **Desktop app**.

Java and Gradle do not need to be installed. The Terraform build hook downloads a JDK and Gradle automatically. The code targets Java 17 bytecode and runs on AWS's Java 21 Lambda runtime.

## Deploy

```bash
terraform -chdir=terraform init
terraform -chdir=terraform apply
python3 scripts/configure.py
```

The last command opens Strava and Google OAuth pages, creates a dedicated `Strava` calendar, writes credentials directly to SSM SecureString parameters, and registers the webhook. Secrets are neither placed in `.tfvars` nor stored in Terraform state.

For a named AWS profile or another region:

```bash
AWS_PROFILE=my-profile terraform -chdir=terraform apply -var='aws_region=eu-central-1'
python3 scripts/configure.py --profile my-profile --region eu-central-1
```

## Important privacy note

Strava's **Only You** visibility is supported. Strava's separate **Hide Start Time** privacy control may cause the API to return an obfuscated time; no downstream integration can recover the hidden start time.

## Operations

Logs are retained for 14 days under:

- `/aws/lambda/strava-calendar-sync-webhook`
- `/aws/lambda/strava-calendar-sync-worker`

To inspect failed messages:

```bash
aws sqs receive-message --queue-url "$(aws sqs get-queue-url --queue-name strava-calendar-sync-dlq --query QueueUrl --output text)"
```

To remove AWS infrastructure:

```bash
terraform -chdir=terraform destroy
```

Delete the Strava webhook subscription before destroying if you no longer want Strava delivery attempts.
