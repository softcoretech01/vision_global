import re
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from ..db import prop_engine, q, one, execute
from ..security import require_auth
from ..templating import get_template, render, quotation_mapping
from ..integrations.notify import dispatch, wa_window_open

router = APIRouter()

# Buyer Quotation tabs -> filter on the buyer's WhatsApp response (see buyer_flow).
TABS = {
    "all": "1=1",
    # Interested buyers stay Potential while they go on to ask for / receive photos.
    "potential": "(qt.interested_at IS NOT NULL AND qt.buyer_status<>'not_interested')",
    "photos": "qt.buyer_status='photos_requested'",
    "support": "qt.support_open=1",
    "not_interested": "qt.buyer_status='not_interested'",
}


@router.get("")
def list_quotations(
    q_text: str = Query("", alias="q"),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    tab: str = "all",
    proposal: str = "",
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_auth),
):
    where, params = [], {}
    if date_from:
        where.append("qt.sent_at>=:df"); params["df"] = f"{date_from} 00:00:00"
    if date_to:
        where.append("qt.sent_at<=:dt"); params["dt"] = f"{date_to} 23:59:59"
    if q_text:
        where.append("(qt.machine LIKE :q OR b.name LIKE :q OR qt.ref LIKE :q)"); params["q"] = f"%{q_text}%"
    if proposal.isdigit():   # buyers quoted from one supplier proposal (its details page)
        where.append("qt.proposal_item_id=:pid"); params["pid"] = int(proposal)
    base_w = f"WHERE {' AND '.join(where)}" if where else ""
    # Per-tab counts honour the search/date filters, so the badges match what you'd see.
    counts = one(prop_engine, f"""
        SELECT COUNT(*) `all`, {', '.join(f"SUM({cond}) `{k}`" for k, cond in TABS.items() if k != 'all')}
        FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id {base_w}
    """, params)
    counts = {k: int(v or 0) for k, v in counts.items()}
    where.append(TABS.get(tab, "1=1"))
    w = f"WHERE {' AND '.join(where)}"
    lim = min(int(pageSize) or 50, 200)
    off = (max(int(page), 1) - 1) * lim
    total = one(prop_engine, f"SELECT COUNT(*) c FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id {w}", params)["c"]
    rows = q(prop_engine, f"""
        SELECT qt.id, qt.ref, qt.machine, qt.amount, qt.channel, qt.status, qt.sent_at,
               qt.buyer_status, qt.buyer_status_at, qt.interested_at, qt.support_open, qt.support_reason, qt.support_at,
               qt.wa_msgid IS NOT NULL OR qt.channel='whatsapp' via_whatsapp,
               qt.email_msgid IS NOT NULL OR qt.channel='email' via_email,
               b.name buyer_name, b.company buyer_company, f.frequency followup
        FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id
        LEFT JOIN followups f ON f.quotation_id=qt.id
        {w} ORDER BY qt.sent_at DESC LIMIT :lim OFFSET :off
    """, {**params, "lim": lim, "off": off})
    for r in rows:
        if r.get("amount") is not None:
            r["amount"] = float(r["amount"])
    return {"rows": rows, "total": total, "counts": counts}


@router.get("/{qid}")
def get_quotation(qid: int, user=Depends(require_auth)):
    row = one(prop_engine, """
        SELECT qt.*, b.name buyer_name, b.company buyer_company, b.city buyer_city, b.phone buyer_phone, b.email buyer_email
        FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id WHERE qt.id=:id
    """, {"id": qid})
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("amount", "base_price", "margin_pct"):
        if row.get(k) is not None:
            row[k] = float(row[k])
    # Quantity the buyer asked for (from their enquiry).
    qty = 1
    if row.get("enquiry_id"):
        e = one(prop_engine, "SELECT quantity FROM enquiries WHERE id=:id", {"id": row["enquiry_id"]})
        if e and e.get("quantity"):
            qty = int(e["quantity"])
    amount = float(row.get("amount") or 0)
    tpl = get_template("buyer_quotation", row.get("channel"))
    item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": row.get("proposal_item_id")}) or {"machine": row.get("machine")}
    buyer = {"name": row.get("buyer_name"), "company": row.get("buyer_company"), "city": row.get("buyer_city")}
    mapping = quotation_mapping(item, buyer, amount, qty, row.get("quote_no"), row.get("sent_at"))
    row["qty"] = qty
    row["rendered_subject"] = render(tpl["subject"], mapping) if tpl and tpl.get("subject") else f"Quotation — {row.get('machine')}"
    row["rendered_body"] = (render(tpl["body"], mapping) if tpl else
                            f"Hello {row.get('buyer_name')}, our offer for {row.get('machine')} (qty {qty}): "
                            f"{mapping['price']} per unit, total {mapping['total']}.")
    return {"row": row}


@router.put("/{qid}/followup")
async def set_followup(qid: int, req: Request, user=Depends(require_auth)):
    body = await req.json()
    frequency = body.get("frequency")
    qrow = one(prop_engine, "SELECT buyer_id, sent_at FROM quotations WHERE id=:id", {"id": qid})
    if not qrow:
        raise HTTPException(status_code=404, detail="not found")
    # next_run: daily = 24h after the quotation was sent, weekly = 7 days; dnd = never.
    next_expr = {
        "daily": "DATE_ADD((SELECT sent_at FROM quotations WHERE id=:qid), INTERVAL 1 DAY)",
        "weekly": "DATE_ADD((SELECT sent_at FROM quotations WHERE id=:qid), INTERVAL 7 DAY)",
    }.get(frequency, "NULL")
    execute(prop_engine, f"""
        INSERT INTO followups (quotation_id,buyer_id,frequency,next_run)
        VALUES (:qid,:bid,:freq,{next_expr})
        ON DUPLICATE KEY UPDATE frequency=VALUES(frequency), next_run=VALUES(next_run)
    """, {"qid": qid, "bid": qrow["buyer_id"], "freq": frequency})
    return {"ok": True}


@router.post("/{qid}/resolve")
def resolve_support(qid: int, user=Depends(require_auth)):
    """Team has handled the buyer's question/bargain: close the Need Support case."""
    res = execute(prop_engine, "UPDATE quotations SET support_open=0, support_resolved_at=NOW() WHERE id=:id", {"id": qid})
    if not res["rowcount"]:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


@router.get("/{qid}/chat")
def get_chat(qid: int, user=Depends(require_auth)):
    qrow = one(prop_engine, """SELECT qt.buyer_id, qt.support_open, b.phone, b.email FROM quotations qt
                               LEFT JOIN buyers b ON b.id=qt.buyer_id WHERE qt.id=:id""", {"id": qid})
    if not qrow:
        return {"rows": []}
    rows = q(prop_engine,
             "SELECT * FROM chat_messages WHERE party_type='buyer' AND party_id=:bid ORDER BY created_at ASC",
             {"bid": qrow["buyer_id"]})
    has_phone = bool(re.sub(r"\D", "", qrow.get("phone") or ""))
    return {"rows": rows, "reply_channel": "whatsapp" if has_phone else ("email" if qrow.get("email") else None),
            # Channels the team can reply on from Chat History (its WhatsApp / Email tabs).
            "channels": {"whatsapp": qrow.get("phone") if has_phone else None, "email": qrow.get("email") or None},
            "window_open": wa_window_open(qrow.get("phone")) if has_phone else None,
            "support_open": bool(qrow.get("support_open"))}


@router.post("/{qid}/reply")
async def reply(qid: int, req: Request, user=Depends(require_auth)):
    """Team reply to the buyer from Chat History, on `channel` ('whatsapp' / 'email'; by
    default WhatsApp if they have a phone, else email). `resolve: true` also closes their
    Need Support case."""
    b = await req.json()
    msg = (b.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message is empty")
    qrow = one(prop_engine, """SELECT qt.buyer_id, qt.machine, b.phone, b.email FROM quotations qt
                               LEFT JOIN buyers b ON b.id=qt.buyer_id WHERE qt.id=:id""", {"id": qid})
    if not qrow:
        raise HTTPException(status_code=404, detail="not found")
    has_phone = bool(re.sub(r"\D", "", qrow.get("phone") or ""))
    channel = b.get("channel") if b.get("channel") in ("whatsapp", "email") else ("whatsapp" if has_phone else "email")
    to = (qrow["phone"] if has_phone else None) if channel == "whatsapp" else qrow.get("email")
    if not to:
        raise HTTPException(status_code=400, detail=f"Buyer has no {'phone number' if channel == 'whatsapp' else 'email address'}")
    res = dispatch(channel, to, f"Re: your {qrow.get('machine')} quotation", msg)
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=f"Not sent on {channel}: {str(res.get('error') or '')[:300]}")
    execute(prop_engine,
            "INSERT INTO chat_messages (party_type,party_id,channel,direction,body,source_msg_id) VALUES ('buyer',:b,:ch,'out',:body,:mid)",
            {"b": qrow["buyer_id"], "ch": channel, "body": msg, "mid": res.get("message_id")})
    if b.get("resolve"):
        execute(prop_engine, "UPDATE quotations SET support_open=0, support_resolved_at=NOW() WHERE id=:id", {"id": qid})
    return {"ok": True, "channel": channel, "simulated": res.get("simulated", False),
            "window_closed": bool(res.get("window_closed"))}
