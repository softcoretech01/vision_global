import os
import ssl
import smtplib
from fastapi import APIRouter, Depends, Request
from ..db import admin_engine, q, execute
from ..security import require_auth, hash_pw
from ..integrations import gmail, imap_fetch

router = APIRouter()


# ---------- Keywords (supplier-email intake) ----------
@router.get("/keywords")
def list_keywords(user=Depends(require_auth)):
    return {"rows": q(admin_engine, "SELECT * FROM keywords ORDER BY word")}


@router.post("/keywords")
async def add_keyword(req: Request, user=Depends(require_auth)):
    b = await req.json()
    word = (b.get("word") or "").strip()
    if word:
        try:
            execute(admin_engine, "INSERT INTO keywords (word) VALUES (:w)", {"w": word})
        except Exception:
            pass  # duplicate — ignore
    return {"ok": True}


@router.delete("/keywords/{kid}")
def delete_keyword(kid: int, user=Depends(require_auth)):
    execute(admin_engine, "DELETE FROM keywords WHERE id=:id", {"id": kid})
    return {"ok": True}


# ---------- Machine masters (Make / Model / Machine) ----------
# Reference lists used to recognize machines in supplier email/WhatsApp intake and
# to populate dropdowns. Makes carry a category; models and machines are name-only.
@router.get("/machine-makes")
def list_makes(user=Depends(require_auth)):
    return {"rows": q(admin_engine, "SELECT * FROM machine_makes ORDER BY name")}


@router.post("/machine-makes")
async def add_make(req: Request, user=Depends(require_auth)):
    b = await req.json()
    name = (b.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "Name required"}
    try:
        res = execute(admin_engine, "INSERT INTO machine_makes (name,category,active) VALUES (:n,:c,1)",
                      {"n": name, "c": (b.get("category") or "").strip() or None})
        return {"id": res["lastrowid"]}
    except Exception:
        return {"ok": False, "error": "That make already exists"}


@router.put("/machine-makes/{mid}")
async def update_make(mid: int, req: Request, user=Depends(require_auth)):
    b = await req.json()
    execute(admin_engine, "UPDATE machine_makes SET name=:n, category=:c, active=:a WHERE id=:id",
            {"n": (b.get("name") or "").strip(), "c": (b.get("category") or "").strip() or None,
             "a": 1 if b.get("active", True) else 0, "id": mid})
    return {"ok": True}


def _name_master(table):
    """CRUD endpoints for a simple name+active master (models, machines)."""
    def _list(user=Depends(require_auth)):
        return {"rows": q(admin_engine, f"SELECT * FROM {table} ORDER BY name")}

    async def _add(req: Request, user=Depends(require_auth)):
        b = await req.json()
        name = (b.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Name required"}
        try:
            res = execute(admin_engine, f"INSERT INTO {table} (name,active) VALUES (:n,1)", {"n": name})
            return {"id": res["lastrowid"]}
        except Exception:
            return {"ok": False, "error": "That name already exists"}

    async def _update(mid: int, req: Request, user=Depends(require_auth)):
        b = await req.json()
        execute(admin_engine, f"UPDATE {table} SET name=:n, active=:a WHERE id=:id",
                {"n": (b.get("name") or "").strip(), "a": 1 if b.get("active", True) else 0, "id": mid})
        return {"ok": True}
    return _list, _add, _update


_models_list, _models_add, _models_update = _name_master("models")
router.get("/models")(_models_list)
router.post("/models")(_models_add)
router.put("/models/{mid}")(_models_update)

_machines_list, _machines_add, _machines_update = _name_master("machines")
router.get("/machines")(_machines_list)
router.post("/machines")(_machines_add)
router.put("/machines/{mid}")(_machines_update)


# ---------- Channels ----------
@router.get("/channels")
def list_channels(purpose: str = "", user=Depends(require_auth)):
    if purpose:
        rows = q(admin_engine, "SELECT * FROM channels WHERE purpose=:p ORDER BY id", {"p": purpose})
    else:
        rows = q(admin_engine, "SELECT * FROM channels ORDER BY purpose, id")
    return {"rows": rows}


@router.post("/channels")
async def create_channel(req: Request, user=Depends(require_auth)):
    b = await req.json()
    res = execute(admin_engine,
                  "INSERT INTO channels (purpose,type,label,address) VALUES (:purpose,:type,:label,:address)",
                  {"purpose": b.get("purpose"), "type": b.get("type"), "label": b.get("label"), "address": b.get("address")})
    return {"id": res["lastrowid"]}


@router.put("/channels/{cid}")
async def update_channel(cid: int, req: Request, user=Depends(require_auth)):
    b = await req.json()
    execute(admin_engine, "UPDATE channels SET label=:label, address=:address, active=:active WHERE id=:id",
            {"label": b.get("label"), "address": b.get("address"), "active": 1 if b.get("active") else 0, "id": cid})
    return {"ok": True}


@router.delete("/channels/{cid}")
def delete_channel(cid: int, user=Depends(require_auth)):
    execute(admin_engine, "DELETE FROM channels WHERE id=:id", {"id": cid})
    return {"ok": True}


# ---------- Templates ----------
@router.get("/templates")
def list_templates(user=Depends(require_auth)):
    return {"rows": q(admin_engine, "SELECT * FROM templates ORDER BY kind")}


@router.post("/templates")
async def create_template(req: Request, user=Depends(require_auth)):
    b = await req.json()
    res = execute(admin_engine,
                  "INSERT INTO templates (kind,channel,name,subject,body,active) VALUES (:kind,:channel,:name,:subject,:body,:active)",
                  {"kind": b.get("kind"), "channel": b.get("channel") or "any", "name": b.get("name"),
                   "subject": b.get("subject"), "body": b.get("body"), "active": 1 if b.get("active", True) else 0})
    return {"id": res["lastrowid"]}


@router.put("/templates/{tid}")
async def update_template(tid: int, req: Request, user=Depends(require_auth)):
    b = await req.json()
    execute(admin_engine, "UPDATE templates SET name=:name, subject=:subject, body=:body, active=:active WHERE id=:id",
            {"name": b.get("name"), "subject": b.get("subject"), "body": b.get("body"),
             "active": 1 if b.get("active") else 0, "id": tid})
    return {"ok": True}


# ---------- Integrations status & tests ----------
@router.get("/integrations")
def integrations(user=Depends(require_auth)):
    smtp_on = bool(os.environ.get("SMTP_HOST"))
    imap_on = bool(os.environ.get("IMAP_USER") and os.environ.get("IMAP_PASS"))
    return {
        "email": {
            "configured": smtp_on or imap_on,
            "account": os.environ.get("SMTP_USER") or os.environ.get("IMAP_USER", ""),
            "smtp_host": os.environ.get("SMTP_HOST", ""),
            "smtp_port": os.environ.get("SMTP_PORT", ""),
            "imap_host": os.environ.get("IMAP_HOST", ""),
            "send_ready": smtp_on,
            "fetch_ready": imap_on,
            "from": os.environ.get("SMTP_FROM", "") or os.environ.get("SMTP_USER", ""),
            "auto_fetch": os.environ.get("FETCH_AUTO", "true").lower() in ("1", "true", "yes", "on"),
            "fetch_interval": int(os.environ.get("FETCH_INTERVAL_SECONDS", "180")),
        },
        "whatsapp": {
            "provider": os.environ.get("WA_PROVIDER", "meta"),
            "number": os.environ.get("WA_NUMBER", ""),
            "configured": bool(os.environ.get("WA_TOKEN") and os.environ.get("WA_PHONE_ID")),
            "send_ready": bool(os.environ.get("WA_TOKEN") and os.environ.get("WA_PHONE_ID")),
            "phone_id_set": bool(os.environ.get("WA_PHONE_ID")),
            "token_set": bool(os.environ.get("WA_TOKEN")),
            "verify_token": os.environ.get("WA_VERIFY_TOKEN", ""),
            "webhook_url": f"{os.environ.get('PUBLIC_BASE', 'http://localhost:8000').rstrip('/')}/api/whatsapp/webhook",
            "api_version": os.environ.get("WA_API_VERSION", "v21.0"),
        },
    }


@router.post("/test-email")
def test_email(user=Depends(require_auth)):
    """Verify SMTP (send) and IMAP (fetch) logins — no email is sent."""
    host = os.environ.get("SMTP_HOST")
    smtp = {"ok": False, "detail": "No SMTP_HOST configured."}
    if host:
        port = int(os.environ.get("SMTP_PORT", 587))
        try:
            if port == 465:
                s = smtplib.SMTP_SSL(host, port, timeout=20, local_hostname="localhost", context=ssl.create_default_context())
            else:
                s = smtplib.SMTP(host, port, timeout=20, local_hostname="localhost")
                s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
            s.login(os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", ""))
            s.quit()
            smtp = {"ok": True, "detail": f"SMTP login OK ({host})."}
        except smtplib.SMTPAuthenticationError:
            smtp = {"ok": False, "detail": "SMTP auth rejected. For Gmail use a 16-char App Password (2-Step Verification must be on)."}
        except Exception as e:
            smtp = {"ok": False, "detail": f"SMTP: {type(e).__name__}: {e}"}
    imap = imap_fetch.test_login()
    ok = smtp["ok"] and imap["ok"]
    return {"ok": ok, "detail": f"Send — {smtp['detail']}  |  Fetch — {imap['detail']}", "smtp": smtp, "imap": imap}


# ---------- Users ----------
@router.get("/users")
def list_users(user=Depends(require_auth)):
    return {"rows": q(admin_engine, "SELECT id,name,email,phone,role,status,created_at FROM users ORDER BY id")}


@router.post("/users")
async def create_user(req: Request, user=Depends(require_auth)):
    b = await req.json()
    res = execute(admin_engine,
                  "INSERT INTO users (name,email,phone,password_hash,role) VALUES (:name,:email,:phone,:ph,:role)",
                  {"name": b.get("name"), "email": b.get("email"), "phone": b.get("phone"),
                   "ph": hash_pw(b.get("password") or "changeme"), "role": b.get("role") or "operator"})
    return {"id": res["lastrowid"]}


@router.put("/users/{uid}")
async def update_user(uid: int, req: Request, user=Depends(require_auth)):
    b = await req.json()
    if b.get("password"):
        execute(admin_engine,
                "UPDATE users SET name=:name, phone=:phone, role=:role, status=:status, password_hash=:ph WHERE id=:id",
                {"name": b.get("name"), "phone": b.get("phone"), "role": b.get("role"),
                 "status": b.get("status"), "ph": hash_pw(b["password"]), "id": uid})
    else:
        execute(admin_engine,
                "UPDATE users SET name=:name, phone=:phone, role=:role, status=:status WHERE id=:id",
                {"name": b.get("name"), "phone": b.get("phone"), "role": b.get("role"),
                 "status": b.get("status"), "id": uid})
    return {"ok": True}
