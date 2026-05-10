"""네이티브 Aplus/UT(h-ut) 업로드 주기(로그캣 기준 ~30s)에 맞춘 대기·폴링."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# logcat: UTUploadCycleConfigMgr getFuCycleTime:30, UploadMgr CurrentUploadInterval:30000
H_UT_FLUSH_INTERVAL_S = 30.0


def h_ut_flush_wait_seconds_from_config(app_config: Optional[dict[str, Any]] = None) -> float:
    """config.json proxy.hUtUploadFlushWaitSeconds (기본 35)."""
    if app_config is None:
        return 35.0
    proxy = app_config.get("proxy") or {}
    try:
        v = float(proxy.get("hUtUploadFlushWaitSeconds", 35))
    except (TypeError, ValueError):
        return 35.0
    return max(0.0, v)


def h_ut_poll_extra_seconds_from_config(app_config: Optional[dict[str, Any]] = None) -> float:
    """첫 flush 이후 연속 /upload(배치 분할)를 잡기 위한 추가 폴링 시간. proxy.hUtUploadPollExtraSeconds (기본 12)."""
    if app_config is None:
        return 12.0
    proxy = app_config.get("proxy") or {}
    try:
        v = float(proxy.get("hUtUploadPollExtraSeconds", 12))
    except (TypeError, ValueError):
        return 12.0
    return max(0.0, v)


def configure_native_h_ut_wait_env(app_config: Optional[dict[str, Any]] = None) -> None:
    """Appium 런타임에서 TRACKING_H_UT_* 환경 변수 설정."""
    if app_config is None:
        return
    rb = (
        str(app_config.get("runner_backend") or app_config.get("automation_backend") or "")
        .strip()
        .lower()
    )
    if rb not in {"appium", "appium_android", "appium_hybrid_android"}:
        return
    flush = h_ut_flush_wait_seconds_from_config(app_config)
    extra = h_ut_poll_extra_seconds_from_config(app_config)
    os.environ["TRACKING_H_UT_FLUSH_WAIT_S"] = str(flush)
    os.environ["TRACKING_H_UT_POLL_EXTRA_S"] = str(extra)
    logger.info(
        "Native h-ut mitm: TRACKING_H_UT_FLUSH_WAIT_S=%s, TRACKING_H_UT_POLL_EXTRA_S=%s (~30s flush + burst)",
        flush,
        extra,
    )


def native_h_ut_initial_wait_ms() -> int:
    """폴링 전 1회 대기(ms). 0이면 비활성."""
    raw = os.environ.get("TRACKING_H_UT_FLUSH_WAIT_S", "").strip()
    if not raw:
        return 0
    try:
        sec = float(raw)
    except ValueError:
        return 0
    return int(max(0.0, sec) * 1000)


def native_h_ut_poll_extra_s(base_timeout_s: float) -> float:
    """기본 timeout_s에 더할 초."""
    raw = os.environ.get("TRACKING_H_UT_POLL_EXTRA_S", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            return 0.0
    if os.environ.get("TRACKING_H_UT_FLUSH_WAIT_S", "").strip():
        return 12.0
    return 0.0


def pre_poll_native_h_ut_wait(page: Any, tracker: Any) -> None:
    """네이티브: 첫 /upload가 잡히기 전 mitm 폴링에 들어가지 않도록 선대기 + 1회 sync."""
    ms = native_h_ut_initial_wait_ms()
    if ms <= 0:
        return
    logger.info("h-ut native: waiting %d ms before tracker poll (upload interval ~%.0fs)", ms, H_UT_FLUSH_INTERVAL_S)
    try:
        page.wait_for_timeout(ms)
    except Exception as exc:
        logger.debug("wait_for_timeout skipped: %s", exc)
    try:
        if tracker is not None and hasattr(tracker, "sync_from_source"):
            tracker.sync_from_source()
    except Exception as exc:
        logger.debug("sync_from_source after h-ut wait: %s", exc)
