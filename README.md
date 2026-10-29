# Vision Global — AI Buyer Automation (Prototype)

An AI-assisted procurement automation prototype built with **React + Vite**. It takes a
buyer enquiry (WhatsApp / email), extracts the requirement with AI, matches suppliers,
auto-dispatches RFQs, collects quotations, lets a user apply margin, and — on approval —
auto-sends the final offer back to the buyer.

> Prototype data lives in the browser (`localStorage`). No backend or API keys needed to run.

---

## Run it

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default http://localhost:5173).

**Demo login:** `admin` / `admin`

---

## The automation flow

```
Buyer enquiry (WhatsApp/Email)
      │
      ▼
🤖 AI extracts  →  machine + category + quantity + specs  (confidence score)
      │
      ▼
AI matches suppliers by category  →  auto-dispatch RFQ on WhatsApp
      │
      ▼
Supplier quotations captured (Supplier Proposal)
      │
      ▼
💹 Buyer Proposal  →  user picks a quote + sets MARGIN  (manual step)
      │
      ▼
✅ Approval  →  approve  →  offer AUTO-SENT to the buyer
```

### Menus
1. **Dashboard** — KPIs + pipeline funnel + recent enquiries
2. **Buyer Enquiry** — capture enquiry, run AI extraction
3. **Supplier Enquiry** — AI supplier match + WhatsApp RFQ dispatch
4. **Supplier Proposal** — quotations received from suppliers (lowest highlighted)
5. **Buyer Proposal** — set margin, generate the buyer offer
6. **Approval** — review, approve → auto-send to buyer
- **Suppliers (DB)** — registered suppliers & categories

---

## Try the full loop (demo)
1. **Buyer Enquiry → ＋ New Enquiry** → pick a *Sample* message → **Capture**.
2. Click **🤖 Run AI** on the row (machine + category extracted).
3. **Supplier Enquiry** → **Dispatch RFQ** (preview the WhatsApp message) → send.
4. On each dispatched supplier row → **⇩ Simulate reply** (mimics a supplier WhatsApp quote).
5. **Buyer Proposal** → choose a quote, set **Margin %** → **Create proposal**.
6. **Approval** → **Review** → **Approve & Auto-send to Buyer**. Done ✅

Use **Reset demo data** (sidebar) to start fresh.

---

## Where the real integrations plug in

This prototype simulates the AI and WhatsApp so it runs offline. In production:

| Prototype piece | Production replacement |
| --- | --- |
| `src/lib/ai.js › extractEnquiry()` | **Claude API** call (`claude-opus-4-8`) returning structured JSON |
| "Simulate reply" / dispatch | **WhatsApp Business API** (or Twilio) send + inbound webhook |
| `localStorage` store | Real backend DB (Postgres / MongoDB) + REST/GraphQL API |
| Hard-coded `admin/admin` | Proper auth (JWT / OAuth) |

---

## Project structure

```
frontend/
  src/
    main.jsx              app entry + providers
    App.jsx               auth gate + routes
    index.css             ERP theme (royal blue + teal) — swap tokens at top
    store/useStore.jsx    localStorage "DB" + all workflow actions
    lib/ai.js             AI extraction + message drafting (prototype)
    data/seed.js          seed suppliers / sample enquiry
    components/           Login, Layout, shared UI
    pages/                Dashboard, BuyerEnquiry, SupplierEnquiry,
                          SupplierProposal, BuyerProposal, Approval, Suppliers
backend/
  app/                    FastAPI app, routers, models, integrations
  requirements.txt        Python dependencies
```

## Theming
The ERP palette is defined as CSS variables at the top of `frontend/src/index.css`
(`--brand-900/700/600`, `--teal-600`, …). Replace those hex values with your
school ERP's exact colors to reskin the whole app.
