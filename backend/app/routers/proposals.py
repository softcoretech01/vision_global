import re
import json
import time
import random
from fastapi import APIRouter, Depends, Request, HTTPException, Query, UploadFile, File
from sqlalchemy import text, bindparam
from ..db import prop_engine, q, one, execute
from ..security import require_auth
from ..integrations.notify import dispatch, email_ready, wa_template, wa_window_open
from ..templating import get_template, render, quotation_mapping
from .. import intake, storage, buyer_flow, photos

router = APIRouter()


@router.post("/fetch-emails")
def fetch_emails(user=Depends(require_auth)):
    """Pull inbox emails matching the configured keywords into supplier proposals."""
    if not intake.connected():
        raise HTTPException(status_code=400, detail="Email inbox is not connected. Configure it in Administration → Integrations.")
    return intake.run_fetch()


def _norm(row: dict) -> dict:
    p = row.get("photos")
    if isinstance(p, str):
        try:
            row["photos"] = json.loads(p)
        except Exception:
            row["photos"] = []
    elif p is None:
        row["photos"] = []

    w = row.get("waiting_list")
    if isinstance(w, str):
        try:
            row["waiting_list"] = json.loads(w)
        except Exception:
            row["waiting_list"] = []
    elif w is None:
        row["waiting_list"] = []

    row["accessories"] = row.get("accessories") or ""

    for k in ("price", "margin_pct"):
        if row.get(k) is not None:
            row[k] = float(row[k])
    return row


@router.get("")
def list_proposals(
    q_text: str = Query("", alias="q"),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    supplier: str = "",
    state: str = "",
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_auth),
):
    """One page of proposal rows (newest first) plus the total, for the page bar."""
    where, params = [], {}
    if date_from:
        where.append("pi.created_at>=:df"); params["df"] = f"{date_from} 00:00:00"
    if date_to:
        where.append("pi.created_at<=:dt"); params["dt"] = f"{date_to} 23:59:59"
    if supplier:
        where.append("pi.supplier_id=:sid"); params["sid"] = int(supplier)
    if state in ("active", "sold", "hold"):
        where.append("COALESCE(pi.state,'active')=:st"); params["st"] = state
    if q_text:
        where.append("(pi.machine LIKE :q OR pi.model LIKE :q OR pi.pro_no LIKE :q OR s.name LIKE :q)"); params["q"] = f"%{q_text}%"
    w = f"WHERE {' AND '.join(where)}" if where else ""
    joins = """FROM proposal_items pi
        LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN proposal_emails pe ON pe.id=pi.proposal_email_id"""
    total = one(prop_engine, f"SELECT COUNT(*) c {joins} {w}", params)["c"]
    lim = max(1, min(int(pageSize) or 50, 200))
    off = (max(int(page), 1) - 1) * lim
    rows = q(prop_engine, f"""
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone, s.email supplier_email,
               pe.channel source_channel, pe.received_at,
               (CASE WHEN EXISTS (SELECT 1 FROM quotations q WHERE q.proposal_item_id = pi.id) THEN 'sent' ELSE 'new' END) as status
        {joins}
        {w} ORDER BY COALESCE(pe.received_at, pi.created_at) DESC, pi.id DESC LIMIT :lim OFFSET :off
    """, {**params, "lim": lim, "off": off})
    return {"rows": [_norm(r) for r in rows], "total": total}


@router.get("/{item_id:int}")
def get_proposal(item_id: int, user=Depends(require_auth)):
    """Single proposal row (all fields) for the full-page details view."""
    row = one(prop_engine, """
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone, s.email supplier_email,
               pe.channel source_channel, pe.received_at
        FROM proposal_items pi
        LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN proposal_emails pe ON pe.id=pi.proposal_email_id
        WHERE pi.id=:id
    """, {"id": item_id})
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"row": _norm(row)}


# Columns the proposal edit form / inline cells may update. Keys are column names,
# so they are safe to interpolate into the UPDATE (never user-supplied identifiers).
_EDITABLE = {
    "machine", "margin_pct", "buyer_segment", "price", "supplier_id",
    "pro_no", "model", "width", "priority", "remarks", "state",
    "through", "payment_term", "confidential", "purchased_by", "mode",
    "machine_color", "year", "quantity", "rate_type", "rate", "price_term",
    "currency", "machine_name", "accessories", "waiting_list", "photos",
}


@router.patch("/{item_id}")
async def update_proposal(item_id: int, req: Request, user=Depends(require_auth)):
    body = await req.json()
    before = one(prop_engine, "SELECT machine, model, machine_name FROM proposal_items WHERE id=:id", {"id": item_id})
    if not before:
        raise HTTPException(status_code=404, detail="not found")
    # The required Model Name is this row's machine everywhere else (list, Send dialog,
    # quotations), so a new Model Name replaces the old machine name too.
    new_model = (body.get("model") or "").strip()
    if new_model and new_model != (before.get("model") or ""):
        body["machine"] = new_model
    sets, params = [], {"id": item_id}
    for key, val in body.items():
        if key in _EDITABLE:
            if key == "confidential":
                val = 1 if val else 0
            elif key in ("photos", "waiting_list") and isinstance(val, (list, dict)):
                val = json.dumps(val)
            sets.append(f"{key}=:{key}"); params[key] = val
    if sets:
        execute(prop_engine, f"UPDATE proposal_items SET {', '.join(sets)} WHERE id=:id", params)
    removed = _prune_waiting_list(item_id, before)
    return {"ok": True, "waiting_list_removed": removed}


def _prune_waiting_list(item_id, before) -> int:
    """After the machine / model / machine name changes, drop Waiting List buyers whose
    enquiries don't match the new machine (Send goes to the Waiting List). Returns how
    many were removed."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item or all(_name_key(before.get(k)) == _name_key(item.get(k)) for k in ("machine", "model", "machine_name")):
        return 0
    ids = _waiting_ids(item)
    if not ids:
        return 0
    still = {r["id"] for r in q(prop_engine, f"""SELECT DISTINCT b.id FROM enquiries e JOIN buyers b ON b.id=e.buyer_id
                                                 WHERE {ENQUIRY_MATCH_SQL}""", _match_params(item))}
    wl = json.loads(item["waiting_list"]) if isinstance(item["waiting_list"], str) else (item["waiting_list"] or [])
    kept = [w for w in wl if int(w.get("id") if isinstance(w, dict) else w) in still]
    if len(kept) != len(wl):
        execute(prop_engine, "UPDATE proposal_items SET waiting_list=:w WHERE id=:id", {"w": json.dumps(kept), "id": item_id})
    return len(wl) - len(kept)


# An enquiry is "for this machine" when its machine/model matches the row's machine or
# model (exactly or as a substring), or its make names the row's machine/model/brand.
# Names are compared ignoring case, spaces and punctuation, so a supplier's
# "Sulzer project ile" or "OpenEnd" still finds "Sulzer Projectile" / "Open End".
# Shared by the Waiting List picker and Send so both see the same buyers.
def _norm_sql(col):
    return f"LOWER(REGEXP_REPLACE(COALESCE({col},''),'[^A-Za-z0-9]',''))"


ENQUIRY_MATCH_SQL = f"""(
       (:m<>'' AND ({_norm_sql('e.machine')}=:m OR {_norm_sql('e.model')}=:m
                   OR {_norm_sql('e.machine')} LIKE CONCAT('%', :m, '%')))
    OR (:mdl<>'' AND ({_norm_sql('e.machine')}=:mdl OR {_norm_sql('e.model')}=:mdl
                     OR {_norm_sql('e.machine')} LIKE CONCAT('%', :mdl, '%')))
    OR ({_norm_sql('e.make')}<>'' AND {_norm_sql('e.make')} IN (:m, :mdl, :mn))
)"""


def _name_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _match_params(item):
    return {"m": _name_key(item.get("machine")), "mdl": _name_key(item.get("model")), "mn": _name_key(item.get("machine_name"))}


def _waiting_ids(item):
    """Buyer ids saved on the row's Waiting List (entries are objects or bare ids)."""
    w = item.get("waiting_list")
    if isinstance(w, str):
        try:
            w = json.loads(w)
        except Exception:
            w = []
    ids = []
    for x in w or []:
        bid = x.get("id") if isinstance(x, dict) else x
        try:
            ids.append(int(bid))
        except (TypeError, ValueError):
            pass
    return ids


@router.get("/{item_id}/enquired-buyers")
def get_enquired_buyers(item_id: int, user=Depends(require_auth)):
    """Fetch buyers who enquired for this machine/model."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    buyers = q(prop_engine, f"""
        SELECT DISTINCT b.id, b.name, b.company, b.city, b.phone, b.email, b.segment,
               e.id enquiry_id, e.machine, e.model
        FROM enquiries e
        JOIN buyers b ON b.id=e.buyer_id
        WHERE {ENQUIRY_MATCH_SQL}
        ORDER BY b.name ASC
    """, _match_params(item))
    # Only buyers who enquired for this machine — no fallback to unrelated buyers.
    formatted, seen = [], set()
    for b in buyers:
        if b["id"] in seen:          # one entry per buyer, even with several enquiries
            continue
        seen.add(b["id"])
        name_part = f"{b['name']} / {b['company']}" if b.get('name') and b.get('company') and b['name'] != b['company'] else (b.get('company') or b.get('name') or 'Buyer')
        label = f"{name_part}-{b['city']}" if b.get('city') else name_part
        if b.get('segment') == 'cold' and 'do not call' not in label.lower():
            label = f"(Do Not Call){label}"
        formatted.append({
            "id": b["id"],
            "label": label,
            "name": b.get("name"),
            "company": b.get("company"),
            "city": b.get("city"),
            "phone": b.get("phone"),
            "email": b.get("email"),
            "segment": b.get("segment"),
            "enquiry_id": b.get("enquiry_id"),
            "machine": b.get("machine"),
            "model": b.get("model"),
        })
    return {"buyers": formatted}


@router.post("/{item_id}/upload-images")
async def upload_proposal_images(
    item_id: int,
    files: list[UploadFile] = File(...),
    user=Depends(require_auth)
):
    """Upload one or more photos for a proposal and append to its photos list."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")

    current_photos = item.get("photos")
    if isinstance(current_photos, str):
        try:
            photos = json.loads(current_photos)
        except Exception:
            photos = []
    elif isinstance(current_photos, list):
        photos = list(current_photos)
    else:
        photos = []

    uploaded = []
    for f in files:
        data = await f.read()
        if data:
            url = storage.save_image(f.filename or "photo.jpg", data, f.content_type or "image/jpeg")
            uploaded.append(url)
            photos.append(url)

    # Photos arriving (also from the team) go to any buyer waiting for them — see buyer_flow.
    execute(prop_engine, """UPDATE proposal_items SET photos=:p, photos_received_at=IF(:new, NOW(), photos_received_at),
                                   photo_status=IF(:new, 'received', photo_status) WHERE id=:id""",
            {"p": json.dumps(photos), "new": 1 if uploaded else 0, "id": item_id})
    return {"ok": True, "uploaded": uploaded, "photos": photos}


@router.post("/{item_id}/state")
async def set_state(item_id: int, req: Request, user=Depends(require_auth)):
    """Set the Active / Sold / Hold state of a proposal row."""
    body = await req.json()
    st = (body.get("state") or "").strip().lower()
    if st not in ("active", "sold", "hold"):
        raise HTTPException(status_code=400, detail="state must be active, sold or hold")
    execute(prop_engine, "UPDATE proposal_items SET state=:st WHERE id=:id", {"st": st, "id": item_id})
    return {"ok": True, "state": st}


@router.post("/bulk-segment")
async def bulk_segment(req: Request, user=Depends(require_auth)):
    body = await req.json()
    seg = body.get("buyer_segment")
    ids = body.get("ids") or []
    with prop_engine.begin() as c:
        if ids:
            stmt = text("UPDATE proposal_items SET buyer_segment=:seg WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            c.execute(stmt, {"seg": seg, "ids": list(ids)})
        else:
            c.execute(text("UPDATE proposal_items SET buyer_segment=:seg"), {"seg": seg})
    return {"ok": True}


@router.post("/{item_id}/request-photo")
def request_photo(item_id: int, user=Depends(require_auth)):
    res = photos.request_supplier_photos(item_id, force=True)
    if res.get("not_found"):
        raise HTTPException(status_code=404, detail="not found")
    if not res.get("ok", True):
        # Don't mark the row "requested" when the message never left.
        raise HTTPException(status_code=502, detail=f"Photo request not sent on {res.get('channel')}: {str(res.get('error') or '')[:300]}")
    return {"ok": True, "channel": res.get("channel"), "simulated": res.get("simulated", True),
            "kind": res.get("kind"), "window_closed": res.get("window_closed", False), "error": res.get("error")}


def _match_buyers(item):
    """Who a Send reaches -> (buyers, source).
      - the row's saved Waiting List, if it has one (hand-picked, so no segment filter)
      - otherwise buyers who enquired for this machine, filtered by the buyer segment.
    One entry per buyer, carrying their latest enquiry (channel, quantity)."""
    ids = _waiting_ids(item)
    if ids:
        stmt = text("""
            SELECT b.id, b.name, b.company, b.city, b.phone, b.email, b.segment, e.channel, e.id enquiry_id, e.quantity qty
            FROM buyers b LEFT JOIN enquiries e ON e.id=(SELECT MAX(id) FROM enquiries WHERE buyer_id=b.id)
            WHERE b.id IN :ids ORDER BY b.name
        """).bindparams(bindparam("ids", expanding=True))
        with prop_engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(stmt, {"ids": ids})], "waiting_list"
    seg = (item.get("buyer_segment") or "everyone").lower()
    seg_sql = ""
    if seg != "everyone":
        segs = [s.strip() for s in seg.split(",") if s.strip() in ("cold", "hot", "very_hot")]
        if segs:
            seg_sql = "AND LOWER(b.segment) IN (" + ", ".join(f"'{s}'" for s in segs) + ")"
    rows = q(prop_engine, f"""
        SELECT b.id, b.name, b.company, b.city, b.phone, b.email, b.segment, e.channel, e.id enquiry_id, e.quantity qty
        FROM enquiries e JOIN buyers b ON b.id=e.buyer_id
        WHERE {ENQUIRY_MATCH_SQL} {seg_sql}
        ORDER BY e.id DESC
    """, _match_params(item))
    seen, buyers = set(), []
    for r in rows:                      # newest enquiry first -> keep one per buyer
        if r["id"] not in seen:
            seen.add(r["id"]); buyers.append(r)
    return buyers, "enquiries"


WA_BUTTON_TEXT_MAX = 1024   # WhatsApp limit for the text of a message with reply buttons


def _buyer_channels(b) -> list:
    """Where a quotation goes: WhatsApp if the buyer has a phone (the conversation —
    Interested / Send photos / Not interested — happens there) and email if they have an
    address and email is set up. A buyer with only an email address still gets email
    (simulated until email is configured)."""
    chans = []
    if re.sub(r"\D", "", b.get("phone") or ""):
        chans.append("whatsapp")
    if b.get("email") and (email_ready() or not chans):
        chans.append("email")
    return chans


@router.get("/{item_id}/recipients")
def recipients(item_id: int, user=Depends(require_auth)):
    """Preview who a Send would reach, given the row's machine + buyer segment."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    buyers, source = _match_buyers(item)
    return {
        "machine": item["machine"],
        "segment": item.get("buyer_segment") or "everyone",
        "count": len(buyers),
        "source": source,   # "waiting_list" or "enquiries"
        "email_ready": email_ready(),
        "buyers": [{"name": b["name"], "email": b["email"], "phone": b["phone"], "segment": b["segment"],
                    "channels": _buyer_channels(b)} for b in buyers],
    }


@router.post("/{item_id}/send")
def send_proposal(item_id: int, user=Depends(require_auth)):
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    buyers, source = _match_buyers(item)
    base = float(item["price"] or 0)
    amount = round(base * (1 + float(item["margin_pct"]) / 100))   # final price per unit
    item_photos = photos.photo_list(item)
    ins_q = text("""INSERT INTO quotations (ref,quote_no,buyer_id,enquiry_id,proposal_item_id,machine,base_price,margin_pct,amount,
                                            channel,status,sent_msgid,wa_msgid,email_msgid,photos_sent_n)
                    VALUES (:ref,:qno,:bid,:eid,:pid,:m,:bp,:mp,:amt,:ch,'sent',:smid,:wmid,:emid,:np)""")
    # Short sequential quotation numbers shown in the offer ("Quotation No 10001").
    quote_no = int(one(prop_engine, "SELECT COALESCE(MAX(quote_no), 10000) n FROM quotations")["n"])
    ins_c = text("INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:bid,:ch,'out',:body,:smid)")
    sent, failed, errors = 0, 0, []
    by_channel = {"whatsapp": 0, "email": 0}
    window_closed = 0   # WhatsApp buyers outside the 24h window with no Meta template set
    for b in buyers:
        chans = _buyer_channels(b)
        if not chans:
            failed += 1
            errors.append(f"{b['name']}: no phone or email")
            continue
        qty = int(b.get("qty") or 1)
        quote_no += 1
        ref = f"QT-{int(time.time()*1000)}-{b['id']}-{random.randint(0,999)}"
        mapping = quotation_mapping(item, b, amount, qty, quote_no)
        fallback = (f"Hello {b['name']}, our offer for {item['machine']} (qty {qty}): "
                    f"{mapping['price']} per unit, total {mapping['total']}.")
        wa_msgid = email_msgid = None
        wa_ok = email_ok = False
        n_photos, logs = 0, []
        if "whatsapp" in chans:
            wtpl = get_template("buyer_quotation", "whatsapp")
            offer = render(wtpl["body"], mapping) if wtpl else fallback
            wbody = f"{offer}\n\n{buyer_flow.prompt_text()}"
            buttons = buyer_flow.buttons_for(ref)
            if wa_template(wtpl, mapping) and not wa_window_open(b["phone"]):
                # First contact: only the approved template is delivered. The first photo
                # rides in its image header; the buttons carry this quotation's ref.
                res = dispatch("whatsapp", b["phone"], "", wbody, wtpl, mapping, buttons,
                               header_image=item_photos[0] if item_photos else None)
                if res.get("ok") and item_photos and res.get("header_image") == item_photos[0]:
                    n_photos = 1
            else:
                # Photos first, then the quotation with the buttons, so they end up at the bottom.
                n_photos = photos.send_images(b["phone"], item_photos)
                if len(wbody) > WA_BUTTON_TEXT_MAX:
                    # A button message holds 1024 characters: send a long offer as its own
                    # message, then the "tick your thoughts" prompt with the buttons.
                    res = dispatch("whatsapp", b["phone"], "", offer, None, mapping)
                    if res.get("ok"):
                        res = dispatch("whatsapp", b["phone"], "", buyer_flow.prompt_text(), None, mapping, buttons)
                else:
                    res = dispatch("whatsapp", b["phone"], "", wbody, wtpl, mapping, buttons)
            if res.get("window_closed"):
                window_closed += 1
            if res.get("ok"):
                wa_ok, wa_msgid = True, res.get("message_id")
                logs.append(("whatsapp", f"[{n_photos} photo(s) sent]\n{wbody}" if n_photos else wbody, wa_msgid))
            else:
                errors.append(f"{b['name']} (WhatsApp): {str(res.get('error') or '')[:200]}")
        if "email" in chans:
            etpl = get_template("buyer_quotation", "email")
            subject = render(etpl["subject"], mapping) if etpl and etpl.get("subject") else f"Quotation — {item['machine']}"
            ebody = render(etpl["body"], mapping) if etpl else fallback
            if item_photos:
                ebody += f"\n\nPhotos of the {item['machine']} are attached."
            res = dispatch("email", b["email"], subject, ebody, etpl, mapping, attachments=item_photos)
            if res.get("ok"):
                email_ok, email_msgid = True, res.get("message_id")
                n_att = res.get("attached") or 0
                logs.append(("email", f"[{n_att} photo(s) attached]\n{ebody}" if n_att else ebody, email_msgid))
            else:
                errors.append(f"{b['name']} (email): {str(res.get('error') or '')[:200]}")
        if not (wa_ok or email_ok):
            failed += 1
            continue
        channel = "whatsapp" if wa_ok else "email"   # where the conversation continues
        with prop_engine.begin() as c:
            c.execute(ins_q, {"ref": ref, "qno": quote_no, "bid": b["id"], "eid": b["enquiry_id"], "pid": item_id,
                              "m": item["machine"], "bp": base, "mp": item["margin_pct"], "amt": amount, "ch": channel,
                              "smid": wa_msgid or email_msgid, "wmid": wa_msgid, "emid": email_msgid, "np": n_photos})
            for ch, body, mid in logs:
                c.execute(ins_c, {"bid": b["id"], "ch": ch, "body": body, "smid": mid})
        by_channel["whatsapp"] += 1 if wa_ok else 0
        by_channel["email"] += 1 if email_ok else 0
        sent += 1
    return {"ok": True, "sent": sent, "failed": failed, "errors": errors[:5], "byChannel": by_channel,
            "amount": amount, "matchedBuyers": len(buyers), "source": source, "windowClosed": window_closed}
