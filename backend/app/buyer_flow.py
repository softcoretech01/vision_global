"""WhatsApp conversation with a buyer after a quotation is sent.

The quotation goes out with three reply buttons (Interested / Send photos / Not
interested). Each button id carries the quotation ref, so a tap updates exactly that
quotation. Typed answers ("1", "yes", "send photos", "not interested") count too.
Small talk (thanks, hello, ok, bye) just gets a friendly reply. A question or a
bargain (price, location, delivery, payment, details, chasing photos) opens a Need
Support case for the team, with a reply that fits the topic. The generic "Fine. Our team
will keep in touch" line goes to a buyer at most once.

Photos: "Send photos" sends the row's photos the buyer doesn't have yet. If there are
none, the supplier is asked automatically and the buyer waits in Photos Requested;
process_photo_forwards() delivers the supplier's photos as soon as they arrive.

  quotations.buyer_status   sent | interested | photos_requested | photos_sent | not_interested
  quotations.support_open   1 while the buyer needs a person
"""
import os
import re
from .db import prop_engine, q, one, execute
from .integrations.notify import dispatch
from .templating import get_template, render
from . import photos

# (action, button title) — titles are max 20 chars on WhatsApp.
BUTTONS = [("interested", "Interested"), ("photos", "Send photos"), ("not_interested", "Not interested")]

# Every message the bot sends, by template kind. These are the starting wording; each is
# seeded into Admin -> Message Templates (migrate_v16) and edited there.
DEFAULTS = {
    "quotation_prompt": ("Dear Sir, we have sent the Quotation herewith. Pls go thru it and tick your thoughts;\n"
                         "1. Interested\n2. Send photos\n3. Not interested"),
    "interested_reply": "Thank you for your interest! 🙏 Our sales team will contact you shortly to take the {{machine}} forward.",
    "photos_reply": "Sure, we will share the photos of the {{machine}} shortly.",
    "photos_sent_reply": "Here are the photos of the {{machine}}. Please tick your thoughts:",
    "not_interested_reply": "Thank you. We will share other offers that suit you.",
    # Thanks, appreciation and acknowledgements (ok / okay / fine …).
    "thanks_reply": "Fine. If you need any support, pls message us.",
    "greeting_pending_reply": "Hello! 👋 Hope you're doing well. Did you get a chance to look at our quotation for the {{machine}}?",
    "greeting_interested_reply": "Hello! 👋 Our team will be in touch shortly about the {{machine}}. Anything else I can help you with?",
    "greeting_reply": "Hello! 👋 How can I help you today?",
    "bye_reply": "Thank you. Have a great day! 🙏",
    # Need Support: sent at most once per buyer; later questions get a topic reply or generic_reply.
    "support_reply": "Fine. Our team will keep in touch with you shortly.",
    "price_reply": ("Thank you for your interest 🙏 I've shared your price request with our sales team. "
                    "They'll come back to you with the best possible offer for the {{machine}} shortly."),
    "photos_wait_reply": ("Sorry for the wait! We've asked for the photos of the {{machine}} and will send them "
                          "to you as soon as we receive them."),
    "visit_reply": "Sure. Our team will share the location and help you arrange an inspection of the {{machine}} shortly.",
    "delivery_reply": ("Noted. Our team will confirm the delivery and transport details for the {{machine}} "
                       "and get back to you shortly."),
    "payment_reply": "Sure. Our team will share the payment terms for the {{machine}} with you shortly.",
    "details_reply": "Good question. Let me check the exact details of the {{machine}} with our team — we'll reply shortly.",
    "generic_reply": "Thank you for your message. I've passed it on to our team — they'll get back to you shortly.",
    "noted_reply": "Noted 👍 I've added this to your request — our team will cover it when they get back to you.",
}
# Names shown on the Message Templates page.
TEMPLATE_NAMES = {
    "quotation_prompt": "Quotation prompt (Interested / Send photos / Not interested)",
    "interested_reply": "Reply — buyer tapped Interested",
    "photos_reply": "Reply — Send photos, none yet (supplier is asked)",
    "photos_sent_reply": "Reply — sent with the photos",
    "not_interested_reply": "Reply — buyer tapped Not interested",
    "thanks_reply": "Reply — Thanks / Thank you / Ok / Okay / Fine",
    "greeting_pending_reply": "Reply — Hello (hasn't answered the quotation)",
    "greeting_interested_reply": "Reply — Hello (interested buyer)",
    "greeting_reply": "Reply — Hello",
    "bye_reply": "Reply — Bye",
    "support_reply": "Reply — Need Support (first time only)",
    "price_reply": "Reply — price / discount question",
    "photos_wait_reply": "Reply — asks for photos again",
    "visit_reply": "Reply — location / inspection question",
    "delivery_reply": "Reply — delivery / transport question",
    "payment_reply": "Reply — payment terms question",
    "details_reply": "Reply — machine details question",
    "generic_reply": "Reply — any other question",
    "noted_reply": "Reply — more messages on an open case",
}
# Tapping the same button again resends its reply, at most once in this many minutes.
REPEAT_REPLY_MINUTES = 5

# Question topic -> template kind of its reply.
TOPIC_KINDS = {"price": "price_reply", "photos": "photos_wait_reply", "visit": "visit_reply",
               "delivery": "delivery_reply", "payment": "payment_reply", "details": "details_reply"}

# Typed answers (after lower-casing and stripping punctuation). "not interested" is
# checked first because it contains "interested". "ok" is small talk, not a yes.
TYPED = [
    ("not_interested", {"3", "not interested", "no", "no thanks", "no thank you", "not needed", "not required"}),
    ("interested", {"1", "interested", "yes", "yes interested", "i am interested", "im interested"}),
    ("photos", {"2", "send photos", "send photo", "photos", "photo", "images", "send images", "pics", "send pics",
                "pictures", "send pictures"}),
]
PHOTO_WORDS = re.compile(r"(?i)\b(photos?|images?|pics?|pictures?)\b")

# What a buyer's free text is about. A topic (or a "?") means a person should follow up
# (Need Support); otherwise short small talk gets a friendly reply and nothing else.
TOPICS = [
    ("price", "Price", re.compile(r"(?i)\b(price|rate|cost|discount|negotiat\w*|budget|reduce|lowest|best\s+price|"
                                  r"last\s+price|final\s+price|less|lakhs?|lacs?|\d+(\.\d+)?\s*(l|k|lakh|lac)\b)")),
    ("photos", "Photos", PHOTO_WORDS),
    ("visit", "Inspection", re.compile(r"(?i)\b(where|location|located|place|address|inspect\w*|visit|see\s+the\s+machine)\b")),
    ("delivery", "Delivery", re.compile(r"(?i)\b(deliver\w*|ship\w*|transport\w*|freight|dispatch\w*|loading)\b")),
    ("payment", "Payment", re.compile(r"(?i)\b(payment|pay|advance|gst|invoice|bill|emi|credit|terms)\b")),
    ("details", "Details", re.compile(r"(?i)\b(condition|working|running|video|year|specs?|specification|details?|"
                                      r"width|warranty|service|spares?|model)\b")),
]
SMALL_TALK = [   # first match wins; "ok thanks" is thanks
    ("thanks", re.compile(r"(?i)\b(thanks?|thank\s*(you|u)|thx|tq|ty|tnx|appreciat\w*)\b|🙏")),
    ("bye", re.compile(r"(?i)\b(bye|good\s*night|see\s*you|talk\s*later|ttyl)\b")),
    ("greeting", re.compile(r"(?i)^\s*(hi+|hello+|hey+|hai|good\s*(morning|afternoon|evening)|vanakkam|namaste|namaskar)\b")),
    ("ack", re.compile(r"(?i)^\s*(ok+|okay|k|fine|sure|noted|got\s*it|alright|all\s*right|done|great|nice|good)\b|^\s*(👍|👌)")),
]


def prompt_text() -> str:
    tpl = get_template("quotation_prompt", "whatsapp")
    return (tpl or {}).get("body") or DEFAULTS["quotation_prompt"]


def buttons_for(ref: str) -> list:
    """Reply buttons for a quotation: id 'q:<ref>:<action>'."""
    return [(f"q:{ref}:{action}", title) for action, title in BUTTONS]


def _typed_action(text: str):
    t = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*(sir|madam)$", "", t)
    for action, words in TYPED:
        if t in words:
            return action
    return None


def _topic(text: str):
    for key, _label, rx in TOPICS:
        if rx.search(text or ""):
            return key
    return None


def _small_talk(text: str):
    t = (text or "").strip()
    if not t or "?" in t or len(t.split()) > 8:
        return None
    for key, rx in SMALL_TALK:
        if rx.search(t):
            return key
    return None


def _sent_within(buyer_id, minutes, body=None) -> bool:
    """Did we message this buyer in the last `minutes` (optionally: this exact text)?"""
    sql = f"""SELECT id FROM chat_messages WHERE party_type='buyer' AND party_id=:b AND direction='out'
              AND created_at > NOW() - INTERVAL {int(minutes)} MINUTE {'AND body=:body' if body else ''} LIMIT 1"""
    return bool(one(prop_engine, sql, {"b": buyer_id, "body": body}))


def _ever_sent(buyer_id, body) -> bool:
    return bool(one(prop_engine, """SELECT id FROM chat_messages WHERE party_type='buyer' AND party_id=:b
                                    AND direction='out' AND body=:body LIMIT 1""", {"b": buyer_id, "body": body}))


def _send(phone, buyer_id, body, tpl=None, mapping=None, buttons=None):
    res = dispatch("whatsapp", phone, "", body, tpl, mapping, buttons)
    if res.get("ok"):
        execute(prop_engine,
                "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('buyer',:b,'whatsapp','out',:body)",
                {"b": buyer_id, "body": body})
    else:
        print(f"[WHATSAPP · buyer-reply-failed] -> {phone}: {res.get('error')}")
    return res


def _text(kind, mapping):
    """(template row, rendered text) for a message kind — the Message Templates entry,
    else the default wording."""
    tpl = get_template(kind, "whatsapp")
    return tpl, render((tpl or {}).get("body") or DEFAULTS[kind], mapping)


def _reply(kind, phone, buyer_id, mapping):
    tpl, body = _text(kind, mapping)
    return _send(phone, buyer_id, body, tpl, mapping)


def _set_status(qid, status):
    # interested_at keeps an interested buyer in Potential while they go on to ask for photos.
    execute(prop_engine, """UPDATE quotations SET buyer_status=:s, buyer_status_at=NOW(),
                            interested_at=CASE WHEN :s='interested' THEN COALESCE(interested_at, NOW())
                                               WHEN :s='not_interested' THEN NULL ELSE interested_at END
                            WHERE id=:id""", {"s": status, "id": qid})


def _small_talk_reply(kind, qt, status, phone, buyer_id, mapping):
    """Friendly answer to thanks / ok / hello / bye. Undecided buyers who say hello get
    the three options again. The same line isn't repeated within 10 minutes."""
    buttons = None
    interested = status == "interested" or bool(qt.get("interested_at"))
    if kind in ("thanks", "ack"):
        tkind = "thanks_reply"
    elif kind == "bye":
        tkind = "bye_reply"
    elif status == "sent":   # greeting from a buyer who hasn't answered the quotation yet
        tkind, buttons = "greeting_pending_reply", buttons_for(qt["ref"])
    elif interested:
        tkind = "greeting_interested_reply"
    else:
        tkind = "greeting_reply"
    _tpl, body = _text(tkind, mapping)
    if _sent_within(buyer_id, 10, body):
        return None
    return _send(phone, buyer_id, body, None, mapping, buttons)


def handle_buyer_message(buyer_id: int, phone: str, text: str, button_id: str = None) -> dict:
    """Act on one inbound buyer message (already logged to chat history by the caller)."""
    qt = None
    action = None
    if button_id and button_id.startswith("q:"):
        parts = button_id.split(":")
        if len(parts) == 3:
            qt = one(prop_engine, "SELECT * FROM quotations WHERE ref=:r AND buyer_id=:b", {"r": parts[1], "b": buyer_id})
            action = parts[2]
        if not qt:
            # A tap on a quotation we can't find (deleted / another buyer): never apply it
            # to a different quotation — that would e.g. send another machine's photos.
            print(f"[WHATSAPP · stale-button] {button_id} from buyer {buyer_id}")
            return {"action": None, "stale_button": True}
    if not qt:   # typed reply: the buyer's latest quotation
        qt = one(prop_engine, "SELECT * FROM quotations WHERE buyer_id=:b ORDER BY id DESC LIMIT 1", {"b": buyer_id})
    if not qt:
        return {"action": None}
    action = action or _typed_action(text)
    buyer = one(prop_engine, "SELECT name FROM buyers WHERE id=:id", {"id": buyer_id}) or {}
    mapping = {"buyer": buyer.get("name") or "", "machine": qt.get("machine") or "", "ref": qt.get("ref") or ""}
    status = qt.get("buyer_status") or "sent"
    topic = None if action else _topic(text)

    # "Can you send photos?" is the Send photos option — unless we're already waiting on them.
    if not action and topic == "photos" and status != "photos_requested":
        action = "photos"
    # Asking for photos again while we're still waiting on them -> a person follows up
    # (the case closes itself once the photos are delivered).
    if (action == "photos" or topic == "photos") and status == "photos_requested":
        action, topic, text = None, "photos", f"Asked for photos again: {text or 'Send photos'}"

    if action == "photos":
        item = one(prop_engine, "SELECT * FROM proposal_items WHERE id=:id", {"id": qt.get("proposal_item_id")})
        unsent = photos.photo_list(item)[int(qt.get("photos_sent_n") or 0):]
        if unsent:                 # we have photos this buyer hasn't seen -> send now
            send_photos_to_buyer(qt, phone, buyer_id, unsent, mapping)
        else:                      # none (or all already sent) -> ask the supplier for more
            _set_status(qt["id"], "photos_requested")
            _reply("photos_reply", phone, buyer_id, mapping)
            if item:
                photos.request_supplier_photos(item["id"])
        return {"action": action, "quotation_id": qt["id"]}

    if action in ("interested", "not_interested"):
        changed = action != status
        if changed:
            _set_status(qt["id"], action)
        # A repeated tap gets the reply again — but not the same reply twice within a few minutes.
        tpl, body = _text(f"{action}_reply", mapping)
        if changed or not _sent_within(buyer_id, REPEAT_REPLY_MINUTES, body):
            _send(phone, buyer_id, body, tpl, mapping)
        return {"action": action, "quotation_id": qt["id"]}

    # Small talk (thanks / hello / ok / bye): a friendly reply, no Need Support.
    talk = None if topic else _small_talk(text)
    if talk:
        _small_talk_reply(talk, qt, status, phone, buyer_id, mapping)
        return {"action": talk, "quotation_id": qt["id"]}

    # A question / bargaining / anything else -> Need Support, with a reply that fits.
    label = next((lbl for key, lbl, _rx in TOPICS if key == topic), "Question")
    reason = text if (text or "").startswith("Asked for photos") else f"{label}: {text}"
    was_open = bool(qt.get("support_open"))
    execute(prop_engine, """
        UPDATE quotations SET support_open=1, support_reason=:r, support_at=NOW(), support_resolved_at=NULL
        WHERE id=:id""", {"r": (reason or "")[:500], "id": qt["id"]})
    if was_open and _sent_within(buyer_id, 2):
        return {"action": "support", "quotation_id": qt["id"]}      # don't answer every line of a burst
    _tpl, first_time = _text("support_reply", mapping)
    if topic in TOPIC_KINDS:
        _tpl, body = _text(TOPIC_KINDS[topic], mapping)
    elif not _ever_sent(buyer_id, first_time):
        body = first_time                                            # only ever once per buyer
    else:
        _tpl, body = _text("generic_reply", mapping)
    if _sent_within(buyer_id, 30, body):
        _tpl, body = _text("noted_reply", mapping)
        if _sent_within(buyer_id, 30, body):
            return {"action": "support", "quotation_id": qt["id"]}
    _send(phone, buyer_id, body, None, mapping)
    return {"action": "support", "quotation_id": qt["id"], "topic": topic}


def send_photos_to_buyer(qt, phone, buyer_id, urls, mapping) -> int:
    """Send photos, then ask again (Interested / Not interested). Returns photos sent."""
    n = photos.send_images(phone, urls)
    if not n:
        return 0
    execute(prop_engine, """UPDATE quotations SET buyer_status='photos_sent', buyer_status_at=NOW(),
                            photos_sent_n=photos_sent_n+:n WHERE id=:id""", {"n": n, "id": qt["id"]})
    tpl, body = _text("photos_sent_reply", mapping)
    buttons = [b for b in buttons_for(qt["ref"]) if not b[0].endswith(":photos")]
    res = dispatch("whatsapp", phone, "", body, tpl, mapping, buttons)
    log = f"[{n} photo(s) of the {mapping.get('machine')} sent]"
    execute(prop_engine,
            "INSERT INTO chat_messages (party_type,party_id,channel,direction,body) VALUES ('buyer',:b,'whatsapp','out',:body)",
            {"b": buyer_id, "body": f"{log}\n{body}" if res.get("ok") else log})
    return n


def _forward_delay() -> int:
    try:
        return max(10, int(os.environ.get("WA_PHOTO_FORWARD_DELAY_SECONDS", "60")))
    except ValueError:
        return 60


def process_photo_forwards() -> int:
    """Scheduler job: buyers waiting in Photos Requested get the row's new photos once
    the supplier has gone quiet for a minute (WhatsApp delivers each image separately).
    A Need Support case that was only about chasing these photos is closed."""
    due = q(prop_engine, f"""
        SELECT qt.*, b.phone buyer_phone, b.name buyer_name, pi.photos item_photos
        FROM quotations qt JOIN buyers b ON b.id=qt.buyer_id JOIN proposal_items pi ON pi.id=qt.proposal_item_id
        WHERE qt.buyer_status='photos_requested'
          AND pi.photos_received_at IS NOT NULL AND pi.photos_received_at <= NOW() - INTERVAL {_forward_delay()} SECOND
    """)
    forwarded = 0
    for qt in due:
        unsent = photos.photo_list({"photos": qt["item_photos"]})[int(qt.get("photos_sent_n") or 0):]
        if not unsent or not qt.get("buyer_phone"):
            continue
        # Claim it so a second server process can't send the same photos.
        if execute(prop_engine, "UPDATE quotations SET buyer_status='photos_sending' WHERE id=:id AND buyer_status='photos_requested'",
                   {"id": qt["id"]})["rowcount"] != 1:
            continue
        mapping = {"buyer": qt.get("buyer_name") or "", "machine": qt.get("machine") or "", "ref": qt.get("ref") or ""}
        if send_photos_to_buyer(qt, qt["buyer_phone"], qt["buyer_id"], unsent, mapping):
            forwarded += 1
            if (qt.get("support_reason") or "").startswith("Asked for photos again"):
                execute(prop_engine, "UPDATE quotations SET support_open=0, support_resolved_at=NOW() WHERE id=:id", {"id": qt["id"]})
        else:
            execute(prop_engine, "UPDATE quotations SET buyer_status='photos_requested' WHERE id=:id", {"id": qt["id"]})
    return forwarded
