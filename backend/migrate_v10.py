"""Missing-details follow-up on proposal_items: after a WhatsApp quote the supplier is
asked for the fields/photos it left out, and replies fill the same row.
  details_status        NULL | pending_check | sending | requested | complete | incomplete
  details_requests      how many times we've asked (capped)
  details_due_at        when to (re)check the row — set a little after the last message
  details_requested_at  when we last asked
Safe to re-run."""
from app.db import prop_engine, execute

COLS = [
    ("details_status", "VARCHAR(16) NULL"),
    ("details_requests", "INT NOT NULL DEFAULT 0"),
    ("details_due_at", "DATETIME NULL"),
    ("details_requested_at", "DATETIME NULL"),
]
for col, typ in COLS:
    try:
        execute(prop_engine, f"ALTER TABLE `proposal_items` ADD COLUMN `{col}` {typ}")
        print(f"  + proposal_items.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:50]})")

print("migrate_v10 done")
