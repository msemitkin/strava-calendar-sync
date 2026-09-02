#!/usr/bin/env python3
"""Replace existing Strava subscriptions with the secret-path callback URL."""

import argparse
import json
import subprocess
import urllib.parse
import urllib.request


def terraform_output(name):
    return subprocess.check_output(
        ["terraform", "-chdir=terraform", "output", "-raw", name], text=True
    ).strip()


def aws(command, region, profile):
    args = ["aws", *command, "--region", region, "--output", "json", "--no-cli-pager"]
    if profile:
        args += ["--profile", profile]
    return json.loads(subprocess.check_output(args, text=True))


def request_json(url, method="GET", form=None):
    data = urllib.parse.urlencode(form).encode() if form else None
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if form else {}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request) as response:
        body = response.read()
        return json.loads(body) if body else None


def main():
    parser = argparse.ArgumentParser(description="Move the Strava webhook to its secret callback path")
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--profile")
    args = parser.parse_args()

    prefix = terraform_output("parameter_prefix")
    names = [f"{prefix}/strava_client_id", f"{prefix}/strava_client_secret"]
    response = aws(["ssm", "get-parameters", "--with-decryption", "--names", *names], args.region, args.profile)
    values = {item["Name"].removeprefix(prefix + "/"): item["Value"] for item in response["Parameters"]}
    client_id = values["strava_client_id"]
    client_secret = values["strava_client_secret"]
    callback_url = terraform_output("webhook_callback_url")
    verify_token = terraform_output("webhook_verify_token")

    auth_query = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret})
    subscriptions = request_json(f"https://www.strava.com/api/v3/push_subscriptions?{auth_query}")
    for subscription in subscriptions:
        request_json(
            f"https://www.strava.com/api/v3/push_subscriptions/{subscription['id']}?{auth_query}",
            method="DELETE",
        )

    created = request_json("https://www.strava.com/api/v3/push_subscriptions", method="POST", form={
        "client_id": client_id,
        "client_secret": client_secret,
        "callback_url": callback_url,
        "verify_token": verify_token,
    })
    print(f"Secured Strava webhook subscription ID: {created['id']}")


if __name__ == "__main__":
    main()

