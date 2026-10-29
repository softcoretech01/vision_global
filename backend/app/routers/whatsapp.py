"""Meta WhatsApp Cloud API webhook.

Meta delivers inbound WhatsApp messages by calling this endpoint (it does NOT work
over IMAP-style polling), so the backend must be reachable at a public HTTPS URL.
On localhost, expose it with a tunnel (e.g. `ngrok http 8000`) and register
    https://<public-host>/api/whatsapp/webhook
in the Meta app dashboard with the verify token from WA_VERIFY_TOKEN.

  GET  -> webhook verification handshake (returns hub.challenge)
  POST -> inbound messages: buyer replies, supplier photos, supplier proposals
"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from .. import intake

router = APIRouter()


@router.get("/webhook")
def verify(request: Request):
    """Meta calls this once when you save the webhook URL to confirm the verify token."""
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == os.environ.get("WA_VERIFY_TOKEN", ""):
        return PlainTextResponse(p.get("hub.challenge", ""))
    return PlainTextResponse("verification failed", status_code=403)


@router.post("/webhook")
async def inbound(request: Request):
    """Receive message notifications. Always 200 quickly so Meta doesn't retry."""
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}
    # Diagnostic log: every inbound hit, so we can see exactly what Meta delivers.
    try:
        import os, json, datetime
        logp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "whatsapp_inbound.log")
        with open(logp, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.datetime.now().isoformat()} {json.dumps(payload)[:2000]}\n")
    except Exception:
        pass
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                if value.get("messages"):
                    intake.handle_whatsapp_messages(value)
    except Exception as e:
        print(f"[WHATSAPP · webhook-error] {e}")
    return {"ok": True}
