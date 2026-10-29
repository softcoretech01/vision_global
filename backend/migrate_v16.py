"""Seed Admin -> Message Templates with every message the app sends automatically
(WhatsApp chatbot replies to buyers, supplier photo / details requests), using the
current wording, so they can be edited on that page. Kinds that already have a
template are left alone. Safe to re-run."""
from app.db import admin_engine, one, execute
from app.buyer_flow import DEFAULTS, TEMPLATE_NAMES
from app.intake import SUPPLIER_DEFAULTS
from app.photos import PHOTO_REQUEST_DEFAULT, PHOTO_REQUEST_SUBJECT

# templates.kind was an ENUM of the first four kinds; it must accept the new ones.
execute(admin_engine, "ALTER TABLE `templates` MODIFY `kind` VARCHAR(40) NOT NULL")
print("  templates.kind -> VARCHAR(40)")

ROWS = [(kind, "whatsapp", TEMPLATE_NAMES[kind], "", body) for kind, body in DEFAULTS.items()]
ROWS += [
    ("photo_request", "any", "Photo request to supplier", PHOTO_REQUEST_SUBJECT, PHOTO_REQUEST_DEFAULT),
    ("details_request", "whatsapp", "Missing details request to supplier", "", SUPPLIER_DEFAULTS["details_request"]),
    ("details_followup", "whatsapp", "Missing details — second request to supplier", "", SUPPLIER_DEFAULTS["details_followup"]),
]

added = 0
for kind, channel, name, subject, body in ROWS:
    if one(admin_engine, "SELECT id FROM templates WHERE kind=:k", {"k": kind}):
        print(f"  ({kind} already has a template)")
        continue
    execute(admin_engine,
            "INSERT INTO templates (kind,channel,name,subject,body,active) VALUES (:k,:c,:n,:s,:b,1)",
            {"k": kind, "c": channel, "n": name, "s": subject, "b": body})
    added += 1
    print(f"  + {kind}: {name}")
print(f"migrate_v16 done ({added} added)")
