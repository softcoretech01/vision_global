"""Adds the keywords table (Etex_admin) and a source_msg_id column to
proposal_emails (Etex_Proposal). Safe to re-run."""
from app.db import admin_engine, prop_engine, execute

execute(admin_engine, """
CREATE TABLE IF NOT EXISTS `keywords` (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  word       VARCHAR(120) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_word (word)
) ENGINE=InnoDB
""")
print("  + Etex_admin.keywords")

# Add source_msg_id (ignore if it already exists).
try:
    execute(prop_engine, "ALTER TABLE `proposal_emails` ADD COLUMN `source_msg_id` VARCHAR(80) NULL")
    execute(prop_engine, "ALTER TABLE `proposal_emails` ADD UNIQUE KEY `uq_msg` (`source_msg_id`)")
    print("  + proposal_emails.source_msg_id")
except Exception as e:
    print(f"  (source_msg_id already present: {str(e)[:60]})")

print("migrate_v2 done")
