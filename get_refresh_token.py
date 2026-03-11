"""OAuth2 helper to obtain a Google Ads API refresh token.

Prerequisites:
  1. Go to https://console.cloud.google.com/apis/library/googleads.googleapis.com
     and enable the Google Ads API for your project.
  2. Go to https://console.cloud.google.com/apis/credentials
     and create an OAuth 2.0 Client ID (type: Desktop app).
  3. Copy the Client ID and Client Secret.

Usage:
  uv run python get_refresh_token.py
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

SCOPES = ["https://www.googleapis.com/auth/adwords"]
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main():
    print("\n=== Google Ads OAuth2 Refresh Token Helper ===\n")

    client_id = input("Client ID: ").strip()
    if not client_id:
        print("Error: Client ID is required.")
        sys.exit(1)

    client_secret = input("Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required.")
        sys.exit(1)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print(f"\nOpening browser for authorization...\n")
    print(f"If it doesn't open, visit this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to catch the callback
    auth_code = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = parse_qs(urlparse(self.path).query)

            if "error" in query:
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization failed.</h1><p>You can close this tab.</p>")
                print(f"\nError: {query['error'][0]}")
                return

            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab and return to your terminal.</p>")

        def log_message(self, format, *args):
            pass  # Suppress request logging

    server = HTTPServer(("localhost", 8080), CallbackHandler)
    print("Waiting for authorization callback on http://localhost:8080 ...")
    server.handle_request()

    if not auth_code:
        print("Error: No authorization code received.")
        sys.exit(1)

    # Exchange code for tokens
    print("\nExchanging authorization code for tokens...")
    resp = requests.post(TOKEN_URL, data={
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        print(f"Error: Token exchange failed.\n{resp.text}")
        sys.exit(1)

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print(f"Error: No refresh token in response.\n{json.dumps(tokens, indent=2)}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("SUCCESS! Here's your refresh token:\n")
    print(f"  {refresh_token}")
    print(f"\nAdd it to your .env file:")
    print(f"  GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
