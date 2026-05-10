"""h_ut_log_ingest 단위 테스트."""

from __future__ import annotations

from utils.h_ut_log_ingest import build_synthetic_aplus_ingest


def test_build_synthetic_product_exposure() -> None:
    ev = {
        "_capture_subtype": "h_ut_pipe_record",
        "record_index": 0,
        "event_path": "/Product.Exposure.Event",
        "pipe_fields": [
            "google",
            "sdk",
            "a",
            "b",
            "app_env=dev,_p_prod=4307185035,spm=gmktapp.pdp.pdpjfy.ditem14,utLogMap=%7B%22x_object_id%22%3A%224307185035%22%7D",
        ],
    }
    out = build_synthetic_aplus_ingest(ev)
    assert out is not None
    url, method, payload = out
    assert "/product.exposure.event" in url.lower()
    assert method == "POST"
    assert "decoded_gokey" not in payload
    assert "expdata" not in payload
    assert payload["h_ut"]["kv"]["spm"] == "gmktapp.pdp.pdpjfy.ditem14"
    assert payload["h_ut"]["kv"]["_p_prod"] == "4307185035"
    assert payload["h_ut"]["utLogMap"]["parsed"]["x_object_id"] == "4307185035"


def test_build_synthetic_product_click_keeps_h_ut_flat_params() -> None:
    ev = {
        "_capture_subtype": "h_ut_pipe_record",
        "record_index": 105,
        "event_path": "/Product.Click.Event",
        "pipe_fields": [
            "google",
            "sdk_gphone16k_x86_64",
            "2400*1080",
            "T-Mobile",
            "Wi-Fi",
            "Unknown",
            "600000",
            "35008440",
            "10.8.6",
            "-",
            "-",
            "-",
            "-",
            "Unknown",
            "a",
            "17",
            "6.5.12.36",
            "1778399823273",
            "device-id",
            "mini",
            "-",
            "73000133,73000004",
            "-",
            "hmos=0,oaid=null",
            "_spt5g=1,_glat=0",
            "1778399890894",
            "searchlist",
            "2101",
            "/Product.Click.Event",
            "-",
            "-",
            (
                "app_env=dev,server_env=prod,channel_code=200003602,"
                "cguid=11778399856611001702000000,gmkt_area_code=200011491,"
                "utLogMap=%7B%22x_object_id%22%3A%224687001616%22%2C%22query%22%3A%22%EB%AC%BC%ED%8B%B0%EC%8A%88%22%7D,"
                "module_index=2,is_airticket=N,section_index=,_p_prod=4687001616,"
                "pguid=21778399856611001702010000,gmkt_page_id=,is_ad=Y,"
                "spm-pre=gmktapp.pdp.pdpjfy.ditem28,_p_catalog=,"
                "spm-cnt=gmktapp.searchlist,ab_buckets=abc,"
                "spm=gmktapp.searchlist.cpc.d0_6,"
                "spm-url=gmktapp.pdp.searchpopup.dbestkeyword4,"
                "_p_group=56833481,sguid=31778399856611001702510000,"
                "_p_sku=0,utpvid=6\x01batch-token"
            ),
            "tail-token",
        ],
    }

    out = build_synthetic_aplus_ingest(ev)
    assert out is not None
    url, method, payload = out
    assert url == "https://aplus.gmarket.co.kr/product.click.event"
    assert method == "POST"
    assert payload.get("page") == "searchlist"
    assert payload.get("event_code") == "2101"
    assert "decoded_gokey" not in payload
    assert "params" not in payload
    assert "params-clk" not in payload

    kv = payload["h_ut"]["kv"]
    assert payload["h_ut"]["page"] == "searchlist"
    assert payload["h_ut"]["event_code"] == "2101"
    assert payload["h_ut"]["event_path"] == "/Product.Click.Event"
    assert kv["gmkt_area_code"] == "200011491"
    assert kv["module_index"] == "2"
    assert kv["_p_prod"] == "4687001616"
    assert kv["is_ad"] == "Y"
    assert kv["spm-pre"] == "gmktapp.pdp.pdpjfy.ditem28"
    assert kv["spm"] == "gmktapp.searchlist.cpc.d0_6"
    assert kv["spm-cnt"] == "gmktapp.searchlist"
    assert kv["spm-url"] == "gmktapp.pdp.searchpopup.dbestkeyword4"
    assert kv["utpvid"] == "6"
    assert payload["h_ut"]["utLogMap"]["parsed"]["x_object_id"] == "4687001616"
    assert payload["h_ut"]["utLogMap"]["parsed"]["query"] == "물티슈"
