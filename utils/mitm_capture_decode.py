"""mitm Aplus / h-ut 업로드 바디 디코딩 (gzip + 이벤트 단위 분리)."""

from __future__ import annotations

import base64
import gzip
import json
from typing import Any, Iterable, List
from urllib.parse import parse_qs, urlparse

GZIP_MAGIC = b"\x1f\x8b\x08"
# 네이티브 UT 배치 본문에서 레코드 경계로 쓰이는 고정 토큰(디바이스 블록 앵커)
_H_UT_RECORD_ANCHOR = b"||google||"


def should_capture_request(host: str, path: str, pretty_url: str) -> bool:
    """https://h-ut.gmarket.co.kr/upload 및 aplus.gmarket.co.kr 포함 URL만."""
    url_l = (pretty_url or "").lower()
    h = (host or "").lower()
    p = path or ""
    if "aplus.gmarket.co.kr" in url_l:
        return True
    if h == "h-ut.gmarket.co.kr" and p == "/upload":
        return True
    return False


def _try_gzip_decompress(raw: bytes) -> bytes | None:
    if not raw:
        return None
    idx = raw.find(GZIP_MAGIC)
    if idx < 0:
        return None
    blob = raw[idx:]
    try:
        return gzip.decompress(blob)
    except OSError:
        return None


def _split_json_events(text: str) -> List[Any] | None:
    s = text.strip()
    if not s:
        return []

    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        data = None

    if data is not None:
        if isinstance(data, list):
            return list(data)
        if isinstance(data, dict):
            for key in ("events", "logs", "items", "records", "batch", "data"):
                inner = data.get(key)
                if isinstance(inner, list) and inner:
                    return list(inner)
            return [data]
        return [data]

    out: List[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if out:
        return out
    return None


def _h_ut_chunk_to_event(chunk: bytes, record_index: int) -> dict[str, Any]:
    text = chunk.decode("utf-8", errors="replace")
    fields = [f for f in text.split("||") if f != ""]
    event_path = next(
        (
            f
            for f in fields
            if "/Product." in f or "/Module." in f or "/General." in f or "/Page." in f.lower()
        ),
        None,
    )
    return {
        "_capture_subtype": "h_ut_pipe_record",
        "record_index": record_index,
        "event_path": event_path,
        "pipe_field_count": len(fields),
        "pipe_fields": fields,
    }


def _split_h_ut_pipe_records(data: bytes) -> List[Any] | None:
    """gzip 해제 후 JSON이 아닌 전형적 UT 배치( ||google|| 앵커 반복 ) 분리."""
    positions: list[int] = []
    start = 0
    while True:
        p = data.find(_H_UT_RECORD_ANCHOR, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1

    if len(positions) < 2:
        return None

    out: list[Any] = []
    if positions[0] > 0:
        head = data[: positions[0]].decode("utf-8", errors="replace").lstrip("\x00")
        out.append({"_capture_subtype": "h_ut_session_prefix", "text": head})

    for i in range(len(positions) - 1):
        out.append(_h_ut_chunk_to_event(data[positions[i] : positions[i + 1]], i))

    out.append(_h_ut_chunk_to_event(data[positions[-1] :], len(positions) - 1))
    return out


def events_from_h_ut_decompressed(data: bytes) -> List[Any]:
    """h-ut gzip 해제 직후 바이트 → 이벤트 dict 리스트."""
    if not data:
        return []

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")

    parsed = _split_json_events(text)
    if parsed is not None:
        return parsed

    pipe = _split_h_ut_pipe_records(data)
    if pipe is not None:
        return pipe

    return [
        {
            "_decode": "non_json_non_pipe_ut",
            "_raw_decompressed_utf8_replace": text[:200_000],
        }
    ]


def events_from_decompressed_bytes(data: bytes) -> List[Any]:
    """압축 해제된 바이트에서 JSON / NDJSON / 단일 blob 이벤트 리스트로 정규화."""
    if not data:
        return []

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [
            {
                "_decode": "utf8_failed",
                "_raw_decompressed_base64": base64.b64encode(data).decode("ascii"),
            }
        ]

    parsed = _split_json_events(text)
    if parsed is not None:
        return parsed

    return [
        {
            "_decode": "non_json",
            "_raw_decompressed_utf8": text[:200_000],
        }
    ]


def events_from_h_ut_raw_body(raw: bytes) -> List[Any]:
    """h-ut /upload: 커스텀 헤더 뒤 gzip 페이로드 추출 후 이벤트 리스트."""
    if not raw:
        return []
    dec = _try_gzip_decompress(raw)
    if dec is None:
        return [
            {
                "_decode": "gzip_not_found_or_invalid",
                "_prefix_hex": raw[:32].hex(),
                "_raw_body_base64": base64.b64encode(raw[:50_000]).decode("ascii"),
            }
        ]
    return events_from_h_ut_decompressed(dec)


def events_from_aplus_raw_body(raw: bytes, url: str, method: str) -> List[Any]:
    """aplus: raw_content 기준. gzip이면 해제, 아니면 UTF-8 JSON/폼/쿼리."""
    m = (method or "").upper()
    if raw:
        dec = _try_gzip_decompress(raw)
        if dec is not None:
            return events_from_decompressed_bytes(dec)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return [
                {
                    "_decode": "utf8_failed",
                    "_raw_body_base64": base64.b64encode(raw).decode("ascii"),
                }
            ]
        parsed = _split_json_events(text)
        if parsed is not None:
            return parsed
        if "=" in text or "&" in text:
            return [{"_form_raw": text}]
        return [{"_raw_text": text}]

    if m == "GET":
        q = urlparse(url).query
        if not q:
            return []
        flat = {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(q, keep_blank_values=True).items()}
        return [flat]

    return []


def iter_capture_event_dicts(
    *,
    host: str,
    path: str,
    pretty_url: str,
    method: str,
    raw_body: bytes,
    timestamp: float,
    request_id: str,
) -> Iterable[dict[str, Any]]:
    """한 HTTP 요청에서 JSONL로 쓸 레코드들(이벤트당 1줄)."""
    is_h_ut = (host or "").lower() == "h-ut.gmarket.co.kr" and (path or "") == "/upload"

    if is_h_ut:
        kind = "h_ut_upload"
        events = events_from_h_ut_raw_body(raw_body)
    else:
        kind = "aplus"
        events = events_from_aplus_raw_body(raw_body, pretty_url, method)

    if not events:
        events = [{"_note": "empty_payload"}]

    for i, ev in enumerate(events):
        post_data: str
        if isinstance(ev, (dict, list)):
            post_data = json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
        else:
            post_data = json.dumps({"_value": ev}, ensure_ascii=False, separators=(",", ":"))

        yield {
            "source": "mitmproxy",
            "timestamp": timestamp,
            "url": pretty_url,
            "host": host,
            "path": path,
            "method": method,
            "post_data": post_data,
            "request_id": f"{request_id}:{i}",
            "parent_request_id": request_id,
            "capture_kind": kind,
            "event_index": i,
            "event_count": len(events),
        }
