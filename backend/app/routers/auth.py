from fastapi import APIRouter, HTTPException, Request, Depends
from ..db import admin_engine, one
from ..security import verify_pw, make_token, require_auth

router = APIRouter()


@router.post("/login")
async def login(req: Request):
    body = await req.json()
    email = (body.get("email") or "").strip()
    if email and "@" not in email:
        email = f"{email}@etex.local"
    u = one(admin_engine, 'SELECT * FROM users WHERE email=:e AND status="active" LIMIT 1', {"e": email})
    if not u or not verify_pw(body.get("password") or "", u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "token": make_token(u),
        "user": {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]},
    }


@router.get("/me")
def me(user=Depends(require_auth)):
    return {"user": user}
