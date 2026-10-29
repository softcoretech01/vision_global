import json
import time
import random
from fastapi import APIRouter, Depends, Request, HTTPException, Query, UploadFile, File
from sqlalchemy import text, bindparam
from ..db import prop_engine, q, one, execute
from ..security import require_auth
from ..integrations.notify import dispatch
from ..templating import get_template, render
from .. import intake, storage

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
    user=Depends(require_auth),
):
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
    rows = q(prop_engine, f"""
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone, s.email supplier_email,
               pe.channel source_channel, pe.received_at,
               (CASE WHEN EXISTS (SELECT 1 FROM quotations q WHERE q.proposal_item_id = pi.id) THEN 'sent' ELSE 'new' END) as status
        FROM proposal_items pi
        LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN proposal_emails pe ON pe.id=pi.proposal_email_id
        {w} ORDER BY COALESCE(pe.received_at, pi.created_at) DESC, pi.id DESC LIMIT 1000
    """, params)
    return {"rows": [_norm(r) for r in rows]}


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
    return {"ok": True}


@router.get("/{item_id}/enquired-buyers")
def get_enquired_buyers(item_id: int, user=Depends(require_auth)):
    """Fetch buyers who enquired for this machine/model."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    m = (item.get("machine") or "").strip()
    mdl = (item.get("model") or "").strip()
    # Find all enquiries matching machine or model
    buyers = q(prop_engine, """
        SELECT DISTINCT b.id, b.name, b.company, b.city, b.phone, b.email, b.segment,
               e.id enquiry_id, e.machine, e.model
        FROM enquiries e
        JOIN buyers b ON b.id=e.buyer_id
        WHERE (:m<>'' AND (e.machine=:m OR e.model=:m))
           OR (:mdl<>'' AND (e.machine=:mdl OR e.model=:mdl))
           OR (:m<>'' AND LOWER(e.machine) LIKE LOWER(CONCAT('%', :m, '%')))
           OR (:mdl<>'' AND LOWER(e.machine) LIKE LOWER(CONCAT('%', :mdl, '%')))
        ORDER BY b.name ASC
    """, {"m": m, "mdl": mdl})
    # If none found for this specific model, fallback to recent enquired buyers
    if not buyers:
        buyers = q(prop_engine, """
            SELECT DISTINCT b.id, b.name, b.company, b.city, b.phone, b.email, b.segment,
                   e.id enquiry_id, e.machine, e.model
            FROM enquiries e
            JOIN buyers b ON b.id=e.buyer_id
            ORDER BY e.received_at DESC LIMIT 50
        """)
    formatted = []
    for b in buyers:
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

    execute(prop_engine, "UPDATE proposal_items SET photos=:p WHERE id=:id",
            {"p": json.dumps(photos), "id": item_id})
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
    item = one(prop_engine, """
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone, s.email supplier_email, pe.channel
        FROM proposal_items pi LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN proposal_emails pe ON pe.id=pi.proposal_email_id WHERE pi.id=:id
    """, {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    channel = item.get("channel") or "email"
    to = item["supplier_phone"] if channel == "whatsapp" else item["supplier_email"]
    tpl = get_template("photo_request")
    mapping = {"supplier": item["supplier_name"], "machine": item["machine"]}
    subject = render(tpl["subject"], mapping) if tpl and tpl.get("subject") else "Please share machine photos"
    body = (render(tpl["body"], mapping) if tpl
            else f"Hi {item['supplier_name']}, kindly share clear photos of the {item['machine']} for buyer review.")
    res = dispatch(channel, to, subject, body)
    msgid = res.get("message_id")
    execute(prop_engine, "INSERT INTO photo_requests (proposal_item_id,supplier_id,channel,status) VALUES (:p,:s,:c,'sent')",
            {"p": item_id, "s": item["supplier_id"], "c": channel})
    execute(prop_engine, "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('supplier',:s,:c,'out',:b)",
            {"s": item["supplier_id"], "c": channel, "b": body})
    execute(prop_engine, "UPDATE proposal_items SET photo_status='requested', photo_request_msgid=:mid WHERE id=:id",
            {"mid": msgid, "id": item_id})
    return {"ok": True, "channel": channel, "simulated": res.get("simulated", True)}


def _match_buyers(item):
    """Buyers who enquired for this machine, filtered by the row's buyer segment."""
    seg = (item.get("buyer_segment") or "everyone").lower()
    seg_sql = ""
    if seg != "everyone":
        segs = [s.strip() for s in seg.split(",") if s.strip() in ("cold", "hot", "very_hot")]
        if segs:
            seg_sql = "AND LOWER(b.segment) IN (" + ", ".join(f"'{s}'" for s in segs) + ")"
    return q(prop_engine, f"""
        SELECT DISTINCT b.id, b.name, b.phone, b.email, b.segment, e.channel, e.id enquiry_id, e.quantity qty
        FROM enquiries e JOIN buyers b ON b.id=e.buyer_id
        WHERE e.machine=:m {seg_sql}
    """, {"m": item["machine"]})


@router.get("/{item_id}/recipients")
def recipients(item_id: int, user=Depends(require_auth)):
    """Preview who a Send would reach, given the row's machine + buyer segment."""
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    buyers = _match_buyers(item)
    return {
        "machine": item["machine"],
        "segment": item.get("buyer_segment") or "everyone",
        "count": len(buyers),
        "buyers": [{"name": b["name"], "email": b["email"], "segment": b["segment"], "channel": b["channel"]} for b in buyers],
    }


@router.post("/{item_id}/send")
def send_proposal(item_id: int, user=Depends(require_auth)):
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    buyers = _match_buyers(item)
    base = float(item["price"] or 0)
    amount = round(base * (1 + float(item["margin_pct"]) / 100))   # final price per unit
    sent = 0
    ins_q = text("""INSERT INTO quotations (ref,buyer_id,enquiry_id,proposal_item_id,machine,base_price,margin_pct,amount,channel,status,sent_msgid)
                    VALUES (:ref,:bid,:eid,:pid,:m,:bp,:mp,:amt,:ch,'sent',:smid)""")
    ins_c = text("INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:bid,:ch,'out',:body,:smid)")
    sent = 0
    for b in buyers:
        channel = b["channel"] or "email"
        to = b["phone"] if channel == "whatsapp" else b["email"]
        qty = int(b.get("qty") or 1)
        unit_str = f"₹{amount:,}"
        total_str = f"₹{amount * qty:,}"
        tpl = get_template("buyer_quotation", channel)
        ref = f"QT-{int(time.time()*1000)}-{b['id']}-{random.randint(0,999)}"
        mapping = {
            "buyer": b["name"], "machine": item["machine"], "qty": qty,
            "price": unit_str, "amount": unit_str, "total": total_str, "supplier": "",
        }
        subject = render(tpl["subject"], mapping) if tpl and tpl.get("subject") else f"Quotation — {item['machine']}"
        body = (render(tpl["body"], mapping) if tpl
                else f"Hello {b['name']}, our offer for {item['machine']} (qty {qty}): {unit_str} per unit, total {total_str}.")
        res = dispatch(channel, to, subject, body)   # sent before DB write so we capture the Message-ID
        msgid = res.get("message_id") if isinstance(res, dict) else None
        with prop_engine.begin() as c:
            c.execute(ins_q, {"ref": ref, "bid": b["id"], "eid": b["enquiry_id"], "pid": item_id,
                              "m": item["machine"], "bp": base, "mp": item["margin_pct"], "amt": amount, "ch": channel, "smid": msgid})
            c.execute(ins_c, {"bid": b["id"], "ch": channel, "body": body, "smid": msgid})
        sent += 1
    return {"ok": True, "sent": sent, "amount": amount, "matchedBuyers": len(buyers)}
