"""Read supplier emails over IMAP: full body text, image attachments, reply headers.
Stdlib only (imaplib + email)."""
import os
import re
import html as _html
import email
import imaplib
from email.header import decode_header


def _strip_html(h: str) -> str:
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h or "")
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return _html.unescape(h)


def is_configured() -> bool:
    return bool(os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASS"))


def _decode(value: str) -> str:
    if not value:
        return ""
    out = ""
    for text, enc in decode_header(value):
        out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def _decode_part(part) -> str:
    try:
        return (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return ""


def _parse(msg):
    """Return (body_text, [ {filename, data, content_type} ] images). Prefers
    text/plain, falls back to stripped HTML so HTML-only emails still parse."""
    plain, html_body, images = "", "", []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                plain += _decode_part(part)
            elif ctype == "text/html" and "attachment" not in disp:
                html_body += _decode_part(part)
            elif ctype.startswith("image/"):
                data = part.get_payload(decode=True)
                if data:
                    images.append({"filename": _decode(part.get_filename() or ""), "data": data, "content_type": ctype})
    else:
        payload = _decode_part(msg)
        if msg.get_content_type() == "text/html":
            html_body = payload
        else:
            plain = payload
    body = plain.strip() or _strip_html(html_body).strip()
    return body, images


def _to_dict(msg, num, keyword=None):
    body, images = _parse(msg)
    return {
        "msg_id": msg.get("Message-ID", "") or f"imap-{num}",
        "from": _decode(msg.get("From", "")),
        "subject": _decode(msg.get("Subject", "")),
        "date": msg.get("Date", ""),
        "in_reply_to": (msg.get("In-Reply-To", "") or "").strip(),
        "body": body,
        "snippet": body[:300],
        "images": images,
        "keyword": keyword,
    }


def _connect():
    M = imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"), int(os.environ.get("IMAP_PORT", 993)))
    M.login(os.environ["IMAP_USER"], os.environ["IMAP_PASS"])
    M.select("INBOX")
    return M


def search(keywords: list, max_per_kw: int = 15) -> list:
    """Messages matching any keyword (subject/body)."""
    M = _connect()
    seen, out = set(), []
    try:
        for kw in keywords:
            kw = (kw or "").strip()
            if not kw:
                continue
            typ, data = M.search(None, "X-GM-RAW", f'"{kw}"')
            if typ != "OK" or not data or not data[0]:
                typ, data = M.search(None, "OR", "SUBJECT", f'"{kw}"', "BODY", f'"{kw}"')
            ids = (data[0].split() if data and data[0] else [])[-max_per_kw:]
            for num in reversed(ids):
                typ, md = M.fetch(num, "(RFC822)")
                if typ != "OK" or not md or not md[0]:
                    continue
                msg = email.message_from_bytes(md[0][1])
                mid = msg.get("Message-ID", "") or f"imap-{num.decode()}"
                if mid in seen:
                    continue
                seen.add(mid)
                out.append(_to_dict(msg, num.decode(), kw))
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def find_replies(request_msgids: list) -> list:
    """Messages that are replies (In-Reply-To) to any of the given sent message-ids."""
    out = []
    ids = [r for r in (request_msgids or []) if r]
    if not ids:
        return out
    M = _connect()
    try:
        for rid in ids:
            typ, data = M.search(None, "HEADER", "In-Reply-To", rid)
            nums = (data[0].split() if typ == "OK" and data and data[0] else [])
            for num in nums:
                typ, md = M.fetch(num, "(RFC822)")
                if typ != "OK" or not md or not md[0]:
                    continue
                msg = email.message_from_bytes(md[0][1])
                d = _to_dict(msg, num.decode())
                d["reply_to_request"] = rid
                out.append(d)
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def search_from(addr: str, limit: int = 10) -> list:
    """Recent messages received FROM a given address (for buyer replies)."""
    if not addr:
        return []
    M = _connect()
    out = []
    try:
        typ, data = M.search(None, "FROM", f'"{addr}"')
        nums = (data[0].split() if typ == "OK" and data and data[0] else [])[-limit:]
        for num in reversed(nums):
            typ, md = M.fetch(num, "(RFC822)")
            if typ != "OK" or not md or not md[0]:
                continue
            out.append(_to_dict(email.message_from_bytes(md[0][1]), num.decode()))
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return out


def test_login() -> dict:
    if not is_configured():
        return {"ok": False, "detail": "IMAP not configured."}
    try:
        M = imaplib.IMAP4_SSL(os.environ.get("IMAP_HOST", "imap.gmail.com"), int(os.environ.get("IMAP_PORT", 993)))
        M.login(os.environ["IMAP_USER"], os.environ["IMAP_PASS"])
        M.logout()
        return {"ok": True, "detail": "IMAP login OK."}
    except Exception as e:
        return {"ok": False, "detail": f"IMAP: {e}"}
