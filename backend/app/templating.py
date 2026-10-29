"""Load message templates from Etex_admin and render {{placeholder}} values."""
from .db import admin_engine, one, q


def get_template(kind: str, channel: str = None):
    """Pick the active template for this kind, preferring an exact channel match,
    then an 'any' template, then whatever exists."""
    rows = q(admin_engine, "SELECT * FROM templates WHERE kind=:k AND active=1 ORDER BY id", {"k": kind})
    if not rows:
        return None
    if channel:
        for r in rows:
            if (r.get("channel") or "").lower() == channel.lower():
                return r
        for r in rows:
            if (r.get("channel") or "").lower() == "any":
                return r
    return rows[0]


def render(text: str, mapping: dict) -> str:
    out = text or ""
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", "" if v is None else str(v))
    return out
