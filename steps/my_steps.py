"""
BDD Step Definitions for My 페이지 트래킹 테스트
features/my_tracking.feature 전용
"""
import logging
import time
from pytest_bdd import given, when, then, parsers
from utils.mobile_web_adapter import expect
from pages.my_page import MyPage
from pages.home_page import HomePage
from utils.frontend_helpers import record_frontend_failure

logger = logging.getLogger(__name__)


@when("사용자가 My 페이지 주문내역으로 이동한다")
def when_user_goes_to_my_order_history(browser_session, bdd_context):
    """
    My 페이지로 이동 후 주문내역 메뉴 클릭
    실패 시에도 다음 스텝으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        logger.info("My 페이지 주문내역으로 이동 시작")
        my_page = MyPage(browser_session.page)
        home_page = HomePage(browser_session.page)

        my_page.close_popup()

        # 홈에서 My(마이) 페이지로 이동
        home_page.click_my_page()
        time.sleep(1)

        # 주문내역 메뉴 클릭
        my_page.click_order_history()
        time.sleep(1)
        logger.info("My 페이지 주문내역으로 이동 완료")

    except Exception as e:
        logger.error(f"My 페이지 주문내역 이동 실패: {e}", exc_info=True)
        record_frontend_failure(
            browser_session, bdd_context,
            f"My 페이지 주문내역 이동 실패: {str(e)}",
            "사용자가 My 페이지 주문내역으로 이동한다"
        )


@then("주문내역으로 이동했다")
def then_order_history_page_is_displayed(browser_session, bdd_context):
    """
    주문내역 페이지 표시 확인
    실패 시에도 다음 스텝으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        my_page = MyPage(browser_session.page)

        # 주문내역 페이지 표시 여부 확인
        visible = my_page.is_order_history_page_displayed()
        if not visible:
            raise AssertionError("주문내역 페이지가 표시되지 않았습니다.")
        logger.info("주문내역으로 이동 확인 완료")

    except Exception as e:
        logger.error(f"주문내역 페이지 표시 확인 실패: {e}", exc_info=True)
        record_frontend_failure(
            browser_session, bdd_context,
            f"주문내역 페이지 표시 확인 실패: {str(e)}",
            "주문내역으로 이동했다"
        )


@given("주문내역이 존재한다")
def given_order_history_has_items(browser_session, bdd_context):
    """
    주문내역에 상품이 존재하는지 확인 (Given)
    없으면 skip_reason 설정 후 다음 스텝 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        my_page = MyPage(browser_session.page)

        # 주문내역 첫 상품에서 goodscode 추출
        goodscode = my_page.get_goods_code_from_order_history()
        if not goodscode or not str(goodscode).strip():
            # 상품 없으면 skip_reason 설정 후 다음 스텝으로 진행
            skip_reason = "주문내역에 상품이 없습니다."
            logger.warning(skip_reason)
            bdd_context.store["skip_reason"] = skip_reason
            bdd_context.store["module_title"] = "주문내역"
            return

        # bdd context에 module_title, goodscode 저장 (다음 스텝에서 사용)
        bdd_context.store["module_title"] = "주문내역"
        bdd_context.store["goodscode"] = goodscode
        logger.info(f"주문내역 상품 존재 확인: goodscode={goodscode}")

    except Exception as e:
        logger.error(f"주문내역 존재 확인 실패: {e}", exc_info=True)
        record_frontend_failure(
            browser_session, bdd_context,
            f"주문내역 존재 확인 실패: {str(e)}",
            "주문내역이 존재한다"
        )
        # 실패 시에도 module_title은 저장 (다음 스텝에서 사용 가능하도록)
        bdd_context.store["module_title"] = "주문내역"


@when(parsers.parse('사용자가 "{module_title}" 내 상품을 확인하고 클릭한다'))
def when_user_confirms_and_clicks_product_in_order_history(browser_session, module_title, bdd_context):
    """
    주문내역 모듈 내 상품 확인 후 클릭 (Atomic POM 조합)
    goodscode는 bdd_context 또는 페이지에서 가져옴
    실패 시에도 다음 스텝으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀 (예: "주문내역")
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        my_page = MyPage(browser_session.page)

        # 모듈별 광고상품 노출 여부 확인 (Y/N/F)
        ad_check = my_page.check_ad_item_in_order_history_module(module_title)

        # goodscode 가져오기 (bdd_context 우선, 없으면 주문내역 첫 상품에서 추출)
        goodscode = bdd_context.store.get("goodscode") or bdd_context.get("goodscode")
        if not goodscode:
            goodscode = my_page.get_goods_code_from_order_history()
        if not goodscode or not str(goodscode).strip():
            raise ValueError("주문내역에서 상품코드를 가져올 수 없습니다.")

        # 모듈별 광고상품 여부 저장 (F면 상품별 ad 태그 확인)
        if ad_check == "F":
            product = my_page.get_order_history_product_locator(str(goodscode))
            is_ad = my_page.check_ad_tag_in_order_history_product(product)
        else:
            is_ad = ad_check

        # 장바구니 담기 버튼 존재할 경우 클릭 후 얼럿 닫기
        my_page.click_atc_in_order_history_by_goodscode(str(goodscode))
        # 상품 클릭 — 새 탭이 열리면 전환, 같은 탭 이동이면 URL 전환 대기 (SearchPage.click_product_and_wait_new_page와 동일 패턴)
        try:
            new_page = my_page.click_product_in_order_history_and_wait_new_page(str(goodscode))
            browser_session.switch_to(new_page)
            product_url = new_page.url
            logger.debug("주문내역 상품 클릭: 새 탭 열림, 전환 완료")
        except Exception:
            # 같은 탭에서 이동 (클릭은 이미 메서드 내부에서 실행됨, URL 전환만 대기)
            browser_session.page.wait_for_url(f"*{goodscode}*", timeout=15000)
            product_url = browser_session.page.url
            logger.debug("주문내역 상품 클릭: 같은 탭 이동, URL 전환 대기 완료")

        # bdd context에 저장 (module_title, goodscode, product_url, is_ad)
        bdd_context.store["module_title"] = module_title
        bdd_context.store["goodscode"] = goodscode
        bdd_context.store["product_url"] = product_url
        bdd_context.store["is_ad"] = is_ad
        logger.info(f"{module_title} 내 상품 확인 및 클릭 완료: goodscode={goodscode}")

    except Exception as e:
        logger.error(f"주문내역 내 상품 클릭 실패: {e}", exc_info=True)
        record_frontend_failure(
            browser_session, bdd_context,
            f"주문내역 내 상품 클릭 실패: {str(e)}",
            f'사용자가 "{module_title}" 내 상품을 확인하고 클릭한다'
        )
        # goodscode는 저장 (일부 정보라도 보존)
        bdd_context.store["module_title"] = module_title
        if "goodscode" in locals() and goodscode:
            bdd_context.store["goodscode"] = goodscode
