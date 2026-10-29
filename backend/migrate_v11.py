"""Buyer response tracking on quotations (WhatsApp Interested / Send photos / Not
interested buttons) for the Buyer Quotation tabs.
  buyer_status      sent | interested | photos_requested | photos_sent | not_interested
  buyer_status_at   when buyer_status last changed
  support_open      1 while the buyer needs a person (bargaining, questions, chasing photos)
  support_reason    the buyer's message that opened it
  support_at / support_resolved_at
Safe to re-run."""
from app.db import prop_engine, execute

COLS = [
    ("buyer_status", "VARCHAR(20) NOT NULL DEFAULT 'sent'"),
    ("buyer_status_at", "DATETIME NULL"),
    ("support_open", "TINYINT NOT NULL DEFAULT 0"),
    ("support_reason", "VARCHAR(500) NULL"),
    ("support_at", "DATETIME NULL"),
    ("support_resolved_at", "DATETIME NULL"),
]
for col, typ in COLS:
    try:
        execute(prop_engine, f"ALTER TABLE `quotations` ADD COLUMN `{col}` {typ}")
        print(f"  + quotations.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:50]})")

print("migrate_v11 done")
