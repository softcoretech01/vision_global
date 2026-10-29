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
    WA_TEMPLATE_LANG (default "en")  -> language of approved Meta templates

WhatsApp only delivers free text to a number that messaged us in the last 24 hours.
Outside that window (Meta) we send the approved template named in the app template's
`wa_template`, filling its named {{placeholders}} from the same values as the body.
"""
import os
import re
import json
import time
import uuid
import base64
import mimetypes
import smtplib
import urllib.request
import urllib.parse
import urllib.error
from email.message import EmailMessage
from email.utils import make_msgid
from dotenv import load_dotenv
from . import gmail
from .. import storage
from ..db import prop_engine, one


# backend/.env, re-read whenever it changes so a new WA_TOKEN (Meta tokens expire) or
# SMTP setting works straight away, without restarting the server.
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
_env_mtime = [None]


def _fresh_env():
    try:
        m = os.path.getmtime(ENV_PATH)
    except OSError:
        return
    if m != _env_mtime[0]:
        load_dotenv(ENV_PATH, override=True)
        _env_mtime[0] = m


# ----------------------------- Email -----------------------------
def email_ready() -> bool:
    """True when email really sends (Gmail OAuth or SMTP), not just simulates."""
    _fresh_env()
    return gmail.is_configured() or bool(os.environ.get("SMTP_HOST"))


def pick_channel(channel: str, phone: str) -> str:
    """The channel to actually use for a buyer: their own, except that an email buyer
    with a phone number goes to WhatsApp while email isn't set up (it'd only simulate)."""
    channel = channel or "email"
    if channel == "email" and not email_ready() and _digits(phone):
        return "whatsapp"
    return channel


EMAIL_MAX_PHOTOS = 5
EMAIL_MAX_BYTES = 15 * 1024 * 1024   # keep well under Gmail's 25 MB message limit


def _email_attachments(urls: list) -> list:
    """Our own photo files (/uploads/... URLs or paths) as email attachments:
    [(filename, maintype, subtype, data)], capped in count and total size."""
    out, total = [], 0
    for url in (urls or [])[:EMAIL_MAX_PHOTOS]:
        path = url if os.path.isfile(url or "") else _local_upload(url)
        if not path:
            continue
        size = os.path.getsize(path)
        if total + size > EMAIL_MAX_BYTES:
            break
        ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
        maintype, subtype = ctype.split("/", 1)
        with open(path, "rb") as fh:
            out.append((f"photo-{len(out) + 1}{os.path.splitext(path)[1] or '.jpg'}", maintype, subtype, fh.read()))
        total += size
    return out


def send_email(to: str, subject: str, body: str, attachments: list = None) -> dict:
    """Send an email. `attachments` = photo URLs/paths (our own uploads) to attach."""
    _fresh_env()
    files = _email_attachments(attachments)
    # Prefer Gmail OAuth when connected.
    if gmail.is_configured() and to:
        try:
            gmail.send(to, subject, body, files)
            print(f"[EMAIL · gmail-sent] -> {to} | {subject}{f' (+{len(files)} photo(s))' if files else ''}")
            return {"ok": True, "simulated": False, "channel": "email", "via": "gmail", "attached": len(files)}
        except Exception as e:
            print(f"[EMAIL · gmail-error] -> {to}: {e}")
            return {"ok": False, "simulated": False, "channel": "email", "error": str(e)}

    host = os.environ.get("SMTP_HOST")
    if not host or not to:
        print(f"[EMAIL · simulated] -> {to} | {subject}{f' (+{len(files)} photo(s))' if files else ''}")
        return {"ok": True, "simulated": True, "channel": "email", "attached": len(files)}
    msgid = make_msgid()
    try:
        msg = EmailMessage()
        msg["Message-ID"] = msgid
        msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@etex.in"
        msg["To"] = to
        msg["Subject"] = subject or "Vision Global"
        msg.set_content(body)
        for fname, maintype, subtype, data in files:
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
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
        print(f"[EMAIL · sent] -> {to} | {subject}{f' (+{len(files)} photo(s))' if files else ''}")
        return {"ok": True, "simulated": False, "channel": "email", "message_id": msgid, "attached": len(files)}
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
    _fresh_env()
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


# Named template placeholders, in the order they first appear: {{buyer}}, {{machine}}…
PARAM_RE = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")


def wa_window_open(to: str) -> bool:
    """True if this number sent us a WhatsApp message in the last 24 hours (5-minute
    safety margin), i.e. free-text messages to it will be delivered."""
    d = _digits(to)
    if not d:
        return False
    try:
        return bool(one(prop_engine,
                        "SELECT 1 FROM wa_contacts WHERE phone10=RIGHT(:ph,10) AND last_inbound_at > NOW() - INTERVAL 1435 MINUTE",
                        {"ph": d}))
    except Exception:
        return False


def wa_template(tpl: dict, mapping: dict):
    """Build the Meta template spec for an app template row, or None if it has no
    approved WhatsApp template. Parameters are named after the body's placeholders,
    so the Meta template must use the same {{names}} as the app template body."""
    name = ((tpl or {}).get("wa_template") or "").strip()
    if not name:
        return None
    names = list(dict.fromkeys(PARAM_RE.findall(tpl.get("body") or "")))
    params = []
    for n in names:
        # Meta rejects empty values and newlines/tabs inside a parameter.
        val = re.sub(r"\s+", " ", str((mapping or {}).get(n) or "")).strip() or "-"
        params.append({"type": "text", "parameter_name": n, "text": val[:1000]})
    values = {k: re.sub(r"\s+", " ", str(v if v is not None else "")).strip() for k, v in (mapping or {}).items()}
    return {"name": name,
            "lang": (tpl.get("wa_lang") or os.environ.get("WA_TEMPLATE_LANG") or "en").strip(),
            "params": params, "values": values}


_tpl_info_cache = {}   # (name, lang) -> (info, fetched_at)
ANY_PARAM_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def wa_template_info(name: str, lang: str):
    """The approved template's shape, read from Meta (cached for an hour): header type,
    body variable names, quick-reply button texts and approval status. None when it
    can't be read (no WA_WABA_ID / API error) — then only body parameters are sent."""
    _fresh_env()
    key = (name, lang)
    hit = _tpl_info_cache.get(key)
    if hit and time.time() - hit[1] < 3600:
        return hit[0]
    waba, token = os.environ.get("WA_WABA_ID"), os.environ.get("WA_TOKEN")
    if not (waba and token and name):
        return None
    ver = os.environ.get("WA_API_VERSION", "v21.0")
    url = (f"https://graph.facebook.com/{ver}/{waba}/message_templates?"
           + urllib.parse.urlencode({"name": name, "fields": "name,language,status,components", "limit": 50}))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}), timeout=20) as r:
            rows = [t for t in json.loads(r.read().decode() or "{}").get("data", []) if t.get("name") == name]
    except Exception as e:
        print(f"[WHATSAPP · template-info-error] {name}: {e}")
        return None
    if not rows:
        info = {"found": False}
    else:
        t = next((x for x in rows if x.get("language") == lang), rows[0])
        comps = {c.get("type"): c for c in t.get("components", [])}
        body_names = list(dict.fromkeys(ANY_PARAM_RE.findall((comps.get("BODY") or {}).get("text") or "")))
        info = {"found": True, "status": t.get("status"), "language": t.get("language"),
                "header": (comps.get("HEADER") or {}).get("format"),
                "body_params": body_names,
                "positional": all(n.isdigit() for n in body_names) and bool(body_names),
                "buttons": [b.get("text") or "" for b in (comps.get("BUTTONS") or {}).get("buttons", [])
                            if b.get("type") == "QUICK_REPLY"]}
    _tpl_info_cache[key] = (info, time.time())
    return info


def _media_object(url_or_path: str) -> dict:
    """Image for a Meta message: our own files are uploaded, anything else is a link."""
    path = url_or_path if os.path.isfile(url_or_path or "") else _local_upload(url_or_path)
    return {"id": wa_upload_media(path)} if path else {"link": url_or_path}


def _button_payloads(template_buttons: list, buttons: list) -> list:
    """Give each of the template's quick-reply buttons the id of our matching button
    (by title, then by meaning, then by position), so a tap comes back as 'q:<ref>:<action>'."""
    out = []
    for i, text in enumerate(template_buttons):
        t = (text or "").lower()
        match = next((bid for bid, title in buttons if title.lower() == t), None)
        if not match:
            want = "not_interested" if "not" in t else "photos" if ("photo" in t or "image" in t) else "interested" if "interest" in t else None
            match = next((bid for bid, _ in buttons if want and bid.endswith(":" + want)), None)
        if not match and i < len(buttons):
            match = buttons[i][0]
        if match:
            out.append({"type": "button", "sub_type": "quick_reply", "index": str(i),
                        "parameters": [{"type": "payload", "payload": match[:256]}]})
    return out


def _wa_error(e, detail: str) -> str:
    """Meta's rejection as a message people can act on (raw details stay in the log)."""
    try:
        err = json.loads(detail).get("error", {})
    except Exception:
        err = {}
    code = err.get("code")
    if code == 190:
        return "WhatsApp access token has expired. Put a new WA_TOKEN in backend/.env (no restart needed)."
    if code == 131030:
        return "This number isn't in the WhatsApp test number's allowed list (Meta app → WhatsApp → API Setup → To)."
    if code == 131047:
        return "The buyer hasn't messaged in 24 hours, so WhatsApp only allows an approved template here."
    return f"{err.get('message') or e} (code {code})" if code else f"{e} {detail}"


def send_whatsapp(to: str, body: str, template: dict = None, buttons: list = None, header_image: str = None) -> dict:
    """Send a WhatsApp message. `buttons` = [(id, title), ...] (max 3, title <= 20 chars)
    turns a Meta text message into an interactive one with reply buttons; a tap comes
    back to the webhook carrying that id. When the approved template is used (outside
    the 24h window), `buttons` ids become its quick-reply payloads and `header_image`
    (else WA_FALLBACK_IMAGE) fills an image header."""
    _fresh_env()
    provider = (os.environ.get("WA_PROVIDER") or "meta").lower()
    token = os.environ.get("WA_TOKEN")
    phone_id = os.environ.get("WA_PHONE_ID")
    tw_sid = os.environ.get("TWILIO_SID")

    # Outside the 24h window free text is dropped by Meta, so use the approved template.
    window = wa_window_open(to)
    use_template = bool(template) and provider == "meta" and not window
    use_buttons = bool(buttons) and provider == "meta" and not use_template
    info = {"kind": "template" if use_template else ("buttons" if use_buttons else "text"),
            "window_closed": not window and not use_template}

    # No creds for the selected provider -> simulate.
    configured = (provider == "meta" and token and phone_id) or (provider == "twilio" and tw_sid)
    if not configured or not to:
        what = f"template:{template['name']}" if use_template else info["kind"]
        print(f"[WHATSAPP · simulated/{what}] -> {to} | {str(body)[:60]}")
        return {"ok": True, "simulated": True, "channel": "whatsapp", **info}

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
            payload = {"messaging_product": "whatsapp", "to": _digits(to)}
            if use_template:
                tmpl = {"name": template["name"], "language": {"code": template["lang"]}}
                tinfo = wa_template_info(template["name"], template["lang"]) or {}
                params = template["params"]
                if tinfo.get("found"):
                    # Send exactly the variables the approved template has (Meta rejects extras).
                    vals = template.get("values") or {}
                    if tinfo["positional"]:
                        params = [{"type": "text", "text": p["text"]} for p in params][:len(tinfo["body_params"])]
                    else:
                        params = [{"type": "text", "parameter_name": n, "text": (vals.get(n) or "-")[:1000]}
                                  for n in tinfo["body_params"]]
                comps = []
                if tinfo.get("header") == "IMAGE":
                    img = header_image or os.environ.get("WA_FALLBACK_IMAGE")
                    if img:
                        comps.append({"type": "header", "parameters": [{"type": "image", "image": _media_object(img)}]})
                        info["header_image"] = img
                if params:
                    comps.append({"type": "body", "parameters": params})
                if tinfo.get("buttons") and buttons:
                    comps += _button_payloads(tinfo["buttons"], buttons)
                if comps:
                    tmpl["components"] = comps
                payload.update({"type": "template", "template": tmpl})
            elif use_buttons:
                payload.update({"type": "interactive", "interactive": {
                    "type": "button",
                    "body": {"text": body[:1024]},
                    "action": {"buttons": [{"type": "reply", "reply": {"id": bid[:256], "title": title[:20]}}
                                           for bid, title in buttons[:3]]},
                }})
            else:
                payload.update({"type": "text", "text": {"body": body}})
            resp = _post_json(url, payload, {"Authorization": f"Bearer {token}"})
            msgs = resp.get("messages") if isinstance(resp, dict) else None
            msgid = msgs[0].get("id") if msgs else None
        print(f"[WHATSAPP · sent/{provider}/{info['kind']}] -> {to}")
        return {"ok": True, "simulated": False, "channel": "whatsapp", "message_id": msgid, **info}
    except urllib.error.HTTPError as e:
        # Meta explains rejections (bad template name/params, etc.) in the response body.
        detail = e.read().decode(errors="replace")[:500]
        print(f"[WHATSAPP · error] -> {to}: {e} {detail}")
        return {"ok": False, "simulated": False, "channel": "whatsapp", "error": _wa_error(e, detail), **info}
    except Exception as e:
        print(f"[WHATSAPP · error] -> {to}: {e}")
        return {"ok": False, "simulated": False, "channel": "whatsapp", "error": str(e), **info}



# Meta media ids stay valid for 30 days; re-upload a file after a day to be safe.
_media_cache = {}   # local path -> (media_id, uploaded_at)


def _local_upload(url: str):
    """Our own /uploads/<file> URL -> the file on disk (Meta can't reach localhost)."""
    m = re.search(r"/uploads/([^/?#]+)$", url or "")
    if m:
        path = os.path.join(storage.UPLOAD_DIR, m.group(1))
        if os.path.isfile(path):
            return path
    return None


def wa_upload_media(path: str) -> str:
    """Upload a local image to the Meta Cloud API and return its media id."""
    _fresh_env()
    hit = _media_cache.get(path)
    if hit and time.time() - hit[1] < 86400:
        return hit[0]
    ver = os.environ.get("WA_API_VERSION", "v21.0")
    ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as fh:
        data = fh.read()
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    parts = []
    for name, val in (("messaging_product", "whatsapp"), ("type", ctype)):
        parts += [f"--{boundary}".encode(), f'Content-Disposition: form-data; name="{name}"'.encode(), b"", val.encode()]
    parts += [f"--{boundary}".encode(),
              f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"'.encode(),
              f"Content-Type: {ctype}".encode(), b"", data, f"--{boundary}--".encode(), b""]
    body = crlf.join(parts)
    req = urllib.request.Request(
        f"https://graph.facebook.com/{ver}/{os.environ.get('WA_PHONE_ID')}/media", data=body, method="POST",
        headers={"Authorization": f"Bearer {os.environ.get('WA_TOKEN')}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        media_id = json.loads(r.read().decode() or "{}").get("id")
    if not media_id:
        raise RuntimeError("Meta returned no media id")
    _media_cache[path] = (media_id, time.time())
    return media_id


def send_whatsapp_image(to: str, url: str, caption: str = "") -> dict:
    """Send one photo on WhatsApp (Meta). Our own uploads are pushed to Meta first;
    any other URL is sent as a link Meta fetches itself."""
    _fresh_env()
    token, phone_id = os.environ.get("WA_TOKEN"), os.environ.get("WA_PHONE_ID")
    provider = (os.environ.get("WA_PROVIDER") or "meta").lower()
    if provider != "meta" or not (token and phone_id) or not to:
        print(f"[WHATSAPP · simulated/image] -> {to} | {url}")
        return {"ok": True, "simulated": True, "channel": "whatsapp", "kind": "image"}
    try:
        path = _local_upload(url)
        image = {"id": wa_upload_media(path)} if path else {"link": url}
        if caption:
            image["caption"] = caption[:1024]
        ver = os.environ.get("WA_API_VERSION", "v21.0")
        resp = _post_json(f"https://graph.facebook.com/{ver}/{phone_id}/messages",
                          {"messaging_product": "whatsapp", "to": _digits(to), "type": "image", "image": image},
                          {"Authorization": f"Bearer {token}"})
        msgs = resp.get("messages") if isinstance(resp, dict) else None
        print(f"[WHATSAPP · sent/meta/image] -> {to}")
        return {"ok": True, "simulated": False, "channel": "whatsapp", "kind": "image",
                "message_id": msgs[0].get("id") if msgs else None}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        print(f"[WHATSAPP · image-error] -> {to}: {e} {detail}")
        return {"ok": False, "simulated": False, "channel": "whatsapp", "kind": "image", "error": _wa_error(e, detail)}
    except Exception as e:
        print(f"[WHATSAPP · image-error] -> {to}: {e}")
        return {"ok": False, "simulated": False, "channel": "whatsapp", "kind": "image", "error": str(e)}


def dispatch(channel: str, to: str, subject: str, body: str, tpl: dict = None, mapping: dict = None,
             buttons: list = None, header_image: str = None, attachments: list = None) -> dict:
    """Send on the given channel. Pass the app template row + its values so WhatsApp
    can fall back to the approved Meta template outside the 24-hour window, and
    optional WhatsApp reply `buttons` / template `header_image`, or email photo `attachments`."""
    if channel == "whatsapp":
        return send_whatsapp(to, body, wa_template(tpl, mapping), buttons, header_image)
    return send_email(to, subject, body, attachments)
