"""
상품 관련 Step Definitions
상품 선택 / 상세
"""
from pytest_bdd import given, when, then, parsers
from utils.mobile_web_adapter import expect
from pages.product_page import ProductPage
from utils.urls import product_url
import logging
import time

# 프론트 실패 처리 헬퍼 함수 import
from utils.frontend_helpers import record_frontend_failure


logger = logging.getLogger(__name__)

@given(parsers.parse('상품 "{goodscode}"의 상세페이지로 접속했음'))
def go_to_product_page(browser_session, goodscode, bdd_context):
    """특정 상품번호의 상품 상세페이지로 접속
    실패 시에도 다음 스텝으로 진행"""
    try:
        product_page = ProductPage(browser_session.page)
        # browser_session.page.goto(f"https://item.gmarket.co.kr/Item?goodscode={goodscode}")
        product_page.go_to_product_page(goodscode)
        logger.info("상품 페이지로 이동")
        product_page.close_popup()
        logger.info("팝업 닫기")
    except Exception as e:
        logger.error(f"페이지 이동 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"페이지 이동 실패: {str(e)}", "상품 상품번호의 상세페이지로 접속했음")
     
@then("상품 상세 페이지가 표시된다")
def product_detail_page_is_displayed(browser_session, bdd_context):
    """상품 상세 페이지가 표시되는지 확인
    실패 시에도 다음 스텝으로 진행"""
    try:
        product_page = ProductPage(browser_session.page)
        product_page.wait_for_page_load()
        logger.info("상품 상세 페이지 표시 확인")
    except Exception as e:
        logger.error(f"상품 상세 페이지 표시 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"상품 상세 페이지 표시 확인 실패: {str(e)}", "상품 상세 페이지가 표시된다")


@given("상품 상세 페이지가 표시된다")
def product_detail_page_is_displayed_given(browser_session, bdd_context):
    """
    상품 상세 페이지 상태 보장 (확인 + 필요시 생성)
    
    bdd_context.store['goodscode']에 저장된 상품번호를 기준으로
    현재 URL에 goodscode가 없으면 상품 상세 페이지 URL로 이동
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    goodscode = bdd_context.store.get('goodscode')
    if not goodscode:
        logger.warning("bdd_context.store에 goodscode가 없습니다")
        return
    
    current_url = browser_session.page.url
    if goodscode in current_url:
        logger.info(f"현재 URL에 goodscode({goodscode})가 이미 포함되어 있음")
        return
    
    product_url_value = product_url(goodscode)
    product_page = ProductPage(browser_session.page)
    product_page.goto(product_url_value)
    logger.info(f"상품 상세 페이지로 이동: {product_url_value}")
    
    # 이동 후 확인
    assert product_page.is_product_detail_displayed(), "상품 상세 페이지 생성 실패"
    logger.info("상품 상세 페이지 상태 보장 완료")

@then('상품 페이지로 이동되었다')
def product_page_is_opened(browser_session, bdd_context):
    """
    상품 페이지 이동 확인 (검증)
    PDP PV 로그 수집 관련 로그가 뜰 때까지 대기 (tracker 있으면 수집 확인, 없으면 load 대기)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)
        
        # bdd context에서 값 가져오기 (store 또는 딕셔너리 방식 모두 지원)
        goodscode = bdd_context.store.get('goodscode') or bdd_context.get('goodscode')
        stored_url = bdd_context.store.get('product_url')
        
        if not goodscode:
            # goodscode가 없으면 이전 스텝에서 실패했을 가능성
            logger.warning("goodscode가 설정되지 않았습니다. 이전 스텝에서 실패했을 수 있습니다.")
            bdd_context['frontend_action_failed'] = True
            bdd_context['frontend_error_message'] = "goodscode가 설정되지 않았습니다."
            return

        goodscode_str = str(goodscode).strip()

        if stored_url:
            url = stored_url
        else:
            # product_url이 없으면 현재 페이지에서 URL 전환 대기 후 수집 (타이밍 이슈 방지)
            try:
                browser_session.page.wait_for_url(f"*{goodscode_str}*", timeout=3000)
                logger.debug("상품 페이지 URL 전환 대기 완료")
            except Exception as e:
                logger.warning(f"URL 전환 대기 실패: {e}")
            url = browser_session.page.url

        # 검증 (실패 시 예외 발생)
        try:
            product_page.verify_product_code_in_url(url or "", goodscode_str)
        except AssertionError as e:
            logger.error(f"상품 페이지 이동 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 페이지 이동 확인 실패: {str(e)}", "상품 페이지로 이동되었다")
            # 계속 진행 (PDP PV 로그 수집은 시도)
        
        # 🔥 PDP PV 로그 수집 관련 로그가 뜰 때까지 대기 (tracker 있으면 수집 확인, 없으면 load 대기)
        tracker = bdd_context.get("tracker") or bdd_context.store.get("tracker")

        try:
            browser_session.page.wait_for_load_state("networkidle", timeout=3000)
            logger.debug("networkidle 상태 대기 완료 (tracker 없음, PDP PV 대체 대기)")
        except Exception as e:
            logger.warning(f"networkidle 대기 실패, load 상태로 대기: {e}")
            try:
                browser_session.page.wait_for_load_state("load", timeout=3000)
                logger.debug("load 상태 대기 완료")
            except Exception as e2:
                logger.warning(f"load 상태 대기도 실패: {e2}")
        time.sleep(3)
        logger.info(f"상품 페이지 이동 확인 완료: {goodscode} (PDP PV 로그 수집 대기 완료)")
        
    except Exception as e:
        logger.error(f"상품 페이지 이동 확인 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "상품 페이지로 이동되었다")

@then(parsers.parse('레이어 "{module_title}"가 출력되었다'))
def product_page_is_opened(browser_session, module_title, bdd_context):
    """
    레이어 출력 확인 (검증)
    PDP PV 로그 수집 관련 로그가 뜰 때까지 대기 (tracker 있으면 수집 확인, 없으면 load 대기)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)
        
        module = product_page.get_module_by_title(module_title)
        layer = product_page.get_module_parent(module, 1)
        # 검증 (실패 시 예외 발생)
        try:
            expect(layer).to_be_visible()
            logger.info(f"레이어 출력 확인 완료: {module_title}")
        except AssertionError as e:
            logger.error(f"레이어 출력 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"레이어 출력 확인 실패: {str(e)}", "레이어가 출력되었다")
            # 계속 진행 (PDP PV 로그 수집은 시도)
                
    except Exception as e:
        logger.error(f"레이어 출력 확인 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "레이어가 출력되었다")
        

@when("사용자가 구매하기 버튼을 클릭한다")
def user_clicks_buy_now_button(browser_session):
    """
    사용자가 구매하기 버튼을 클릭한다
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    product_page = ProductPage(browser_session.page)
    try:
        product_page.select_group_product(1)
    except:
        logger.debug(f"그룹상품 선택 실패")
        pass
    product_page.click_buy_now_button()
    logger.info("구매하기 클릭 완료")


@when(parsers.parse('사용자가 PDP에서 "{module_title}" 모듈 내 상품을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_pdp_module(browser_session, module_title, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)

        # 모듈로 이동
        module = product_page.get_module_by_title(module_title)
        product_page.scroll_module_into_view(module)
        time.sleep(2)
        ad_check = product_page.check_ad_item_in_module(module_title)
        
  
        # 모듈 내 상품 찾기
        if module_title == "이 판매자의 인기상품이에요":
            product = product_page.get_product_in_module(module)
        elif module_title == "연관상품":
            parent = product_page.get_module_parent(module, 3)
        else:
            parent = product_page.get_module_parent(module, 2)

        #상품으로 이동
        if module_title == "연관상품 상세보기":
            product = product_page.get_product_in_related_module(parent)
        elif module_title == "BuyBox":
            product = product_page.get_product_in_cheaper_module(module)
        elif module_title == "이 판매자의 인기상품이에요":
             pass # product는 위에서 module로 이미 설정됨
        else:
            product = product_page.get_product_in_module(parent)
        product_page.scroll_product_into_view(product)
        time.sleep(2)

        # 상품 노출 확인 (실패 시 예외 발생)
        try:
            expect(product.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"상품 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 노출 확인 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
    
        # 상품 코드 가져오기
        goodscode = product_page.get_product_code_in_json(product)

        # 모듈별 광고상품 여부 저장장
        if ad_check == "F":
            is_ad = product_page.check_ad_tag_in_product(product)
        else:
            is_ad = ad_check

        # 상품 클릭
        try:
                        
            if "연관상품" in module_title:
                product_page.click_product(product)
            elif "이마트몰" in module_title or module_title == "이 브랜드의 인기상품" or module_title == "점포 행사 상품이에요":
                product_page.click_cart_button(product)
                time.sleep(2)
                product_page.click_product(product)
            else:
                with browser_session.page.expect_navigation(wait_until="networkidle"):
                    product_page.click_product(product)
                
            time.sleep(2)
            product_page.close_popup()
            logger.info("팝업 닫기")
            
            # bdd context에 저장 (module_title, goodscode, product_url)
            bdd_context.store['product_url'] = browser_session.page.url         
            bdd_context.store['module_title'] = module_title
            bdd_context.store['is_ad'] = is_ad
            bdd_context.store['goodscode'] = goodscode

            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode, module_title, is_ad 저장 (검증에서 <is_ad> 치환에 필요)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            if 'is_ad' in locals():
                bdd_context.store['is_ad'] = is_ad
                
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title

@when(parsers.parse('사용자가 PDP에서 "{location_title}"을 클릭한다'))
def user_confirms_and_clicks_product_in_pdp_related_detail_module(browser_session, location_title, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)

        # 모듈로 이동
        module = product_page.get_module_by_title(location_title)
        product_page.scroll_module_into_view(module)
        time.sleep(2)
        # 모듈 내 상품 찾기

        if location_title == "연관상품":
            parent = product_page.get_module_parent(module, 3)
            product = product_page.get_product_in_module(parent)
        else:
            product = module

        product_page.scroll_product_into_view(product)

        # 상품 노출 확인 (실패 시 예외 발생)
        try:
            expect(product.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"상품 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 노출 확인 실패: {str(e)}", "사용자가 모듈 내 상품을 클릭한다")

        try:
            # 상품 클릭
            product_page.click_product(product)
            logger.info(f"{location_title} 모듈 내 상품 클릭 완료")

            product_page.close_popup()
            logger.info("팝업 닫기")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 클릭한다")        

    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 클릭한다")

@when(parsers.parse('사용자가 PDP에서 "{button_title}" 버튼을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_pdp_related_module(browser_session, button_title, bdd_context):
    """
    PDP 내 버튼 노출 확인하고 클릭 (Atomic POM 조합)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        button_title: 버튼 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)
        
        module = product_page.get_module_by_title(button_title)

        product_page.select_button()
        # 버튼으로 이동
        button = product_page.get_module_parent(module, 1)
        product_page.scroll_module_into_view(button)
        time.sleep(2)    
        # 버튼 노출 확인 (실패 시 예외 발생)
        try:
            expect(button.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"버튼 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"버튼 노출 확인 실패: {str(e)}", "사용자가 모듈 내 버튼을 확인하고 클릭한다")
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = button_title
            return  # 여기서 종료 (다음 스텝으로 진행)
    
        # 상품 코드 가져오기
        if "연관상품" in button_title:
            time.sleep(2)
            detail_page = product_page.get_product_code_in_detail_page()
            goodscode = product_page.get_product_code_in_json(detail_page)
        else:
            goodscode = product_page.get_product_code_in_json(button)

        try:
            # bdd context에 저장 (product_url, module_title, goodscode)
            bdd_context.store['product_url'] = browser_session.page.url        
            bdd_context.store['module_title'] = button_title
            bdd_context.store['goodscode'] = goodscode

            # 버튼 클릭
            product_page.click_product(button)
            time.sleep(2)
            logger.info(f"{button_title} 버튼 확인 및 클릭 완료: {goodscode}")

            product_page.close_popup()
            logger.info("팝업 닫기")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode는 저장 (일부 정보라도 보존)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = button_title

    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = button_title

@then(parsers.parse('버튼 "{module_title}"가 클릭되었다'))
def other_page_is_opened(browser_session, bdd_context, module_title):
    """
    상품 페이지 이동 확인 (검증)
    PDP PV 로그 수집 관련 로그가 뜰 때까지 대기 (tracker 있으면 수집 확인, 없으면 load 대기)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)
        
        if "장바구니" in module_title:
            product_page.verify_display_layer(module_title)    
        else:
            product_page.verify_keyword_in_url(module_title)
            try:
                browser_session.page.wait_for_load_state("networkidle", timeout=10000)
                logger.debug("networkidle 상태 대기 완료")
            except Exception as e:
                logger.warning(f"networkidle 대기 실패, load 상태로 대기: {e}")
                browser_session.page.wait_for_load_state("load", timeout=30000)    
        time.sleep(1)
        logger.info(f"페이지 이동 확인 완료: {module_title}")
        
    except Exception as e:
        logger.error(f"페이지 이동 확인 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "상품 페이지로 이동되었다")

@when("사용자가 상품 옵션을 입력한다")
def user_inputs_product_option(browser_session):
    """
    사용자가 상품 옵션(수량 등) 입력
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
    """
    product_page = ProductPage(browser_session.page)
    try:
        # 옵션 영역으로 스크롤
        option = product_page.option_area_locator(0)
        product_page.scroll_module_into_view(option)
        time.sleep(1)
        # 선택형 옵션 입력
        for i in range(10):
            if product_page.is_in_select_option(option, i):
                product_page.select_option_box(option, i)
            else:    
                break
        # 선택형 옵션 입력 완료 후 텍스트형 옵션 입력
        for j in range(10):
            if product_page.is_in_text_option(option, j):
                product_page.fill_in_text_option(option, j, "테스트")
            elif j != 0:
                product_page.get_by_text_and_click_where("입력한 정보로 선택", 0)
                break
            else:
                break
        time.sleep(1)
        logger.info("상품 옵션 입력 완료")

    except Exception as e:
        logger.error(f"상품 옵션 입력 실패: {e}", exc_info=True)
        raise e


@when(parsers.parse('사용자가 BuyBox에서 "{module_title}" 모듈 내 상품을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_BuyBox_module(browser_session, module_title, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        product_page = ProductPage(browser_session.page)

        # 모듈로 이동
        module = product_page.get_module_by_title(module_title)
        ad_check = product_page.check_ad_item_in_module(module_title)
        product_page.scroll_module_into_view(module)
        time.sleep(2)     
  
        # 모듈 내 상품 찾기
        parent = product_page.get_module_parent(module, 3)

        #상품으로 이동       
        product = product_page.get_product_in_module(parent)
        product_page.scroll_product_into_view(product)
        time.sleep(2)

        # 상품 노출 확인 (실패 시 예외 발생)
        try:
            expect(product.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"상품 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 노출 확인 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
    
        # 상품 코드 가져오기
        goodscode = product_page.get_product_code(product)

                # 모듈별 광고상품 여부 저장장
        if ad_check == "F":
            is_ad = product_page.check_ad_tag_in_product(product)
        else:
            is_ad = ad_check

        # 상품 클릭
        try:
                        
            if "연관상품" in module_title:
                product_page.click_product(product)
            else:
                with browser_session.page.expect_navigation(wait_until="networkidle"):
                    product_page.click_product(product)
                
            time.sleep(2)
            product_page.close_popup()
            logger.info("팝업 닫기")
            
            # bdd context에 저장 (module_title, goodscode, product_url)
            bdd_context.store['product_url'] = browser_session.page.url         
            bdd_context.store['module_title'] = module_title
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['is_ad'] = is_ad

            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode, module_title, is_ad 저장 (검증에서 <is_ad> 치환에 필요)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            if 'is_ad' in locals():
                bdd_context.store['is_ad'] = is_ad

    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title



@when(parsers.parse('사용자가 PDP에서 "{module_title}" 모듈 내 {n}번째 상품을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_pdp_module(browser_session, module_title, n, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        n: 번째 상품 (Examples 컬럼 n, 저장/검증 시 nth로 사용)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        nth_idx = int(n) if n is not None and str(n).strip() else 0
        product_page = ProductPage(browser_session.page)

        # 모듈로 이동
        module = product_page.get_module_by_title(module_title)
        product_page.scroll_module_into_view(module)
        time.sleep(2)
        ad_check = product_page.check_ad_item_in_module(module_title)
        

        # 모듈 내 상품 찾기
        if module_title == "이 판매자의 인기상품이에요":
            product = product_page.get_product_in_module(module)
        elif module_title == "연관상품":
            parent = product_page.get_module_parent(module, 3)
        else:
            parent = product_page.get_module_parent(module, 2)

        #상품으로 이동
        if module_title == "연관상품 상세보기":
            product = product_page.get_product_in_related_module(parent)
        elif module_title == "BuyBox":
            product = product_page.get_product_in_cheaper_module(module)
        elif module_title == "이 판매자의 인기상품이에요":
             pass # product는 위에서 module로 이미 설정됨
        else:
            product = product_page.get_product_in_module(parent, nth_idx)
        product_page.scroll_product_into_view(product)
        time.sleep(2)

        # 상품 노출 확인 (실패 시 예외 발생)
        try:
            expect(product.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"상품 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 노출 확인 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
    
        # 상품 코드 가져오기
        goodscode = product_page.get_product_code_in_json(product)

        # 모듈별 광고상품 여부 저장장
        if ad_check == "F":
            is_ad = product_page.check_ad_tag_in_product(product)
        else:
            is_ad = ad_check

        # 상품 클릭
        try:
                        
            if "연관상품" in module_title:
                product_page.click_product(product)
            elif "이마트몰" in module_title or module_title == "이 브랜드의 인기상품" or module_title == "점포 행사 상품이에요":
                product_page.click_cart_button(product)
                time.sleep(2)
                product_page.click_product(product)
            else:
                with browser_session.page.expect_navigation(wait_until="networkidle"):
                    product_page.click_product(product)
                
            time.sleep(2)
            product_page.close_popup()
            logger.info("팝업 닫기")
            
            # bdd context에 저장 (module_title, goodscode, product_url, nth)
            bdd_context.store['product_url'] = browser_session.page.url         
            bdd_context.store['module_title'] = module_title
            bdd_context.store['is_ad'] = is_ad
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['nth'] = n

            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode는 저장 (일부 정보라도 보존)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            bdd_context.store['nth'] = n
            if 'is_ad' in locals():
                bdd_context.store['is_ad'] = is_ad
                
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
        bdd_context.store['nth'] = n
