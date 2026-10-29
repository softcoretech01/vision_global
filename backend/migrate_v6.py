"""Buyer Enquiry legacy fields: buyer City, and enquiry Make / Model / Priority
(Status already exists on enquiries). Backfills Model from the existing free-text
machine and derives a Priority from the buyer segment. Safe to re-run."""
from app.db import prop_engine, execute

ALTERS = [
    ("buyers", "city", "ALTER TABLE `buyers` ADD COLUMN `city` VARCHAR(120) NULL"),
    ("enquiries", "make", "ALTER TABLE `enquiries` ADD COLUMN `make` VARCHAR(160) NULL"),
    ("enquiries", "model", "ALTER TABLE `enquiries` ADD COLUMN `model` VARCHAR(160) NULL"),
    ("enquiries", "priority", "ALTER TABLE `enquiries` ADD COLUMN `priority` VARCHAR(40) NULL"),
]
for tbl, col, sql in ALTERS:
    try:
        execute(prop_engine, sql)
        print(f"  + {tbl}.{col}")
    except Exception as e:
        print(f"  ({tbl}.{col} already present: {str(e)[:50]})")

# Backfill: use the existing free-text machine as the Model where none is set.
execute(prop_engine, "UPDATE `enquiries` SET model=machine WHERE (model IS NULL OR model='') AND machine IS NOT NULL AND machine<>''")
print("  backfilled enquiries.model from machine")

# Derive a Priority from the buyer segment for existing enquiries.
execute(prop_engine, """
    UPDATE `enquiries` e JOIN `buyers` b ON b.id=e.buyer_id
    SET e.priority = CASE b.segment WHEN 'very_hot' THEN 'Very high' WHEN 'hot' THEN 'High' ELSE 'Medium' END
    WHERE e.priority IS NULL OR e.priority=''
""")
print("  backfilled enquiries.priority from buyer segment")
print("migrate_v6 done")
