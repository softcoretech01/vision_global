"""Manual fallback: exchange an authorization code for a refresh token.

If the browser redirect didn't reach the local listener, copy the FULL URL from
the browser address bar after clicking Allow (it looks like
http://localhost:8765/?code=4/XXXX&scope=...) and run:

    .venv\\Scripts\\python.exe exchange_code.py "<paste full URL or just the code>"
"""
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv()
from app.integrations.gmail import exchange_code, save_token  # noqa: E402

if len(sys.argv) < 2:
    print("Usage: exchange_code.py <code-or-redirect-url>")
    sys.exit(1)

arg = sys.argv[1].strip()
if arg.startswith("http"):
    qs = urllib.parse.urlparse(arg).query
    code = urllib.parse.parse_qs(qs).get("code", [""])[0]
else:
    code = arg

if not code:
    print("No code found in the argument.")
    sys.exit(1)

tokens = exchange_code(code)
if "refresh_token" not in tokens:
    print("ERROR: no refresh_token in response:", tokens)
    sys.exit(1)
save_token(tokens)
print("SUCCESS: token.json saved. Gmail connected.")
