"""Background jobs:
  - auto-fetch: periodically pull supplier emails into proposals.
    Controlled by env:  FETCH_AUTO (true/false), FETCH_INTERVAL_SECONDS (default 180).
  - details follow-up: every 20s, ask WhatsApp suppliers for missing quote details/photos,
    forward newly arrived supplier photos to buyers waiting for them, and send due
    daily/weekly buyer follow-ups."""
import os
import threading

from .intake import run_fetch, process_details_requests, process_followups, retry_pending_media
from .buyer_flow import process_photo_forwards

_stop = threading.Event()
_thread = None
_details_thread = None
DETAILS_TICK = 20


def enabled() -> bool:
    return os.environ.get("FETCH_AUTO", "true").lower() in ("1", "true", "yes", "on")


def interval() -> int:
    # Floor of 15s guards against hammering the mailbox; FETCH_INTERVAL_SECONDS sets the rest.
    try:
        return max(15, int(os.environ.get("FETCH_INTERVAL_SECONDS", "180")))
    except ValueError:
        return 180


def _loop():
    _stop.wait(15)  # let the server settle first
    iv = interval()
    while not _stop.is_set():
        try:
            res = run_fetch()
            if res.get("fetched"):
                print(f"[auto-fetch] imported {res['fetched']} new email(s) from {res['matched']} matched")
        except Exception as e:
            print(f"[auto-fetch] error: {e}")
        _stop.wait(iv)


def _details_loop():
    _stop.wait(10)
    while not _stop.is_set():
        try:
            n = process_details_requests()
            if n:
                print(f"[details-followup] asked {n} supplier(s) for missing details")
        except Exception as e:
            print(f"[details-followup] error: {e}")
        try:
            n = retry_pending_media()    # photos that failed to download (e.g. expired token)
            if n:
                print(f"[media-retry] recovered {n} WhatsApp photo(s)")
        except Exception as e:
            print(f"[media-retry] error: {e}")
        try:
            n = process_photo_forwards()
            if n:
                print(f"[photo-forward] sent photos to {n} waiting buyer(s)")
        except Exception as e:
            print(f"[photo-forward] error: {e}")
        try:
            n = process_followups()      # here, not in auto-fetch, so it runs without email
            if n:
                print(f"[followups] sent {n} follow-up(s)")
        except Exception as e:
            print(f"[followups] error: {e}")
        _stop.wait(DETAILS_TICK)


def start():
    global _thread, _details_thread
    _details_thread = threading.Thread(target=_details_loop, name="details-followup", daemon=True)
    _details_thread.start()
    if not enabled():
        print("[auto-fetch] disabled (FETCH_AUTO=false)")
        return
    _thread = threading.Thread(target=_loop, name="auto-fetch", daemon=True)
    _thread.start()
    print(f"[auto-fetch] started — every {interval()}s")


def stop():
    _stop.set()
