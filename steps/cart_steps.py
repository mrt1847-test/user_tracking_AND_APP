"""
BDD Step Definitions for Cart
"""
import logging
from pytest_bdd import given, when, then, parsers
from utils.mobile_web_adapter import expect
from pages.cart_page import CartPage
import time

# 프론트 실패 처리 헬퍼 함수 import
from utils.frontend_helpers import record_frontend_failure

logger = logging.getLogger(__name__)


# Cart 관련 step definitions는 여기에 추가

@given("장바구니 비우기")
def clear_cart(browser_session, bdd_context):
    """
    장바구니를 비운 상태로 만든다 (Given)
    장바구니 페이지로 이동한 뒤, 전체 선택 후 삭제하여 이전 시나리오의 상품이 남지 않도록 한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.go_to_cart_page()
        cart_page.wait_for_cart_page_load()
        cart_page.select_all_and_delete()
    except Exception as e:
        logger.error("장바구니 비우기 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 비우기 실패: {e}", "장바구니 비우기")

@when(parsers.parse('사용자가 "{goodscode}" 상품을 장바구니에 추가한다'))
def add_product_to_cart(browser_session, goodscode, bdd_context):
    """
    사용자가 상품을 장바구니에 추가한다 (When)
    상품 페이지로 이동한 뒤, 구매하기 버튼 클릭 및 장바구니로 이동한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        goodscode: 상품 번호
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.go_to_product_page(goodscode)
        cart_page.click_buy_now_button()
        try:
            cart_page.select_group_product(2)
        except:
            logger.debug("그룹상품 선택 실패: %s")

        cart_page.click_cart_now_button()
        cart_page.click_go_to_cart_page()
        logger.info("장바구니 추가 완료: %s", goodscode)
    except Exception as e:
        logger.error("장바구니 추가 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 추가 실패: {e}", '사용자가 "{goodscode}" 상품을 장바구니에 추가한다')


@when("사용자가 장바구니 페이지로 이동한다")
def add_product_to_cart(browser_session, bdd_context):
    """
    상단 장바구니 버튼 클릭
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.close_popup()
        cart_page.click_go_to_cart_page()
        logger.info("장바구니 버튼 클릭 완료")
    except Exception as e:
        logger.error("장바구니 추가 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 추가 실패: {e}", '사용자가 "{goodscode}" 상품을 장바구니에 추가한다')



@then("장바구니 페이지가 표시된다")
def cart_page_is_displayed(browser_session, bdd_context):
    """
    장바구니 페이지가 표시되었는지 확인한다 (Then)
    h3.title '장바구니' 요소가 보일 때까지 대기한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.wait_for_cart_page_load()
        logger.info("장바구니 페이지 표시 확인됨")
    except Exception as e:
        logger.error("장바구니 페이지 표시 확인 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 페이지 표시 확인 실패: {e}", "장바구니 페이지가 표시된다")

@given(parsers.parse('장바구니 페이지에 "{module_title}" 모듈이 있다'))
def cart_page_has_module(browser_session, module_title, bdd_context):
    """
    장바구니 페이지에 특정 모듈이 존재하는지 확인하고 보장 (Given)
    모듈이 없으면 skip 플래그 설정 후 다음으로 진행
    모듈이 있지만 보이지 않으면 실패 플래그만 설정하고 다음으로 진행

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.wait_for_cart_page_load()
        # 모듈 찾기
        module = cart_page.check_module_in_cart(module_title)
        # 모듈이 존재하는지 확인 (count == 0이면 모듈이 없음)
        module_count = module.count()
        logger.info(f"모듈 존재 확인: {module_count}")
        # 모듈이 있으면 visibility 확인 (실패 시 플래그만 설정)
        try:
            expect(module.first).to_be_attached()
        except AssertionError as e:
            logger.error(f"모듈 존재 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"모듈 존재 확인 실패: {str(e)}", "검색 결과 페이지에 모듈이 있다")
            # module_title은 저장 (다음 스텝에서 사용 가능하도록)
            bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
        
        # bdd_context에 module_title 저장 (다음 step에서 사용)
        bdd_context.store['module_title'] = module_title
        
        logger.info(f"{module_title} 모듈 존재 확인 완료")
    except Exception as e:
        logger.error("장바구니 페이지에 모듈 확인 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 페이지에 모듈 확인 실패: {e}", "장바구니 페이지에 모듈이 있다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title

@when(parsers.parse('사용자가 "{module_title}" 장바구니 모듈 내 상품을 확인하고 클릭한다'))
def clicks_product_in_cart_module(browser_session, module_title, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (When)
    모듈로 스크롤·상품 찾기·노출 검증·장바구니 담기(가능 시)·상품 클릭(새 탭)을 수행한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        
        # 모듈로 이동
        module = cart_page.check_module_in_cart(module_title)
        cart_page.scroll_module_into_view(module)
        ad_check = cart_page.check_ad_item_in_module(module_title)
        
        # 모듈 내 상품 찾기
        parent = cart_page.get_module_parent(module, 2)
        product = cart_page.get_product_in_module(parent)
        cart_page.scroll_product_into_view(product)
        
        # 상품 코드 가져오기
        goodscode = cart_page.get_product_code(product)

        if ad_check == "F":
            is_ad = cart_page.check_ad_tag_in_product(product)
        else:
            is_ad =ad_check
        
        # 상품 클릭
        try:
            cart_page.click_product_and_wait_pdp_pv(product)
            
            # bdd context에 저장 (module_title, goodscode, product_url 등)
            bdd_context.store['module_title'] = module_title
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['is_ad'] = is_ad

            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode는 저장 (일부 정보라도 보존)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title

@given("이전페이지로 이동해서 장바구니 페이지로 이동")
def goes_back_to_previous_page(browser_session, bdd_context):
    """
    이전페이지로 이동한다 (Given)
    이전 페이지로 이동한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)

    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        cart_page = CartPage(browser_session.page)
        cart_page.go_back()
        cart_page.wait_for_cart_page_load()
    except Exception as e:
        logger.error("이전페이지로 이동 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"이전페이지로 이동 실패: {e}", "이전페이지로 이동한다")

@when("모듈 내 장바구니 버튼 클릭")
def clicks_cart_button_in_module(browser_session, bdd_context):
    """
    모듈 내 장바구니 버튼 클릭 (When)
    모듈 내 장바구니 버튼 클릭한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)
    """
    try:
        cart_page = CartPage(browser_session.page)
        goodscode = bdd_context.store['goodscode']
        cart_page.click_cart_button_in_module(goodscode)
    except Exception as e:
        logger.error("모듈 내 장바구니 버튼 클릭 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"모듈 내 장바구니 버튼 클릭 실패: {e}", "모듈 내 장바구니 버튼 클릭")

@then("장바구니 담기 완료되었다")
def cart_added_successfully(browser_session, bdd_context):
    """
    장바구니 담기 완료되었는지 확인한다 (Then)
    장바구니 담기 완료되었는지 확인한다.
    실패 시 record_frontend_failure로 기록하고 다음 스텝으로 진행 (soft assertion)
    """
    try:
        cart_page = CartPage(browser_session.page)
        goodscode = bdd_context.store['goodscode']
        cart_page.check_cart_added(goodscode)
    except Exception as e:
        logger.error("장바구니 담기 완료 확인 실패: %s", e, exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"장바구니 담기 완료 확인 실패: {e}", "장바구니 담기 완료되었다")
