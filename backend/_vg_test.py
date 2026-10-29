import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from app import intake
from app.db import prop_engine, q
before = q(prop_engine,"SELECT COUNT(*) c FROM proposal_items")[0]['c']
res = intake.run_fetch()
after = q(prop_engine,"SELECT COUNT(*) c FROM proposal_items")[0]['c']
print("run_fetch:", res)
print(f"proposal_items: {before} -> {after}  (matched {res.get('matched')} emails, imported {res.get('fetched')})")
