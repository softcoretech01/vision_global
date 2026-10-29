"""Add proposal_emails.received_at (the supplier email's own Date header) so the
Supplier Proposal table can show the received date, not our import time.
Backfills existing rows from created_at. Safe to re-run."""
from app.db import prop_engine, execute

try:
    execute(prop_engine, "ALTER TABLE `proposal_emails` ADD COLUMN `received_at` DATETIME NULL")
    print("  + proposal_emails.received_at")
except Exception as e:
    print(f"  (received_at already present: {str(e)[:60]})")

# Backfill: for emails imported before this column was captured, use the linked
# item's import time (proposal_emails has no created_at of its own).
execute(prop_engine, """
    UPDATE `proposal_emails` pe
    JOIN (SELECT proposal_email_id, MIN(created_at) ca FROM `proposal_items` GROUP BY proposal_email_id) pi
      ON pi.proposal_email_id = pe.id
    SET pe.received_at = pi.ca
    WHERE pe.received_at IS NULL
""")
print("  backfilled received_at from item import time where empty")
print("migrate_v4 done")
