#!/usr/bin/env python3
"""One-time OAuth setup. Secrets are read locally and written directly to SSM."""

import argparse, getpass, json, pathlib, subprocess, urllib.parse, urllib.request, webbrowser
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
    webhook_url = terraform_output("webhook_callback_url")
    verify_token = terraform_output("webhook_verify_token")

    strava_id = input("Strava client ID: ").strip()
    strava_secret = getpass.getpass("Strava client secret: ").strip()
    strava_auth = "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": strava_id, "redirect_uri": REDIRECT, "response_type": "code",
        "approval_prompt": "force", "scope": "read,activity:read_all"})
    strava_code = oauth_code(strava_auth)
    strava_tokens = post_form("https://www.strava.com/oauth/token", {
        "client_id": strava_id, "client_secret": strava_secret, "code": strava_code, "grant_type": "authorization_code"})

    key_path = pathlib.Path(input("Path to Google service account JSON key: ").strip()).expanduser()
    service_account = json.loads(key_path.read_text())
    required_key_fields = {"type", "client_email", "private_key", "token_uri"}
    if service_account.get("type") != "service_account" or not required_key_fields.issubset(service_account):
        raise SystemExit("The selected file is not a valid Google service account JSON key")
    calendar_id = input("Google Strava calendar ID: ").strip()
    if not calendar_id:
        raise SystemExit("Google calendar ID is required")

    values = {
        "strava_client_id": strava_id, "strava_client_secret": strava_secret,
        "strava_refresh_token": strava_tokens["refresh_token"],
        "google_service_account_json": json.dumps(service_account, separators=(",", ":")),
        "google_calendar_id": calendar_id}
    for key, value in values.items(): put_parameter(f"{prefix}/{key}", str(value), args.region, args.profile)

    subscription = post_form("https://www.strava.com/api/v3/push_subscriptions", {
        "client_id": strava_id, "client_secret": strava_secret,
        "callback_url": webhook_url, "verify_token": verify_token})
    print(f"\nDone. Strava webhook subscription ID: {subscription['id']}")
    print(f"Google Calendar: {calendar_id}")
    print(f"Service account: {service_account['client_email']}")

if __name__ == "__main__": main()
