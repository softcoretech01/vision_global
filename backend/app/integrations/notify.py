"""
Email + WhatsApp dispatch.

Real sending is used when the matching provider credentials are present in
.env; otherwise the message is SIMULATED (logged) so the app works offline.
Uses only the Python standard library (smtplib / urllib) — no extra installs.

Env:
  Email (SMTP):   SMTP_HOST, SMTP_PORT(587), SMTP_USER, SMTP_PASS, SMTP_FROM
  WhatsApp:       WA_PROVIDER = "meta" (default) | "twilio"
    meta   -> WA_TOKEN, WA_PHONE_ID            (Meta WhatsApp Cloud API)
    twilio -> TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM   (e.g. whatsapp:+14155238886)
"""
import os
import re
import json
import base64
import smtplib
import urllib.request
import urllib.parse
from email.message import EmailMessage
from email.utils import make_msgid
from . import gmail


# ----------------------------- Email -----------------------------
def send_email(to: str, subject: str, body: str) -> dict:
    # Prefer Gmail OAuth when connected.
    if gmail.is_configured() and to:
        try:
            gmail.send(to, subject, body)
            print(f"[EMAIL · gmail-sent] -> {to} | {subject}")
            return {"ok": True, "simulated": False, "channel": "email", "via": "gmail"}
        except Exception as e:
            print(f"[EMAIL · gmail-error] -> {to}: {e}")
            return {"ok": False, "simulated": False, "channel": "email", "error": str(e)}

    host = os.environ.get("SMTP_HOST")
    if not host or not to:
        print(f"[EMAIL · simulated] -> {to} | {subject}")
        return {"ok": True, "simulated": True, "channel": "email"}
    msgid = make_msgid()
    try:
        msg = EmailMessage()
        msg["Message-ID"] = msgid
        msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@etex.in"
        msg["To"] = to
        msg["Subject"] = subject or "Vision Global"
        msg.set_content(body)
        port = int(os.environ.get("SMTP_PORT", 587))
        user = os.environ.get("SMTP_USER")
        pwd = os.environ.get("SMTP_PASS", "")
        if port == 465:
            s = smtplib.SMTP_SSL(host, port, timeout=20, local_hostname="localhost")
        else:
            s = smtplib.SMTP(host, port, timeout=20, local_hostname="localhost")
            s.ehlo()
            s.starttls()
            s.ehlo()
        try:
            if user:
                s.login(user, pwd)
            s.send_message(msg)
        finally:
            s.quit()
        print(f"[EMAIL · sent] -> {to} | {subject}")
        return {"ok": True, "simulated": False, "channel": "email", "message_id": msgid}
    except Exception as e:
        print(f"[EMAIL · error] -> {to}: {e}")
        return {"ok": False, "simulated": False, "channel": "email", "error": str(e)}


# --------------------------- WhatsApp ----------------------------
def _digits(num: str) -> str:
    return re.sub(r"\D", "", num or "")


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode() or "{}")


def _post_form(url: str, form: dict, headers: dict) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode() or "{}")


def wa_download_media(media_id: str) -> tuple:
    """Meta Cloud API media is a two-step fetch: resolve the media-id to a short-lived
    URL, then download the bytes with the same bearer token. Returns (data, content_type)."""
    token = os.environ.get("WA_TOKEN")
    ver = os.environ.get("WA_API_VERSION", "v21.0")
    if not token or not media_id:
        return b"", ""
    meta_req = urllib.request.Request(
        f"https://graph.facebook.com/{ver}/{media_id}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(meta_req, timeout=20) as r:
        info = json.loads(r.read().decode() or "{}")
    url = info.get("url")
    if not url:
        return b"", info.get("mime_type", "")
    dl_req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(dl_req, timeout=30) as r:
        return r.read(), (r.headers.get("Content-Type") or info.get("mime_type") or "")


def send_whatsapp(to: str, body: str) -> dict:
    provider = (os.environ.get("WA_PROVIDER") or "meta").lower()
    token = os.environ.get("WA_TOKEN")
    phone_id = os.environ.get("WA_PHONE_ID")
    tw_sid = os.environ.get("TWILIO_SID")

    # No creds for the selected provider -> simulate.
    configured = (provider == "meta" and token and phone_id) or (provider == "twilio" and tw_sid)
    if not configured or not to:
        print(f"[WHATSAPP · simulated] -> {to} | {str(body)[:60]}")
        return {"ok": True, "simulated": True, "channel": "whatsapp"}

    try:
        msgid = None
        if provider == "twilio":
            sid = tw_sid
            auth = base64.b64encode(f"{sid}:{os.environ.get('TWILIO_TOKEN','')}".encode()).decode()
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
            resp = _post_form(url, {
                "From": os.environ.get("TWILIO_FROM", ""),
                "To": f"whatsapp:+{_digits(to)}",
                "Body": body,
            }, {"Authorization": f"Basic {auth}"})
            msgid = resp.get("sid")
        else:  # meta WhatsApp Cloud API
            ver = os.environ.get("WA_API_VERSION", "v21.0")
            url = f"https://graph.facebook.com/{ver}/{phone_id}/messages"
            resp = _post_json(url, {
                "messaging_product": "whatsapp",
                "to": _digits(to),
                "type": "text",
                "text": {"body": body},
            }, {"Authorization": f"Bearer {token}"})
            msgs = resp.get("messages") if isinstance(resp, dict) else None
            msgid = msgs[0].get("id") if msgs else None
        print(f"[WHATSAPP · sent/{provider}] -> {to}")
        return {"ok": True, "simulated": False, "channel": "whatsapp", "message_id": msgid}
    except Exception as e:
        print(f"[WHATSAPP · error] -> {to}: {e}")
        return {"ok": False, "simulated": False, "channel": "whatsapp", "error": str(e)}


def dispatch(channel: str, to: str, subject: str, body: str) -> dict:
    return send_whatsapp(to, body) if channel == "whatsapp" else send_email(to, subject, body)
