"""Background auto-fetch: periodically pull supplier emails into proposals.
Controlled by env:  FETCH_AUTO (true/false), FETCH_INTERVAL_SECONDS (default 180)."""
import os
import threading

from .intake import run_fetch

_stop = threading.Event()
_thread = None


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


def start():
    global _thread
    if not enabled():
        print("[auto-fetch] disabled (FETCH_AUTO=false)")
        return
    _thread = threading.Thread(target=_loop, name="auto-fetch", daemon=True)
    _thread.start()
    print(f"[auto-fetch] started — every {interval()}s")


def stop():
    _stop.set()
