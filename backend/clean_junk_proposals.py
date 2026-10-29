"""Remove supplier proposals that were imported from non-quote emails
(newsletters / notifications that merely matched a keyword).

Junk is decided by the SAME rule the live intake now uses: an email is a real
supplier quote only if intake.parse_items() finds a `Machine name:` / `Price:`
marker. Anything else — plus any supplier left with no remaining emails/items —
is deleted. Genuine quotes and their suppliers are kept. Safe to re-run.

Run:  .venv\\Scripts\\python.exe clean_junk_proposals.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.db import prop_engine, q, execute
from app import intake


def _ids(rows, key="id"):
    return [int(r[key]) for r in rows]


def _in(ids):
    """Inline a safe IN(...) list of validated ints (empty -> NULL set)."""
    return "(" + ",".join(str(int(i)) for i in ids) + ")" if ids else "(NULL)"


emails = q(prop_engine, "SELECT id, supplier_id, subject, body FROM proposal_emails ORDER BY id")
junk_email_ids = [int(e["id"]) for e in emails
                  if not intake.parse_items(e["subject"] or "", e["body"] or "")]
keep_email_ids = [int(e["id"]) for e in emails if int(e["id"]) not in junk_email_ids]

print(f"proposal_emails: {len(emails)}  →  keep {len(keep_email_ids)}, delete {len(junk_email_ids)}")

if junk_email_ids:
    # Items belonging to the junk emails.
    junk_items = _ids(q(prop_engine,
        f"SELECT id FROM proposal_items WHERE proposal_email_id IN {_in(junk_email_ids)}"))
    print(f"  junk proposal_items: {len(junk_items)}")

    # Remove child rows first (FK-safe), then the items and the emails.
    if junk_items:
        execute(prop_engine, f"DELETE FROM quotations WHERE proposal_item_id IN {_in(junk_items)}")
        execute(prop_engine, f"DELETE FROM photo_requests WHERE proposal_item_id IN {_in(junk_items)}")
        execute(prop_engine, f"DELETE FROM proposal_items WHERE id IN {_in(junk_items)}")
    execute(prop_engine, f"DELETE FROM proposal_emails WHERE id IN {_in(junk_email_ids)}")
    print("  deleted junk emails + items (+ their quotations/photo_requests)")

# Drop suppliers that are now fully orphaned (no emails, items, quotations,
# photo_requests, or chat history left). Keeps real/registered suppliers.
orphans = q(prop_engine, """
    SELECT s.id, s.name, s.email FROM suppliers s
    WHERE NOT EXISTS (SELECT 1 FROM proposal_emails pe WHERE pe.supplier_id=s.id)
      AND NOT EXISTS (SELECT 1 FROM proposal_items pi WHERE pi.supplier_id=s.id)
      AND NOT EXISTS (SELECT 1 FROM quotations qt    WHERE qt.proposal_item_id IN
                      (SELECT id FROM proposal_items WHERE supplier_id=s.id))
      AND NOT EXISTS (SELECT 1 FROM photo_requests pr WHERE pr.supplier_id=s.id)
      AND NOT EXISTS (SELECT 1 FROM chat_messages cm WHERE cm.party_type='supplier' AND cm.party_id=s.id)
    ORDER BY s.id
""")
if orphans:
    print(f"  orphan suppliers to delete: {len(orphans)}")
    for s in orphans:
        print(f"     - #{s['id']} {s['name']!r} <{s['email']}>")
    execute(prop_engine, f"DELETE FROM suppliers WHERE id IN {_in(_ids(orphans))}")

# Final state.
print("\nRemaining:")
print("  proposal_emails:", q(prop_engine, "SELECT COUNT(*) c FROM proposal_emails")[0]["c"])
print("  proposal_items :", q(prop_engine, "SELECT COUNT(*) c FROM proposal_items")[0]["c"])
print("  suppliers      :", q(prop_engine, "SELECT COUNT(*) c FROM suppliers")[0]["c"])
for r in q(prop_engine, """
        SELECT pi.id, s.name supplier, pi.machine, pi.price
        FROM proposal_items pi LEFT JOIN suppliers s ON s.id=pi.supplier_id ORDER BY pi.id"""):
    print(f"     item#{r['id']}  {r['supplier']!r}  machine={r['machine']!r}  price={r['price']}")
print("\nDone.")
