"""
홈페이지 관련 Step Definitions
진입 / 초기 상태
"""
import os
from pathlib import Path
from typing import Optional
from pytest_bdd import given, when, then, parsers
from pages.base_page import BasePage
from pages.home_page import HomePage
from utils.validation_helpers import (
    detect_area_from_feature_path,
    load_module_config,
    _find_spm_recursive,
)
import logging
import pytest
import time
# 프론트 실패 처리 헬퍼 함수 import
from utils.frontend_helpers import record_frontend_failure

logger = logging.getLogger(__name__)

# 홈 섹션 탭 전환 후 Module Exposure 수신 대기 (페이지 로딩 대기 스텝)
_MODULE_EXPOSURE_WAIT_TIMEOUT_S = 15.0
_MODULE_EXPOSURE_POLL_MS = 250

# 홈 모듈 상품 클릭 전 Product Exposure 수신 대기 (goodscode만 매칭, SPM 미사용)
_PRODUCT_EXPOSURE_WAIT_TIMEOUT_S = 15.0
_PRODUCT_EXPOSURE_POLL_MS = 250

# General 요소 클릭 전 General Exposure 적재 증가 대기
_GENERAL_EXPOSURE_WAIT_TIMEOUT_S = 15.0
_GENERAL_EXPOSURE_POLL_MS = 250


@given("사용자가 G마켓 홈페이지에 접속한다")
def user_navigates_to_homepage(browser_session):
    """
    사용자가 G마켓 홈페이지에 접속
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    home_page = HomePage(browser_session.page)
    home_page.navigate()
    logger.info("홈페이지 접속 완료")


@given("G마켓 홈 페이지에 접속했음")
def given_gmarket_home_page_accessed(browser_session, request, bdd_context):
    """G마켓 홈 페이지에 접속 및 영역 추론"""
    # Feature 파일 경로 또는 테스트 파일 경로에서 영역 추론
    try:
        area = None
        
        # 방법 1: feature fixture에서 feature 파일 경로 가져오기
        if hasattr(request, 'getfixturevalue'):
            try:
                feature = request.getfixturevalue('feature')
                if feature and hasattr(feature, 'filename'):
                    feature_path = str(feature.filename)
                    area = detect_area_from_feature_path(feature_path)
                    if area:
                        bdd_context.store['area'] = area
                        logger.info(f"영역 자동 감지: {area} (Feature: {feature_path})")
            except (pytest.FixtureLookupError, AttributeError):
                pass
        
        # 방법 2: request.node에서 테스트 파일 경로 가져오기 (test_*.py)
        if not area and hasattr(request, 'node'):
            try:
                # request.node.path 또는 request.node.fspath 사용
                test_file_path = None
                if hasattr(request.node, 'path'):
                    test_file_path = request.node.path
                elif hasattr(request.node, 'fspath'):
                    test_file_path = request.node.fspath
                
                if test_file_path:
                    test_file_path = Path(test_file_path)
                    test_file_name = test_file_path.stem  # 파일명에서 확장자 제거
                    
                    # test_*.py 패턴에서 영역 추론 (예: test_srp.py -> SRP, test_lp.py -> LP)
                    if test_file_name.startswith('test_'):
                        area_name = test_file_name.replace('test_', '').upper()
                        # valid_areas 제한 제거 - 모든 영역명 허용
                        area = area_name
                        bdd_context.store['area'] = area
                        logger.info(f"영역 자동 감지: {area} (Test 파일: {test_file_path})")
            except (AttributeError, Exception) as e:
                logger.debug(f"테스트 파일 경로에서 영역 추론 실패: {e}")
        
        # 방법 3: 기본값 사용
        if not area:
            bdd_context.store['area'] = 'SRP'
            logger.warning("영역 기본값 사용: SRP (feature 파일 및 test 파일 경로에서 추론 실패)")
            
    except Exception as e:
        # 오류 발생 시 기본값 사용
        bdd_context.store['area'] = 'SRP'
        logger.warning(f"영역 추론 실패, 기본값 사용: {e}")
    
    home_page = HomePage(browser_session.page)
    home_page.navigate()
    home_page.close_popup()
    logger.info("G마켓 홈 페이지 접속 완료")


@then("홈페이지가 표시된다")
def homepage_is_displayed(browser_session):
    """
    홈페이지가 올바르게 표시되는지 확인
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    # TODO: 홈페이지 특정 요소 확인 로직 구현
    logger.info("홈페이지 표시 확인")


@given("브라우저가 실행되었다")
def browser_is_launched(browser_session):
    """
    브라우저가 실행된 상태 (자동으로 fixture에서 처리됨)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    logger.info("브라우저 실행 확인")


@then("페이지가 로드되었다")
def page_is_loaded(browser_session):
    """
    페이지가 완전히 로드되었는지 확인
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    browser_session.page.wait_for_load_state("networkidle")
    logger.info("페이지 로드 완료 확인")

@given("최근 본 내역이 존재한다")
def recent_viewed_exists(browser_session, bdd_context):
    """
    RVH 페이지에 최근 본 내역(strong.list-rvh__date)이 노출되는지 확인한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion).

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        home_page = HomePage(browser_session.page)
        if not home_page.is_recently_viewed_displayed():
            raise AssertionError("최근 본 내역이 노출되지 않았습니다.")
        logger.info("최근 본 내역 존재 확인됨")
    except Exception as e:
        logger.error("최근 본 내역 존재 확인 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"최근 본 내역 존재 확인 실패: {e}", "최근 본 내역이 존재한다")


@when("사용자가 RVH 페이지로 이동한다")
def add_product_to_cart(browser_session, bdd_context):
    """
    RVH 페이지로 이동 (BNB RVH 버튼 클릭)
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        home_page = HomePage(browser_session.page)
        home_page.close_popup()
        home_page.click_rvh()
        logger.info("RVH 버튼 클릭 완료")
    except Exception as e:
        logger.error("RVH 버튼 클릭 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"RVH 이동 실패: {e}", '사용자가 RVH 페이지로 이동한다')

@then("RVH으로 이동했다")
def cart_page_is_displayed(browser_session, bdd_context):
    """
    RVH 페이지로 이동했는지 확인한다 (Then)
    RVH 페이지가 로드될 때까지 대기한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        home_page = HomePage(browser_session.page)
        home_page.wait_for_rvh_page_load()
        logger.info("RVH 페이지 표시 확인됨")
    except Exception as e:
        logger.error("RVH 페이지 표시 확인 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"RVH 페이지 표시 확인 실패: {e}", "RVH으로 이동했다")


@when("사용자가 최근본 상품을 확인하고 클릭한다")
def click_recently_viewed_product(browser_session, bdd_context):
    """
    최근본 상품 요소를 가져와 상품번호(goodscode)를 저장한 뒤, 상품번호로 상품을 클릭한다 (When).
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion).

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        home_page = HomePage(browser_session.page)
        product = home_page.get_product_in_module()
        goodscode = home_page.get_product_code(product)
        if not goodscode:
            raise AssertionError("최근본 상품 코드를 가져올 수 없습니다.")
        bdd_context.store["module_title"] = "최근본 상품"
        bdd_context.store["goodscode"] = goodscode
        bdd_context.store['is_ad'] = 'N'
        product_locator = home_page.get_product_by_code(goodscode)
        home_page.scroll_product_into_view(product_locator)
        product_locator.tap(timeout=5000)
        logger.info("최근본 상품 확인 및 클릭 완료: %s", goodscode)
    except Exception as e:
        logger.error("최근본 상품 확인 및 클릭 실패: %s", e, exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            f"최근본 상품 확인 및 클릭 실패: {e}",
            "사용자가 최근본 상품을 확인하고 클릭한다",
        )
        bdd_context.store["module_title"] = "최근본 상품"
        if "goodscode" in locals() and goodscode:
            bdd_context.store["goodscode"] = goodscode

def _home_module_diag_mode() -> str | None:
    """
    ``PLAYWRIGHT_HOME_MODULE_DIAG`` — 모듈 노출 진단 로그.

    - 비움: 끔
    - ``on_error`` / ``fail``: ``find_module_by_spmc`` 예외 시에만
    - ``1`` / ``true`` / ``always`` / ``yes`` / ``y``: 성공·실패 모두(실패 시에도 출력)
    """
    v = (os.environ.get("PLAYWRIGHT_HOME_MODULE_DIAG") or "").strip().lower()
    if not v:
        return None
    if v in ("on_error", "fail", "failure", "error"):
        return "on_error"
    if v in ("1", "true", "yes", "always", "y", "all"):
        return "always"
    return None


@given(parsers.parse('섹션에 "{n:d}"번째 "{module_title}" 모듈이 있다'))
def section_module_exists(browser_session, n, module_title, bdd_context):
    """
    섹션에 n번째 module_title 모듈이 있는지 확인한다.
    (Examples의 n은 1-based — find_module_by_spmc 두 번째 인자는 0-based 인덱스)
    """
    idx0 = max(int(n) - 1, 0)
    try:
        home_page = HomePage(browser_session.page)
        home_page.find_module_by_spmc(module_title, idx0)
        logger.info('섹션에 "%s"번째 "%s" 모듈이 있는지 확인됨', n, module_title)
        if _home_module_diag_mode() == "always":
            home_page.log_module_visibility_diagnostics(module_title, idx0)
    except Exception as e:
        logger.error('섹션에 "%s"번째 "%s" 모듈이 있는지 확인 실패: %s', n, module_title, e, exc_info=True)
        if _home_module_diag_mode() in ("always", "on_error"):
            try:
                HomePage(browser_session.page).log_module_visibility_diagnostics(module_title, idx0)
            except Exception as diag_e:
                logger.warning("모듈 visibility 진단 로그 실패: %s", diag_e, exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            f'섹션에 "{n}"번째 "{module_title}" 모듈이 있는지 확인 실패: {e}',
            '섹션에 "<n>"번째 "<module_title>" 모듈이 있다',
        )


@when(parsers.parse('사용자가 "{section_name}" 섹션으로 이동한다'))
def navigate_to_section(browser_session, section_name, bdd_context):
    """
    사용자가 section_name 섹션으로 이동한다.
    """
    try:
        home_page = HomePage(browser_session.page)
        home_page.close_popup()
        home_page.click_home_section_tab(section_name)
        tracker = bdd_context.get("tracker")
        if tracker:
            bdd_context.store["_module_exposure_count_after_section_click"] = len(
                tracker.get_logs("Module Exposure")
            )
        logger.info('사용자가 "%s" 섹션으로 이동했습니다.', section_name)
    except Exception as e:
        logger.error('사용자가 "%s" 섹션으로 이동 실패: %s', section_name, e, exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            f'사용자가 "{section_name}" 섹션으로 이동 실패: {e}',
            '사용자가 "<section_name>" 섹션으로 이동한다',
        )

@then(parsers.parse('"{section_name}" 섹션으로 이동했다'))
def section_is_navigated(browser_session, section_name, bdd_context):
    """
    "{section_name}" 섹션으로 이동했는지 확인한다.
    """
    try:
        home_page = HomePage(browser_session.page)
        home_page.expect_home_section_tab_active(section_name)
        bdd_context.store["module_title"] = section_name
        logger.info('"%s" 섹션으로 이동했습니다.', section_name)
    except Exception as e:
        logger.error('"%s" 섹션으로 이동 실패: %s', section_name, e, exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            f'"{section_name}" 섹션으로 이동 실패: {e}',
            '"<section_name>" 섹션으로 이동한다',
        )

@then(parsers.parse('페이지 로딩 대기'))
def wait_for_page_load(browser_session, bdd_context):
    """
    섹션 전환 직후 트래킹 등 비동기 요청을 기다린다.

    SPA 탭 전환에서는 ``domcontentloaded``가 이미 만족된 상태라 거의 즉시 통과하므로,
    ``time.sleep``만으로는 Module.Exposure.Event가 늦게 나오는 경우를 못 잡을 수 있다.
    네트워크 트래킹이 켜져 있으면 섹션 탭 클릭 직후 건수를 기준으로 Module Exposure 로그가
    늘어날 때까지 짧게 폴링한다.
    """
    try:
        page = browser_session.page
        base_page = BasePage(page)
        tracker = bdd_context.get("tracker")
        baseline = bdd_context.store.get("_module_exposure_count_after_section_click")
        base_page.wait_for_module_exposure_increase(
            tracker=tracker,
            baseline_count=baseline,
            timeout_s=_MODULE_EXPOSURE_WAIT_TIMEOUT_S,
            poll_ms=_MODULE_EXPOSURE_POLL_MS,
        )
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception as e:
        logger.error('페이지 로딩 대기 실패: %s', e, exc_info=True)


@when(parsers.parse('홈에서 사용자가 "{n:d}"번째 "{module_title}" 모듈 내 {nth:d}번째 상품을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_module_by_spmc(browser_session, n, module_title, nth, bdd_context):
    """
    홈 섹션 모듈 내 상품 노출 확인 후 클릭.
    스텝 문구는 `홈에서`로 시작해 `steps.srp_lp_steps`의
    `사용자가 "{module_title}" 모듈 내 …` 와 겹치지 않게 한다 (같은 문장이면 SRP 쪽이 나중 로드되어 덮어씀).
    모듈은 `data-spm`(SPMC)로 `find_module_by_spmc`에 찾는다.

    실패 시에도 다음 스텝으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        n: 모듈 순번(1-based)
        module_title: 모듈 SPMC (`data-spm` 속성값)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        # 트래킹 스키마 로드 시 모듈명(n).json 매칭용
        bdd_context.store["module_title"] = module_title
        bdd_context.store["module_order"] = int(n)
        bdd_context.store['nth'] = int(nth)
        home_page = HomePage(browser_session.page)

        # 모듈 찾기 (n은 1-based 입력이므로 0-based 인덱스로 변환)
        module = home_page.find_module_by_spmc(module_title, max(int(n) - 1, 0))

        # 모듈 내 상품 찾기
        nth_idx = max(int(nth) - 1, 0)
        products = module.locator('a[data-montelena-goodscode][href*="product"]')
        if products.count() <= nth_idx:
            parent = home_page.get_module_parent(module, 3)
            products = parent.locator('a[data-montelena-goodscode][href*="product"]')

        if products.count() <= nth_idx:
            raise AssertionError(
                f'모듈 "{module_title}"의 {nth}번째 상품을 찾을 수 없습니다 '
                f"(요청 index={nth_idx}, 발견 count={products.count()})"
            )

        product = products.nth(nth_idx)
        home_page.scroll_product_into_view(product)
        product.wait_for(state="visible", timeout=10000)

        # 상품 코드 가져오기
        goodscode = home_page.get_product_code(product)
        if not goodscode:
            raise AssertionError("상품 goodscode를 찾을 수 없습니다.")

        # 상품 클릭 전: 네트워크 트래킹이 있으면 goodscode 기준 Product Exposure 적재 확인
        tracker = bdd_context.get("tracker")
        base_page = BasePage(browser_session.page)
        base_page.wait_for_product_exposure_by_goodscode(
            tracker=tracker,
            goodscode=goodscode,
            timeout_s=_PRODUCT_EXPOSURE_WAIT_TIMEOUT_S,
            poll_ms=_PRODUCT_EXPOSURE_POLL_MS,
        )

        # 홈 영역에서는 광고 여부를 기본값 N으로 저장
        bdd_context.store["goodscode"] = goodscode
        bdd_context.store["is_ad"] = "N"

        # 상품 클릭 (모바일 웹 동작을 위해 tap 우선)
        product.tap(timeout=5000)
        try:
            browser_session.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        bdd_context.store["product_url"] = browser_session.page.url
        logger.info('%s 모듈(%s번째) 내 %s번째 상품 클릭 완료: %s', module_title, n, nth, goodscode)

    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            str(e),
            '홈에서 사용자가 "<n>"번째 "<module_title>" 모듈 내 <nth>번째 상품을 확인하고 클릭한다',
        )
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
        bdd_context.store['nth'] = int(nth)



@when(parsers.parse('홈에서 사용자가 "{n:d}"번째 "{module_title}" 모듈 내 General 요소를 클릭한다'))
def user_clicks_general_element_in_home_module(browser_session, n, module_title, bdd_context):
    """
    홈 섹션 모듈 내 General 링크/버튼 클릭.
    스텝 문구는 `홈에서`로 시작해 `steps.srp_lp_steps`의
    `사용자가 "{module_title}" 모듈 내 …` 와 겹치지 않게 한다.

    네트워크 트래킹이 켜져 있으면 ``module_config``의 ``general_exposure`` SPM(없으면 전체 건수) 기준으로
    스크롤 직전 대비 General Exposure 적재가 늘어날 때까지 짧게 폴링한 뒤 탭한다.

    실패 시에도 다음 스텝으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        n: 모듈 순번(1-based)
        module_title: 모듈 SPMC (`data-spm` 속성값)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        # 트래킹 스키마 로드 시 모듈명(n).json 매칭용
        bdd_context.store["module_title"] = module_title
        bdd_context.store["module_order"] = int(n)
        home_page = HomePage(browser_session.page)
        base_page = BasePage(browser_session.page)
        tracker = bdd_context.get("tracker")

        area = bdd_context.store.get("area") or bdd_context.get("area")
        general_spm = None
        if area and module_title:
            try:
                mc = load_module_config(area=area, module_title=module_title)
                ge = mc.get("general_exposure") if isinstance(mc, dict) else None
                if ge:
                    general_spm = _find_spm_recursive(ge)
            except Exception as ex:
                logger.debug("general_exposure SPM 로드 실패(전체 General 건수로 대기): %s", ex)

        def _general_exposure_baseline() -> Optional[int]:
            if not tracker:
                return None
            if not general_spm:
                return len(tracker.get_logs("General Exposure"))
            if isinstance(general_spm, str):
                return len(tracker.get_general_exposure_logs_by_spm(general_spm))
            if isinstance(general_spm, list):
                return sum(
                    len(tracker.get_general_exposure_logs_by_spm(s))
                    for s in general_spm
                    if isinstance(s, str) and s
                )
            return len(tracker.get_logs("General Exposure"))

        # 모듈 찾기 (n은 1-based 입력이므로 0-based 인덱스로 변환)
        module = home_page.find_module_by_spmc(module_title, max(int(n) - 1, 0))

        baseline_ge = _general_exposure_baseline()
        # 모듈 내 버튼으로 스크롤(노출 트리거) 후 General Exposure 적재 증가 대기
        button = home_page.get_button_by_name(module_title, module)
        base_page.wait_for_general_exposure_increase(
            tracker=tracker,
            baseline_count=baseline_ge,
            spm=general_spm,
            timeout_s=_GENERAL_EXPOSURE_WAIT_TIMEOUT_S,
            poll_ms=_GENERAL_EXPOSURE_POLL_MS,
        )
        button.tap(timeout=5000)
        logger.info('%s 모듈(%s번째) 내 General 요소 클릭 완료', module_title, n)
        try:
            browser_session.page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        bdd_context.store["product_url"] = browser_session.page.url
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            str(e),
            '홈에서 사용자가 "<n>"번째 "<module_title>" 모듈 내 General 요소를 클릭한다',
        )
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title