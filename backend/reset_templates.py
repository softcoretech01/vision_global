"""Reset message templates to exactly 4: Buyer Quotation (Email/WhatsApp) + Follow-up (Email/WhatsApp)."""
from app.db import admin_engine, execute

execute(admin_engine, "DELETE FROM templates")

Q_EMAIL = (
    "Dear {{buyer}},\n\n"
    "Thank you for your enquiry. Please find our quotation below:\n\n"
    "Machine    : {{machine}}\n"
    "Quantity   : {{qty}}\n"
    "Unit price : {{price}}\n"
    "Total       : {{total}}\n\n"
    "This quotation is valid for 15 days. Reply to this email to confirm your order.\n\n"
    "Regards,\nVision Global"
)
Q_WA = (
    "Hello {{buyer}} 👋\n"
    "Quotation from Vision Global:\n"
    "• Machine: {{machine}}\n"
    "• Quantity: {{qty}}\n"
    "• Unit price: {{price}}\n"
    "• Total: {{total}}\n\n"
    "Reply YES to confirm your order."
)
F_EMAIL = (
    "Dear {{buyer}},\n\n"
    "Just following up on our quotation for {{machine}} (quantity {{qty}}, {{price}} per unit).\n"
    "Would you like to proceed? We're glad to help with any questions.\n\n"
    "Regards,\nVision Global"
)
F_WA = (
    "Hi {{buyer}}, following up on the {{machine}} quotation (qty {{qty}}, {{price}}/unit). Shall we proceed?"
)

rows = [
    ("buyer_quotation", "email",    "Buyer Quotation (Email)",    "Quotation for {{machine}} — Vision Global", Q_EMAIL),
    ("buyer_quotation", "whatsapp", "Buyer Quotation (WhatsApp)", "",                                          Q_WA),
    ("followup",        "email",    "Follow-up (Email)",          "Following up on your {{machine}} quotation", F_EMAIL),
    ("followup",        "whatsapp", "Follow-up (WhatsApp)",       "",                                          F_WA),
]
for kind, channel, name, subject, body in rows:
    execute(admin_engine,
            "INSERT INTO templates (kind,channel,name,subject,body,active) VALUES (:k,:c,:n,:s,:b,1)",
            {"k": kind, "c": channel, "n": name, "s": subject, "b": body})
print("Templates reset to 4 (buyer_quotation + followup, each email & whatsapp)")
