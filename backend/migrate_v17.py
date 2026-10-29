"""quotations.quote_no: a short sequential quotation number for the offer message
("Quotation No 10001"), instead of the long internal ref. Existing rows are numbered
in order. Safe to re-run."""
from app.db import prop_engine, execute

try:
    execute(prop_engine, "ALTER TABLE `quotations` ADD COLUMN `quote_no` INT NULL")
    print("  + quotations.quote_no")
except Exception as e:
    print(f"  (quote_no already present: {str(e)[:50]})")
execute(prop_engine, "UPDATE quotations SET quote_no = 10000 + id WHERE quote_no IS NULL")
print("migrate_v17 done")
