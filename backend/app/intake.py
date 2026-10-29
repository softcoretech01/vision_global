"""Shared supplier-email intake:
  - keyword search -> create one proposal row PER MACHINE (parse machine name + price)
  - save image attachments -> Photos column
  - detect replies to our photo-request emails -> auto-attach the photos
Used by the manual /proposals/fetch-emails endpoint and the auto scheduler."""
import os
import re
import json
from email.utils import parsedate_to_datetime
from datetime import datetime
from .db import prop_engine, admin_engine, q, one, execute
from .integrations import gmail, imap_fetch
from .integrations.notify import dispatch
from .templating import get_template, render
from . import storage, details, buyer_flow


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
          AND qt.buyer_status='sent' AND qt.support_open=0   -- stop once the buyer has answered
    """)
    n = 0
    for f in due:
        # The conversation lives on WhatsApp; email only for buyers without a phone.
        channel = "whatsapp" if re.sub(r"\D", "", f.get("phone") or "") else "email"
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
        dispatch(channel, to, subject, body, tpl, mapping)
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
    # A name that only differs from a master by spacing/case uses the master spelling,
    # so it matches buyer enquiries and the detail-form dropdowns.
    machines = [details._snap(m, known or []) or m for m in machines]

    # No explicit "Machine name:" line → recognize machines from the master vocabulary.
    if not machines and known:
        machines = _find_known_machines(text, known)
        # A name given as "model: X" describes the machine before it, not a second machine.
        labelled_models = {v.strip().lower() for v in re.findall(r"(?im)\bmodel(?:\s*name)?\s*[:=\-]\s*([^,;\n]+)", text)}
        rest = [m for m in machines if m.lower() not in labelled_models]
        machines = rest or machines

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


DETAIL_FIELDS = ("model", "machine_name", "width", "year", "quantity", "mode", "machine_color",
                 "rate_type", "rate", "price_term", "payment_term", "currency", "accessories")


def _insert_proposal_item(pe, sid, machine, photos_json, price, pstatus, remarks, through, details=None):
    """Insert one proposal row with the legacy fields seeded (model/machine_name from
    the parsed machine, Active state, source channel as Through) and assign its Pro No.
    `details` (from details.parse_details) overrides/fills the detail-form fields."""
    res = execute(prop_engine,
                  """INSERT INTO proposal_items
                     (proposal_email_id,supplier_id,machine,model,machine_name,category,photos,
                      price,margin_pct,buyer_segment,photo_status,remarks,state,through)
                     VALUES (:pe,:s,:m,:m,:m,'',:photos,:price,15,'everyone',:ps,:rem,'active',:thr)""",
                  {"pe": pe, "s": sid, "m": machine, "photos": photos_json, "price": price,
                   "ps": pstatus, "rem": (remarks or "")[:2000], "thr": through})
    iid = res["lastrowid"]
    execute(prop_engine, "UPDATE proposal_items SET pro_no=CONCAT('', 52000+id) WHERE id=:id", {"id": iid})
    found = {k: v for k, v in (details or {}).items() if k in DETAIL_FIELDS and v}
    if found:
        sets = ", ".join(f"`{k}`=:{k}" for k in found)
        execute(prop_engine, f"UPDATE proposal_items SET {sets} WHERE id=:id", {**found, "id": iid})
    return iid


def _item_details(text, items):
    """Per-machine detail fields for a parsed quote (each machine reads its own part of
    the message; message-wide terms like currency come from the whole text)."""
    try:
        models, machines = details.masters()
        blocks = details.split_blocks(text, [it["machine"] for it in items])
        return [details.parse_details(b, text, models, machines) for b in blocks]
    except Exception as e:
        print(f"[INTAKE · details-error] {e}")
        return [{} for _ in items]


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


def _record_wa_inbound(sender: str):
    """Any inbound message opens that number's 24-hour free-text window."""
    try:
        execute(prop_engine,
                """INSERT INTO wa_contacts (phone10,phone,last_inbound_at) VALUES (RIGHT(:ph,10),:ph,NOW())
                   ON DUPLICATE KEY UPDATE phone=:ph, last_inbound_at=NOW()""",
                {"ph": sender})
    except Exception as e:
        print(f"[WHATSAPP · window-track-error] {e}")


def handle_whatsapp_statuses(value: dict):
    """Meta reports delivery outcomes asynchronously. Log failures (e.g. 131047 =
    outside the 24h window with no template, 132001 = template not found/approved)."""
    for st in (value or {}).get("statuses") or []:
        if st.get("status") == "failed":
            errs = "; ".join(f"{e.get('code')} {e.get('title')}" for e in st.get("errors") or [])
            print(f"[WHATSAPP · delivery-failed] -> {st.get('recipient_id')} msg={st.get('id')}: {errs}")


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
    texts, images, sender, first_id, button_id = [], [], "", None, None
    for m in msgs:
        sender = sender or re.sub(r"\D", "", m.get("from") or "")
        first_id = first_id or m.get("id")
        mtype = m.get("type")
        if mtype == "text":
            texts.append(((m.get("text") or {}).get("body") or ""))
        elif mtype == "interactive":       # tap on a reply button we sent
            rep = (m.get("interactive") or {}).get("button_reply") or (m.get("interactive") or {}).get("list_reply") or {}
            button_id = button_id or rep.get("id")
            texts.append(rep.get("title") or "")
        elif mtype == "button":            # tap on a template quick-reply button
            btn = m.get("button") or {}
            button_id = button_id or btn.get("payload")
            texts.append(btn.get("text") or "")
        elif mtype in ("image", "document", "video"):
            media = m.get(mtype) or {}
            if media.get("caption"):
                texts.append(media["caption"])
            if media.get("id"):
                images.append((m.get("id"), media["id"]))
    if not sender or not first_id:
        return out
    _record_wa_inbound(sender)
    body_text = "\n".join(t for t in texts if t).strip()

    # ---- 1) Buyer reply? (sender is a buyer who has been quoted) ----
    # One person can have several buyer records with the same phone (one per enquiry
    # email). A button tap names its quotation, so its buyer wins; otherwise the buyer
    # of the most recent quotation sent to this phone.
    buyer = None
    if button_id and button_id.startswith("q:") and button_id.count(":") == 2:
        buyer = one(prop_engine, f"""
            SELECT b.id FROM quotations qt JOIN buyers b ON b.id=qt.buyer_id
            WHERE qt.ref=:ref AND {_phone_match_sql('b.phone')} LIMIT 1
        """, {"ref": button_id.split(":")[1], "ph": sender})
    if not buyer:
        buyer = one(prop_engine, f"""
            SELECT b.id FROM quotations qt JOIN buyers b ON b.id=qt.buyer_id
            WHERE {_phone_match_sql('b.phone')} ORDER BY qt.id DESC LIMIT 1
        """, {"ph": sender})
    supplier = one(prop_engine, f"SELECT id, name FROM suppliers WHERE {_phone_match_sql('phone')} LIMIT 1", {"ph": sender})
    # Same number as a supplier we're collecting quote details from? A quotation button
    # tap is still the buyer's; anything else goes to the supplier flow below.
    supplier_busy = bool(supplier and not button_id and _pending_detail_rows(supplier["id"]))
    if buyer and (body_text or button_id) and not supplier_busy:
        if not one(prop_engine, "SELECT id FROM chat_messages WHERE source_msg_id=:mid", {"mid": first_id}):
            execute(prop_engine,
                    "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:bid,'whatsapp','in',:b,:mid)",
                    {"bid": buyer["id"], "b": (body_text or button_id)[:4000], "mid": first_id})
            out["buyer_replies"] += 1
            out.update(buyer_flow.handle_buyer_message(buyer["id"], sender, body_text, button_id))
        return out

    # ---- 2) Photos answering a photo request (📷 button / buyer "Send photos")? ----
    # They belong to the row we asked about — not to every row of that supplier's quote.
    # A message that's clearly a new quote for another machine keeps its photos.
    if supplier and images:
        asked = _requested_photo_row(supplier["id"])
        if asked and not _is_new_quote(body_text, [asked]):
            out["photos"] += _attach_requested_photos(supplier["id"], asked, images, None if body_text else first_id)
            images = []
            if not body_text:
                return out
            # A caption describes the photo's machine: fill only that row's details.
            mine = [r for r in _pending_detail_rows(supplier["id"]) if r["id"] == asked["id"]]
            if mine:
                out.update(_apply_supplier_reply(supplier["id"], mine, body_text, [], first_id))
                return out

    # ---- 2a) Supplier answering our missing-details request? -> fill the same row(s) ----
    if supplier and (body_text or images):
        pending = _pending_detail_rows(supplier["id"])
        if pending and not _is_new_quote(body_text, pending):
            out.update(_apply_supplier_reply(supplier["id"], pending, body_text, images, first_id))
            return out

    # ---- 3) New supplier proposal? (Machine/Price quote or known machine + keyword match) ----
    items = parse_items("", body_text, known=known_machine_names())
    if items and _matches_keyword(body_text):
        if one(prop_engine, "SELECT id FROM proposal_emails WHERE source_msg_id=:mid", {"mid": first_id}):
            return out
        sid = supplier["id"] if supplier else execute(
            prop_engine, "INSERT INTO suppliers (name,phone) VALUES (:n,:ph)",
            {"n": profile_name or f"WhatsApp {sender[-10:]}", "ph": sender})["lastrowid"]
        failed = []
        img_urls = _download_wa_images(images, failed)
        per_item = _distribute_photos(items, img_urls, body_text)
        pe = execute(prop_engine,
                     "INSERT INTO proposal_emails (supplier_id,channel,subject,body,source_msg_id,received_at) VALUES (:s,'whatsapp',:sub,:body,:mid,NOW())",
                     {"s": sid, "sub": "WhatsApp quote", "body": body_text[:5000], "mid": first_id})["lastrowid"]
        per_details = _item_details(body_text, items)
        first_row = None
        for idx, it in enumerate(items):
            photos = per_item[idx] if idx < len(per_item) else []
            iid = _insert_proposal_item(pe, sid, it["machine"], json.dumps(photos), it["price"],
                                        "received" if photos else "none", body_text, "whatsapp", per_details[idx])
            first_row = first_row or iid
            out["proposals"] += 1
        _queue_media(first_row, failed)   # photos that couldn't be fetched yet -> retried
        # Check for missing details shortly, once any follow-up images have arrived.
        execute(prop_engine,
                f"UPDATE proposal_items SET details_status='pending_check', details_due_at=NOW() + INTERVAL {_details_delay()} SECOND WHERE proposal_email_id=:pe",
                {"pe": pe})
        return out

    out["ignored"] += 1
    return out


# ------------------- Missing-details follow-up (WhatsApp) -------------------
# After a WhatsApp quote, the supplier is asked for the required details/photos it left
# out (details.REQUIRED); their reply fills the same row. Each message pushes the check
# back a little (WhatsApp delivers every image as its own message), then the scheduler
# asks again for anything still missing — at most DETAILS_MAX_REQUESTS times.
DETAILS_MAX_REQUESTS = 2
# Starting wording of the supplier details requests (seeded into Message Templates).
SUPPLIER_DEFAULTS = {
    "details_request": ("Hi {{supplier}}, thank you for your quotation for {{machine}} (Ref {{pro_no}}).\n"
                        "To complete it, please reply with:\n{{missing}}\n\nYou can send the photos right here."),
    "details_followup": "Thanks {{supplier}}! For your {{machine}} quotation (Ref {{pro_no}}) we still need:\n{{missing}}",
}


def _details_delay() -> int:
    try:
        return max(10, int(os.environ.get("WA_DETAILS_DELAY_SECONDS", "90")))
    except ValueError:
        return 90


def _pending_detail_rows(supplier_id) -> list:
    """This supplier's rows still collecting details — only from their latest such quote."""
    latest = one(prop_engine, """
        SELECT MAX(proposal_email_id) pe FROM proposal_items
        WHERE supplier_id=:s AND details_status IN ('pending_check','sending','requested','incomplete')
          AND COALESCE(details_requested_at, details_due_at) > NOW() - INTERVAL 7 DAY
    """, {"s": supplier_id})
    if not latest or not latest.get("pe"):
        return []
    return q(prop_engine, """
        SELECT * FROM proposal_items
        WHERE proposal_email_id=:pe AND details_status IN ('pending_check','sending','requested','incomplete') ORDER BY id
    """, {"pe": latest["pe"]})


def _is_new_quote(text: str, pending: list) -> bool:
    """A reply only counts as a NEW quote if it has an explicit 'Machine name:' line for a
    machine we aren't already collecting details for; anything else is a details reply."""
    named = [m.strip().lower() for blob in MACHINE_RE.findall(text or "") for m in blob.split(",") if m.strip()]
    if not named:
        return False
    have = {(r.get(f) or "").strip().lower() for r in pending for f in ("machine", "model", "machine_name")}
    return any(n not in have for n in named)


def _reply_price(text: str):
    for blob in PRICE_RE.findall(text or ""):
        for tok in NUM_RE.findall(blob):
            v = _to_number(tok)
            if v:
                return v
    return None


def _positional_answers(row, block) -> dict:
    """Map an unlabelled reply onto the fields we asked for, in the order we asked —
    e.g. '2016 / 200 / 10 / CIF' answering 'Year, Width, Quantity, Price term'. Only
    used when the number of plain answers matches the number of missing fields."""
    want = [f for f, _ in details.REQUIRED if row.get(f) in (None, "", 0)]
    lines = [ln.strip() for ln in (block or "").splitlines() if ln.strip()]
    if len(lines) == 1 and "," in lines[0]:
        lines = [x.strip() for x in lines[0].split(",") if x.strip()]
    lines = [ln for ln in lines if not re.search(r"[A-Za-z][A-Za-z ]*\s*[:=]", ln)]   # labelled lines parse normally
    if not want or len(lines) != len(want):
        return {}
    out = {}
    for f, val in zip(want, lines):
        if f == "price":
            out[f] = _to_number(NUM_RE.findall(val)[0]) if NUM_RE.findall(val) else None
        elif f == "price_term":
            out[f] = details._cue(val, details.PRICE_TERM_CUES) or val[:80]
        elif f == "width" and re.fullmatch(r"\d+(?:\.\d+)?", val):
            out[f] = f"{val} cm"
        else:
            out[f] = val[:160]
    return {k: v for k, v in out.items() if v}


def _apply_supplier_reply(supplier_id, pending, body_text, images, msg_id) -> dict:
    """Fill the pending row(s) from the supplier's reply: only fields that are still
    empty, plus any images. Then re-check missing details after a short quiet period."""
    if one(prop_engine, "SELECT id FROM chat_messages WHERE source_msg_id=:mid", {"mid": msg_id}):
        return {}
    filled, n_photos = 0, 0
    failed = []
    urls = _download_wa_images(images, failed) if images else []
    _queue_media(pending[0]["id"], failed)
    per_photos = _distribute_photos(pending, urls, body_text) if urls else [[] for _ in pending]
    blocks = [body_text] * len(pending)
    if body_text and len(pending) > 1:
        blocks = details.split_blocks(body_text, [r["machine"] for r in pending])
    models, machines = details.masters() if body_text else ([], [])
    for idx, row in enumerate(pending):
        updates = {}
        if body_text:
            found = details.parse_details(blocks[idx], body_text, models, machines)
            # In a reply, plain lines are answers (year, width…), not parts: only an
            # explicit "Accessories:" line counts as accessories.
            if not re.search(r"(?im)^\s*accessor(?:y|ies)\s*[:=\-]", blocks[idx]):
                found.pop("accessories", None)
            # Only fill what's still empty, so a reply never overwrites the quote.
            for f, v in found.items():
                if f in DETAIL_FIELDS and v and row.get(f) in (None, ""):
                    updates[f] = v
            if row.get("price") in (None, 0):
                p = _reply_price(blocks[idx])
                if p:
                    updates["price"] = p
            # Plain answers in the order we asked override the guesswork above.
            updates.update(_positional_answers(row, blocks[idx]))
        if per_photos[idx]:
            updates["photos"] = _merge_photos(row.get("photos"), per_photos[idx])
            updates["photo_status"] = "received"
            n_photos += len(per_photos[idx])
        filled += len([k for k in updates if k not in ("photos", "photo_status")])
        sets = "".join(f", `{k}`=:{k}" for k in updates)
        if per_photos[idx]:
            sets += ", photos_received_at=NOW()"   # buyers waiting for photos get them shortly
        execute(prop_engine,
                f"""UPDATE proposal_items SET details_status='pending_check',
                       details_due_at=NOW() + INTERVAL {_details_delay()} SECOND{sets} WHERE id=:id""",
                {**updates, "id": row["id"]})
    note = body_text[:4000] if body_text else f"Supplier sent {n_photos} photo(s) on WhatsApp."
    execute(prop_engine,
            "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('supplier',:s,'whatsapp','in',:b,:mid)",
            {"s": supplier_id, "b": note, "mid": msg_id})
    return {"details_filled": filled, "photos": n_photos}


def process_details_requests() -> int:
    """Scheduler job: for WhatsApp quotes whose quiet period is over, ask the supplier for
    whatever required details/photos are still missing (one message per quote), or mark
    the rows complete. Returns the number of requests sent."""
    due = q(prop_engine, """
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone
        FROM proposal_items pi JOIN suppliers s ON s.id=pi.supplier_id
        WHERE pi.details_status='pending_check' AND pi.details_due_at <= NOW()
        ORDER BY pi.proposal_email_id, pi.id
    """)
    groups = {}
    for r in due:
        groups.setdefault(r["proposal_email_id"], []).append(r)
    sent = 0
    for rows in groups.values():
        # Claim the rows so a second server process can't send the same request.
        mine = [r for r in rows if execute(prop_engine,
                "UPDATE proposal_items SET details_status='sending' WHERE id=:id AND details_status='pending_check'",
                {"id": r["id"]})["rowcount"] == 1]
        if not mine:
            continue
        ask, done, gave_up = [], [], []
        for r in mine:
            miss = details.missing_fields(r)
            if not miss:
                done.append(r)
            elif int(r.get("details_requests") or 0) >= DETAILS_MAX_REQUESTS:
                gave_up.append(r)
            else:
                ask.append((r, miss))
        for state, rs in (("complete", done), ("incomplete", gave_up)):
            for r in rs:
                execute(prop_engine, "UPDATE proposal_items SET details_status=:st WHERE id=:id", {"st": state, "id": r["id"]})
        if not ask:
            continue
        first = ask[0][0]
        if len(ask) == 1:
            missing_txt = "\n".join(f"• {m}" for m in ask[0][1])
        else:
            missing_txt = "\n".join(f"{r['machine']} (Ref {r.get('pro_no')}): {', '.join(m)}" for r, m in ask)
        mapping = {"supplier": first["supplier_name"], "machine": ", ".join(r["machine"] for r, _ in ask),
                   "pro_no": ", ".join(str(r.get("pro_no") or "") for r, _ in ask), "missing": missing_txt}
        again = any(int(r.get("details_requests") or 0) > 0 for r, _ in ask)
        kind = "details_followup" if again else "details_request"
        tpl = get_template(kind, "whatsapp")
        body = render(tpl["body"] if tpl else SUPPLIER_DEFAULTS[kind], mapping)
        res = dispatch("whatsapp", first["supplier_phone"], "", body, tpl, mapping)
        for r, miss in ask:
            if res.get("ok"):
                execute(prop_engine, """
                    UPDATE proposal_items SET details_status='requested', details_requests=details_requests+1,
                           details_requested_at=NOW(),
                           photo_status=CASE WHEN :need_photo AND COALESCE(photo_status,'none')<>'received' THEN 'requested' ELSE photo_status END
                    WHERE id=:id""", {"id": r["id"], "need_photo": 1 if any(m.startswith("Photos") for m in miss) else 0})
            else:
                execute(prop_engine, "UPDATE proposal_items SET details_status='incomplete' WHERE id=:id", {"id": r["id"]})
        if res.get("ok"):
            execute(prop_engine,
                    "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('supplier',:s,'whatsapp','out',:b)",
                    {"s": first["supplier_id"], "b": body})
            sent += 1
        else:
            print(f"[WHATSAPP · details-request-failed] -> {first['supplier_phone']}: {res.get('error')}")
    return sent


def _requested_photo_row(supplier_id):
    """The supplier's row with an open photo request — the most recently asked one."""
    return one(prop_engine, """
        SELECT pi.id, pi.photos, pi.machine, pi.model, pi.machine_name FROM proposal_items pi
        WHERE pi.supplier_id=:s AND pi.photo_status='requested'
        ORDER BY (SELECT MAX(pr.id) FROM photo_requests pr WHERE pr.proposal_item_id=pi.id) DESC, pi.id DESC
        LIMIT 1""", {"s": supplier_id})


def _attach_requested_photos(supplier_id, row, images, msg_id) -> int:
    """Save the supplier's photos on the requested row; returns how many were added.
    Photos that can't be downloaded yet are queued for retry on the same row."""
    failed = []
    urls = _download_wa_images(images, failed)
    _queue_media(row["id"], failed)
    if urls:
        execute(prop_engine, "UPDATE proposal_items SET photos=:p, photo_status='received', photos_received_at=NOW() WHERE id=:id",
                {"p": _merge_photos(row["photos"], urls), "id": row["id"]})
        execute(prop_engine,
                "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('supplier',:s,'whatsapp','in',:b,:mid)",
                {"s": supplier_id, "b": f"Supplier sent {len(urls)} photo(s) for {row['machine']} on WhatsApp.", "mid": msg_id})
    return len(urls)


def _download_wa_images(images, failed: list = None) -> list:
    """images: [(msg_id, media_id)] -> saved public image URLs (skips non-images).
    Media that couldn't be fetched (expired token, network) go into `failed` so the
    caller can queue them for retry instead of losing the photo."""
    from .integrations.notify import wa_download_media
    urls = []
    for _mid, media_id in images:
        try:
            data, ctype = wa_download_media(media_id)
        except Exception as e:
            print(f"[WHATSAPP · media-download-failed] {media_id}: {e}")
            data, ctype = b"", ""
        if not data:
            if failed is not None:
                failed.append(media_id)
            continue
        if not ctype or ctype.startswith("image/"):
            urls.append(storage.save_image("", data, ctype or "image/jpeg"))
    return urls


def _queue_media(item_id, media_ids):
    """Remember WhatsApp photos we couldn't download yet on a proposal row."""
    if not item_id or not media_ids:
        return
    row = one(prop_engine, "SELECT pending_media FROM proposal_items WHERE id=:id", {"id": item_id})
    try:
        cur = json.loads((row or {}).get("pending_media") or "[]")
    except Exception:
        cur = []
    have = {m.get("id") for m in cur}
    cur += [{"id": mid, "at": datetime.now().isoformat(timespec="seconds")} for mid in media_ids if mid not in have]
    execute(prop_engine, "UPDATE proposal_items SET pending_media=:p WHERE id=:id", {"p": json.dumps(cur), "id": item_id})


MEDIA_RETRY_DAYS = 7    # Meta keeps inbound media ~30 days; stop trying well before


def retry_pending_media() -> int:
    """Scheduler job: fetch queued WhatsApp photos (e.g. once a new token is in place),
    add them to the row's photos and let waiting buyers / the details check see them.
    Returns the number of photos recovered."""
    rows = q(prop_engine, "SELECT id, photos, pending_media, details_status FROM proposal_items "
                          "WHERE pending_media IS NOT NULL AND pending_media NOT IN ('', '[]')")
    recovered = 0
    for r in rows:
        try:
            queue = json.loads(r["pending_media"])
        except Exception:
            queue = []
        keep, urls = [], []
        for m in queue:
            fail = []
            got = _download_wa_images([(None, m.get("id"))], fail)
            if got:
                urls += got
            elif fail:
                try:
                    age = (datetime.now() - datetime.fromisoformat(m.get("at"))).days
                except Exception:
                    age = 0
                if age < MEDIA_RETRY_DAYS:
                    keep.append(m)
        sets, params = "pending_media=:pm", {"pm": json.dumps(keep) if keep else None, "id": r["id"]}
        if urls:
            sets += ", photos=:p, photo_status='received', photos_received_at=NOW()"
            params["p"] = _merge_photos(r["photos"], urls)
            if r.get("details_status") in ("requested", "incomplete"):
                sets += ", details_status='pending_check', details_due_at=NOW()"   # re-check what's still missing
            recovered += len(urls)
        execute(prop_engine, f"UPDATE proposal_items SET {sets} WHERE id=:id", params)
    return recovered


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
        execute(prop_engine, "UPDATE proposal_items SET photos=:p, photo_status='received', photos_received_at=NOW() WHERE id=:id",
                {"p": _merge_photos(item["photos"], urls), "id": item["id"]})
        execute(prop_engine, "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('supplier',:s,'email','in',:b)",
                {"s": item["supplier_id"], "b": f"Supplier replied with {len(urls)} photo(s)."})
        attached += 1
    return attached


def _own_addresses() -> set:
    """Email addresses we send from (SMTP / IMAP / Gmail account), lower-cased."""
    out = set()
    for key in ("SMTP_FROM", "SMTP_USER", "IMAP_USER", "GMAIL_USER"):
        _name, addr = parse_from(os.environ.get(key) or "")
        if addr and "@" in addr:
            out.add(addr.lower())
    return out


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
    kws =[r["word"] for r in q(admin_engine, "SELECT word FROM keywords ORDER BY word")]
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
    own = _own_addresses()
    for m in msgs:
        try:
            # Replies (to our photo requests or any thread) are not new proposals.
            if m.get("in_reply_to") or (m.get("subject", "").strip().lower().startswith("re:")):
                continue
            if one(prop_engine, "SELECT id FROM proposal_emails WHERE source_msg_id=:mid", {"mid": m["msg_id"]}):
                continue
            # Our own outgoing mail (quotations, follow-ups) can land in this inbox and
            # mentions "quotation" + a machine — never import it as a supplier proposal.
            name, email = parse_from(m["from"])
            if (email or "").lower() in own or one(prop_engine,
                    "SELECT id FROM quotations WHERE email_msgid=:mid OR sent_msgid=:mid LIMIT 1", {"mid": m["msg_id"]}):
                continue
            # A genuine supplier quote names a machine via a "Machine name:" line OR a
            # known machine/model/make from the masters. Newsletters match neither →
            # yield no items → skipped (no junk supplier or empty proposal_email).
            items = parse_items(m["subject"], m.get("body", ""), known=known)
            if not items:
                continue
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
            per_details = _item_details(m.get("body") or "", items)
            for idx, it in enumerate(items):
                photos = per_item[idx] if idx < len(per_item) else []
                _insert_proposal_item(pe, sid, it["machine"], json.dumps(photos), it["price"],
                                      "received" if photos else "none", m["subject"], "e_mail", per_details[idx])
                created += 1
        except Exception:
            continue
    return {"ok": True, "fetched": created, "matched": len(msgs), "photos": photos_attached}
