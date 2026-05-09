import json
import os
import hashlib
import threading
import time
from pathlib import Path

from mitmproxy import http

try:
    from mitmproxy import ctx
except ImportError:  # pragma: no cover
    ctx = None  # type: ignore[misc, assignment]


def _log_each_capture_enabled() -> bool:
    raw = os.environ.get("TRACKING_CAPTURE_LOG", "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


OUTPUT_PATH = Path(os.environ["TRACKING_PROXY_OUTPUT"]).expanduser()
CAPTURE_DOMAINS = {
    item.strip().lower()
    for item in os.environ.get("TRACKING_CAPTURE_DOMAINS", "").split(",")
    if item.strip()
}
LOCK = threading.Lock()


def _matches_capture_domain(hostname: str) -> bool:
    host = (hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in CAPTURE_DOMAINS)


def request(flow: http.HTTPFlow) -> None:
    if flow.request.method.upper() not in ("POST", "GET"):
        return
    if CAPTURE_DOMAINS and not _matches_capture_domain(flow.request.host):
        return

    body = flow.request.get_text(strict=False)
    fingerprint = hashlib.sha1(
        f"{flow.request.method}|{flow.request.pretty_url}|{body}".encode("utf-8", errors="ignore")
    ).hexdigest()
    payload = {
        "source": "mitmproxy",
        "timestamp": time.time(),
        "url": flow.request.pretty_url,
        "host": flow.request.host,
        "path": flow.request.path,
        "method": flow.request.method,
        "post_data": body,
        "request_id": fingerprint,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with OUTPUT_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    if _log_each_capture_enabled() and ctx is not None:
        try:
            ctx.log.info(f"TRACKING_CAPTURE -> {OUTPUT_PATH}: {payload.get('method')} {payload.get('host')}")
        except Exception:
            pass
