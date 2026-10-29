from fastapi import APIRouter, Depends, Request, HTTPException, Query
from ..db import prop_engine, q, one, execute
from ..security import require_auth
from ..templating import get_template, render

router = APIRouter()


@router.get("")
def list_quotations(
    q_text: str = Query("", alias="q"),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
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
    w = f"WHERE {' AND '.join(where)}" if where else ""
    lim = min(int(pageSize) or 50, 200)
    off = (max(int(page), 1) - 1) * lim
    total = one(prop_engine, f"SELECT COUNT(*) c FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id {w}", params)["c"]
    rows = q(prop_engine, f"""
        SELECT qt.id, qt.ref, qt.machine, qt.amount, qt.channel, qt.status, qt.sent_at,
               b.name buyer_name, b.company buyer_company, f.frequency followup
        FROM quotations qt LEFT JOIN buyers b ON b.id=qt.buyer_id
        LEFT JOIN followups f ON f.quotation_id=qt.id
        {w} ORDER BY qt.sent_at DESC LIMIT :lim OFFSET :off
    """, {**params, "lim": lim, "off": off})
    for r in rows:
        if r.get("amount") is not None:
            r["amount"] = float(r["amount"])
    return {"rows": rows, "total": total}


@router.get("/{qid}")
def get_quotation(qid: int, user=Depends(require_auth)):
    row = one(prop_engine, """
        SELECT qt.*, b.name buyer_name, b.company buyer_company, b.phone buyer_phone, b.email buyer_email
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
    unit = f"₹{amount:,.0f}"
    total = f"₹{amount * qty:,.0f}"
    tpl = get_template("buyer_quotation", row.get("channel"))
    mapping = {"buyer": row.get("buyer_name"), "machine": row.get("machine"), "qty": qty,
               "price": unit, "amount": unit, "total": total, "supplier": ""}
    row["qty"] = qty
    row["rendered_subject"] = render(tpl["subject"], mapping) if tpl and tpl.get("subject") else f"Quotation — {row.get('machine')}"
    row["rendered_body"] = render(tpl["body"], mapping) if tpl else f"Hello {row.get('buyer_name')}, our offer for {row.get('machine')} (qty {qty}): {unit} per unit, total {total}."
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


@router.get("/{qid}/chat")
def get_chat(qid: int, user=Depends(require_auth)):
    qrow = one(prop_engine, "SELECT buyer_id FROM quotations WHERE id=:id", {"id": qid})
    if not qrow:
        return {"rows": []}
    rows = q(prop_engine,
             "SELECT * FROM chat_messages WHERE party_type='buyer' AND party_id=:bid ORDER BY created_at ASC",
             {"bid": qrow["buyer_id"]})
    return {"rows": rows}
