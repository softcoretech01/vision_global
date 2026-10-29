"""proposal_items.pending_media: WhatsApp photos that couldn't be downloaded yet (e.g. the
token had expired). JSON list of {"id": <media id>, "at": <iso time>}; the scheduler
retries them and moves them into `photos`. Safe to re-run."""
from app.db import prop_engine, execute

try:
    execute(prop_engine, "ALTER TABLE `proposal_items` ADD COLUMN `pending_media` TEXT NULL")
    print("  + proposal_items.pending_media")
except Exception as e:
    print(f"  (pending_media already present: {str(e)[:50]})")
print("migrate_v14 done")
