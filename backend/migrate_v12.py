"""Photo forwarding on WhatsApp:
  proposal_items.photos_received_at  when supplier/team photos last arrived on the row
                                     (buyers waiting for photos get them shortly after)
  quotations.photos_sent_n           how many of the row's photos this buyer already has
Safe to re-run."""
from app.db import prop_engine, execute

COLS = [
    ("proposal_items", "photos_received_at", "DATETIME NULL"),
    ("quotations", "photos_sent_n", "INT NOT NULL DEFAULT 0"),
]
for tbl, col, typ in COLS:
    try:
        execute(prop_engine, f"ALTER TABLE `{tbl}` ADD COLUMN `{col}` {typ}")
        print(f"  + {tbl}.{col}")
    except Exception as e:
        print(f"  ({tbl}.{col} already present: {str(e)[:50]})")

print("migrate_v12 done")
