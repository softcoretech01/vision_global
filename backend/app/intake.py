"""Shared supplier-email intake:
  - keyword search -> create one proposal row PER MACHINE (parse machine name + price)
  - save image attachments -> Photos column
  - detect replies to our photo-request emails -> auto-attach the photos
Used by the manual /proposals/fetch-emails endpoint and the auto scheduler."""
import re
import json
from email.utils import parsedate_to_datetime
from datetime import datetime
from .db import prop_engine, admin_engine, q, one, execute
from .integrations import gmail, imap_fetch
from .integrations.notify import dispatch
from .templating import get_template, render
from . import storage


def _ts(val):
    """Best-effort epoch seconds from an email Date header or a DB datetime string."""
    if not val:
        return None
    try:
        if isinstance(val, datetime):
            return val.timestamp()
        d = parsedate_to_datetime(val)        # email Date header
        return d.timestamp()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(val).replace("T", " ")).timestamp()
    except Exception:
        return None


def _handle_buyer_replies():
    """Log buyer replies into chat history — only emails received AFTER the buyer's
    latest quotation was sent (so old/stale replies don't reappear). Matched by sender."""
    if not imap_fetch.is_configured():
        return 0
    buyers = q(prop_engine, """
        SELECT b.id bid, b.email, UNIX_TIMESTAMP(MAX(qt.sent_at)) floor_ts
        FROM quotations qt JOIN buyers b ON b.id=qt.buyer_id
        WHERE b.email IS NOT NULL AND b.email <> ''
        GROUP BY b.id, b.email
    """)
    n = 0
    for r in buyers:
        floor = float(r["floor_ts"]) if r.get("floor_ts") else None
        try:
            msgs = imap_fetch.search_from(r["email"], 10)
        except Exception:
            continue
        for m in msgs:
            mts = _ts(m.get("date"))
            if floor and mts and mts < floor - 60:   # older than this quotation → skip
                continue
            if one(prop_engine, "SELECT id FROM chat_messages WHERE source_msg_id=:mid", {"mid": m["msg_id"]}):
                continue
            body = (m.get("body") or m.get("snippet") or "(message)")[:4000]
            execute(prop_engine,
                    "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:bid,'email','in',:b,:mid)",
                    {"bid": r["bid"], "b": body, "mid": m["msg_id"]})
            n += 1
    return n


def process_followups():
    """Send due follow-ups (daily = 24h after quotation, weekly = 7 days), then reschedule."""
    due = q(prop_engine, """
        SELECT f.id fid, f.frequency, qt.buyer_id, qt.machine, qt.amount, qt.channel, qt.enquiry_id,
               b.name buyer_name, b.email, b.phone
        FROM followups f
        JOIN quotations qt ON qt.id=f.quotation_id
        JOIN buyers b ON b.id=qt.buyer_id
        WHERE f.frequency IN ('daily','weekly') AND f.next_run IS NOT NULL AND f.next_run <= NOW()
    """)
    n = 0
    for f in due:
        channel = f["channel"] or "email"
        to = f["phone"] if channel == "whatsapp" else f["email"]
        qty = 1
        if f.get("enquiry_id"):
            e = one(prop_engine, "SELECT quantity FROM enquiries WHERE id=:id", {"id": f["enquiry_id"]})
            if e and e.get("quantity"):
                qty = int(e["quantity"])
        amount = float(f["amount"] or 0)
        unit, total = f"₹{amount:,.0f}", f"₹{amount * qty:,.0f}"
        tpl = get_template("followup", channel)
        mapping = {"buyer": f["buyer_name"], "machine": f["machine"], "qty": qty,
                   "price": unit, "amount": unit, "total": total, "supplier": ""}
        subject = render(tpl["subject"], mapping) if tpl and tpl.get("subject") else f"Following up on your {f['machine']} quotation"
        body = render(tpl["body"], mapping) if tpl else f"Hi {f['buyer_name']}, following up on the {f['machine']} quotation."
        dispatch(channel, to, subject, body)
        execute(prop_engine,
                "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('buyer',:bid,:ch,'out',:b)",
                {"bid": f["buyer_id"], "ch": channel, "b": body})
        delta = "INTERVAL 1 DAY" if f["frequency"] == "daily" else "INTERVAL 7 DAY"
        execute(prop_engine, f"UPDATE followups SET next_run=DATE_ADD(NOW(), {delta}), last_sent_at=NOW() WHERE id=:id", {"id": f["fid"]})
        n += 1
    return n

# "Machine name: <X>" — matches anywhere on a line (so a subject-only quote like
# "Machine name CNC machine Price : 105999" still parses), capturing up to the next
# "Price" clause or end of line so the price never leaks into the machine name.
# Machine line: handles "Machine name:" and plural "Machine names:"; stops before a
# "price" clause or end of line so the price never leaks into the machine name.
MACHINE_RE = re.compile(r"(?im)\bmachine\s+names?\b\s*[:;=\-]?\s*(.+?)\s*(?=\bprice\b|$)")
# Price line: handles "Price:", "Machine price:" and loose separators (:, ;, =, -).
# Captures the REST of the line (not just the first number) so a comma+space list
# like "120000, 569000" is kept whole; individual numbers are pulled out with NUM_RE.
PRICE_RE = re.compile(r"(?im)\b(?:machine\s+)?prices?\b\s*[:;=\-]?\s*(.+)")
# One numeric token, keeping its own comma/dot grouping (e.g. 1,05,999 or 569000).
NUM_RE = re.compile(r"[0-9][0-9,\.]*")


def parse_from(frm: str):
    m = re.search(r"<([^>]+)>", frm or "")
    email = (m.group(1) if m else frm or "").strip()
    name = re.sub(r"<[^>]+>", "", frm or "").strip().strip('"') or email
    return name, email


def _to_number(s: str):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def known_machine_names():
    """Active Machine / Model / Make names (the master vocabulary), longest first so
    a specific "Somet Rapier" is matched before a bare "Somet". Used to recognize a
    machine in a supplier message that has no explicit "Machine name:" line."""
    names = []
    for tbl in ("machines", "models", "machine_makes"):
        try:
            for r in q(admin_engine, f"SELECT name FROM {tbl} WHERE active=1"):
                n = (r.get("name") or "").strip()
                if len(n) >= 3:
                    names.append(n)
        except Exception:
            pass
    seen, uniq = set(), []
    for n in sorted(names, key=len, reverse=True):
        k = n.lower()
        if k not in seen:
            seen.add(k); uniq.append(n)
    return uniq


def _find_known_machines(text: str, known):
    """Known master names present in `text`, in order of appearance, de-overlapped
    (a longer match wins over a shorter one it contains). Matches on word-ish
    boundaries so 'CNC' doesn't fire inside 'CNCfoo'."""
    low = (text or "").lower()
    hits = []
    for name in known:                       # known is pre-sorted longest-first
        nl = name.lower()
        start = 0
        while True:
            i = low.find(nl, start)
            if i < 0:
                break
            before = low[i - 1] if i > 0 else " "
            after = low[i + len(nl)] if i + len(nl) < len(low) else " "
            # Left edge: ok unless glued to a letter — but allow a quantity prefix
            # like "1x" / "10x" (common supplier shorthand, e.g. "1xSulzer Projectile").
            before_ok = (not before.isalpha()) or before == "x"
            after_ok = not after.isalnum()
            if before_ok and after_ok:
                hits.append((i, i + len(nl), name))
            start = i + len(nl)
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    chosen, occupied = [], []
    for s, e, name in hits:
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        chosen.append((s, name)); occupied.append((s, e))
    chosen.sort()
    return [name for _, name in chosen]


def parse_items(subject: str, body: str, known=None):
    """Return [{machine, price}] for a genuine supplier quote — one per machine.

    A valid quote names a machine either via a `Machine name:` / `Machine names:`
    line, OR by mentioning a known machine/model/make from the masters (passed in
    `known`). Price alone is not enough — newsletters often mention a "price", so an
    email with neither a machine line nor a known machine name yields [] and is
    skipped. The subject is never used as a blind machine label."""
    text = f"{subject or ''}\n{body or ''}"
    machine_blobs = [m.strip() for m in MACHINE_RE.findall(text) if m.strip()]
    price_blobs = [p.strip() for p in PRICE_RE.findall(text) if p.strip()]

    # A machine line may list several machines separated by commas -> one row each.
    machines = []
    for mb in machine_blobs:
        parts = [x.strip()[:200] for x in mb.split(",") if x.strip()]
        machines.extend(parts if parts else [mb[:200]])

    # No explicit "Machine name:" line → recognize machines from the master vocabulary.
    if not machines and known:
        machines = _find_known_machines(text, known)

    # Pull the numeric tokens out of the price line(s). Each token keeps its own
    # comma/dot grouping, so "1,05,999" stays a single number.
    price_tokens = []
    for pb in price_blobs:
        price_tokens.extend(NUM_RE.findall(pb))
    # Map prices to machines:
    #   • one token per machine        -> commas inside a token are thousands groupings
    #   • else split tokens on commas  -> handles a "120000, 569000" list for 2 machines
    if machines and len(price_tokens) == len(machines):
        prices = [_to_number(t) for t in price_tokens]
    else:
        split = []
        for t in price_tokens:
            split.extend([x for x in t.split(",") if x.strip()])
        if machines and len(split) == len(machines):
            prices = [_to_number(x) for x in split]
        else:
            prices = [_to_number(t) for t in price_tokens]

    # No named machine → not a supplier proposal (price alone is not enough).
    if not machines:
        return []
    return [{"machine": mac, "price": prices[i] if i < len(prices) else None}
            for i, mac in enumerate(machines)]


def _insert_proposal_item(pe, sid, machine, photos_json, price, pstatus, remarks, through):
    """Insert one proposal row with the legacy fields seeded (model/machine_name from
    the parsed machine, Active state, source channel as Through) and assign its Pro No."""
    res = execute(prop_engine,
                  """INSERT INTO proposal_items
                     (proposal_email_id,supplier_id,machine,model,machine_name,category,photos,
                      price,margin_pct,buyer_segment,photo_status,remarks,state,through)
                     VALUES (:pe,:s,:m,:m,:m,'',:photos,:price,15,'everyone',:ps,:rem,'active',:thr)""",
                  {"pe": pe, "s": sid, "m": machine, "photos": photos_json, "price": price,
                   "ps": pstatus, "rem": (remarks or "")[:2000], "thr": through})
    iid = res["lastrowid"]
    execute(prop_engine, "UPDATE proposal_items SET pro_no=CONCAT('', 52000+id) WHERE id=:id", {"id": iid})
    return iid


def connected() -> bool:
    return imap_fetch.is_configured() or gmail.is_configured()


def _merge_photos(existing, urls):
    cur = existing
    if isinstance(cur, str):
        try:
            cur = json.loads(cur)
        except Exception:
            cur = []
    cur = cur or []
    return json.dumps(cur + [u for u in urls if u not in cur])


# "machine 1 image", "machine 2 photo"… — tells which machine an attached image belongs to.
IMG_HINT_RE = re.compile(r"(?im)\bmachine\s*(\d+)\s*(?:image|images|photo|photos|pic|pics)\b")


def _distribute_photos(items, img_urls, body=""):
    """Decide which machine each attached image belongs to.

    1. If the body annotates images like "machine 1 image", the Nth such note maps
       the Nth attachment to that machine (so a lone image for machine 1 shows only
       on machine 1, not on every row).
    2. Otherwise, when image and machine counts match, pair them 1:1 in order.
    3. Otherwise (ambiguous), show every image on each row — the old safe default."""
    n = len(items)
    if not img_urls or n == 0:
        return [[] for _ in range(n)]
    hints = [int(x) for x in IMG_HINT_RE.findall(body or "")]
    if hints:
        per = [[] for _ in range(n)]
        for k, url in enumerate(img_urls):
            mi = (hints[k] - 1) if k < len(hints) else k  # 1-based note -> 0-based index
            if not (0 <= mi < n):
                mi = min(k, n - 1)
            per[mi].append(url)
        return per
    if len(img_urls) == n:
        return [[u] for u in img_urls]
    return [list(img_urls) for _ in items]


def _matches_keyword(text: str) -> bool:
    """True if the WhatsApp message contains a configured keyword (same gate as email
    intake). If no keywords are set, allow it (a structured quote is enough)."""
    kws = [(r.get("word") or "").strip().lower() for r in q(admin_engine, "SELECT word FROM keywords")]
    kws = [k for k in kws if k]
    if not kws:
        return True
    low = (text or "").lower()
    return any(k in low for k in kws)


def _phone_match_sql(col: str) -> str:
    """SQL to match a phone column against :ph by its last 10 digits (ignores +, spaces,
    country code), so '8778853952', '+91 8778853952' and '918778853952' all match."""
    return f"RIGHT(REGEXP_REPLACE(COALESCE({col},''),'[^0-9]',''),10) = RIGHT(:ph,10)"


def handle_whatsapp_messages(value: dict) -> dict:
    """Process one Meta Cloud API webhook 'value' block. Routes each inbound message:
      - a known buyer with a quotation  -> log the reply into chat history
      - a supplier with a pending photo request -> attach the image(s) to that row
      - a structured quote (Machine/Price) -> create supplier proposal row(s)
    Returns a small summary dict. Idempotent: dedups by WhatsApp message id."""
    msgs = (value or {}).get("messages") or []
    contacts = (value or {}).get("contacts") or []
    profile_name = ""
    if contacts:
        profile_name = ((contacts[0] or {}).get("profile") or {}).get("name") or ""
    out = {"buyer_replies": 0, "photos": 0, "proposals": 0, "ignored": 0}

    # Split this webhook batch into text + images (WhatsApp sends one message per image).
    texts, images, sender, first_id = [], [], "", None
    for m in msgs:
        sender = sender or re.sub(r"\D", "", m.get("from") or "")
        first_id = first_id or m.get("id")
        mtype = m.get("type")
        if mtype == "text":
            texts.append(((m.get("text") or {}).get("body") or ""))
        elif mtype in ("image", "document", "video"):
            media = m.get(mtype) or {}
            if media.get("caption"):
                texts.append(media["caption"])
            if media.get("id"):
                images.append((m.get("id"), media["id"]))
    if not sender or not first_id:
        return out
    body_text = "\n".join(t for t in texts if t).strip()

    # ---- 1) Buyer reply? (sender is a buyer who has been quoted) ----
    buyer = one(prop_engine, f"""
        SELECT b.id FROM buyers b
        WHERE {_phone_match_sql('b.phone')} AND EXISTS (SELECT 1 FROM quotations qt WHERE qt.buyer_id=b.id)
        LIMIT 1
    """, {"ph": sender})
    if buyer and body_text:
        if not one(prop_engine, "SELECT id FROM chat_messages WHERE source_msg_id=:mid", {"mid": first_id}):
            execute(prop_engine,
                    "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:bid,'whatsapp','in',:b,:mid)",
                    {"bid": buyer["id"], "b": body_text[:4000], "mid": first_id})
            out["buyer_replies"] += 1
        return out

    # ---- 2) Supplier photo reply? (pending photo request + images) ----
    supplier = one(prop_engine, f"SELECT id, name FROM suppliers WHERE {_phone_match_sql('phone')} LIMIT 1", {"ph": sender})
    if supplier and images:
        row = one(prop_engine,
                  "SELECT id, photos FROM proposal_items WHERE supplier_id=:s AND photo_status='requested' ORDER BY id DESC LIMIT 1",
                  {"s": supplier["id"]})
        if row:
            urls = _download_wa_images(images)
            if urls:
                execute(prop_engine, "UPDATE proposal_items SET photos=:p, photo_status='received' WHERE id=:id",
                        {"p": _merge_photos(row["photos"], urls), "id": row["id"]})
                execute(prop_engine,
                        "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('supplier',:s,'whatsapp','in',:b,:mid)",
                        {"s": supplier["id"], "b": f"Supplier sent {len(urls)} photo(s) on WhatsApp.", "mid": first_id})
                out["photos"] += len(urls)
            return out

    # ---- 3) New supplier proposal? (Machine/Price quote or known machine + keyword match) ----
    items = parse_items("", body_text, known=known_machine_names())
    if items and _matches_keyword(body_text):
        if one(prop_engine, "SELECT id FROM proposal_emails WHERE source_msg_id=:mid", {"mid": first_id}):
            return out
        sid = supplier["id"] if supplier else execute(
            prop_engine, "INSERT INTO suppliers (name,phone) VALUES (:n,:ph)",
            {"n": profile_name or f"WhatsApp {sender[-10:]}", "ph": sender})["lastrowid"]
        img_urls = _download_wa_images(images)
        per_item = _distribute_photos(items, img_urls, body_text)
        pe = execute(prop_engine,
                     "INSERT INTO proposal_emails (supplier_id,channel,subject,body,source_msg_id,received_at) VALUES (:s,'whatsapp',:sub,:body,:mid,NOW())",
                     {"s": sid, "sub": "WhatsApp quote", "body": body_text[:5000], "mid": first_id})["lastrowid"]
        for idx, it in enumerate(items):
            photos = per_item[idx] if idx < len(per_item) else []
            _insert_proposal_item(pe, sid, it["machine"], json.dumps(photos), it["price"],
                                  "received" if photos else "none", body_text, "whatsapp")
            out["proposals"] += 1
        return out

    out["ignored"] += 1
    return out


def _download_wa_images(images) -> list:
    """images: [(msg_id, media_id)] -> saved public image URLs (skips non-images)."""
    from .integrations.notify import wa_download_media
    urls = []
    for _mid, media_id in images:
        try:
            data, ctype = wa_download_media(media_id)
            if data and (not ctype or ctype.startswith("image/")):
                urls.append(storage.save_image("", data, ctype or "image/jpeg"))
        except Exception:
            continue
    return urls


def _handle_photo_replies():
    """Find replies to our photo-request emails and attach their images."""
    if not imap_fetch.is_configured():
        return 0
    pending = q(prop_engine, """
        SELECT id, supplier_id, photos, photo_request_msgid
        FROM proposal_items WHERE photo_status='requested' AND photo_request_msgid IS NOT NULL
    """)
    if not pending:
        return 0
    replies = imap_fetch.find_replies([p["photo_request_msgid"] for p in pending])
    attached = 0
    for rep in replies:
        if not rep.get("images"):
            continue
        item = next((p for p in pending if p["photo_request_msgid"] == rep.get("reply_to_request")), None)
        if not item:
            continue
        urls = [storage.save_image(im["filename"], im["data"], im["content_type"]) for im in rep["images"]]
        execute(prop_engine, "UPDATE proposal_items SET photos=:p, photo_status='received' WHERE id=:id",
                {"p": _merge_photos(item["photos"], urls), "id": item["id"]})
        execute(prop_engine, "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('supplier',:s,'email','in',:b)",
                {"s": item["supplier_id"], "b": f"Supplier replied with {len(urls)} photo(s)."})
        attached += 1
    return attached


def run_fetch() -> dict:
    """Pull inbox: attach any photo replies, then import new keyword-matched emails."""
    if not connected():
        return {"ok": False, "fetched": 0, "matched": 0, "detail": "Email inbox is not connected."}

    photos_attached = 0
    try:
        photos_attached = _handle_photo_replies()
    except Exception:
        pass
    try:
        _handle_buyer_replies()   # log buyer replies to quotations into chat history
    except Exception:
        pass
    try:
        process_followups()       # send due daily/weekly follow-ups
    except Exception:
        pass

    kws = [r["word"] for r in q(admin_engine, "SELECT word FROM keywords ORDER BY word")]
    if not kws:
        return {"ok": True, "fetched": 0, "matched": 0, "photos": photos_attached, "detail": "No keywords configured."}
    try:
        msgs = imap_fetch.search(kws) if imap_fetch.is_configured() else gmail.search(kws)
    except Exception as e:
        return {"ok": False, "fetched": 0, "matched": 0, "detail": f"Inbox search failed: {e}"}

    # Known photo-request ids so we don't turn a photo reply into a new proposal.
    req_ids = {p["photo_request_msgid"] for p in q(prop_engine, "SELECT photo_request_msgid FROM proposal_items WHERE photo_request_msgid IS NOT NULL")}

    known = known_machine_names()   # master vocabulary, loaded once per fetch
    created = 0
    for m in msgs:
        try:
            # Replies (to our photo requests or any thread) are not new proposals.
            if m.get("in_reply_to") or (m.get("subject", "").strip().lower().startswith("re:")):
                continue
            if one(prop_engine, "SELECT id FROM proposal_emails WHERE source_msg_id=:mid", {"mid": m["msg_id"]}):
                continue
            # A genuine supplier quote names a machine via a "Machine name:" line OR a
            # known machine/model/make from the masters. Newsletters match neither →
            # yield no items → skipped (no junk supplier or empty proposal_email).
            items = parse_items(m["subject"], m.get("body", ""), known=known)
            if not items:
                continue
            name, email = parse_from(m["from"])
            sup = one(prop_engine, "SELECT id FROM suppliers WHERE email=:e LIMIT 1", {"e": email})
            sid = sup["id"] if sup else execute(
                prop_engine, "INSERT INTO suppliers (name,email) VALUES (:n,:e)", {"n": name, "e": email})["lastrowid"]
            # Images attached to the proposal email, saved in order, then mapped to the
            # machine each belongs to (honouring "machine N image" notes in the body).
            img_urls = [storage.save_image(im["filename"], im["data"], im["content_type"]) for im in m.get("images", [])]
            per_item = _distribute_photos(items, img_urls, m.get("body", ""))
            # When the supplier's email actually arrived (from its Date header), so the
            # table shows the received date rather than our import time. Falls back to NULL.
            try:
                recv = parsedate_to_datetime(m.get("date") or "")
                received_at = recv.astimezone().replace(tzinfo=None) if recv else None
            except Exception:
                received_at = None
            pe = execute(prop_engine,
                         "INSERT INTO proposal_emails (supplier_id,channel,subject,body,source_msg_id,received_at) VALUES (:s,'email',:sub,:body,:mid,:rcv)",
                         {"s": sid, "sub": m["subject"], "body": (m.get("body") or m.get("snippet") or "")[:5000],
                          "mid": m["msg_id"], "rcv": received_at})["lastrowid"]
            for idx, it in enumerate(items):
                photos = per_item[idx] if idx < len(per_item) else []
                _insert_proposal_item(pe, sid, it["machine"], json.dumps(photos), it["price"],
                                      "received" if photos else "none", m["subject"], "e_mail")
                created += 1
        except Exception:
            continue
    return {"ok": True, "fetched": created, "matched": len(msgs), "photos": photos_attached}
