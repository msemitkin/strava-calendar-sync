#!/usr/bin/env python3
"""Enqueue recent Strava activities for idempotent Calendar backfill."""

import argparse
import datetime
import json
import subprocess
import time
import urllib.parse
import urllib.request


def aws(command, region, profile):
    args = ["aws", *command, "--region", region, "--output", "json", "--no-cli-pager"]
    if profile:
        args += ["--profile", profile]
    return json.loads(subprocess.check_output(args, text=True))


def terraform_output(name):
    return subprocess.check_output(
        ["terraform", "-chdir=terraform", "output", "-raw", name], text=True
    ).strip()


def get_parameters(prefix, region, profile):
    names = [f"{prefix}/{name}" for name in (
        "strava_client_id", "strava_client_secret", "strava_refresh_token"
    )]
    response = aws(["ssm", "get-parameters", "--with-decryption", "--names", *names], region, profile)
    values = {item["Name"].removeprefix(prefix + "/"): item["Value"] for item in response["Parameters"]}
    missing = [name for name in ("strava_client_id", "strava_client_secret", "strava_refresh_token") if name not in values]
    if missing:
        raise SystemExit("Missing SSM parameters: " + ", ".join(missing))
    return values


def request_json(url, method="GET", form=None, access_token=None):
    data = urllib.parse.urlencode(form).encode() if form else None
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if form else {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def refresh_strava(parameters, prefix, region, profile):
    tokens = request_json("https://www.strava.com/oauth/token", "POST", {
        "client_id": parameters["strava_client_id"],
        "client_secret": parameters["strava_client_secret"],
        "refresh_token": parameters["strava_refresh_token"],
        "grant_type": "refresh_token",
    })
    rotated = tokens.get("refresh_token")
    if rotated and rotated != parameters["strava_refresh_token"]:
        aws([
            "ssm", "put-parameter", "--name", f"{prefix}/strava_refresh_token",
            "--type", "SecureString", "--value", rotated, "--overwrite",
        ], region, profile)
    return tokens["access_token"]


def load_activities(access_token, after):
    activities = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"after": after, "page": page, "per_page": 100})
        batch = request_json(
            f"https://www.strava.com/api/v3/athlete/activities?{query}", access_token=access_token
        )
        activities.extend(batch)
        if len(batch) < 100:
            return activities
        page += 1


def main():
    parser = argparse.ArgumentParser(description="Import recent Strava activities into Google Calendar")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--profile")
    args = parser.parse_args()
    if args.days < 1:
        raise SystemExit("--days must be at least 1")

    prefix = terraform_output("parameter_prefix")
    parameters = get_parameters(prefix, args.region, args.profile)
    access_token = refresh_strava(parameters, prefix, args.region, args.profile)
    after = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.days)).timestamp())
    activities = load_activities(access_token, after)
    queue_url = aws([
        "sqs", "get-queue-url", "--queue-name", "strava-calendar-sync-events"
    ], args.region, args.profile)["QueueUrl"]

    for activity in activities:
        event = {
            "object_type": "activity",
            "object_id": activity["id"],
            "aspect_type": "create",
            "owner_id": activity.get("athlete", {}).get("id", 0),
            "event_time": int(time.time()),
            "updates": {},
        }
        aws([
            "sqs", "send-message", "--queue-url", queue_url,
            "--message-body", json.dumps(event, separators=(",", ":")),
        ], args.region, args.profile)

    print(f"Enqueued {len(activities)} activities from the last {args.days} days.")
    print("The worker will create or update Calendar events asynchronously.")


if __name__ == "__main__":
    main()

