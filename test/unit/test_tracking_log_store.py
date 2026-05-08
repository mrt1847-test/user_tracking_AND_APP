import json
import time
from pathlib import Path

from utils.NetworkTracker import TrackingLogStore


def _write_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def test_classifies_product_click_from_raw_json_payload() -> None:
    store = TrackingLogStore(source_path="does-not-exist.jsonl")
    store.record_request(
        url="https://aplus.gmarket.co.kr/product.click.event",
        method="POST",
        post_data=json.dumps({"_p_prod": "12345"}),
        timestamp=time.time(),
    )

    logs = store.get_product_click_logs_by_goodscode("12345")

    assert len(logs) == 1
    assert logs[0]["type"] == "Product Click"
    assert logs[0]["payload"]["_p_prod"] == "12345"


def test_filters_module_exposure_by_spm() -> None:
    store = TrackingLogStore(source_path="does-not-exist.jsonl")
    store.record_request(
        url="https://aplus.gmarket.co.kr/module.exposure.event",
        method="POST",
        post_data=json.dumps({"spm": "gmktm.home.section"}),
        timestamp=time.time(),
    )

    logs = store.get_module_exposure_logs_by_spm("gmktm.home.section")

    assert len(logs) == 1
    assert logs[0]["type"] == "Module Exposure"


def test_scenario_markers_only_expose_logs_between_start_and_stop(tmp_path: Path) -> None:
    capture_file = tmp_path / "capture.jsonl"
    store = TrackingLogStore(source_path=str(capture_file))

    _write_jsonl(
        capture_file,
        {
            "timestamp": 1.0,
            "url": "https://aplus.gmarket.co.kr/product.click.event",
            "method": "POST",
            "post_data": json.dumps({"_p_prod": "111"}),
        },
    )

    store.start()

    _write_jsonl(
        capture_file,
        {
            "timestamp": 2.0,
            "url": "https://aplus.gmarket.co.kr/product.click.event",
            "method": "POST",
            "post_data": json.dumps({"_p_prod": "222"}),
        },
    )
    assert [log["payload"]["_p_prod"] for log in store.get_logs()] == ["222"]

    store.stop()

    _write_jsonl(
        capture_file,
        {
            "timestamp": 3.0,
            "url": "https://aplus.gmarket.co.kr/product.click.event",
            "method": "POST",
            "post_data": json.dumps({"_p_prod": "333"}),
        },
    )
    assert [log["payload"]["_p_prod"] for log in store.get_logs()] == ["222"]
