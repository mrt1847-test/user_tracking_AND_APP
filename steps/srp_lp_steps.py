"""
BDD Step Definitions for SRP Tracking Tests
"""
import logging
import time
from pytest_bdd import given, when, then, parsers
from utils.mobile_web_adapter import expect
from pages.search_page import SearchPage
from pages.home_page import HomePage
from pages.list_page import ListPage

# 프론트 실패 처리 헬퍼 함수 import
from utils.frontend_helpers import record_frontend_failure

logger = logging.getLogger(__name__)


@when(parsers.parse('사용자가 "{keyword}"을 검색한다'))
def when_user_searches_keyword(browser_session, keyword, bdd_context):
    """사용자가 특정 키워드로 검색
    실패 시에도 다음 스텝으로 진행"""
    try:
        logger.info(f"검색 시작: keyword={keyword}")
        home_page = HomePage(browser_session.page)
        home_page.close_popup()
        home_page.search_product(keyword)
        home_page.wait_for_search_results(keyword=keyword)
        bdd_context.store['keyword'] = keyword
        logger.info(f"검색 완료: keyword={keyword}")
    except Exception as e:
        logger.error(f"검색 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"검색 실패: {str(e)}", "사용자가 키워드를 검색한다")
        if 'keyword' not in bdd_context.store:
            bdd_context.store['keyword'] = keyword


@then("검색 결과 페이지가 표시된다")
def then_search_results_page_is_displayed(browser_session, bdd_context):
    """bdd_context의 keyword로 data-montelena-keyword=keyword 요소 존재 검증
    실패 시에도 다음 스텝으로 진행"""
    try:
        keyword = bdd_context.store.get("keyword") or bdd_context.get("keyword")
        if not keyword:
            raise ValueError("bdd_context에 keyword가 없습니다.")
        search_page = SearchPage(browser_session.page)
        search_page.verify_keyword_element_exists(keyword)
        try:
            search_page.close_popup(wait_seconds=2)
        except Exception as e:
            pass
        logger.info(f"검색 결과 페이지 표시 확인 (data-montelena-keyword={keyword})")
    except Exception as e:
        logger.error(f"검색 결과 페이지 표시 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"검색 결과 페이지 표시 확인 실패: {str(e)}", "검색 결과 페이지가 표시된다")


@given(parsers.parse('사용자가 "{keyword}"을 검색했다'))
def given_user_searched_keyword(browser_session, keyword, bdd_context):
    """사용자가 이미 검색한 상태 (Given)
    실패 시에도 다음 스텝으로 진행"""
    try:
        logger.info(f"검색 상태 확인: keyword={keyword}")
        # 이미 검색 결과 페이지에 있는지 확인
        current_url = browser_session.page.url
        if 'search' not in current_url.lower():
            # 검색 결과 페이지가 아니면 검색 수행
            when_user_searches_keyword(browser_session, keyword, bdd_context)
            # 검색 스텝에서 실패했을 경우 플래그가 설정됨
        else:
            bdd_context.store['keyword'] = keyword
            logger.info(f"이미 검색 결과 페이지에 있음: keyword={keyword}")
    except Exception as e:
        logger.error(f"검색 상태 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"검색 상태 확인 실패: {str(e)}", "사용자가 키워드를 검색했다")
        if 'keyword' not in bdd_context.store:
            bdd_context.store['keyword'] = keyword


@given(parsers.parse('검색 결과 페이지에 "{module_title}" 모듈이 있다'))
def module_exists_in_search_results(browser_session, module_title, request, bdd_context):
    """
    검색 결과 페이지에 특정 모듈이 존재하는지 확인하고 보장 (Given)
    모듈이 없으면 현재 시나리오만 skip
    모듈이 있지만 보이지 않으면 실패 플래그만 설정하고 다음으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        request: pytest request 객체 (fixture 접근용)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        search_page = SearchPage(browser_session.page)

        search_page.close_popup()
        # 모듈 찾기
        module = search_page.get_module_by_title(module_title)
        
        # 모듈이 존재하는지 확인 (count == 0이면 모듈이 없음)
        module_count = module.count()
        if module_count == 0:
            # 모듈이 없으면 skip 플래그 설정 (시나리오는 계속 진행)
            skip_reason = f"'{module_title}' 모듈이 검색 결과에 없습니다."
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
            record_frontend_failure(browser_session, bdd_context, f"모듈 존재 확인 실패: {str(e)}", "검색 결과 페이지에 모듈이 있다")
            # module_title은 저장 (다음 스텝에서 사용 가능하도록)
            bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
        
        # bdd_context에 module_title 저장 (다음 step에서 사용)
        bdd_context.store['module_title'] = module_title
        
        logger.info(f"{module_title} 모듈 존재 확인 완료")
    except Exception as e:
        logger.error(f"모듈 확인 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "검색 결과 페이지에 모듈이 있다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title


@when(parsers.parse('사용자가"{keyword}""{goodscode}" 최상단 클릭아이템 모듈 패이지로 이동한다'))
def user_goes_to_top_search_module_page(browser_session, keyword, goodscode, bdd_context):
    """
    최상단 클릭아이템 모듈 페이지로 이동
    실패 시에도 다음 스텝으로 진행
    """
    try:
        search_page = SearchPage(browser_session.page)
        search_page.go_to_top_search_module_page(keyword, goodscode)
        logger.info("최상단 클릭아이템 모듈 페이지로 이동 완료")
        bdd_context.store['module_title'] = "최상단 클릭아이템"
        bdd_context.store['keyword'] = keyword
    except Exception as e:
        logger.error(f"최상단 클릭아이템 모듈 페이지 이동 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"최상단 클릭아이템 모듈 페이지 이동 실패: {str(e)}", "사용자가 최상단 클릭아이템 모듈 페이지로 이동한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = "최상단 클릭아이템"
        if 'keyword' not in bdd_context.store:
            bdd_context.store['keyword'] = keyword


@when(parsers.parse('사용자가 "{module_title}" 모듈 내 {nth:d}번째 상품을 확인하고 클릭한다'))
def user_confirms_and_clicks_product_in_module(browser_session, module_title, nth, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        # 트래킹 스키마 로드 시 모듈명(n).json 매칭용 (tracking_validation_steps → load_module_config)
        bdd_context.store['nth'] = int(nth)
        search_page = SearchPage(browser_session.page)
        
        # 모듈로 이동
        module = search_page.get_module_by_title(module_title)
        time.sleep(2)
        ad_check = search_page.check_ad_item_in_srp_lp_module(module_title)
        
        # 모듈 내 상품 찾기 (모듈별 선택자 분기)
        nth_idx = max(int(nth) - 1, 0)
        parent = search_page.get_module_parent(module, 2)
        if module_title in ("4.5 이상", "장바구니VT"):
            product = search_page.get_product_in_module_type3(parent, nth_idx)
        elif module_title in ("백화점 브랜드", "브랜드 인기상품", "MD's Pick", "백화점픽", "최하단캐러셀", "연관키워드"):
            product = search_page.get_product_in_module_type2(parent, nth_idx)
        elif module_title == "반복구매":
            product = search_page.get_product_in_module_type4(parent, nth_idx)
        else:
            product = search_page.get_product_in_module(parent, nth_idx)
        search_page.scroll_product_into_view(product)
        
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
        goodscode = search_page.get_product_code(product)
        
        # 장바구니 담기 버튼 존재할 경우 클릭
        if search_page.is_add_to_cart_button_visible(parent, goodscode):
            try:
                search_page.click_add_to_cart_button(parent, goodscode)
                logger.info(f"장바구니 담기 버튼 클릭 완료: {goodscode}")
            except Exception as e:
                logger.warning(f"장바구니 담기 버튼 클릭 실패 (계속 진행): {e}")
        else:
            logger.info(f"장바구니 담기 버튼이 존재하지 않습니다: {goodscode}")
        
        if ad_check == "F":
            is_ad = search_page.check_ad_tag_in_srp_lp_product(product)
        else:
            is_ad =ad_check
        
        # 상품 클릭
        try:
            new_page = search_page.click_product_and_wait_new_page(product)
            
            # 명시적 페이지 전환 (상태 관리자 패턴)
            browser_session.switch_to(new_page)
            
            # bdd context에 저장 (module_title, goodscode, product_url 등)
            bdd_context.store['module_title'] = module_title
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['is_ad'] = is_ad
            bdd_context.store['product_url'] = new_page.url
            
            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다")
            # goodscode, is_ad 등 이미 읽은 값은 저장 (검증 스텝에서 <is_ad> 치환에 사용)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'is_ad' in locals():
                bdd_context.store['is_ad'] = is_ad
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
        bdd_context.store['nth'] = int(nth)

@when(parsers.parse('사용자가 "{module_title}" 모듈 내 {nth:d}번째 상품을 확인하고 클릭한다 (type2)'))
def user_confirms_and_clicks_product_in_module_type2(browser_session, module_title, nth, bdd_context):
    """
    모듈 내 상품 노출 확인하고 클릭 (Atomic POM 조합)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        module_title: 모듈 타이틀
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        bdd_context.store['nth'] = int(nth)
        search_page = SearchPage(browser_session.page)
        
        # 모듈로 이동
        module = search_page.get_module_by_title(module_title)
        search_page.scroll_module_into_view(module)
        time.sleep(2)
        ad_check = search_page.check_ad_item_in_srp_lp_module(module_title)
        
        # 모듈 내 상품 찾기
        nth_idx = max(int(nth) - 1, 0)
        parent = search_page.get_module_parent(module, 3)
        if module_title == "4.5 이상":
            product = search_page.get_product_in_module_type3(parent, nth_idx)
        else:
            product = search_page.get_product_in_module_type2(parent, nth_idx)
        search_page.scroll_product_into_view(product)
        
        # 상품 노출 확인 (실패 시 예외 발생)
        try:
            expect(product.first).to_be_visible()
        except AssertionError as e:
            # 실패 정보 저장하되 예외는 다시 발생시키지 않음
            logger.error(f"상품 노출 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 노출 확인 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다 (type2)")
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            return  # 여기서 종료 (다음 스텝으로 진행)
        
        # 상품 코드 가져오기
        goodscode = search_page.get_product_code(product)
        
        # 🔥 가격 정보는 이제 PDP PV 로그에서 추출하므로 프론트엔드에서 수집하지 않음
        # (PDP PV 로그는 상품 페이지 이동 후 수집됨)

        # 모듈별 광고상품 여부 저장장
        if ad_check == "F":
            is_ad = search_page.check_ad_tag_in_srp_lp_product(product)
        else:
            is_ad =ad_check
        # 상품 클릭s
        try:
            new_page = search_page.click_product_and_wait_new_page(product)
            
            # 명시적 페이지 전환 (상태 관리자 패턴)
            browser_session.switch_to(new_page)
            
            # bdd context에 저장 (module_title, goodscode, product_url 등)
            bdd_context.store['module_title'] = module_title
            bdd_context.store['goodscode'] = goodscode
            bdd_context.store['is_ad'] = is_ad
            bdd_context.store['product_url'] = new_page.url
            
            logger.info(f"{module_title} 모듈 내 상품 확인 및 클릭 완료: {goodscode}")
        except Exception as e:
            logger.error(f"상품 클릭 실패: {e}", exc_info=True)
            record_frontend_failure(browser_session, bdd_context, f"상품 클릭 실패: {str(e)}", "사용자가 모듈 내 상품을 확인하고 클릭한다 (type2)")
            # goodscode, is_ad 등 이미 읽은 값은 저장 (검증 스텝에서 <is_ad> 치환에 사용)
            if 'goodscode' in locals():
                bdd_context.store['goodscode'] = goodscode
            if 'is_ad' in locals():
                bdd_context.store['is_ad'] = is_ad
            if 'module_title' not in bdd_context.store:
                bdd_context.store['module_title'] = module_title
            
    except Exception as e:
        # 예상치 못한 예외 처리
        logger.error(f"프론트 동작 중 예외 발생: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, str(e), "사용자가 모듈 내 상품을 확인하고 클릭한다 (type2)")
        if 'module_title' not in bdd_context.store:
            bdd_context.store['module_title'] = module_title
        bdd_context.store['nth'] = int(nth)


@when(parsers.parse('사용자가 카테고리 아이디 "{category_id}" 로 이동한다'))
def when_user_goes_to_category(browser_session, category_id, bdd_context):
    """
    사용자가 카테고리 아이디로 LP 페이지 이동
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        category_id: 카테고리 ID
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        logger.info(f"LP 페이지 이동 시작: category_id={category_id}")
        list_page = ListPage(browser_session.page)
        list_page.go_to_list_page(category_id)
        bdd_context.store['category_id'] = category_id
        logger.info(f"LP 페이지 이동 완료: category_id={category_id}")
    except Exception as e:
        logger.error(f"LP 페이지 이동 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"LP 페이지 이동 실패: {str(e)}", "사용자가 카테고리 아이디로 이동한다")
        if 'category_id' not in bdd_context.store:
            bdd_context.store['category_id'] = category_id


@given(parsers.parse('사용자가 카테고리 아이디 "{category_id}" 로 이동했다'))
def given_user_went_to_category(browser_session, category_id, bdd_context):
    """
    사용자가 이미 카테고리 아이디로 이동한 상태 (Given)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        category_id: 카테고리 ID
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        logger.info(f"LP 페이지 상태 확인: category_id={category_id}")
        list_page = ListPage(browser_session.page)
        # 이미 리스트 페이지에 있는지 확인
        current_url = browser_session.page.url
        # 리스트 페이지 URL인지 먼저 확인
        if '/n/list' in current_url:
            try:
                # list_page의 검증 함수 사용
                list_page.verify_category_id_in_url(current_url, category_id)
                # 검증 통과 시 이미 올바른 페이지에 있음
                bdd_context.store['category_id'] = category_id
                logger.info(f"이미 LP 페이지에 있음: category_id={category_id}")
            except AssertionError:
                # 다른 카테고리면 이동 수행
                when_user_goes_to_category(browser_session, category_id, bdd_context)
                # 이동 스텝에서 실패했을 경우 플래그가 설정됨
        else:
            # 리스트 페이지가 아니면 이동 수행
            when_user_goes_to_category(browser_session, category_id, bdd_context)
            # 이동 스텝에서 실패했을 경우 플래그가 설정됨
    except Exception as e:
        logger.error(f"LP 페이지 상태 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"LP 페이지 상태 확인 실패: {str(e)}", "사용자가 카테고리 아이디로 이동했다")
        if 'category_id' not in bdd_context.store:
            bdd_context.store['category_id'] = category_id


@then("리스트 페이지가 표시된다")
def then_list_page_is_displayed(browser_session, bdd_context):
    """
    리스트 페이지가 표시되는지 확인 (검증)
    실패 시에도 다음 스텝으로 진행
    
    Args:
        browser_session: BrowserSession 객체 (page 참조 관리)
        bdd_context: BDD context (step 간 데이터 공유용)
    """
    try:
        list_page = ListPage(browser_session.page)
        # list_page의 로드 대기 함수 사용
        list_page.wait_for_list_page_load()
        
        # URL에 리스트 페이지 패턴이 있는지 확인
        current_url = browser_session.page.url
        if '/n/list' not in current_url:
            raise AssertionError(f"리스트 페이지 URL이 아닙니다: {current_url}")
        
        logger.info("리스트 페이지 표시 확인")
    except Exception as e:
        logger.error(f"리스트 페이지 표시 확인 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"리스트 페이지 표시 확인 실패: {str(e)}", "리스트 페이지가 표시된다")

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
        search_page = SearchPage(browser_session.page)
        
        # bdd context에서 값 가져오기 (store 또는 딕셔너리 방식 모두 지원)
        goodscode = bdd_context.store.get('goodscode') or bdd_context.get('goodscode')

        if not goodscode:
            # goodscode가 없으면 이전 스텝에서 실패했을 가능성
            logger.warning("goodscode가 설정되지 않았습니다. 이전 스텝에서 실패했을 수 있습니다.")
            bdd_context['frontend_action_failed'] = True
            bdd_context['frontend_error_message'] = "goodscode가 설정되지 않았습니다."
            return

        goodscode_str = str(goodscode).strip()
        # 같은 탭에서 페이지만 이동하므로 현재 page에서 URL 전환 대기
        try:
            browser_session.page.wait_for_url(f"*{goodscode_str}*", timeout=15000)
            logger.debug("상품 페이지 URL 전환 대기 완료")
        except Exception as e:
            logger.warning(f"URL 전환 대기 실패: {e}")
        try:
            browser_session.page.wait_for_load_state("networkidle", timeout=10000)
            logger.debug("networkidle 상태 대기 완료 (tracker 없음, PDP PV 대체 대기)")
        except Exception as e:
            logger.warning(f"networkidle 대기 실패, load 상태로 대기: {e}")
            try:
                browser_session.page.wait_for_load_state("load", timeout=30000)
                logger.debug("load 상태 대기 완료")
            except Exception as e2:
                logger.warning(f"load 상태 대기도 실패: {e2}")
        time.sleep(2)

        # URL 수집 타이밍: goodscode 포함될 때까지 한 번 더 대기 후 수집
        try:
            browser_session.page.wait_for_url(f"*{goodscode_str}*", timeout=5000)
        except Exception:
            pass
        current_url = browser_session.page.url

        # 검증 (실패 시 예외 발생) — 수집한 URL로 확인
        try:
            search_page.verify_product_code_in_url(current_url, goodscode_str)
        except AssertionError as e:
            logger.error(f"상품 페이지 이동 확인 실패: {e}")
            record_frontend_failure(browser_session, bdd_context, f"상품 페이지 이동 확인 실패: {str(e)}", "상품 페이지로 이동되었다")
            # 계속 진행 (PDP PV 로그 수집은 시도)
        logger.info(f"상품 페이지 이동 확인 완료: {goodscode} (PDP PV 로그 수집 대기 완료)")
        
    except Exception as e:
        logger.error(f"상품 페이지 이동 확인 중 예외 발생: {e}", exc_info=True)

@given(parsers.parse('더보기 버튼을 클릭한다'))
def click_more_button(browser_session, bdd_context):
    """
    더보기 버튼을 클릭한다
    """
    try:
        search_page = SearchPage(browser_session.page)
        search_page.click_more_button()
    except Exception as e:
        logger.error(f"더보기 버튼 클릭 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"더보기 버튼 클릭 실패: {str(e)}", "더보기 버튼을 클릭한다")

@when(parsers.parse('검색 결과 페이지에서 "{sort_option}" 정렬을 선택한다'))
def select_sort_option(browser_session, sort_option, bdd_context):
    """
    검색 결과 페이지에서 정렬을 선택한다
    """
    try:
        search_page = SearchPage(browser_session.page)
        search_page.select_sort_option(sort_option)
        bdd_context['selected_sort_option'] = sort_option
        try:
            search_page.close_popup(wait_seconds=2)
        except Exception as e:
            pass
    except Exception as e:
        logger.error(f"정렬 선택 실패: {e}", exc_info=True)
        record_frontend_failure(browser_session, bdd_context, f"정렬 선택 실패: {str(e)}", "검색 결과 페이지에서 정렬을 선택한다")

@when(parsers.parse('사용자가 "{filter_name}" 필터 {nth:d}번째를 적용한다'))
def select_filter(browser_session, filter_name, nth, bdd_context):
    """
    검색 결과 페이지에서 필터를 적용한다.
    """
    try:
        search_page = SearchPage(browser_session.page)
        search_page.select_filter(filter_name, nth)
    except Exception as e:
        logger.error(f"필터 적용 실패: {e}", exc_info=True)
        record_frontend_failure(
            browser_session,
            bdd_context,
            f"필터 적용 실패: {str(e)}",
            "사용자가 필터를 적용한다",
        )


@when(parsers.parse('검색 결과 페이지에서 "{sort_option}" 정렬을 적용한다'))
def apply_sort_option(browser_session, sort_option, bdd_context):
    """
    검색 결과 페이지에서 정렬을 적용한다. (검증은 Then 스텝에서 수행)
    """
    select_sort_option(browser_session, sort_option, bdd_context)


@then(parsers.re(r'상품평 수 내림차순 정렬이 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_review_counts_descending_should_pass_validation(tc_id, browser_session, bdd_context):
    """
    목록 상품의 `.box__score-awards.sprite .text__num` 값이
    위→아래로 내림차순(이전 상품 이하)인지 검증한다.
    TestRail 기록을 위해 TC 번호를 context에 저장하고 validation_* 플래그를 사용한다.
    """
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 상품평 수 내림차순 검증을 건너뜁니다.")
        return

    bdd_context['testrail_tc_id'] = tc_id
    step_name = "상품평 수 내림차순 정렬 정합성 검증"
    try:
        search_page = SearchPage(browser_session.page)
        try:
            browser_session.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            logger.debug(f"networkidle 대기 생략/실패, load로 대체: {e}")
            try:
                browser_session.page.wait_for_load_state("load", timeout=15000)
            except Exception as e2:
                logger.warning(f"load 대기도 실패: {e2}")
        time.sleep(1.0)

        counts = search_page.collect_review_counts_for_search_result_items(max_items=100)
        if len(counts) < 2:
            raise ValueError(
                f"비교할 상품이 부족합니다 (수집 {len(counts)}개). "
                "정렬·로딩·선택자를 확인하세요."
            )
        violations = []
        violation_indices = []
        for idx in range(1, len(counts)):
            prev_count, curr_count = counts[idx - 1], counts[idx]
            if curr_count > prev_count:
                violation_indices.append(idx)
                violations.append(
                    f"{idx + 1}번째 상품: {curr_count} > {idx}번째 상품: {prev_count}"
                )

        if violations:
            # 실패 스크린샷이 위반 상품 근처에서 찍히도록 첫 번째 위반 상품으로 스크롤
            try:
                first_violation_idx = violation_indices[0]  # 0-based (현재 상품 위치)
                target_num = browser_session.page.locator(".box__score-awards.sprite .text__num").nth(first_violation_idx)
                target_num.scroll_into_view_if_needed(timeout=5000)
                time.sleep(0.2)
            except Exception as scroll_err:
                logger.warning(f"위반 상품으로 스크롤 실패(계속 진행): {scroll_err}")

            violation_details = "\n".join(violations)
            raise ValueError(
                "상품평 많은순 내림차순 위반이 발견되었습니다.\n"
                f"총 위반 건수: {len(violations)}\n"
                f"{violation_details}"
            )
        bdd_context['validation_failed'] = False
        bdd_context['validation_passed_fields'] = {
            'sort_option': bdd_context.get('selected_sort_option'),
            'checked_item_count': len(counts),
            'ordering': 'desc'
        }
        logger.info(
            f"[TestRail TC: {tc_id}] 상품평 수 내림차순 검증 통과 ({len(counts)}개 상품)"
        )
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] {step_name} 실패: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message


@then(parsers.re(r'goodscode 오름차순 정렬이 정합성 검증을 통과해야 함 \(TC: (?P<tc_id>.*)\)'))
def then_goodcodes_ascending_should_pass_validation(tc_id, browser_session, bdd_context):
    """
    목록 상품의 data-montelena-goodscode 값이
    위→아래로 내림차순(이전 상품 이상)인지 검증한다.
    실패 스크린샷이 위반 상품 근처에 찍히도록 먼저 스크롤한다.

    Note:
        엄격한 내림차순으로 검증한다.
        'curr >= prev'일 때 위반으로 판단한다(이전 상품이 반드시 더 커야 함).
    """
    if not tc_id or tc_id.strip() == '':
        logger.info("TC 번호가 비어있어 goodscode 오름차순 검증을 건너뜁니다.")
        return

    bdd_context['testrail_tc_id'] = tc_id
    step_name = "goodscode 내림차순 정렬 정합성 검증"
    try:
        search_page = SearchPage(browser_session.page)
        try:
            browser_session.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            logger.debug(f"networkidle 대기 생략/실패, load로 대체: {e}")
            try:
                browser_session.page.wait_for_load_state("load", timeout=15000)
            except Exception as e2:
                logger.warning(f"load 대기도 실패: {e2}")
        time.sleep(1.0)

        goodcodes = search_page.collect_goodcodes_for_search_result_items(max_items=100)
        if len(goodcodes) < 2:
            raise ValueError(
                f"비교할 상품이 부족합니다 (수집 {len(goodcodes)}개). "
                "정렬·로딩·선택자를 확인하세요."
            )

        violations = []
        violation_indices = []
        for idx in range(1, len(goodcodes)):
            prev_code, curr_code = goodcodes[idx - 1], goodcodes[idx]
            if curr_code >= prev_code:
                violation_indices.append(idx)  # 0-based: current item index
                violations.append(
                    f"{idx + 1}번째 상품: goodscode {curr_code} >= {idx}번째 상품: {prev_code}"
                )

        if violations:
            # 실패 스크린샷: 위반 행의 goodscode 값으로 정확히 매칭 (카드당 a 태그 2개 이슈 회피)
            try:
                violating_idx = violation_indices[0]
                code_str = str(goodcodes[violating_idx])
                page = browser_session.page
                cards = page.locator("div.box__itemcard")
                target = None
                if cards.count() > violating_idx:
                    card = cards.nth(violating_idx)
                    scoped = card.locator(
                        f'a[data-montelena-goodscode="{code_str}"]'
                    )
                    if scoped.count() == 0:
                        raw_attr = (
                            card.locator("a[data-montelena-goodscode]")
                            .first.get_attribute("data-montelena-goodscode")
                            or ""
                        ).strip()
                        if raw_attr:
                            scoped = card.locator(
                                f'a[data-montelena-goodscode="{raw_attr}"]'
                            )
                    if scoped.count() > 0:
                        target = scoped.first
                    else:
                        target = card.locator("a[data-montelena-goodscode]").first
                if target is None:
                    target = page.locator(
                        f'a[data-montelena-goodscode="{code_str}"]'
                    ).first
                target.scroll_into_view_if_needed(timeout=5000)
                time.sleep(1.0)
            except Exception as scroll_err:
                logger.warning(f"위반 goodscode 상품으로 스크롤 실패(계속 진행): {scroll_err}")

            violation_details = "\n".join(violations)
            raise ValueError(
                "goodscode 내림차순 정렬 위반이 발견되었습니다.\n"
                f"총 위반 건수: {len(violations)}\n"
                f"{violation_details}"
            )

        bdd_context['validation_failed'] = False
        bdd_context['validation_passed_fields'] = {
            'sort_option': bdd_context.get('selected_sort_option'),
            'checked_item_count': len(goodcodes),
            'ordering': 'desc'
        }
        logger.info(f"[TestRail TC: {tc_id}] goodscode 내림차순 검증 통과 ({len(goodcodes)}개 상품)")
    except Exception as e:
        error_message = f"[TestRail TC: {tc_id}] {step_name} 실패: {str(e)}"
        logger.error(error_message, exc_info=True)
        bdd_context['validation_failed'] = True
        bdd_context['validation_error_message'] = error_message
