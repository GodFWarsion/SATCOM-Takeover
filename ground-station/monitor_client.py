# monitor_client.py
import os
import requests
import time
import threading
import queue
import traceback

# The monitoring log ingestion endpoint
MONITOR_SERVER_URL = os.environ.get(
    "MONITOR_SERVER_URL",
    "http://monitoring:5002/api/logs"   # unified ingestion path
)

_MAX_QUEUE_SIZE = int(os.environ.get("MONITOR_QUEUE_SIZE", "500"))
_MAX_RETRIES = int(os.environ.get("MONITOR_MAX_RETRIES", "3"))

_send_queue = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
_worker_started = False
_WORKER_LOCK = threading.Lock()


# ----------------------------------------------------------------------
# JSON WRAPPER HELPER
# ----------------------------------------------------------------------
def make_payload(level, source, event, details):
    """
    Ensures we send the unified API shape:
    {
        "status": "ok",
        "data": {
            "level": ...,
            "source": ...,
            "event": ...,
            "details": {...}
        },
        "ts": <unix>
    }
    """
    return {
        "status": "ok",
        "data": {
            "level": level,
            "source": source,
            "event": event,
            "details": details or {}
        },
        "ts": int(time.time())
    }


# ----------------------------------------------------------------------
# WORKER
# ----------------------------------------------------------------------
def _worker():
    """Background worker that sends queued log entries with retry/backoff."""
    session = requests.Session()

    while True:
        item = _send_queue.get()
        if item is None:
            break  # graceful shutdown (rarely used in containers)

        payload, attempt = item

        try:
            resp = session.post(
                MONITOR_SERVER_URL,
                json=payload,
                timeout=(2, 4)  # connect=2s, read=4s
            )

            if 200 <= resp.status_code < 300:
                print(f"[monitor_client] posted ({payload['data']['event']})")
                _send_queue.task_done()
                continue

            # non-2xx → retry
            print(f"[monitor_client] HTTP {resp.status_code} retry for {payload['data']['event']}")
            raise Exception(f"HTTP {resp.status_code}")

        except Exception as e:
            attempt += 1

            if attempt <= _MAX_RETRIES:
                backoff = min(6.0, 1.5 ** attempt)
                print(f"[monitor_client] retry {attempt}/{_MAX_RETRIES} in {backoff:.1f}s: {e}")
                time.sleep(backoff)
                _enqueue(payload, attempt)
            else:
                print("[monitor_client] DROPPED after max retries:", payload)
            _send_queue.task_done()


# ----------------------------------------------------------------------
# QUEUE MANAGEMENT
# ----------------------------------------------------------------------
def _enqueue(payload, attempt=0):
    """Try to enqueue without blocking; if queue full, drop oldest."""
    try:
        _send_queue.put_nowait((payload, attempt))
    except queue.Full:
        # Drop oldest to preserve newest events
        try:
            old, old_attempt = _send_queue.get_nowait()
            _send_queue.task_done()
            print("[monitor_client] queue full → dropped oldest event")
        except Exception:
            pass

        try:
            _send_queue.put_nowait((payload, attempt))
        except Exception:
            print("[monitor_client] queue full → dropped payload")


# ----------------------------------------------------------------------
# WORKER STARTER
# ----------------------------------------------------------------------
def start_worker_once():
    global _worker_started
    with _WORKER_LOCK:
        if not _worker_started:
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            _worker_started = True
            print("[monitor_client] worker thread started")


# ----------------------------------------------------------------------
# PUBLIC API
# ----------------------------------------------------------------------
def post_alert(level, source, event, details=None):
    """
    Asynchronously push alert/log entry into monitoring service.
    Non-blocking, safe under load, resilient under failure.
    """
    start_worker_once()

    payload = make_payload(level, source, event, details)
    _enqueue(payload, attempt=0)
