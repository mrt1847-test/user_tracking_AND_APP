import json
from pathlib import Path

import pytest

from utils.NetworkTracker import TrackingLogStore
from utils.h_ut_log_ingest import build_synthetic_aplus_ingest
from utils.validation_helpers import build_expected_from_module_config, get_event_logs


def _store_with_logs(logs):
    return TrackingLogStore(source_path="does-not-exist.jsonl", logs=logs)


def test_h_ut_proxy_capture_record_105_keeps_canonical_utlogmap_shape() -> None:
    capture_path = Path("json/proxy_capture.jsonl")
    store = TrackingLogStore(source_path=str(capture_path))
    store.sync_from_source()

    target = None
    for log in store.get_logs("Product Click"):
        meta = log.get("h_ut_capture") or {}
        if meta.get("pipe_record_index") == 105:
            target = log
            break

    assert target is not None
    payload = target["payload"]
    kv = payload["h_ut"]["kv"]
    assert "decoded_gokey" not in payload
    assert "expdata" not in payload
    assert kv["utpvid"] == "6"
    assert payload["h_ut"]["utLogMap"]["parsed"]["x_object_id"] == "4687001616"
    assert payload["h_ut"]["utLogMap"]["parsed"]["query"] == "물티슈"


def test_h_ut_proxy_capture_record_90_product_exposure_without_goodscode_is_not_product_target() -> None:
    capture_path = Path("json/proxy_capture.jsonl")
    raw = next(
        json.loads(line)
        for line in capture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(json.loads(line)["post_data"]).get("record_index") == 90
    )
    ev = json.loads(raw["post_data"])
    built = build_synthetic_aplus_ingest(ev)
    assert built is not None

    url, method, payload = built
    spm = "gmktapp.home.today_campaign.dtab0_item1"
    kv = payload["h_ut"]["kv"]

    assert "decoded_gokey" not in payload
    assert "expdata" not in payload
    assert kv["spm"] == spm
    assert kv["_p_prod"] == ""
    assert payload["h_ut"]["utLogMap"] == {"raw": "", "parsed": None}

    store = TrackingLogStore(source_path="does-not-exist.jsonl", logs=[])
    store.record_request(
        url,
        method,
        json.dumps(payload, ensure_ascii=False),
        timestamp=raw["timestamp"],
    )

    assert len(store.get_product_exposure_logs_by_spm(spm)) == 1
    assert store._extract_goodscode_from_log(store.logs[0]) is None
    assert store.get_product_exposure_logs_by_goodscode("4687001616", spm) == []
    assert store.get_product_exposure_logs_by_goodscode("4687001616") == []


def test_h_ut_proxy_capture_record_0_product_exposure_uses_native_shape() -> None:
    capture_path = Path("json/proxy_capture.jsonl")
    parent = "46a3591658dc9415e98abffe2c07adaf6608d4b4"
    raw = next(
        json.loads(line)
        for line in capture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(line).get("parent_request_id") == parent
        and json.loads(json.loads(line)["post_data"]).get("record_index") == 0
    )
    ev = json.loads(raw["post_data"])
    built = build_synthetic_aplus_ingest(ev)
    assert built is not None

    url, method, payload = built
    assert "decoded_gokey" not in payload
    assert "expdata" not in payload
    assert "params" not in payload

    kv = payload["h_ut"]["kv"]
    utlogmap = payload["h_ut"]["utLogMap"]["parsed"]
    assert kv["_p_prod"] == "1825258886"
    assert kv["spm"] == "gmktapp.pdp.pdpjfy.ditem9"
    assert utlogmap["x_object_id"] == "1825258886"
    assert utlogmap["seed_item_id"] == "4687001616"

    store = TrackingLogStore(source_path="does-not-exist.jsonl", logs=[])
    store.record_request(
        url,
        method,
        json.dumps(payload, ensure_ascii=False),
        timestamp=raw["timestamp"],
    )

    assert len(store.get_product_exposure_logs_by_goodscode("1825258886", kv["spm"])) == 1
    assert store.get_product_exposure_logs_by_goodscode("4687001616", kv["spm"]) == []


def test_product_click_filter_is_goodscode_only_even_when_schema_spm_differs() -> None:
    store = _store_with_logs(
        [
            {
                "type": "Product Click",
                "url": "https://aplus.gmarket.co.kr/product.click.event",
                "method": "POST",
                "payload": {
                    "_p_prod": "4687001616",
                    "decoded_gokey": {
                        "params": {
                            "spm": "gmktapp.searchlist.cpc.d0_6",
                            "utLogMap": {"parsed": {"x_object_id": "4687001616"}},
                        }
                    },
                },
            }
        ]
    )
    module_config = {"product_click": {"spm": "gmktapp.pdp.pdpjfy.ditem28"}}

    logs = get_event_logs(store, "Product Click", "4687001616", module_config)

    assert len(logs) == 1


def test_path_aware_validation_keeps_flat_and_utlogmap_ab_buckets_separate() -> None:
    store = _store_with_logs([])
    log = {
        "type": "Product Click",
        "url": "https://aplus.gmarket.co.kr/product.click.event",
        "method": "POST",
        "payload": {
            "_p_prod": "1",
            "decoded_gokey": {
                "params": {
                    "ab_buckets": "flat-bucket",
                    "utLogMap": {"parsed": {"ab_buckets": "nested-bucket"}},
                }
            },
        },
    }
    module_config = {
        "product_click": {
            "ab_buckets": "flat-bucket",
            "utLogMap": {"ab_buckets": "nested-bucket"},
        }
    }
    expected = build_expected_from_module_config(module_config, "Product Click", "1")

    _, passed = store.validate_payload(log, expected, "1", "Product Click")

    assert passed["ab_buckets"]["actual"] == "flat-bucket"
    assert passed["utLogMap.ab_buckets"]["actual"] == "nested-bucket"


def test_product_exposure_validation_uses_matched_goodscode_slot_first() -> None:
    store = _store_with_logs([])
    log = {
        "type": "Product Exposure",
        "url": "https://aplus.gmarket.co.kr/product.exposure.event",
        "method": "POST",
        "payload": {
            "decoded_gokey": {
                "params": {
                    "expdata": {
                        "parsed": [
                            {
                                "spm": "gmktapp.pdp.pdpjfy.ditem0",
                                "exargs": {
                                    "params-exp": {
                                        "parsed": {
                                            "_p_prod": "111",
                                            "utLogMap": {"query": "wrong-slot"},
                                        }
                                    }
                                },
                            },
                            {
                                "spm": "gmktapp.pdp.pdpjfy.ditem1",
                                "exargs": {
                                    "params-exp": {
                                        "parsed": {
                                            "_p_prod": "222",
                                            "utLogMap": {"query": "right-slot"},
                                        }
                                    }
                                },
                            },
                        ]
                    }
                }
            },
        },
    }
    module_config = {
        "product_exposure": {
            "_p_prod": "222",
            "utLogMap": {"query": "right-slot"},
        }
    }
    expected = build_expected_from_module_config(module_config, "Product Exposure", "222")

    _, passed = store.validate_payload(log, expected, "222", "Product Exposure")

    assert passed["utLogMap.query"]["actual"] == "right-slot"

    bad_expected = build_expected_from_module_config(
        {"product_exposure": {"utLogMap": {"query": "wrong-slot"}}},
        "Product Exposure",
        "222",
    )
    with pytest.raises(AssertionError):
        store.validate_payload(log, bad_expected, "222", "Product Exposure")
