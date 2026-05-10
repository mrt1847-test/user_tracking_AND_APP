import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mitmproxy import http

from utils.mitm_capture_decode import iter_capture_event_dicts, should_capture_request

try:
    from mitmproxy import ctx
except ImportError:  # pragma: no cover
    ctx = None  # type: ignore[misc, assignment]


def _log_each_capture_enabled() -> bool:
    raw = os.environ.get("TRACKING_CAPTURE_LOG", "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


OUTPUT_PATH = Path(os.environ["TRACKING_PROXY_OUTPUT"]).expanduser()
LOCK = threading.Lock()


def _request_fingerprint(method: str, pretty_url: str, raw: bytes) -> str:
    h = hashlib.sha1()
    h.update((method or "").encode("utf-8", errors="ignore"))
    h.update(b"|")
    h.update((pretty_url or "").encode("utf-8", errors="ignore"))
    h.update(b"|")
    h.update(raw or b"")
    return h.hexdigest()


def request(flow: http.HTTPFlow) -> None:
    if flow.request.method.upper() not in ("POST", "GET"):
        return

    host = flow.request.host or ""
    path = flow.request.path or ""
    pretty_url = flow.request.pretty_url or ""
    if not should_capture_request(host, path, pretty_url):
        return

    raw = flow.request.content or b""
    method = flow.request.method
    ts = time.time()
    base_id = _request_fingerprint(method, pretty_url, raw)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with OUTPUT_PATH.open("a", encoding="utf-8") as fp:
            for payload in iter_capture_event_dicts(
                host=host,
                path=path,
                pretty_url=pretty_url,
                method=method,
                raw_body=raw,
                timestamp=ts,
                request_id=base_id,
            ):
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    if _log_each_capture_enabled() and ctx is not None:
        try:
            ctx.log.info(
                "TRACKING_CAPTURE -> %s: %s %s (raw_len=%d)",
                OUTPUT_PATH,
                method,
                host,
                len(raw),
            )
        except Exception:
            pass
