"""
주문 확인 관련 Step Definitions
주문 완료 / 내역 확인
"""
from pages.order_page import OrderPage
from pytest_bdd import given, when, then, parsers
import logging
from utils.mobile_web_adapter import expect
# 프론트 실패 처리 헬퍼 함수 import
from utils.frontend_helpers import record_frontend_failure

logger = logging.getLogger(__name__)


@when(parsers.parse('장바구니 번호 "{cart_num}" 인 주문완료 페이지에 접속했음'))
def goes_to_order_complete_page(browser_session, cart_num, bdd_context):
    """
    장바구니 번호 "{cart_num}" 인 주문완료 페이지에 접속했음
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        cart_num: 장바구니 번호
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    
    try:
        order_page = OrderPage(browser_session.page)
        # 주문완료 페이지로 이동
        order_page.go_to_order_complete_page(cart_num) 
        order_page.close_popup()
        logger.info(f"주문완료 페이지 이동 완료: {cart_num}")
    except Exception as e:
        logger.error(f"주문완료 페이지 이동 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"주문완료 페이지 이동 실패: {e}", "장바구니 번호 '{cart_num}' 인 주문완료 페이지에 접속했음")

@then("주문완료 페이지가 표시된다")
def order_complete_page_is_displayed(browser_session, bdd_context):
    """
    주문완료 페이지가 표시되는지 확인
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        order_page = OrderPage(browser_session.page)
        assert order_page.is_order_complete_page_displayed(), "주문완료 페이지가 표시되지 않았습니다"
        logger.info("주문완료 페이지 표시 확인")
    except Exception as e:
        logger.error(f"주문완료 페이지 표시 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"주문완료 페이지 표시 확인 실패: {e}", "주문완료 페이지가 표시된다")

@given(parsers.parse('주문완료 페이지에 "{module_title}" 모듈이 있다'))
def module_exists_in_order_complete_page(browser_session, module_title, bdd_context):
    """
    주문완료 페이지에 특정 모듈이 존재하는지 확인하고 보장 (Given)
    모듈이 없으면 현재 시나리오만 skip
    모듈이 있지만 보이지 않으면 실패 플래그만 설정하고 다음으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        order_page = OrderPage(browser_session.page)
        
        # 모듈 찾기
        module_spmc = order_page.get_spmc_by_module_title(module_title)
        module = order_page.get_module_by_spmc(module_spmc)
        order_page.scroll_module_into_view(module)
        
        # 모듈이 존재하는지 확인 (count == 0이면 모듈이 없음)
        module_count = module.count()
        if module_count == 0:
            # 모듈이 없으면 skip 플래그 설정 (시나리오는 계속 진행)
            skip_reason = f"'{module_title}' 모듈이 주문완료 페이지에 없습니다."
            logger.warning(skip_reason)
            if hasattr(bdd_context, '__setitem__'):
                bdd_context['skip_reason'] = skip_reason
            elif hasattr(bdd_context, 'store'):
                bdd_context.store['skip_reason'] = skip_reason
            # module_title은 저장 (다음 스텝에서 사용 가능하도록)
            bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행하되 skip 상태로 기록됨)
        
        # 모듈이 있으면 visibility 확인 (실패 시 플래그만 설정)
        try:
            expect(module.first).to_be_attached()
        except AssertionError as e:
            logger.error(f"모듈 존재 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"모듈 존재 확인 실패: {str(e)}", "주문완료 페이지에 모듈이 있다")
            # module_title은 저장 (다음 스텝에서 사용 가능하도록)
            bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
        
        # bdd_context에 module_title 저장 (다음 step에서 사용)
        bdd_context.store['module_title'] = module_title
        
        logger.info(f"{module_title} 모듈 존재 확인 완료")
    except Exception as e:
        logger.error(f"모듈 확인 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "주문완료 페이지에 모듈이 있다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title

@when(parsers.parse('사용자가 "{module_title}" 모듈 내 상품을 확인하고 옵션선택을 클릭한다'))
def user_confirms_and_clicks_product_in_module(browser_session, module_title, bdd_context):
    """
    주문완료 페이지에 특정 모듈 내 옵션선택 버튼 클릭 (비즈니스 로직)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        order_page = OrderPage(browser_session.page)
        
        # 모듈 찾기
        module_spmc = order_page.get_spmc_by_module_title(module_title)
        module = order_page.get_module_by_spmc(module_spmc)
        order_page.scroll_module_into_view(module)
        
        # 모듈별 광고상품 여부 확인
        ad_check = order_page.check_ad_item_in_order_complete_module(module_title)
        
        # 옵션선택 버튼 찾기 및 클릭
        option_select_button = order_page.find_option_select_button_in_module(module)
        goodscode = order_page.get_goodscode_in_product(option_select_button)
        product = order_page.get_product_by_code(goodscode)
        option_select_button.click()
        
        # 광고상품 여부 결정 (모듈 설정이 "F"면 상품 태그 확인, 아니면 모듈 설정 사용)
        if ad_check == "F":
            is_ad = order_page.check_ad_tag_in_order_complete_product(product)
        else:
            is_ad = ad_check
        
        # bdd context에 저장 (module_title, goodscode, is_ad 등)
        bdd_context.store['module_title'] = module_title
        bdd_context.store['goodscode'] = goodscode
        bdd_context.store['is_ad'] = is_ad
        
        logger.info(f"{module_title} 모듈 내 옵션선택 버튼 클릭 완료: goodscode={goodscode}")
    except Exception as e:
        logger.error(f"{module_title} 모듈 내 옵션선택 버튼 클릭 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"{module_title} 모듈 내 옵션선택 버튼 클릭 실패: {e}", "사용자가 모듈 내 상품을 확인하고 옵션선택을 클릭한다")
        # goodscode는 저장 (일부 정보라도 보존)
        if 'goodscode' in locals():
            bdd_context.store['goodscode'] = goodscode
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
        

@when(parsers.parse('사용자가 "{module_title}" 모듈 내 상품을 확인하고 상품을 클릭한다'))
def user_confirms_and_clicks_product_in_module_click(browser_session, module_title, bdd_context):
    """
    주문완료 페이지에 특정 모듈 내 상품을 확인하고 상품을 클릭한다 (비즈니스 로직)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        order_page = OrderPage(browser_session.page)
        
        # 모듈 찾기
        module_spmc = order_page.get_spmc_by_module_title(module_title)
        module = order_page.get_module_by_spmc(module_spmc)
        order_page.scroll_module_into_view(module)
        
        # 모듈별 광고상품 여부 확인
        ad_check = order_page.check_ad_item_in_order_complete_module(module_title)
        
        # ATC 버튼 찾기 및 클릭
        atc_button = order_page.get_atc_button_in_order_complete_module(module)
        goodscode = order_page.get_goodscode_in_product(atc_button)
        product = order_page.get_product_by_code(goodscode)
        atc_button.tap()
        logger.info(f"{module_title} 모듈 내 상품 확인 및 담기 완료: goodscode={goodscode}")
        
        # 광고상품 여부 결정 (모듈 설정이 "F"면 상품 태그 확인, 아니면 모듈 설정 사용)
        if ad_check == "F":
            is_ad = order_page.check_ad_tag_in_order_complete_product(product)
        else:
            is_ad = ad_check
        
        # 상품 클릭
        try:
            product.tap()
            
            # bdd context에 저장 (module_title, goodscode, is_ad 등)
            bdd_context.store['module_title'] = module_title
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['is_ad'] = is_ad
            
            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: goodscode={goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 상품을 클릭한다")
            # goodscode는 저장 (일부 정보라도 보존)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 상품을 클릭한다")
        # goodscode는 저장 (일부 정보라도 보존)
        if 'goodscode' in locals():
            bdd_context.store['goodscode'] = goodscode
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
