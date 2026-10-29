"""Quotations go out on email AND WhatsApp: keep each channel's message id.
  quotations.email_msgid   Message-ID of the quotation email (NULL if not emailed)
  quotations.wa_msgid      WhatsApp message id (NULL if not sent on WhatsApp)
Backfills from sent_msgid using the old single channel. Safe to re-run."""
from app.db import prop_engine, execute

for col in ("email_msgid", "wa_msgid"):
    try:
        execute(prop_engine, f"ALTER TABLE `quotations` ADD COLUMN `{col}` VARCHAR(255) NULL")
        print(f"  + quotations.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:50]})")

execute(prop_engine, "UPDATE quotations SET wa_msgid=sent_msgid WHERE channel='whatsapp' AND wa_msgid IS NULL AND sent_msgid IS NOT NULL")
execute(prop_engine, "UPDATE quotations SET email_msgid=sent_msgid WHERE channel='email' AND email_msgid IS NULL AND sent_msgid IS NOT NULL")
print("migrate_v13 done")
