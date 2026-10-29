"""Diagnostic: show the SMTP conversation and the precise failure (no email sent)."""
import os
import ssl
import smtplib
import traceback
from dotenv import load_dotenv

load_dotenv()
host = os.environ.get("SMTP_HOST")
user = os.environ.get("SMTP_USER")
pwd = os.environ.get("SMTP_PASS", "")

for port in (587, 465):
    print(f"\n===== Trying {host}:{port} =====")
    try:
        if port == 465:
            ctx = ssl.create_default_context()
            s = smtplib.SMTP_SSL(host, port, timeout=25, context=ctx)
        else:
            s = smtplib.SMTP(host, port, timeout=25, local_hostname="localhost")
            s.set_debuglevel(1)
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
        s.set_debuglevel(1)
        s.login(user, pwd)
        print(f"RESULT {port}: OK — auth succeeded")
        s.quit()
        break
    except Exception as e:
        print(f"RESULT {port}: {type(e).__name__}: {e}")
        traceback.print_exc()
