"""Adds accessories (TEXT) and waiting_list (LONGTEXT) to proposal_items. Safe to re-run."""
from app.db import prop_engine, execute

COLS = [
    ("accessories", "TEXT NULL"),
    ("waiting_list", "LONGTEXT NULL"),
]
for col, typ in COLS:
    try:
        execute(prop_engine, f"ALTER TABLE `proposal_items` ADD COLUMN `{col}` {typ}")
        print(f"  + proposal_items.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:50]})")

print("migrate_v8 done")
