from fastapi import APIRouter, Depends
from ..db import prop_engine, q, one
from ..security import require_auth

router = APIRouter()


@router.get("")
def dashboard(user=Depends(require_auth)):
    enquiries = one(prop_engine, "SELECT COUNT(*) c FROM enquiries")["c"]
    proposals = one(prop_engine, "SELECT COUNT(*) c FROM proposal_items")["c"]
    quotations = one(prop_engine, "SELECT COUNT(*) c FROM quotations")["c"]
    buyers = one(prop_engine, "SELECT COUNT(*) c FROM buyers")["c"]
    suppliers = one(prop_engine, "SELECT COUNT(*) c FROM suppliers")["c"]
    chan = q(prop_engine, "SELECT channel, COUNT(*) c FROM enquiries GROUP BY channel")
    by_channel = {"whatsapp": 0, "email": 0}
    for r in chan:
        by_channel[r["channel"]] = r["c"]
    recent = q(prop_engine, """
        SELECT e.id, e.ref, e.channel, e.machine, e.category, e.quantity, e.status, e.received_at,
               b.name buyer_name, b.company buyer_company
        FROM enquiries e LEFT JOIN buyers b ON b.id=e.buyer_id
        ORDER BY e.received_at DESC LIMIT 8
    """)
    return {
        "enquiries": enquiries, "proposals": proposals, "quotations": quotations,
        "buyers": buyers, "suppliers": suppliers, "byChannel": by_channel, "recent": recent,
    }
