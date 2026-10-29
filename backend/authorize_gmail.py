"""
One-time Gmail OAuth consent. Run once:

    .venv\\Scripts\\python.exe authorize_gmail.py

Opens your browser to Google's consent screen for general@etexusa.com.
After you click Allow, the refresh token is saved to token.json and email
sending + keyword inbox search go live.

NOTE: the OAuth client must allow the redirect  http://localhost:8765/
(Desktop-app clients allow loopback automatically; for a Web client, add that
URI under "Authorized redirect URIs" in Google Cloud Console).
"""
import os
import sys
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
from app.integrations.gmail import SCOPES, exchange_code, save_token  # noqa: E402

REDIRECT = os.environ.get("GMAIL_REDIRECT", "http://localhost:8765/")
PORT = int(urllib.parse.urlparse(REDIRECT).port or 8765)
_code = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if "code" in params:
            _code["value"] = params["code"][0]
            self.wfile.write(b"<h2>Vision Global - authorized.</h2>You can close this tab and return to the app.")
        else:
            self.wfile.write(b"<h2>Authorization failed.</h2>" + qs.encode())

    def log_message(self, *a):
        pass


def main():
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": os.environ.get("GMAIL_USER", ""),
    })
    print("Opening browser for consent…")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"Waiting for Google to redirect to {REDIRECT} …")
    while "value" not in _code:
        server.handle_request()
    tokens = exchange_code(_code["value"])
    if "refresh_token" not in tokens:
        print("ERROR: no refresh_token returned:", tokens)
        sys.exit(1)
    save_token(tokens)
    print("SUCCESS: token.json saved. Gmail is connected.")


if __name__ == "__main__":
    main()
