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
- A Google Cloud project with Google Calendar API enabled and a service account JSON key.

Java and Gradle do not need to be installed. On macOS or Linux, the Terraform build hook detects ARM64/x64 and downloads the matching JDK plus Gradle automatically. The code targets Java 17 bytecode and runs on AWS's Java 21 Lambda runtime.

## Deploy

```bash
terraform -chdir=terraform init
terraform -chdir=terraform apply
python3 scripts/configure.py
```

The last command opens Strava OAuth, reads a Google service-account key from your local machine, writes credentials directly to SSM SecureString parameters, and registers the webhook. Secrets are neither placed in `.tfvars` nor stored in Terraform state.

## Google service account setup

1. In Google Cloud Console, create or select a project.
2. Enable **Google Calendar API** under APIs & Services → Library.
3. Open IAM & Admin → Service Accounts and create `strava-calendar-sync`.
4. Open the service account → Keys → Add key → Create new key → JSON. Keep the downloaded file private.
5. In Google Calendar, create a secondary calendar named `Strava`.
6. Open the calendar's Settings and sharing → Share with specific people or groups.
7. Add the service account's `client_email` from the JSON file and choose **Make changes to events**.
8. In Integrate calendar, copy the **Calendar ID**.

The service account can access only calendars explicitly shared with it. Google OAuth consent, branding, production publishing, a custom domain, and refresh tokens are not required.

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
