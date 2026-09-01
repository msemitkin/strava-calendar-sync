#!/usr/bin/env python3
"""One-time OAuth setup. Secrets are read locally and written directly to SSM."""

import argparse, getpass, json, subprocess, threading, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765
REDIRECT = f"http://localhost:{PORT}/callback"

def terraform_output(name):
    return subprocess.check_output(["terraform", f"-chdir=terraform", "output", "-raw", name], text=True).strip()

def oauth_code(url):
    result = {}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = query.get("code", [None])[0]
            result["error"] = query.get("error", [None])[0]
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
            self.wfile.write("Authorization received. You can close this tab.".encode())
        def log_message(self, *_): pass
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"\nOpen this URL if the browser does not open:\n{url}\n")
    webbrowser.open(url)
    server.handle_request()
    if result.get("error") or not result.get("code"): raise SystemExit(f"OAuth failed: {result.get('error', 'missing code')}")
    return result["code"]

def post_form(url, values):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(values).encode(),
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request) as response: return json.load(response)

def json_request(url, token, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response: return json.load(response) if response.length != 0 else {}

def put_parameter(name, value, region, profile):
    command = ["aws", "ssm", "put-parameter", "--name", name, "--type", "SecureString",
               "--value", value, "--overwrite", "--region", region, "--no-cli-pager"]
    if profile: command += ["--profile", profile]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--profile")
    args = parser.parse_args()
    prefix = terraform_output("parameter_prefix")
    webhook_url = terraform_output("webhook_url")
    verify_token = terraform_output("webhook_verify_token")

    strava_id = input("Strava client ID: ").strip()
    strava_secret = getpass.getpass("Strava client secret: ").strip()
    strava_auth = "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": strava_id, "redirect_uri": REDIRECT, "response_type": "code",
        "approval_prompt": "force", "scope": "read,activity:read_all"})
    strava_code = oauth_code(strava_auth)
    strava_tokens = post_form("https://www.strava.com/oauth/token", {
        "client_id": strava_id, "client_secret": strava_secret, "code": strava_code, "grant_type": "authorization_code"})

    google_id = input("Google OAuth client ID: ").strip()
    google_secret = getpass.getpass("Google OAuth client secret: ").strip()
    google_auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": google_id, "redirect_uri": REDIRECT, "response_type": "code",
        "access_type": "offline", "prompt": "consent",
        "scope": "https://www.googleapis.com/auth/calendar.app.created"})
    google_code = oauth_code(google_auth)
    google_tokens = post_form("https://oauth2.googleapis.com/token", {
        "client_id": google_id, "client_secret": google_secret, "code": google_code,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    calendar = json_request("https://www.googleapis.com/calendar/v3/calendars", google_tokens["access_token"],
                            "POST", {"summary": "Strava", "timeZone": "Europe/Kyiv"})

    values = {
        "strava_client_id": strava_id, "strava_client_secret": strava_secret,
        "strava_refresh_token": strava_tokens["refresh_token"],
        "google_client_id": google_id, "google_client_secret": google_secret,
        "google_refresh_token": google_tokens["refresh_token"], "google_calendar_id": calendar["id"]}
    for key, value in values.items(): put_parameter(f"{prefix}/{key}", str(value), args.region, args.profile)

    subscription = post_form("https://www.strava.com/api/v3/push_subscriptions", {
        "client_id": strava_id, "client_secret": strava_secret,
        "callback_url": webhook_url, "verify_token": verify_token})
    print(f"\nDone. Strava webhook subscription ID: {subscription['id']}; calendar: {calendar['id']}")

if __name__ == "__main__": main()

