"""Remove all mock/sample business data. Keeps admin users + message templates.
Run once:  .venv\\Scripts\\python.exe clean_data.py
"""
from app.db import prop_engine, admin_engine, execute

prop_tables = [
    "quotations", "followups", "chat_messages", "photo_requests",
    "proposal_items", "proposal_emails", "enquiries", "buyers", "suppliers",
]

for t in prop_tables:
    execute(prop_engine, f"TRUNCATE TABLE `{t}`")
    print(f"  cleared Etex_Proposal.{t}")

# Clear the seeded sample receiving channels (user configures their own).
execute(admin_engine, "TRUNCATE TABLE `channels`")
print("  cleared Etex_admin.channels")

print("Done — mock data removed. Kept: users, templates.")
