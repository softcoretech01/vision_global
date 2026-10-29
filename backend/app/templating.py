"""Load message templates from Etex_admin and render {{placeholder}} values."""
from datetime import datetime
from .db import admin_engine, one, q


def get_template(kind: str, channel: str = None):
    """Pick the active template for this kind, preferring an exact channel match,
    then an 'any' template, then whatever exists."""
    rows = q(admin_engine, "SELECT * FROM templates WHERE kind=:k AND active=1 ORDER BY id", {"k": kind})
    if not rows:
        return None
    if channel:
        for r in rows:
            if (r.get("channel") or "").lower() == channel.lower():
                return r
        for r in rows:
            if (r.get("channel") or "").lower() == "any":
                return r
    return rows[0]


def render(text: str, mapping: dict) -> str:
    out = text or ""
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", "" if v is None else str(v))
    return out


def inr(amount) -> str:
    """₹ with Indian digit grouping: 287500 -> ₹2,87,500."""
    n = int(round(float(amount or 0)))
    digits, sign = str(abs(n)), "-" if n < 0 else ""
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"₹{sign}{digits}"


def offer_details(item: dict) -> str:
    """The machine lines of an offer, from the supplier proposal row — e.g.
    "1x Muller MBJ3, yoc 1995, width 190 cm" followed by its accessories."""
    item = item or {}
    model = (item.get("model") or item.get("machine") or "").strip()
    qty = str(item.get("quantity") or "").strip()
    parts = [f"{qty}x {model}" if qty and model else model]
    if item.get("year"):
        parts.append(f"yoc {item['year']}")
    if item.get("width"):
        parts.append(f"width {item['width']}")
    if item.get("mode"):
        parts.append(str(item["mode"]))
    if item.get("machine_color"):
        parts.append(f"{item['machine_color']} color")
    lines = [", ".join(x for x in parts if x)]
    acc = (item.get("accessories") or "").strip()
    if acc:
        lines.append(acc)
    return "\n".join(x for x in lines if x)[:700]


def quotation_mapping(item: dict, buyer: dict, amount, qty: int, quote_no=None, when=None) -> dict:
    """Placeholder values for buyer quotation templates (WhatsApp / email / view)."""
    item, buyer = item or {}, buyer or {}
    unit = inr(amount)
    return {
        "buyer": buyer.get("name") or "",
        "company": buyer.get("company") or buyer.get("name") or "",
        "city": buyer.get("city") or "",
        "machine": item.get("machine") or "",
        "model": item.get("model") or item.get("machine") or "",
        "pro_no": item.get("pro_no") or "",
        "details": offer_details(item),
        "qty": qty,
        "price": unit, "amount": unit,
        "total": inr(float(amount or 0) * (qty or 1)),
        "quotation_no": quote_no or "",
        "date": (when or datetime.now()).strftime("%d/%m/%Y"),
        "supplier": "",
    }
