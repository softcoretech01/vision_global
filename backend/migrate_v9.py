"""WhatsApp template messages: templates.wa_template / wa_lang (the approved Meta
template to use outside the 24-hour window), plus wa_contacts to track each number's
last inbound message (which opens that window). Safe to re-run."""
from app.db import admin_engine, prop_engine, execute

COLS = [
    ("wa_template", "VARCHAR(120) NULL"),
    ("wa_lang", "VARCHAR(20) NULL"),
]
for col, typ in COLS:
    try:
        execute(admin_engine, f"ALTER TABLE `templates` ADD COLUMN `{col}` {typ}")
        print(f"  + templates.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:50]})")

execute(prop_engine, """
    CREATE TABLE IF NOT EXISTS `wa_contacts` (
        `phone10` VARCHAR(10) NOT NULL PRIMARY KEY,
        `phone` VARCHAR(32) NULL,
        `last_inbound_at` DATETIME NOT NULL
    )
""")
print("  + wa_contacts")

print("migrate_v9 done")
