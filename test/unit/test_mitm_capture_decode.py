"""mitm_capture_decode 단위 테스트."""

from __future__ import annotations

import gzip
import json

from utils.mitm_capture_decode import (
    events_from_h_ut_raw_body,
    should_capture_request,
)


def test_should_capture_aplus_substring() -> None:
    assert should_capture_request(
        "aplus.gmarket.co.kr",
        "/Product.Exposure.Event",
        "https://aplus.gmarket.co.kr/Product.Exposure.Event",
    )


def test_should_capture_h_ut_upload_only() -> None:
    assert should_capture_request(
        "h-ut.gmarket.co.kr",
        "/upload",
        "https://h-ut.gmarket.co.kr/upload",
    )
    assert not should_capture_request(
        "h-ut.gmarket.co.kr",
        "/other",
        "https://h-ut.gmarket.co.kr/other",
    )


def test_h_ut_prefix_plus_gzip_json_array() -> None:
    inner = [{"k": 1}, {"k": 2}]
    gz = gzip.compress(json.dumps(inner).encode("utf-8"))
    raw = b"\x01\x00\x04\x00prefix!" + gz
    events = events_from_h_ut_raw_body(raw)
    assert events == inner


def test_h_ut_gzip_single_object() -> None:
    inner = {"spm": "x", "n": 1}
    gz = gzip.compress(json.dumps(inner).encode("utf-8"))
    raw = b"\x01\x00" + gz
    events = events_from_h_ut_raw_body(raw)
    assert events == [inner]


def test_h_ut_pipe_anchor_split() -> None:
    r1 = b"||google||a||/Product.Exposure.Event||tail1"
    r2 = b"||google||b||/Product.Click.Event||tail2"
    raw = b"\x00hdr" + r1 + r2
    gz = gzip.compress(raw)
    events = events_from_h_ut_raw_body(b"\x01\x00" + gz)
    assert len(events) == 3
    assert events[0]["_capture_subtype"] == "h_ut_session_prefix"
    assert events[1]["event_path"] == "/Product.Exposure.Event"
    assert events[2]["event_path"] == "/Product.Click.Event"
