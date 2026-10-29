"""Machine photos: ask a supplier for them and send them out on WhatsApp.

Used by the Supplier Proposal 📷 button, by the buyer's "Send photos" tap (when the
row has no photos yet), and by photo forwarding in buyer_flow."""
import json
from .db import prop_engine, one, execute
from .integrations.notify import dispatch, pick_channel, send_whatsapp_image
from .templating import get_template, render

MAX_PHOTOS = 5          # per WhatsApp send, so a buyer isn't flooded
REREQUEST_HOURS = 24    # don't nag the supplier again within this window
# Starting wording of the supplier photo request (seeded into Message Templates).
PHOTO_REQUEST_SUBJECT = "Please share machine photos"
PHOTO_REQUEST_DEFAULT = "Hi {{supplier}}, kindly share clear photos of the {{machine}} for buyer review."


def photo_list(item) -> list:
    p = (item or {}).get("photos")
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            p = []
    return [u for u in (p or []) if u]


def send_images(to: str, urls: list) -> int:
    """Send up to MAX_PHOTOS photos on WhatsApp; returns how many went out."""
    sent = 0
    for url in urls[:MAX_PHOTOS]:
        if send_whatsapp_image(to, url).get("ok"):
            sent += 1
    return sent


def request_supplier_photos(item_id: int, force: bool = False) -> dict:
    """Ask the row's supplier for machine photos (their quote's channel; an email
    supplier with a phone gets WhatsApp while email isn't set up). Without `force`,
    skips if we already asked within REREQUEST_HOURS."""
    item = one(prop_engine, """
        SELECT pi.*, s.name supplier_name, s.phone supplier_phone, s.email supplier_email, pe.channel
        FROM proposal_items pi LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN proposal_emails pe ON pe.id=pi.proposal_email_id WHERE pi.id=:id
    """, {"id": item_id})
    if not item:
        return {"ok": False, "error": "not found", "not_found": True}
    if not force and item.get("photo_status") == "requested" and one(prop_engine, f"""
            SELECT id FROM photo_requests WHERE proposal_item_id=:p AND created_at > NOW() - INTERVAL {REREQUEST_HOURS} HOUR
            LIMIT 1""", {"p": item_id}):
        return {"ok": True, "skipped": True, "channel": item.get("channel")}
    channel = pick_channel(item.get("channel") or "email", item.get("supplier_phone"))
    to = item["supplier_phone"] if channel == "whatsapp" else item["supplier_email"]
    tpl = get_template("photo_request", channel)
    mapping = {"supplier": item["supplier_name"], "machine": item["machine"]}
    subject = render((tpl or {}).get("subject") or PHOTO_REQUEST_SUBJECT, mapping)
    body = render((tpl or {}).get("body") or PHOTO_REQUEST_DEFAULT, mapping)
    res = dispatch(channel, to, subject, body, tpl, mapping)
    if not res.get("ok", True):
        return {**res, "channel": channel}     # don't mark the row "requested" when nothing left
    execute(prop_engine, "INSERT INTO photo_requests (proposal_item_id,supplier_id,channel,status) VALUES (:p,:s,:c,'sent')",
            {"p": item_id, "s": item["supplier_id"], "c": channel})
    execute(prop_engine, "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('supplier',:s,:c,'out',:b)",
            {"s": item["supplier_id"], "c": channel, "b": body})
    execute(prop_engine, "UPDATE proposal_items SET photo_status='requested', photo_request_msgid=:mid WHERE id=:id",
            {"mid": res.get("message_id"), "id": item_id})
    return {**res, "channel": channel}
