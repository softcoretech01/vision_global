"""quotations.interested_at: when the buyer said Interested. Kept while they go on to ask
for photos, so they stay in the Potential tab (buyer_status alone would be overwritten
by photos_requested / photos_sent). Backfilled from current Interested rows. Safe to re-run."""
from app.db import prop_engine, execute

try:
    execute(prop_engine, "ALTER TABLE `quotations` ADD COLUMN `interested_at` DATETIME NULL")
    print("  + quotations.interested_at")
except Exception as e:
    print(f"  (interested_at already present: {str(e)[:50]})")
execute(prop_engine, """UPDATE quotations SET interested_at=COALESCE(buyer_status_at, NOW())
                        WHERE buyer_status='interested' AND interested_at IS NULL""")
print("migrate_v15 done")
