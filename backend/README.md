# Vision Global — FastAPI Backend

Python **FastAPI** + MySQL (CARENEST host), using the existing databases:
- **Etex_admin** — `users`, `channels`, `templates`
- **Etex_Proposal** — `buyers`, `suppliers`, `enquiries`, `proposal_emails`, `proposal_items`, `quotations`, `followups`, `chat_messages`, `photo_requests`

The schema + seed were already created; this service connects to them directly.

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

Config is in `backend/.env` (gitignored). Interactive docs at http://localhost:8000/docs.
Demo login: **admin / admin**.

## Point the frontend at it
Create `D:\Vision Global\frontend\.env.local`:
```
VITE_API_URL=http://localhost:8000/api
```
Restart `npm run dev`. The React app switches from the built-in mock to this live API — no UI changes.

## Endpoints (prefix /api)
| Method | Path | Purpose |
| --- | --- | --- |
| POST | /auth/login | email (or `admin`) + password → JWT |
| GET | /enquiries | paginated/filtered buyer enquiries |
| GET | /proposals | per-machine supplier proposal rows |
| PATCH | /proposals/{id} | edit machine / margin_pct / buyer_segment |
| POST | /proposals/bulk-segment | set buyer segment across the column |
| POST | /proposals/{id}/request-photo | ask supplier for photos |
| POST | /proposals/{id}/send | send quotation to matching buyers |
| GET | /quotations | buyer quotations |
| GET | /quotations/{id} | view one |
| PUT | /quotations/{id}/followup | daily / weekly / dnd |
| GET | /quotations/{id}/chat | chat history |
| GET/POST/PUT/DELETE | /config/channels | receiving email/phone config |
| GET/PUT | /config/templates | message templates |
| GET/POST/PUT | /config/users | admin users |
| GET | /dashboard | counts + recent |

All routes except `/auth/login` and `/health` require `Authorization: Bearer <token>`.

## Integrations — real Email & WhatsApp
`app/integrations/notify.py` sends for real when creds are present, else **simulates (logs)**.
Standard library only (smtplib / urllib) — no extra installs.

**Email (SMTP)** — set in `.env`:
```
SMTP_HOST=smtp.yourhost.com
SMTP_PORT=587
SMTP_USER=you@yourhost.com
SMTP_PASS=••••
SMTP_FROM=sales@yourhost.com
```

**WhatsApp** — pick a provider:
- `WA_PROVIDER=meta` → Meta WhatsApp **Cloud API**: `WA_TOKEN`, `WA_PHONE_ID` (+ optional `WA_API_VERSION`)
- `WA_PROVIDER=twilio` → Twilio: `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM` (e.g. `whatsapp:+14155238886`)

Restart uvicorn after editing `.env`. Note: outside the WhatsApp 24-hour session window,
Meta requires pre-approved message *templates* for the first outbound message — free-form
text (as sent here) works within the window; swap to a template call for cold outreach.
