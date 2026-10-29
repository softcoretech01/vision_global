"""Supplier Proposal legacy fields on proposal_items: Pro No, Model, Width, Priority,
Remarks, state (active/sold/hold), plus the details-form fields (Through, Payment Term,
Confidential, Purchased By, Mode, Machine Color, Year, Quantity, Rate Type, Rate,
Price Term, Currency, Machine Name). Backfills from existing data. Safe to re-run."""
from app.db import prop_engine, execute

COLS = [
    ("pro_no", "VARCHAR(32) NULL"),
    ("model", "VARCHAR(160) NULL"),
    ("width", "VARCHAR(80) NULL"),
    ("priority", "VARCHAR(40) NULL"),
    ("remarks", "TEXT NULL"),
    ("state", "VARCHAR(16) NOT NULL DEFAULT 'active'"),
    ("through", "VARCHAR(40) NULL"),
    ("payment_term", "VARCHAR(120) NULL"),
    ("confidential", "TINYINT NOT NULL DEFAULT 0"),
    ("purchased_by", "VARCHAR(120) NULL"),
    ("mode", "VARCHAR(80) NULL"),
    ("machine_color", "VARCHAR(80) NULL"),
    ("year", "VARCHAR(16) NULL"),
    ("quantity", "VARCHAR(40) NULL"),
    ("rate_type", "VARCHAR(40) NULL"),
    ("rate", "VARCHAR(40) NULL"),
    ("price_term", "VARCHAR(80) NULL"),
    ("currency", "VARCHAR(40) NULL"),
    ("machine_name", "VARCHAR(160) NULL"),
]
for col, typ in COLS:
    try:
        execute(prop_engine, f"ALTER TABLE `proposal_items` ADD COLUMN `{col}` {typ}")
        print(f"  + proposal_items.{col}")
    except Exception as e:
        print(f"  ({col} already present: {str(e)[:45]})")

# Backfill from existing data.
execute(prop_engine, "UPDATE `proposal_items` SET pro_no=CONCAT('', 52000+id) WHERE pro_no IS NULL OR pro_no=''")
execute(prop_engine, "UPDATE `proposal_items` SET model=machine WHERE (model IS NULL OR model='') AND machine IS NOT NULL")
execute(prop_engine, "UPDATE `proposal_items` SET machine_name=machine WHERE (machine_name IS NULL OR machine_name='') AND machine IS NOT NULL")
execute(prop_engine, "UPDATE `proposal_items` SET state='active' WHERE state IS NULL OR state=''")
execute(prop_engine, "UPDATE `proposal_items` SET through='e_mail' WHERE through IS NULL OR through=''")
# Remarks from the source email subject where empty.
execute(prop_engine, """
    UPDATE `proposal_items` pi JOIN `proposal_emails` pe ON pe.id=pi.proposal_email_id
    SET pi.remarks = pe.subject
    WHERE (pi.remarks IS NULL OR pi.remarks='') AND pe.subject IS NOT NULL AND pe.subject<>''
""")
print("  backfilled pro_no, model, machine_name, state, through, remarks")
print("migrate_v7 done")
