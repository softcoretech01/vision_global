"""Password hashing (bcrypt — compatible with the existing seeded hashes) + JWT auth."""
import os
import time
import bcrypt
import jwt
from fastapi import Header, HTTPException


def _secret() -> str:
    return os.environ.get("JWT_SECRET", "dev-secret")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user: dict) -> str:
    payload = {
        "id": user["id"], "role": user["role"], "name": user["name"],
        "exp": int(time.time()) + 7 * 24 * 3600,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def require_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        return jwt.decode(authorization[7:], _secret(), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
