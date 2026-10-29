"""
Gmail via OAuth2 (stdlib only — urllib). Used for both sending email and
reading supplier emails by keyword.

Flow:
  1. One-time consent (authorize_gmail.py) saves a refresh token to token.json.
  2. get_access_token() exchanges the refresh token for a short-lived access token.
  3. send() / search() call the Gmail REST API with that token.
"""
import os
import json
import base64
import urllib.parse
import urllib.request
from email.message import EmailMessage

SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"


def _token_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/
    return os.path.join(base, os.environ.get("GMAIL_TOKEN_FILE", "token.json"))


def is_configured() -> bool:
    return bool(os.environ.get("GMAIL_CLIENT_ID")) and os.path.exists(_token_path())


def _read_token() -> dict:
    with open(_token_path(), "r", encoding="utf-8") as f:
        return json.load(f)


def save_token(data: dict):
    with open(_token_path(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _post_form(url: str, form: dict) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode() or "{}")


def exchange_code(code: str) -> dict:
    """Authorization code -> tokens (includes refresh_token on first consent)."""
    return _post_form(TOKEN_URL, {
        "code": code,
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "redirect_uri": os.environ.get("GMAIL_REDIRECT", "http://localhost:8765/"),
        "grant_type": "authorization_code",
    })


def get_access_token() -> str:
    tok = _read_token()
    refresh = tok.get("refresh_token")
    if not refresh:
        raise RuntimeError("No refresh token — run authorize_gmail.py")
    res = _post_form(TOKEN_URL, {
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    })
    return res["access_token"]


def _api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode() or "{}")


def send(to: str, subject: str, body: str) -> dict:
    token = get_access_token()
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = os.environ.get("GMAIL_USER", "")
    msg["Subject"] = subject or "Vision Global"
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    data = json.dumps({"raw": raw}).encode()
    req = urllib.request.Request(f"{API}/messages/send", data=data,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode() or "{}")


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def search(keywords: list, max_per_kw: int = 10) -> list:
    """Return inbox messages matching any keyword: [{msg_id, from, subject, date, snippet}]."""
    token = get_access_token()
    seen, out = set(), []
    for kw in keywords:
        if not kw:
            continue
        q = urllib.parse.quote(kw)
        listing = _api_get(f"/messages?q={q}&maxResults={max_per_kw}", token)
        for m in listing.get("messages", []):
            mid = m["id"]
            if mid in seen:
                continue
            seen.add(mid)
            full = _api_get(f"/messages/{mid}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date", token)
            headers = full.get("payload", {}).get("headers", [])
            out.append({
                "msg_id": mid,
                "from": _header(headers, "From"),
                "subject": _header(headers, "Subject"),
                "date": _header(headers, "Date"),
                "snippet": full.get("snippet", ""),
                "keyword": kw,
            })
    return out
