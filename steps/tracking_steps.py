"""
BDD Step Definitions for Network Tracking
네트워크 트래킹 관련 공통 스텝 정의
"""
import json
import logging
import time
from pathlib import Path

from pytest_bdd import given, when
from utils.NetworkTracker import NetworkTracker
from utils.h_ut_upload_timing import configure_native_h_ut_wait_env

logger = logging.getLogger(__name__)


@given("네트워크 트래킹이 시작되었음")
def given_network_tracking_started(browser_session, bdd_context):
    """네트워크 트래킹 시작"""
    logger.info("네트워크 트래킹 시작")
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config.json"
        app_config = json.loads(cfg_path.read_text(encoding="utf-8"))
        configure_native_h_ut_wait_env(app_config)
    except Exception as exc:
        logger.debug("h-ut wait env not configured: %s", exc)
    tracker = NetworkTracker(browser_session.page)
    tracker.start()
    bdd_context['tracker'] = tracker


@when("네트워크 요청이 완료될 때까지 대기함")
def when_wait_for_network_request_completion():
    """네트워크 요청 완료 대기"""
    logger.info("네트워크 요청 완료 대기")
    time.sleep(2)


@when("네트워크 트래킹을 중지함")
def when_stop_network_tracking(bdd_context):
    """네트워크 트래킹 중지"""
    logger.info("네트워크 트래킹 중지")
    tracker = bdd_context.get('tracker')
    if tracker:
        tracker.stop()
    else:
        logger.warning("트래킹이 시작되지 않았습니다.")
