"""mitm에서 디코딩된 h_ut_pipe_record → TrackingLogStore가 이해하는 aplus 형식으로 변환."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

logger = logging.getLogger(__name__)


def _parse_kv_blob(blob: str) -> dict[str, str]:
    """'a=1,b=2' 형태(쉼표 구분 key=value)를 느슨하게 파싱."""
    out: dict[str, str] = {}
    if not blob:
        return out
    for part in re.split(r",(?=[^,=]+=)", blob):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        v = re.split(r"[\x00-\x1f]", v, maxsplit=1)[0]
        v = unquote(v)
        if k:
            out[k] = v
    return out


def _first_field_matching(fields: List[str], pred) -> Optional[str]:
    for f in fields:
        if pred(str(f)):
            return str(f)
    return None


def build_synthetic_aplus_ingest(
    ev: Dict[str, Any],
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """
    h_ut_pipe_record 한 건 → (url, method, payload_dict).

    반환 payload는 record_request → _parse_payload → _decode_payload를 거친다.
    """
    if ev.get("_capture_subtype") != "h_ut_pipe_record":
        return None
    event_path = ev.get("event_path")
    if not isinstance(event_path, str) or not event_path.startswith("/"):
        return None
    fields = ev.get("pipe_fields")
    if not isinstance(fields, list) or not fields:
        return None

    path_lower = event_path.lower()
    url = f"https://aplus.gmarket.co.kr{path_lower}"
    page = str(fields[26]).strip() if len(fields) > 26 and fields[26] not in (None, "") else None
    event_code = str(fields[27]).strip() if len(fields) > 27 and fields[27] not in (None, "") else None

    blob = "||".join(str(f) for f in fields)

    p_prod_m = re.search(r"(?:^|[|&,])_p_prod=(\d+)", blob)
    p_prod = p_prod_m.group(1) if p_prod_m else None

    spm_m = re.search(r"(?:^|[|&,])spm=([^|&,]+)", blob)
    spm = unquote(spm_m.group(1).strip()) if spm_m else None

    spm_cnt_m = re.search(r"(?:^|[|&,])spm-cnt=([^|&,]+)", blob)
    spm_cnt = unquote(spm_cnt_m.group(1).strip()) if spm_cnt_m else None

    ut_map: dict[str, Any] = {}
    ut_m = re.search(r"(?:^|[|&,])utLogMap=([^|&,]+)", blob)
    if ut_m:
        raw_um = ut_m.group(1)
        try:
            ut_map = json.loads(unquote(raw_um))
        except (json.JSONDecodeError, TypeError):
            ut_map = {"_raw": raw_um}

    kv_field = _first_field_matching(fields, lambda s: "=" in s and ("_p_prod=" in s or "spm=" in s or "utLogMap=" in s))
    flat_kv: dict[str, str] = _parse_kv_blob(kv_field) if kv_field else {}

    if not p_prod and flat_kv.get("_p_prod"):
        p_prod = str(flat_kv["_p_prod"]).strip()
    if not spm and flat_kv.get("spm"):
        spm = flat_kv["spm"]
    if not spm_cnt and flat_kv.get("spm-cnt"):
        spm_cnt = flat_kv["spm-cnt"]

    kv = {k: v for k, v in flat_kv.items() if k != "utLogMap"}
    if spm:
        kv["spm"] = spm
    if spm_cnt:
        kv["spm-cnt"] = spm_cnt

    payload: dict[str, Any] = {
        "_native_h_ut": True,
        "h_ut": {
            "event_path": event_path,
            "record_index": ev.get("record_index"),
            "pipe_field_count": ev.get("pipe_field_count"),
            "pipe_fields": fields,
            "kv_blob": kv_field or "",
            "kv": kv,
        },
    }
    if "utLogMap" in flat_kv:
        payload["h_ut"]["utLogMap"] = {
            "raw": flat_kv["utLogMap"],
            "parsed": ut_map or None,
        }
    if page and page != "-":
        payload["page"] = page
        payload["h_ut"]["page"] = page
    if event_code and event_code != "-":
        payload["event_code"] = event_code
        payload["h_ut"]["event_code"] = event_code

    return url, "POST", payload
