pytest_plugins = [
    "pytest_bdd",
    "steps.home_steps",
    "steps.login_steps",
    "steps.srp_lp_steps",
    "steps.my_steps",
    "steps.product_steps",
    "steps.cart_steps",
    "steps.checkout_steps",
    "steps.order_steps",
    "steps.tracking_steps",
    "steps.tracking_validation_steps",
]


import shutil
import re
import os
import sys
import pytest
import requests
from datetime import datetime
from pathlib import Path
import json
import time
import logging
from typing import Any, Dict, FrozenSet, Iterable, Optional
from dotenv import load_dotenv  # type: ignore
from utils.appium_runtime import AppiumRuntime
from utils.mobile_web_session import MobileWebSession

# .env 파일 로드 (프로젝트 루트 기준)
project_root = Path(__file__).parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)



# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


# # 브라우저 fixture (세션 단위, 한 번만 실행)
# @pytest.fixture(scope="session")
# def browser():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False, args=["--start-maximized"])  # True/False로 headless 제어
#         yield browser
#         browser.close()
#
#
# # 컨텍스트 fixture (브라우저 환경)
# @pytest.fixture(scope="function")
# def context(browser: Browser):
#     context = browser.new_context(no_viewport=True)
#
#     # navigator.webdriver 우회
#     context.add_init_script("""
#         Object.defineProperty(navigator, 'webdriver', {
#             get: () => undefined
#         });
#     """)
#
#     yield context
#     context.close()
#
#
# # 페이지 fixture
# @pytest.fixture(scope="function")
# def page(context: BrowserContext):
#     page = context.new_page()
#     page.set_default_timeout(10000)  # 기본 10초 타임아웃
#     yield page
#     page.close()


def _require_appium_backend() -> None:
    """현재 conftest는 Appium(Android) 런타임만 지원한다."""
    backend = _selected_runner_backend()
    if backend not in {"appium", "appium_android", "appium_hybrid_android"}:
        raise RuntimeError(
            "config.json의 runner_backend(또는 automation_backend)는 "
            "'appium', 'appium_android', 또는 'appium_hybrid_android'여야 합니다. "
            f"현재 값: {backend!r}. playwright 백엔드는 현재 비활성화되어 있습니다."
        )


def _selected_runner_backend() -> str:
    runner_backend = app_config.get("runner_backend")
    if runner_backend is not None and str(runner_backend).strip():
        return str(runner_backend).strip().lower()
    return str(app_config.get("automation_backend", "appium")).strip().lower()


def _config_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "y", "yes", "on"}


def _make_mobile_session(driver) -> MobileWebSession:
    appium_cfg = dict(app_config.get("appium") or {})
    return MobileWebSession(
        driver,
        app_package=appium_cfg.get("appPackage"),
        prefer_webview=_config_bool(appium_cfg.get("preferWebview"), default=True),
        webview_timeout_ms=int(appium_cfg.get("webviewConnectTimeout", 15000)),
    )


# ------------------------
# :여섯: BDD context fixture (각 시나리오마다 독립적으로 생성)
# ------------------------
def _perform_appium_login_mweb_legacy(browser_session: MobileWebSession) -> None:
    from utils.credentials import MemberType, get_credentials
    from utils.urls import base_url

    page = browser_session.page
    credentials = get_credentials(MemberType.NORMAL)
    page.goto(base_url(), wait_until="domcontentloaded")
    try:
        page.locator(".button__popup-close[aria-label='레이어 닫기']").click(timeout=3000)
    except Exception:
        pass

    try:
        if page.locator("text='로그아웃'").count() > 0:
            return
    except Exception:
        pass

    page.locator("a.link.link__myg").click(timeout=10000)
    page.fill("#typeMemberInputId", credentials["username"])
    page.fill("#typeMemberInputPassword", credentials["password"])
    page.click("#btn_memberLogin")
    page.wait_for_selector("text='로그아웃'", timeout=30000)

def _perform_appium_login(browser_session: MobileWebSession) -> None:
    from utils.credentials import MemberType, get_credentials

    login_cfg = dict(app_config.get("app_login") or app_config.get("login") or {})
    if not _config_bool(login_cfg.get("enabled"), default=True):
        logger.info("Appium session login is disabled by config.")
        return

    appium_cfg = dict(app_config.get("appium") or {})
    page = browser_session.page
    credentials = get_credentials(MemberType.NORMAL)

    try:
        browser_session.reset()
        webview_ready = browser_session.switch_to_webview(
            timeout_ms=int(appium_cfg.get("webviewConnectTimeout", 15000)),
            push=False,
        )
        if not webview_ready and _config_bool(login_cfg.get("require_webview"), default=True):
            raise RuntimeError(
                "The APK launched, but no WEBVIEW context was exposed. "
                "Existing page objects use CSS selectors, so either enable the app WebView "
                "debug context or add native Appium selectors for the login flow."
            )

        for popup_selector in login_cfg.get("popup_close_selectors", []):
            try:
                page.locator(str(popup_selector)).click(timeout=3000, force=True)
            except Exception:
                pass

        success_selector = login_cfg.get("success_selector", "text=로그아웃")
        if success_selector:
            try:
                if page.locator(str(success_selector)).count() > 0:
                    logger.info("Appium session login skipped: already logged in.")
                    return
            except Exception:
                pass

        entry_selector = login_cfg.get("entry_selector", "a.link.link__myg")
        username_selector = login_cfg.get("username_selector", "#typeMemberInputId")
        password_selector = login_cfg.get("password_selector", "#typeMemberInputPassword")
        submit_selector = login_cfg.get("submit_selector", "#btn_memberLogin")

        if entry_selector:
            try:
                page.locator(str(entry_selector)).click(timeout=10000)
            except Exception:
                logger.info("Login entry selector was not clickable; trying login form directly.")

        page.fill(str(username_selector), credentials["username"], timeout=15000)
        page.fill(str(password_selector), credentials["password"], timeout=15000)
        page.click(str(submit_selector), timeout=15000)
        if success_selector:
            page.wait_for_selector(str(success_selector), timeout=30000)
        logger.info("Appium session login completed.")
    except Exception as exc:
        raise RuntimeError(
            "Appium APK login failed. The native app was launched, but the configured "
            "login selectors did not complete successfully. Check app_login selectors "
            "or switch this flow to native Appium locators."
        ) from exc


@pytest.fixture(scope="session")
def appium_runtime():
    _require_appium_backend()
    runtime = AppiumRuntime(project_root, app_config)
    runtime.validate_backend()
    yield runtime
    runtime.shutdown(None)


@pytest.fixture(scope="session")
def appium_driver(appium_runtime):
    driver = None
    try:
        driver = appium_runtime.bootstrap()
        _perform_appium_login(_make_mobile_session(driver))
        yield driver
    finally:
        appium_runtime.shutdown(driver)


@pytest.fixture(scope="function")
def browser_session(appium_driver):
    session = _make_mobile_session(appium_driver)
    session.reset()
    yield session
    session.reset()


@pytest.fixture(scope="function")
def page(browser_session):
    current_page = browser_session.page
    current_page.set_default_timeout(10000)
    return current_page


@pytest.fixture(scope="function")
def context(browser_session):
    return browser_session.page.context


@pytest.fixture(scope="function")
def bdd_context():
    """
    시나리오 내 스텝 간 데이터 공유를 위한 전용 객체
    각 시나리오마다 독립적으로 생성됩니다.
    이름 충돌이 없고, 시나리오 메타데이터와 비즈니스 데이터를 분리해서 관리
    
    하위 호환성: 딕셔너리처럼 사용 가능 (bdd_context['key']) + store 속성 사용 가능 (bdd_context.store['key'])
    """
    class Context:
        def __init__(self):
            self.store = {}
            self._dict = {}  # 하위 호환성을 위한 딕셔너리
        
        def __getitem__(self, key):
            """딕셔너리처럼 접근 가능 (하위 호환성)"""
            # store에 있으면 store에서, 없으면 _dict에서
            if key in self.store:
                return self.store[key]
            return self._dict[key]
        
        def __setitem__(self, key, value):
            """딕셔너리처럼 설정 가능 (하위 호환성)"""
            # store와 _dict 모두에 저장 (양쪽에서 접근 가능)
            self.store[key] = value
            self._dict[key] = value
        
        def get(self, key, default=None):
            """딕셔너리처럼 get 메서드 사용 가능 (하위 호환성)"""
            if key in self.store:
                return self.store[key]
            return self._dict.get(key, default)
        
        def __contains__(self, key):
            """in 연산자 지원"""
            return key in self.store or key in self._dict
    
    return Context()


# ============================================
# pytest-bdd hooks (필요 시 추가)
# ============================================
# 각 시나리오가 독립적으로 실행되므로 feature 단위 상태 관리 hook은 제거됨


def pytest_report_teststatus(report, config):
    # 이름에 'wait_'가 들어간 테스트는 리포트 출력에서 숨김
    if any(keyword in report.nodeid for keyword in ["wait_", "fetch"]):
        return report.outcome, None, ""
    return None


# TestRail 연동을 위한 전역 변수
testrail_run_id = None


# ============================================
# TestRail 헬퍼 함수들
# ============================================

def _get_page_from_request(request, step_func_args=None):
    """
    request나 step_func_args에서 page 객체 찾기
    
    Args:
        request: pytest request 객체
        step_func_args: 스텝 함수 인자 딕셔너리
    
    Returns:
        Page 객체 또는 None
    """
    page = None
    
    # request에서 찾기
    if hasattr(request, 'fixturenames'):
        try:
            if "browser_session" in request.fixturenames:
                browser_session = request.getfixturevalue("browser_session")
                if browser_session and hasattr(browser_session, 'page'):
                    page = browser_session.page
        except Exception:
            pass
        
        if not page:
            try:
                if "page" in request.fixturenames:
                    page = request.getfixturevalue("page")
            except Exception:
                pass
    
    # step_func_args에서 찾기
    if not page and step_func_args:
        if "browser_session" in step_func_args:
            browser_session = step_func_args.get("browser_session")
            if browser_session and hasattr(browser_session, 'page'):
                page = browser_session.page
        elif "page" in step_func_args:
            page = step_func_args.get("page")
    
    return page


def _get_browser_session_from_request(request, step_func_args=None):
    browser_session = None

    if hasattr(request, 'fixturenames'):
        try:
            if "browser_session" in request.fixturenames:
                browser_session = request.getfixturevalue("browser_session")
        except Exception:
            pass

    if not browser_session and step_func_args and "browser_session" in step_func_args:
        browser_session = step_func_args.get("browser_session")

    return browser_session


def _capture_screenshot(case_id_num, request=None, step_func_args=None):
    """
    스크린샷 캡처 및 저장
    
    Args:
        case_id_num: TestRail 케이스 ID 번호 또는 파일명 식별자
        request: pytest request 객체
        step_func_args: 스텝 함수 인자 딕셔너리
    
    Returns:
        스크린샷 파일 경로 또는 None
    """
    try:
        browser_session = _get_browser_session_from_request(request, step_func_args)
        page = _get_page_from_request(request, step_func_args)
        
        if page and not page.is_closed():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # case_id_num이 숫자면 TestRail 케이스 ID, 아니면 일반 파일명
            if isinstance(case_id_num, (int, str)) and str(case_id_num).isdigit():
                screenshot_path = f"screenshots/{case_id_num}_{timestamp}.png"
            else:
                screenshot_path = f"screenshots/{case_id_num}_{timestamp}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            if browser_session and hasattr(browser_session, 'capture_screenshot'):
                browser_session.capture_screenshot(screenshot_path)
            else:
                page.screenshot(path=screenshot_path, timeout=PAGE_SCREENSHOT_TIMEOUT_MS)
            print(f"[TestRail] 스크린샷 저장 완료: {screenshot_path}")
            return screenshot_path
    except Exception as e:
        logger.warning(f"스크린샷 저장 실패: {e}")
    
    return None


# 프론트 실패 처리 헬퍼 함수는 utils.frontend_helpers에서 import
from utils.frontend_helpers import (
    PAGE_SCREENSHOT_TIMEOUT_MS,
    capture_frontend_failure_screenshot,
)


def _collect_step_logs():
    """
    현재 스텝의 로그 수집
    
    Returns:
        로그 문자열 또는 None
    """
    try:
        logs = test_log_handler.get_logs()
        if logs and logs.strip():
            return logs
    except Exception as e:
        logger.warning(f"로그 수집 실패: {e}")
    
    return None


def _attach_screenshot_to_testrail(result_id, screenshot_path):
    """
    TestRail 결과에 스크린샷 첨부
    
    Args:
        result_id: TestRail 결과 ID
        screenshot_path: 스크린샷 파일 경로
    """
    if not screenshot_path or not result_id:
        return
    
    try:
        with open(screenshot_path, "rb") as f:
            testrail_post(
                f"add_attachment_to_result/{result_id}",
                files={"attachment": f},
            )
        print(f"[TestRail] 스크린샷 첨부 완료: {screenshot_path}")
    except Exception as e:
        logger.warning(f"TestRail 스크린샷 업로드 실패: {e}")


@pytest.hookimpl(hookwrapper=True)
def pytest_bdd_before_step(request, feature, scenario, step, step_func):
    """
    각 스텝 실행 전 로그 핸들러 초기화
    스텝별로 로그가 누적되지 않도록 각 스텝 시작 전에 초기화
    """
    test_log_handler.clear()
    outcome = yield


@pytest.hookimpl(hookwrapper=True)
def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    """
    각 스텝 실행 후 TestRail에 기록
    스텝 파라미터에서 TC 번호를 추출하여 TestRail에 기록
    로그와 스크린샷 첨부 기능 포함
    """
    outcome = yield
    
    # 훅 시작 로그 (예외 발생 전에도 출력되도록 try 밖에)
    logger.debug(f"===== pytest_bdd_after_step 시작: 스텝='{step.name}' =====")
    
    try:
        # 디버깅: testrail_run_id 확인
        logger.debug(f"pytest_bdd_after_step 실행: 스텝='{step.name}', testrail_run_id={testrail_run_id}")
        
        # 스텝 실행 결과 확인
        if outcome.excinfo is not None:
            step_status = "failed"
            error_msg = str(outcome.excinfo[1]) if outcome.excinfo[1] else "Unknown error"
            logger.debug(f"스텝 실행 중 예외 발생: {error_msg}")
        else:
            # Soft Assertion 지원: bdd_context에서 실패 여부 확인
            step_status = "passed"
            error_msg = None
            
            if step_func_args:
                bdd_context = step_func_args.get('bdd_context')
                if bdd_context and hasattr(bdd_context, 'get'):
                    # 검증 스텝인지 확인 (스텝 이름에 "정합성 검증" 포함)
                    is_validation_step = "정합성 검증" in step.name
                    
                    if is_validation_step:
                        # 검증 스텝: validation_failed만 확인 (프론트 실패 정보는 이미 error_message에 포함됨)
                        validation_failed = bdd_context.get('validation_failed', False)
                        if validation_failed:
                            step_status = "failed"
                            validation_error = bdd_context.get('validation_error_message', '검증 실패')
                            # outcome.excinfo가 있으면 그것을 우선, 없으면 validation_error 사용
                            if error_msg is None or not error_msg:
                                error_msg = validation_error
                            logger.debug(f"검증 스텝 실패 감지: validation_failed={validation_failed}, error_msg={error_msg}")
                    else:
                        # 프론트 동작 스텝: frontend_action_failed 확인
                        if bdd_context.get('frontend_action_failed'):
                            step_status = "failed"
                            if error_msg is None:
                                error_msg = bdd_context.get('frontend_error_message', '프론트 동작 실패')
        
        # TC 번호 추출 시도
        step_case_id = None
        
        # 디버깅: step_func_args 내용 확인
        if step_func_args:
            logger.debug(f"step_func_args 키: {list(step_func_args.keys())}")
            # TC 번호 후보 값들 확인 (모든 값 출력)
            for arg_name, arg_value in step_func_args.items():
                if arg_name != 'bdd_context':  # bdd_context는 너무 클 수 있으므로 제외
                    logger.debug(f"step_func_args[{arg_name}] = {arg_value} (타입: {type(arg_value).__name__})")
        
        # 1. step_func_args에서 TC 번호 파라미터 찾기 (tc_id, tc_module_exposure, tc_product_exposure 등)
        # 검증 스텝에서 tc_id(또는 tc_*)가 비어 있으면 이 스텝은 TestRail에 기록하지 않음 (폴백 사용 금지)
        validation_step_had_empty_tc = False
        if step_func_args:
            for arg_name, arg_value in step_func_args.items():
                if arg_name == 'bdd_context':
                    continue
                # TC 번호 형식 확인 (C로 시작하는 문자열)
                if isinstance(arg_value, str):
                    arg_value_stripped = arg_value.strip()
                    # C로 시작하고 뒤에 숫자가 오는 경우
                    if arg_value_stripped.startswith("C") and len(arg_value_stripped) > 1:
                        try:
                            if arg_value_stripped[1:].isdigit():
                                step_case_id = arg_value_stripped
                                logger.debug(f"step_func_args에서 TC 번호 발견: {arg_name}={step_case_id} (스텝: {step.name})")
                                break
                        except (ValueError, IndexError):
                            pass
                    # 검증 스텝이고 이 스텝의 TC 파라미터(tc_id, tc_*)가 비어있음 → 폴백 사용 안 함
                    elif "정합성 검증" in step.name and (arg_name == "tc_id" or arg_name.startswith("tc_")):
                        validation_step_had_empty_tc = True
                        logger.warning(f"검증 스텝 '{step.name}'에서 tc_id 파라미터 값이 TC 번호 형식이 아닙니다: '{arg_value_stripped}'")
        
        # 2. step_func_args에서 bdd_context를 통해 TC 번호 찾기 (검증 스텝에서 tc가 비어있으면 폴백 사용 안 함)
        if step_case_id is None and step_func_args and not (validation_step_had_empty_tc):
            bdd_context = step_func_args.get('bdd_context')
            if bdd_context:
                logger.debug(f"bdd_context 타입: {type(bdd_context).__name__}, hasattr('get'): {hasattr(bdd_context, 'get')}")
                if hasattr(bdd_context, 'get'):
                    step_case_id = bdd_context.get('testrail_tc_id')
                    if step_case_id:
                        logger.debug(f"bdd_context.get('testrail_tc_id')에서 TC 번호 발견: {step_case_id}")
                elif hasattr(bdd_context, 'store'):
                    step_case_id = bdd_context.store.get('testrail_tc_id')
                    if step_case_id:
                        logger.debug(f"bdd_context.store.get('testrail_tc_id')에서 TC 번호 발견: {step_case_id}")
                
                # 디버깅: bdd_context에 저장된 모든 testrail 관련 키 확인
                if hasattr(bdd_context, 'get'):
                    testrail_keys = [k for k in dir(bdd_context) if 'testrail' in k.lower() or 'tc' in k.lower()]
                    if testrail_keys:
                        logger.debug(f"bdd_context의 testrail 관련 키: {testrail_keys}")
                        for key in ['testrail_tc_id', 'tc_id']:
                            if hasattr(bdd_context, 'get'):
                                value = bdd_context.get(key)
                                if value:
                                    logger.debug(f"bdd_context.get('{key}') = {value}")
        
        logger.debug(f"추출된 TC 번호: {step_case_id}, testrail_run_id: {testrail_run_id}, step_status: {step_status}")
        
        # TestRail 기록 (testrail_run_id가 설정되어 있고 TC 번호가 있을 때만)
        if step_case_id and testrail_run_id:
            logger.debug(f"TestRail 기록 시작: case_id={step_case_id}, status={step_status}")
            # Cxxxx → 숫자만 추출
            case_id_num = int(step_case_id[1:]) if step_case_id.startswith("C") else int(step_case_id)
            
            # skip_reason 확인
            skip_reason = None
            if step_func_args:
                bdd_context = step_func_args.get('bdd_context')
                if bdd_context:
                    if hasattr(bdd_context, 'get'):
                        skip_reason = bdd_context.get('skip_reason')
                    elif hasattr(bdd_context, 'store'):
                        skip_reason = bdd_context.store.get('skip_reason')
            
            # 상태 결정: skip_reason이 있으면 skip (4), 실패면 failed (5), 아니면 passed (1)
            if skip_reason:
                status_id = 4  # TestRail skip/retest 상태
                step_status = "skipped"
            elif step_status == "failed":
                status_id = 5
            else:
                status_id = 1
            
            comment = f"스텝: {step.name}\n"
            if skip_reason:
                comment += f"Skip: {skip_reason}\n"
            if error_msg:
                comment += f"오류: {error_msg}"
            
            # 검증 스텝인 경우 통과한 필드 목록 추가
            is_validation_step = "정합성 검증" in step.name
            if step_func_args and is_validation_step:
                bdd_context = step_func_args.get('bdd_context')
                if bdd_context:
                    passed_fields = None
                    if hasattr(bdd_context, 'get'):
                        passed_fields = bdd_context.get('validation_passed_fields')
                    elif hasattr(bdd_context, 'store'):
                        passed_fields = bdd_context.store.get('validation_passed_fields')
                    
                    if passed_fields and isinstance(passed_fields, dict) and len(passed_fields) > 0:
                        comment += f"\n\n[통과한 필드]\n"
                        for field, value in passed_fields.items():
                            if isinstance(value, dict):
                                expected = value.get("expected")
                                actual = value.get("actual")
                                comment += f"{field}: expected={expected}, actual={actual}\n"
                            else:
                                # 하위 호환: 과거 포맷(값만 저장된 경우)
                                comment += f"{field}: {value}\n"
            
            # 로그 수집
            log_content = _collect_step_logs()
            if log_content:
                comment += f"\n\n--- 실행 로그 ---\n{log_content}"
            # 로그 수집 후 초기화 (다음 스텝과 로그 섞임 방지)
            test_log_handler.clear()
            
            # 스크린샷 경로 확인 (프론트 실패 시점에 찍은 스크린샷 우선 사용)
            screenshot_path = None
            if step_status == "failed":
                # 검증 스텝인지 확인
                is_validation_step = "정합성 검증" in step.name
                
                if is_validation_step:
                    # 검증 스텝: 프론트 실패로 인한 로그 수집 실패인 경우 프론트 실패 스크린샷 사용
                    if step_func_args:
                        bdd_context = step_func_args.get('bdd_context')
                        if bdd_context:
                            # 프론트 실패가 있고 error_message에 "프론트 실패 사유"가 포함되어 있으면 스크린샷 사용
                            if hasattr(bdd_context, 'get'):
                                if bdd_context.get('frontend_action_failed') and error_msg and "[프론트 실패 사유]" in error_msg:
                                    screenshot_path = bdd_context.get('frontend_failure_screenshot')
                            elif hasattr(bdd_context, 'store'):
                                if bdd_context.store.get('frontend_action_failed') and error_msg and "[프론트 실패 사유]" in error_msg:
                                    screenshot_path = bdd_context.store.get('frontend_failure_screenshot')
                    
                    # 스크린샷이 없으면 검증 실패 스크린샷 찍기
                    if not screenshot_path:
                        screenshot_path = _capture_screenshot(case_id_num, request, step_func_args)
                else:
                    # 프론트 동작 스텝: 프론트 실패 스크린샷 확인
                    if step_func_args:
                        bdd_context = step_func_args.get('bdd_context')
                        if bdd_context:
                            if hasattr(bdd_context, 'get'):
                                screenshot_path = bdd_context.get('frontend_failure_screenshot')
                            elif hasattr(bdd_context, 'store'):
                                screenshot_path = bdd_context.store.get('frontend_failure_screenshot')
                    
                    # 저장된 스크린샷이 없으면 새로 찍기
                    if not screenshot_path:
                        screenshot_path = _capture_screenshot(case_id_num, request, step_func_args)
            
            payload = {
                "status_id": status_id,
                "comment": comment,
            }
            
            result_id = None
            try:
                logger.debug(f"TestRail API 호출: add_result_for_case/{testrail_run_id}/{case_id_num}")
                result_obj = testrail_post(
                    f"add_result_for_case/{testrail_run_id}/{case_id_num}", 
                    payload
                )
                result_id = result_obj.get("id")
                print(f"[TestRail] 스텝 '{step.name}' 결과 기록 완료 (case_id: {step_case_id}, status: {step_status}, result_id: {result_id})")
            except Exception as e:
                logger.warning(f"스텝 TestRail 기록 실패: {e}")
                import traceback
                logger.debug(f"TestRail 기록 실패 상세:\n{traceback.format_exc()}")
            
            # 스크린샷 첨부
            _attach_screenshot_to_testrail(result_id, screenshot_path)
            
        elif step_case_id:
            # TC 번호는 있지만 testrail_run_id가 없는 경우 (TestRail 연동 미활성화)
            logger.debug(f"TC 번호는 있지만 testrail_run_id가 None입니다. step_case_id={step_case_id}, testrail_run_id={testrail_run_id}")
            print(f"[TestRail] 스텝 '{step.name}' TC 번호 발견: {step_case_id} (TestRail 연동 미활성화)")
        elif not step_case_id:
            # TC 번호가 없는 경우 (검증 스텝에서 tc_id가 비어 있으면 의도적으로 기록하지 않음)
            if validation_step_had_empty_tc:
                logger.debug(f"검증 스텝에서 tc_id가 비어 있어 TestRail 기록을 건너뜁니다. 스텝={step.name}")
            else:
                logger.debug(f"TC 번호를 찾을 수 없습니다. step_func_args={step_func_args is not None}, step_status={step_status}")
        
        # TC 번호가 없지만 실패한 프론트 동작 스텝인 경우 - 스크린샷만 저장 (참고용)
        if step_status == "failed" and not step_case_id:
            # 프론트 동작 실패인 경우 로그만 남기고 스크린샷 저장
            print(f"[TestRail] 스텝 '{step.name}' 실패 (TC 번호 없음): {error_msg}")
            # 프론트 실패 시점에 찍은 스크린샷 확인
            screenshot_path = None
            if step_func_args:
                bdd_context = step_func_args.get('bdd_context')
                if bdd_context:
                    if hasattr(bdd_context, 'get'):
                        screenshot_path = bdd_context.get('frontend_failure_screenshot')
                    elif hasattr(bdd_context, 'store'):
                        screenshot_path = bdd_context.store.get('frontend_failure_screenshot')
            
            # 저장된 스크린샷이 없으면 새로 찍기
            if not screenshot_path:
                screenshot_path = _capture_screenshot(f"frontend_fail_{step.name.replace(' ', '_')}", request, step_func_args)
            
            if screenshot_path:
                logger.info(f"프론트 동작 실패 스크린샷 저장: {screenshot_path}")
        
        logger.debug(f"===== pytest_bdd_after_step 종료 (정상) =====")
    
    except Exception as e:
        import traceback
        logger.error(f"pytest_bdd_after_step 처리 중 예외 발생: {e}")
        logger.error(f"예외 상세:\n{traceback.format_exc()}")
        logger.debug(f"===== pytest_bdd_after_step 종료 (예외 발생) =====")


# JSON 파일이 들어 있는 폴더 지정
JSON_DIR = Path(__file__).parent / "json"  # json 폴더 내의 JSON 파일 전부 대상


# Config 파일 로딩 (상위 키 = TestRail 등 폴백; 스위트별 오버레이는 config.json 메타 키로 정의)
_TESTRAIL_CONFIG_META_KEYS = frozenset(
    {"testrail_suite_blocks", "testrail_paths_to_suite", "testrail_overlay_keys"}
)
# 스위트 블록으로 오인하지 않을 일반 최상위 키(값이 dict가 아니거나, dict여도 스위트가 아님)
_TESTRAIL_NON_SUITE_TOP_KEYS = frozenset(
    {
        "tr_url",
        "environment",
        "mobile_profile",
        "spreadsheet_id",
        "testrail_report",
        "testrail_run_name",
        "testrail_close_run_on_finish",
        "multiple_test_use",
        "milestone_id",
        "project_id",
        "section_id",
        "suite_id",
        "testrail_run_id",
        "testrail_run_create",
    }
)


def _shape_inferred_suite_block_names(raw: Dict[str, Any]) -> list[str]:
    """testrail_suite_blocks·testrail_paths_to_suite가 없을 때, 오버레이 ID가 들어 있는 최상위 dict 키를 스위트 블록으로 본다."""
    overlay = set(_testrail_overlay_keys(raw))
    names: list[str] = []
    for k, v in raw.items():
        if k in _TESTRAIL_CONFIG_META_KEYS or k in _TESTRAIL_NON_SUITE_TOP_KEYS:
            continue
        if isinstance(v, dict) and (overlay & v.keys()):
            names.append(str(k))
    return sorted(names)


def _suite_block_keys(raw: Dict[str, Any]) -> FrozenSet[str]:
    """오버레이용으로 app_config에서 제거할 최상위 키.
    - testrail_suite_blocks가 있으면 그 목록만.
    - 없고 testrail_paths_to_suite(구 방식) 객체가 있으면 값 중 raw에 dict인 스위트 이름.
    - 둘 다 없으면 형태 추론(_shape_inferred_suite_block_names).
    """
    spec = raw.get("testrail_suite_blocks")
    if spec is not None:
        if isinstance(spec, dict):
            return frozenset(str(k) for k in spec)
        if isinstance(spec, (list, tuple, set)):
            return frozenset(str(x) for x in spec)
        raise RuntimeError("config.json의 testrail_suite_blocks는 문자열 배열이거나 객체여야 합니다.")
    legacy = raw.get("testrail_paths_to_suite")
    if isinstance(legacy, dict) and legacy:
        return frozenset(
            str(v) for v in legacy.values() if isinstance(raw.get(str(v)), dict)
        )
    return frozenset(_shape_inferred_suite_block_names(raw))


def _paths_to_suite_rules(raw: Dict[str, Any]) -> list[tuple[str, str]]:
    """(경로 부분문자열 소문자, 스위트블록이름) 목록, 긴 marker 우선.
    - 구 방식: testrail_paths_to_suite 가 비어 있지 않은 객체 → 그대로 사용.
    - 기본: 각 스위트 블록에 path_markers가 있으면 사용, 없으면 test_<블록이름> 한 개.
    """
    legacy = raw.get("testrail_paths_to_suite")
    if isinstance(legacy, dict) and legacy:
        pairs = [(str(k), str(v)) for k, v in legacy.items()]
    else:
        pairs = []
        for suite_key in sorted(_suite_block_keys(raw)):
            block = raw.get(suite_key)
            if not isinstance(block, dict):
                continue
            markers = block.get("path_markers")
            if markers is None:
                mlist = [f"test_{suite_key}"]
            elif isinstance(markers, str):
                mlist = [markers]
            elif isinstance(markers, (list, tuple)):
                mlist = [str(x) for x in markers]
            else:
                raise RuntimeError(
                    f"config.json의 '{suite_key}.path_markers'는 문자열 또는 문자열 배열이어야 합니다."
                )
            for m in mlist:
                pairs.append((m, str(suite_key)))
    out = [(m.replace("\\", "/").lower(), sk) for m, sk in pairs]
    out.sort(key=lambda x: -len(x[0]))
    return out


def _testrail_overlay_keys(raw: Dict[str, Any]) -> tuple[str, ...]:
    keys = raw.get("testrail_overlay_keys")
    if keys is None:
        return ("milestone_id", "project_id", "section_id", "suite_id", "testrail_run_id")
    if not isinstance(keys, (list, tuple)):
        raise RuntimeError("config.json의 testrail_overlay_keys는 문자열 배열이어야 합니다.")
    return tuple(str(x) for x in keys)


def _infer_testrail_suite_key_from_paths(
    paths: Iterable[Any], raw: Dict[str, Any]
) -> Optional[str]:
    """경로 규칙으로 스위트 추론(구 testrail_paths_to_suite 또는 test_<블록명>/path_markers). 매칭 스위트가 정확히 하나일 때만 반환."""
    pairs = _paths_to_suite_rules(raw)
    if not pairs:
        return None
    seen: list[str] = []
    for p in paths:
        if not isinstance(p, str):
            continue
        norm = p.replace("\\", "/").lower()
        for marker, suite_key in pairs:
            if marker in norm and suite_key not in seen:
                seen.append(suite_key)
    if len(seen) == 1:
        return seen[0]
    return None


def _build_effective_config(raw: Dict[str, Any], suite_key: Optional[str]) -> Dict[str, Any]:
    block_keys = _suite_block_keys(raw)
    overlay_keys = _testrail_overlay_keys(raw)
    out = {
        k: v
        for k, v in raw.items()
        if k not in block_keys and k not in _TESTRAIL_CONFIG_META_KEYS
    }
    block = raw.get(suite_key) if suite_key else None
    if isinstance(block, dict):
        for rk in overlay_keys:
            val = block.get(rk)
            if val is not None and str(val).strip() != "":
                out[rk] = val
    return out


_raw_config: Dict[str, Any] = {}
try:
    with open("config.json", "r", encoding="utf-8") as config_file:
        _raw_config = json.load(config_file)
except FileNotFoundError:
    raise RuntimeError("config.json 파일을 찾을 수 없습니다.")
except json.JSONDecodeError as e:
    raise RuntimeError(f"config.json 파일의 JSON 형식이 잘못되었습니다: {e}")

app_config = _build_effective_config(
    _raw_config, _infer_testrail_suite_key_from_paths(sys.argv, _raw_config)
)

# 모바일 에뮬레이션 — config.json 키: mobile_profile (없으면 iphone)
#   iphone       : iPhone 12/13 계열 Safari UA (기존 기본)
#   galaxy_s20   : 갤럭시 S20 이상(Android Chrome mweb) 뷰포트·UA
MOBILE_PROFILES = {
    "iphone": {
        "label": "iPhone 12/13 class (Safari)",
        "viewport": {"width": 390, "height": 844},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    },
    "galaxy_s20": {
        "label": "Galaxy S20+ class (Android Chrome)",
        "viewport": {"width": 360, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 14; SM-G981N) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
        ),
    },
}


def _get_mobile_emulation():
    """config.json의 mobile_profile에 따라 뷰포트·User-Agent 반환."""
    raw = (app_config.get("mobile_profile") or "iphone").strip().lower()
    profile = MOBILE_PROFILES.get(raw)
    if profile is None:
        logger.warning(
            "config.json의 mobile_profile=%r은 지원하지 않습니다. 지원 값: %s — iphone으로 대체합니다.",
            raw,
            ", ".join(sorted(MOBILE_PROFILES)),
        )
        profile = MOBILE_PROFILES["iphone"]
        raw = "iphone"
    logger.info("모바일 에뮬레이션: %s (%s)", raw, profile["label"])
    return profile["viewport"], profile["user_agent"]


def _refresh_testrail_globals() -> None:
    """app_config(config.json 병합본) 기준으로 TestRail 관련 모듈 전역을 다시 설정한다."""
    global TESTRAIL_REPORT_ENABLED, TESTRAIL_RUN_NAME, TESTRAIL_CLOSE_RUN_ON_FINISH
    global TESTRAIL_BASE_URL, TESTRAIL_PROJECT_ID, TESTRAIL_SUITE_ID, TESTRAIL_SECTION_ID, TESTRAIL_MILESTONE_ID
    global TESTRAIL_USER, TESTRAIL_TOKEN, TESTRAIL_TARGET_RUN_ID, TESTRAIL_RUN_CREATE

    TESTRAIL_REPORT_ENABLED = (app_config.get("testrail_report") or "N").strip().upper() == "Y"
    TESTRAIL_RUN_NAME = (
        (app_config.get("testrail_run_name") or "GUT Automation test mweb {datetime}").strip()
    )
    TESTRAIL_CLOSE_RUN_ON_FINISH = (
        (app_config.get("testrail_close_run_on_finish") or "Y").strip().upper() == "Y"
    )
    raw_run_create = app_config.get("testrail_run_create", True)
    if isinstance(raw_run_create, bool):
        TESTRAIL_RUN_CREATE = raw_run_create
    else:
        normalized_run_create = str(raw_run_create).strip().lower()
        if normalized_run_create in {"true", "y", "yes", "1"}:
            TESTRAIL_RUN_CREATE = True
        elif normalized_run_create in {"false", "n", "no", "0"}:
            TESTRAIL_RUN_CREATE = False
        else:
            raise RuntimeError(
                f"config.json의 testrail_run_create 값 '{raw_run_create}'는 true/false(또는 Y/N)여야 합니다."
            )
    raw_target_run_id = app_config.get("testrail_run_id")
    if raw_target_run_id is None or str(raw_target_run_id).strip() == "":
        TESTRAIL_TARGET_RUN_ID = None
    else:
        try:
            TESTRAIL_TARGET_RUN_ID = int(str(raw_target_run_id).strip())
        except (TypeError, ValueError):
            raise RuntimeError(
                f"config.json의 testrail_run_id 값 '{raw_target_run_id}'는 숫자여야 합니다."
            )

    if TESTRAIL_REPORT_ENABLED:
        try:
            TESTRAIL_BASE_URL = app_config["tr_url"]
            TESTRAIL_PROJECT_ID = app_config["project_id"]
            TESTRAIL_SUITE_ID = app_config["suite_id"]
            TESTRAIL_SECTION_ID = app_config["section_id"]
            TESTRAIL_MILESTONE_ID = app_config["milestone_id"]
        except KeyError as e:
            raise RuntimeError(f"config.json에 필수 키 '{e}'가 없습니다.")
        try:
            TESTRAIL_USER = os.getenv("TESTRAIL_USERNAME")
            TESTRAIL_TOKEN = os.getenv("TESTRAIL_PASSWORD")
            if not TESTRAIL_USER or not TESTRAIL_TOKEN:
                raise RuntimeError(
                    "TestRail 인증 정보(username 또는 password)가 없습니다. .env 파일에 TESTRAIL_USERNAME과 TESTRAIL_PASSWORD를 설정해주세요."
                )
        except Exception as e:
            raise RuntimeError(f"TestRail 인증 정보를 가져오는 중 오류 발생: {e}")
    else:
        TESTRAIL_BASE_URL = (
            TESTRAIL_PROJECT_ID
        ) = TESTRAIL_SUITE_ID = TESTRAIL_SECTION_ID = TESTRAIL_MILESTONE_ID = None
        TESTRAIL_USER = TESTRAIL_TOKEN = None
        TESTRAIL_TARGET_RUN_ID = None


_refresh_testrail_globals()


def pytest_configure(config):
    """최종 수집 인자 기준으로 스위트 키를 다시 맞추고 TestRail 전역을 동기화한다."""
    global app_config
    suite_key = _infer_testrail_suite_key_from_paths(config.args, _raw_config)
    app_config = _build_effective_config(_raw_config, suite_key)
    _refresh_testrail_globals()
    if suite_key:
        logger.info("TestRail: '%s' 스위트 블록 오버레이 적용", suite_key)
    else:
        logger.debug(
            "TestRail: 상위 config만 사용 (경로 미매칭, 복수 스위트 동시 실행, 또는 스위트 블록 없음)"
        )


testrail_run_id = None
testrail_run_created_by_session = False
case_id_map = {}  # {섹션 이름: [케이스ID 리스트]}
test_logs = {}  # {nodeid: 로그 문자열} - 테스트별 로그 저장
current_test_nodeid = None  # 현재 실행 중인 테스트의 nodeid


def testrail_get(endpoint):
    url = f"{TESTRAIL_BASE_URL}/index.php?/api/v2/{endpoint}"
    r = requests.get(url, auth=(TESTRAIL_USER, TESTRAIL_TOKEN))
    r.raise_for_status()
    return r.json()


def testrail_post(endpoint, payload=None, files=None):
    url = f"{TESTRAIL_BASE_URL}/index.php?/api/v2/{endpoint}"
    if files:
        r = requests.post(url, auth=(TESTRAIL_USER, TESTRAIL_TOKEN), files=files)
    else:
        r = requests.post(url, auth=(TESTRAIL_USER, TESTRAIL_TOKEN), json=payload)
    r.raise_for_status()
    return r.json()


from collections import defaultdict

def get_all_subsection_ids(parent_section_id, all_sections):
    """
    사전 인덱싱(Indexing)을 통해 성능을 비약적으로 향상시킨 버전
    """
    # 1. 데이터를 정수형으로 미리 가공하고, 부모-자식 관계 맵을 생성 (O(N))
    children_map = defaultdict(list)
    
    # 입력 받은 parent_section_id도 미리 정수로 변환
    try:
        root_id = int(parent_section_id)
    except (ValueError, TypeError):
        return [parent_section_id]

    for section in all_sections:
        try:
            s_id = int(section["id"])
            p_id = section.get("parent_id")
            # 부모가 있는 경우에만 맵에 추가
            if p_id is not None:
                p_id = int(p_id)
                children_map[p_id].append(s_id)
        except (ValueError, TypeError):
            continue

    # 2. 재귀적으로 ID를 수집 (O(M), M은 하위 섹션의 개수)
    result_ids = []
    visited = set()

    def collect(current_id):
        if current_id in visited:
            return
        visited.add(current_id)
        result_ids.append(current_id)
        
        # 맵에서 자식들을 바로 찾아 순회 (전체 리스트를 훑지 않음)
        for child_id in children_map.get(current_id, []):
            collect(child_id)

    collect(root_id)
    return result_ids


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    테스트 실행 시작 시:
    1. section_id 기반으로 해당 섹션과 모든 하위 섹션의 케이스 ID 가져오기
    2. 그 케이스들로 Run 생성
    """
    global testrail_run_id, case_id_map, testrail_run_created_by_session
    
    if not TESTRAIL_REPORT_ENABLED:
        print("[TestRail] testrail_report가 Y가 아님 - 기록 비활성화")
        return
    
    logger.debug(f"pytest_sessionstart 실행 시작")
    logger.debug(f"현재 testrail_run_id 값: {testrail_run_id}")
    
    if testrail_run_id is not None:
        print(f"[TestRail] 이미 Run(ID={testrail_run_id})이 존재합니다. 새 Run 생성 생략")
        testrail_run_created_by_session = False
        return

    if not TESTRAIL_RUN_CREATE:
        if TESTRAIL_TARGET_RUN_ID is None:
            raise RuntimeError(
                "[TestRail] testrail_run_create=false 인 경우 config.json에 testrail_run_id를 반드시 설정해야 합니다."
            )
        try:
            testrail_get(f"get_run/{TESTRAIL_TARGET_RUN_ID}")
            testrail_run_id = TESTRAIL_TARGET_RUN_ID
            testrail_run_created_by_session = False
            print(
                f"[TestRail] testrail_run_create=false - 기존 Run(ID={testrail_run_id})에 결과를 기록합니다."
            )
            return
        except Exception as e:
            raise RuntimeError(
                f"[TestRail] config.json에 지정한 testrail_run_id={TESTRAIL_TARGET_RUN_ID} 조회 실패: {e}"
            )

    if TESTRAIL_TARGET_RUN_ID is not None:
        print(
            f"[TestRail] testrail_run_create=true - testrail_run_id={TESTRAIL_TARGET_RUN_ID}는 무시하고 새 Run을 생성합니다."
        )
    
    if not TESTRAIL_SECTION_ID:
        logger.error(f"TESTRAIL_SECTION_ID가 정의되지 않았습니다.")
        raise RuntimeError("[TestRail] TESTRAIL_SECTION_ID가 정의되지 않았습니다.")
    
    # TESTRAIL_SECTION_ID를 정수로 변환
    try:
        section_id_int = int(TESTRAIL_SECTION_ID)
    except (ValueError, TypeError):
        raise RuntimeError(f"[TestRail] TESTRAIL_SECTION_ID '{TESTRAIL_SECTION_ID}'를 정수로 변환할 수 없습니다.")
    
    # 1. 모든 섹션 가져오기
    print(f"[TestRail] 모든 섹션 가져오기 중...")
    all_sections = testrail_get(
        f"get_sections/{TESTRAIL_PROJECT_ID}&suite_id={TESTRAIL_SUITE_ID}"
    )
    
    # 디버깅: 섹션 구조 확인
    print(f"[TestRail] 총 {len(all_sections)}개 섹션 발견")
    print(f"[TestRail] 찾고자 하는 섹션 ID: {section_id_int} (타입: {type(section_id_int).__name__})")
    
    # 지정된 섹션이 존재하는지 확인
    section_exists = any(s.get("id") == section_id_int for s in all_sections)
    if not section_exists:
        logger.warning(f"섹션 ID {section_id_int}가 존재하지 않습니다.")
        logger.debug(f"사용 가능한 섹션 ID 샘플 (최대 10개):")
        for s in all_sections[:10]:
            print(f"  - ID: {s.get('id')}, Name: {s.get('name')}, Parent ID: {s.get('parent_id')}")
    
    # 2. 지정된 섹션과 모든 하위 섹션 ID 찾기 → 서브트리 집합 (O(1) 조회용)
    all_section_ids = get_all_subsection_ids(section_id_int, all_sections)
    all_section_ids = list(dict.fromkeys(all_section_ids))  # 순서 유지하면서 중복 제거
    subtree_section_ids = set(all_section_ids)
    print(f"[TestRail] 섹션 ID {section_id_int}와 하위 섹션 {len(all_section_ids) - 1}개 발견 (중복 제거됨): {all_section_ids}")
    
    # 3. 스위트 전체 케이스 한 번에 가져오기 (페이지네이션) 후 로컬 필터링
    all_case_ids = []
    limit = 250
    offset = 0
    base_cases_url = f"get_cases/{TESTRAIL_PROJECT_ID}&suite_id={TESTRAIL_SUITE_ID}&limit={limit}&offset="
    while True:
        try:
            cases = testrail_get(base_cases_url + str(offset))
        except Exception as e:
            logger.warning(f"스위트 전체 케이스 가져오기 실패 (offset={offset}): {e}")
            break
        if not cases:
            break
        for c in cases:
            sid = c.get("section_id")
            if sid is not None and sid in subtree_section_ids:
                case_id = c["id"]
                all_case_ids.append(case_id)
                case_id_map.setdefault(sid, []).append(case_id)
        if len(cases) < limit:
            break
        offset += limit
    # 중복 제거 (같은 케이스가 여러 번 나올 수 있음)
    all_case_ids = list(dict.fromkeys(all_case_ids))
    
    if not all_case_ids:
        raise RuntimeError(f"[TestRail] section_id '{section_id_int}'와 하위 섹션에 케이스가 없습니다.")
    
    print(f"[TestRail] 총 {len(all_case_ids)}개 케이스 수집 완료")
    
    # 4. Run 생성 (이름은 config.json의 testrail_run_name)
    _dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_name = TESTRAIL_RUN_NAME.replace("{datetime}", _dt)
    payload = {
        "suite_id": TESTRAIL_SUITE_ID,
        "name": run_name,
        "include_all": False,
        "case_ids": all_case_ids,
        "milestone_id": TESTRAIL_MILESTONE_ID
    }
    try:
        logger.debug(f"TestRail Run 생성 시도: project_id={TESTRAIL_PROJECT_ID}, case_ids 개수={len(all_case_ids)}")
        run = testrail_post(f"add_run/{TESTRAIL_PROJECT_ID}", payload)
        testrail_run_id = run["id"]
        testrail_run_created_by_session = True
        print(f"[TestRail] section_id '{section_id_int}' (하위 섹션 포함) Run 생성 완료 (ID={testrail_run_id})")
        logger.debug(f"pytest_sessionstart 완료: testrail_run_id={testrail_run_id}")
    except Exception as e:
        logger.error(f"TestRail Run 생성 실패: {e}")
        import traceback
        logger.debug(f"Run 생성 실패 상세:\n{traceback.format_exc()}")
        raise


# 커스텀 로그 핸들러 - 테스트 실행 중 로그를 수집
class TestLogHandler(logging.Handler):
    """테스트 실행 중 로그를 수집하는 커스텀 핸들러"""
    def __init__(self):
        super().__init__()
        self.logs = []
    
    def emit(self, record):
        """로그 레코드를 수집"""
        if record.levelno >= logging.INFO:  # INFO 이상만 수집
            log_message = self.format(record)
            self.logs.append(log_message)
    
    def clear(self):
        """로그 초기화"""
        self.logs = []
    
    def get_logs(self):
        """수집된 로그 반환"""
        return "\n".join(self.logs)

# 전역 로그 핸들러
test_log_handler = TestLogHandler()
test_log_handler.setLevel(logging.INFO)
test_log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

# 루트 로거에 핸들러 추가
root_logger = logging.getLogger()
root_logger.addHandler(test_log_handler)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """테스트 시작 시 로그 핸들러 초기화"""
    global current_test_nodeid
    current_test_nodeid = item.nodeid
    test_log_handler.clear()
    
    outcome = yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """테스트 종료 시 로그 핸들러 초기화 (다음 테스트와 로그 섞임 방지)"""
    outcome = yield
    # teardown 후에 초기화 (pytest_runtest_logreport와 pytest_runtest_makereport가 모두 실행된 후)
    # 다음 테스트가 있는 경우에만 초기화 (마지막 테스트는 세션 종료 시 정리)
    if nextitem:
        test_log_handler.clear()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_logreport(report):
    """
    각 테스트의 로그를 수집하여 test_logs에 저장
    pytest_runtest_makereport보다 먼저 실행되도록 tryfirst=True 설정
    """
    outcome = yield
    # setup, call, teardown 모든 단계에서 로그 수집
    if report.when == "call":  # 실행 단계만
        nodeid = report.nodeid
        if report.outcome in ("passed", "failed", "skipped"):
            # 수집된 로그 가져오기 (이 시점에 현재 테스트의 로그만 있어야 함)
            # pytest_runtest_setup과 pytest_bdd_before_scenario에서 이미 초기화했으므로
            # 현재 테스트의 로그만 있어야 함
            logs = test_log_handler.get_logs()
            if logs and logs.strip():
                # nodeid를 키로 사용하여 저장 (성공/실패 모두 저장)
                test_logs[nodeid] = logs
                # 로그 라인 수 확인
                log_lines = logs.split(chr(10))
                logger.debug(f"테스트 {nodeid} 로그 수집 완료: {len(log_lines)}줄 (outcome: {report.outcome})")
                # 로그를 test_logs에 저장했으므로 즉시 초기화 (다음 테스트와 로그 섞임 방지)
                # pytest_runtest_makereport에서 사용할 때까지는 test_logs에 보관됨
                test_log_handler.clear()
            else:
                logger.debug(f"테스트 {nodeid} 로그 없음 (빈 로그 또는 수집 실패, outcome: {report.outcome})")
                # 로그가 없어도 초기화 (이전 로그 제거)
                test_log_handler.clear()



@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """
    전체 테스트 종료 후 Run 닫기
    """
    global testrail_run_id, testrail_run_created_by_session
    if (
        testrail_run_id
        and testrail_run_created_by_session
        and TESTRAIL_RUN_CREATE
        and TESTRAIL_CLOSE_RUN_ON_FINISH
    ):
        testrail_post(f"close_run/{testrail_run_id}", {})
        print(f"[TestRail] Run {testrail_run_id} 종료 완료")
    elif testrail_run_id and (not testrail_run_created_by_session or not TESTRAIL_RUN_CREATE):
        print(f"[TestRail] 기존 Run(ID={testrail_run_id}) 재사용 모드 - 자동 종료 생략")
    elif testrail_run_id and not TESTRAIL_CLOSE_RUN_ON_FINISH:
        print(f"[TestRail] testrail_close_run_on_finish=N - Run {testrail_run_id} 자동 종료 생략")

    screenshots_dir = "screenshots"
    if os.path.exists(screenshots_dir):
        shutil.rmtree(screenshots_dir)  # 폴더 통째로 삭제
        print(f"[CLEANUP] '{screenshots_dir}' 폴더 삭제 완료")
