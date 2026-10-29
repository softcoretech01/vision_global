import re
from fastapi import APIRouter, Depends, Query, Request
from ..db import prop_engine, q, one, execute
from ..security import require_auth

router = APIRouter()


@router.post("")
async def create_enquiry(req: Request, user=Depends(require_auth)):
    """Add a buyer enquiry (reuses the buyer with the same phone, else the same email)."""
    b = await req.json()
    email = (b.get("email") or "").strip()
    company = (b.get("company") or "").strip()
    name = (b.get("name") or "").strip() or company or email or "Buyer"
    city = (b.get("city") or "").strip()
    make = (b.get("make") or "").strip()
    model = (b.get("model") or "").strip()
    # The machine used for buyer↔supplier matching is the Model.
    machine = model or (b.get("machine") or "").strip()
    priority = (b.get("priority") or "").strip() or "Medium"
    status = (b.get("status") or "").strip() or "New"
    phone = (b.get("phone") or "").strip()
    digits = re.sub(r"\D", "", phone)
    # Same person = same phone (last 10 digits, ignoring +91 / spaces), else same email.
    # One buyer record per person keeps WhatsApp replies on the right quotations.
    buyer = None
    if len(digits) >= 10:
        buyer = one(prop_engine, """SELECT id FROM buyers
                                    WHERE RIGHT(REGEXP_REPLACE(COALESCE(phone,''),'[^0-9]',''),10)=RIGHT(:d,10)
                                    ORDER BY id LIMIT 1""", {"d": digits})
    if not buyer and email:
        buyer = one(prop_engine, "SELECT id FROM buyers WHERE email=:e LIMIT 1", {"e": email})
    if buyer:
        bid = buyer["id"]
        # Keep company / city / segment fresh on a repeat enquiry; fill a missing phone or email.
        execute(prop_engine, """UPDATE buyers SET company=COALESCE(NULLIF(:co,''),company), city=COALESCE(NULLIF(:ci,''),city),
                                       segment=COALESCE(NULLIF(:seg,''),segment),
                                       phone=COALESCE(NULLIF(phone,''),NULLIF(:p,'')), email=COALESCE(NULLIF(email,''),NULLIF(:e,''))
                                WHERE id=:id""",
                {"co": company, "ci": city, "seg": b.get("segment") or "", "p": phone, "e": email, "id": bid})
    else:
        bid = execute(prop_engine,
                      "INSERT INTO buyers (name,company,city,phone,email,segment) VALUES (:n,:co,:ci,:p,:e,:seg)",
                      {"n": name, "co": company, "ci": city, "p": b.get("phone") or "",
                       "e": email, "seg": (b.get("segment") or "cold")})["lastrowid"]
    mx = one(prop_engine, "SELECT COALESCE(MAX(CAST(SUBSTRING(ref,5) AS UNSIGNED)),2000) m FROM enquiries WHERE ref LIKE 'ENQ-%'")["m"]
    ref = f"ENQ-{int(mx) + 1}"
    eid = execute(prop_engine,
                  """INSERT INTO enquiries (ref,buyer_id,channel,make,model,machine,category,quantity,specs,priority,status)
                     VALUES (:ref,:bid,:ch,:mk,:mdl,:m,:cat,:qty,'',:pri,:st)""",
                  {"ref": ref, "bid": bid, "ch": (b.get("channel") or "whatsapp"), "mk": make, "mdl": model,
                   "m": machine, "cat": b.get("category") or "", "qty": int(b.get("quantity") or 1),
                   "pri": priority, "st": status})["lastrowid"]
    return {"ok": True, "id": eid, "ref": ref, "buyer_id": bid}


@router.get("")
def list_enquiries(
    channel: str = "",
    q_text: str = Query("", alias="q"),
    date_from: str = Query("", alias="from"),
    date_to: str = Query("", alias="to"),
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_auth),
):
    where, params = [], {}
    if channel:
        where.append("e.channel=:ch"); params["ch"] = channel
    if date_from:
        where.append("e.received_at>=:df"); params["df"] = f"{date_from} 00:00:00"
    if date_to:
        where.append("e.received_at<=:dt"); params["dt"] = f"{date_to} 23:59:59"
    if q_text:
        where.append("(e.machine LIKE :q OR e.model LIKE :q OR e.make LIKE :q OR e.ref LIKE :q OR b.name LIKE :q OR b.company LIKE :q OR b.city LIKE :q)")
        params["q"] = f"%{q_text}%"
    w = f"WHERE {' AND '.join(where)}" if where else ""

    lim = min(int(pageSize) or 50, 200)
    off = (max(int(page), 1) - 1) * lim
    total = one(prop_engine, f"SELECT COUNT(*) c FROM enquiries e LEFT JOIN buyers b ON b.id=e.buyer_id {w}", params)["c"]
    rows = q(prop_engine, f"""
        SELECT e.id, e.ref, e.channel, e.make, e.model, e.machine, e.category, e.quantity, e.specs,
               e.priority, e.status, e.received_at,
               b.name buyer_name, b.company buyer_company, b.city buyer_city, b.segment
        FROM enquiries e LEFT JOIN buyers b ON b.id=e.buyer_id
        {w} ORDER BY e.received_at DESC LIMIT :lim OFFSET :off
    """, {**params, "lim": lim, "off": off})
    return {"rows": rows, "total": total, "page": int(page), "pageSize": lim}
