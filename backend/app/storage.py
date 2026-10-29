"""Save email image attachments to disk and return public URLs."""
import os
import uuid

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def public_base() -> str:
    # Images are displayed in the app UI, so they must come from a URL the browser can
    # reach — the local backend, not the webhook tunnel (PUBLIC_BASE). UPLOAD_BASE can
    # override this if images ever need to be publicly reachable (e.g. sent to WhatsApp).
    return os.environ.get("UPLOAD_BASE", "http://localhost:8000").rstrip("/")


def save_image(filename: str, data: bytes, content_type: str = "") -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if not ext and content_type:
        ext = "." + content_type.split("/")[-1].split(";")[0]
    if not ext:
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(data)
    return f"{public_base()}/uploads/{name}"
