"""Add proposal_items.photo_request_msgid (to match supplier photo replies). Safe to re-run."""
from app.db import prop_engine, execute

try:
    execute(prop_engine, "ALTER TABLE `proposal_items` ADD COLUMN `photo_request_msgid` VARCHAR(255) NULL")
    print("  + proposal_items.photo_request_msgid")
except Exception as e:
    print(f"  (photo_request_msgid already present: {str(e)[:60]})")
print("migrate_v3 done")
