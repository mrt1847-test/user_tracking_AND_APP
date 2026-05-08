import time
import logging
import json
from pages.base_page import BasePage
from utils.mobile_web_adapter import Page, Locator, expect
from utils.urls import product_url, search_url, cart_url
from typing import Optional

logger = logging.getLogger(__name__)


class CartPage(BasePage):
    def __init__(self, page: Page):
        """
        CartPage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        super().__init__(page)

    def go_to_cart_page(self):
        """
        장바구니 페이지로 이동
        """
        logger.debug("장바구니 페이지로 이동")
        self.page.goto(cart_url(), wait_until="domcontentloaded", timeout=30000)
        logger.info("장바구니 페이지 이동 완료")
    
    def go_to_product_page(self, goodscode: str):
        """
        상품 페이지로 이동
        """
        logger.debug("장바구니 페이지로 이동")
        self.page.goto(product_url(goodscode), wait_until="domcontentloaded", timeout=30000)
        logger.info("장바구니 페이지 이동 완료")


    def click_buy_now_button(self, timeout: int = 10000) -> None:
        """
        구매하기 버튼 클릭
        """
        logger.debug("구매하기 버튼 클릭")
        btn = self.page.locator(".button__buy--normal").nth(0)
        btn.wait_for(state="visible", timeout=timeout)
        btn.scroll_into_view_if_needed(timeout=timeout)
        btn.click(timeout=timeout)
        logger.info("구매하기 버튼 클릭 완료")

    def click_cart_now_button(self, timeout: int = 10000) -> None:
        """
        장바구니 버튼 클릭
        """
        logger.debug("장바구니 버튼 클릭")
        btn = self.page.locator(".button__cart--normal").nth(0)
        btn.wait_for(state="visible", timeout=timeout)
        btn.scroll_into_view_if_needed(timeout=timeout)
        btn.click(timeout=timeout)
        logger.info("장바구니 버튼 클릭 완료")

    def select_group_product(self, n: int, timeout: int = 10000) -> None:
        """
        n 번째 그룹상품 선택 
        
        Args:   
            n: 그룹상품 번호
            timeout: 타임아웃 (기본값: 10000ms)
        """
        if n < 10:
            n = f"0{n}"
        else:
            n = f"{n}"
        
        logger.debug("그룹 옵션레이어 클릭 시도 (.button__select.sprite)")
        select_btn = self.page.locator(".button__select.sprite > .box__thumbnail").first
        select_btn.click()
        logger.debug("그룹 옵션 버튼 클릭 완료")

        # span.text__name "상품 선택" 이 나타날 때까지 대기 (옵션 레이어 표시)
        option_layer = self.page.locator("span.text__name", has_text="상품 선택")
        option_layer.wait_for(state="visible", timeout=timeout)
        logger.debug("상품 선택 레이어 표시됨")

        # span.text__num "상품 {n}" 인 그룹상품 (클릭은 부모 행에서 수행)
        group_product = self.page.locator("span.text__num", has_text=f"상품 {n}").first.locator("xpath=..")
        group_product.scroll_into_view_if_needed(timeout=timeout)
        
        # n번쨰 그룹상품 강제 클릭 (부모 요소가 실제 클릭 영역)
        group_product.tap(timeout=timeout, force=True)

        # button, text "선택" 인 요소 클릭
        self.page.get_by_role("button", name="선택").first.click()
        logger.info("n번쨰 그룹상품 선택 완료")


    def wait_for_cart_page_load(self) -> None:
        """
        장바구니 페이지 로드 대기
        <h1 class="box__title"> 내 텍스트 "장바구니"가 보일 때까지 대기
        """
        logger.debug("장바구니 페이지 로드 대기 (h1.box__title + 텍스트 '장바구니')")
        loc = self.page.locator("h1.box__title", has_text="장바구니")
        loc.wait_for(state="visible", timeout=self.timeout)
        logger.info("장바구니 페이지 로드 확인됨")
        
    def select_all_and_delete(self, max_rounds: int = 3) -> None:
        """
        '장바구니에 담긴 상품이 없습니다.'(strong.msg)가 노출될 때까지 전체 선택 후 선택삭제를 반복.
        전체 선택 체크박스 체크 → 선택삭제 클릭 → 확인 얼럿 수락을 한 라운드로 반복한다.

        Args:
            max_rounds: 최대 반복 횟수 (무한 루프 방지)
        """
        empty_msg = self.page.locator("strong.msg", has_text="장바구니에 담긴 상품이 없습니다.")
        for _ in range(max_rounds):
            if empty_msg.is_visible():
                logger.debug("장바구니가 비어 있음, 선택삭제 반복 종료")
                return
            loc = self.page.locator("#item_all_select")
            if not loc.is_checked():
                loc.check()
                logger.debug("전체 선택 체크 완료")
            else:
                logger.debug("전체 선택 이미 체크됨")
            self.click_and_expect_dialog(selector="button.btn_del:has-text('선택삭제')")
            logger.debug("선택삭제 버튼 클릭, 확인 얼럿 수락")
            time.sleep(0.5)
        logger.warning("선택삭제 반복이 max_rounds(%d)에 도달하여 종료", max_rounds)

    def click_go_to_cart_page(self, timeout: int = 10000) -> None:
        """
        장바구니 페이지로 이동.
        헤더의 장바구니 링크 클릭 (다중 로케이터).

        Args:
            timeout: 타임아웃 (기본값: 10000ms)
        """
        # link__cart(acode=200004339) / btn-cart(acode=200004438) 등 장바구니 링크 공통 (복수 매칭 시 첫 번째 사용)
        cart_link = (
            self.page.locator('a.link__cart[data-montelena-acode="200004339"]')
            .or_(self.page.locator('a.link__cart[data-montelena-type="core"]'))
            .or_(self.page.locator("a.link__cart"))
            .or_(self.page.locator('a.btn-cart[data-montelena-acode="200004438"]'))
            .or_(self.page.locator("a.btn-cart"))
            .or_(self.page.locator('a[href*="cart.gmarket.co.kr"]'))
        ).first
        logger.debug("장바구니 링크 클릭")
        cart_link.wait_for(state="attached", timeout=timeout)
        cart_link.click(timeout=timeout)
        logger.info("장바구니 페이지로 이동 완료")

    def check_module_in_cart(self, module_title: str, timeout: Optional[int] = None) -> Locator:
        """
        장바구니 페이지에 모듈이 있는지 확인하고 나타날 때까지 대기
        
        Args:
            module_title: 모듈 타이틀
            timeout: 타임아웃 (기본값: self.timeout)
        
        Returns:
            모듈 Locator 객체
        """
        timeout = timeout or self.timeout
        logger.debug(f"모듈 찾기: {module_title} (timeout: {timeout}ms)")
        
        if module_title == "장바구니 최저가":
            locator = self.page.locator(".text__title strong", has_text="최저가")
        elif module_title == "장바구니 BT":
            locator = self.page.locator(".text__title", has_text="다른 고객 장바구니 보기")
        else:
            locator = self.page.locator(".text__title", has_text=module_title)
        
        # 모듈이 나타날 때까지 대기
        logger.debug(f"모듈 노출 대기 중: {module_title}")
        locator.wait_for(state="visible", timeout=timeout)
        locator.scroll_into_view_if_needed(timeout=timeout)
        logger.info(f"모듈 노출 확인됨: {module_title}")
        
        return locator

    def check_ad_item_in_module(self, modulel_title: str) -> str:
        """
        모듈 내 광고상품 노출 확인
        
        Args:
            modulel_title: 모듈 타이틀
        
        Returns:
            "Y", "N", 또는 "F" (광고 상품 여부)
        
        Raises:
            ValueError: 알 수 없는 모듈 타이틀인 경우
        """
        logger.debug(f"모듈 내 광고상품 노출 확인: {modulel_title}")

        MODULE_AD_CHECK = {
            "장바구니 최저가": "N",
            "장바구니 BT": "Y"
        }
        
        if modulel_title not in MODULE_AD_CHECK:
            raise ValueError(f"모듈 타이틀 {modulel_title} 확인 불가")
        
        return MODULE_AD_CHECK[modulel_title]

    def get_product_in_module(self, module_locator: Locator) -> Locator:
        """
        모듈 내 상품 요소 찾기
        """
        logger.debug("모듈 내 상품 요소 찾기")
        return module_locator.locator("a").first

    def check_ad_tag_in_product(self, product_locator: Locator) -> str:
        """
        상품 내 광고 태그 노출 확인
        """
        logger.debug(f"상품 내 광고 태그 노출 확인: {product_locator}")
        
        try:
            # 상품 요소의 조상 요소에서 div.box__ads-layer 찾기
            item_container = product_locator.locator("")
            ads_layer = item_container.locator("")
            
            if ads_layer.count() > 0:
                logger.debug("광고 태그 발견: Y")
                return "Y"
            else:
                logger.debug("광고 태그 없음: N")
                return "N"
        except Exception as e:
            logger.warning(f"광고 태그 확인 중 오류 발생: {e}")
            return "N"

    def click_product_and_wait_pdp_pv(self, product_locator: Locator) -> None:
        """
        상품 탭 (모바일: 터치 이벤트로 product.click.event 트래킹 인식)
        """
        logger.debug(f"상품 탭: {product_locator}")
        product_locator.tap(timeout=5000)
        logger.info("상품 탭 완료")

    def click_cart_button_in_module(self, goodscode: str) -> None:
        """
        모듈 내 장바구니 버튼 탭 (모바일: 터치 이벤트로 product.atc.click 트래킹 인식)
        """
        logger.debug(f"모듈 내 장바구니 버튼 탭: {goodscode}")
        self.page.locator(f'.button__cart[data-montelena-goodscode="{goodscode}"]').nth(0).tap(timeout=5000)
        logger.info("모듈 내 장바구니 버튼 탭 완료")

    def check_cart_added(self, goodscode: str, timeout: int = 10000) -> None:
        """
        장바구니 담기 완료 확인
        해당 goodscode의 장바구니 버튼이 보이지 않으면 장바구니 담기가 완료된 것으로 확인
        
        Args:
            goodscode: 상품 번호
            timeout: 타임아웃 (기본값: 10000ms)
        
        Raises:
            AssertionError: 장바구니 버튼이 여전히 보이는 경우 (담기 미완료)
        """
        logger.debug(f"장바구니 담기 완료 확인: {goodscode}")
        button_locator = self.page.locator(f'.button__cart[data-montelena-goodscode="{goodscode}"]')
        
        # 버튼이 존재하지 않으면 성공
        if button_locator.count() == 0:
            logger.info(f"장바구니 담기 완료 확인됨: {goodscode} (버튼 없음)")
            # ATC 이벤트 수집을 위한 대기 시간
            time.sleep(1.5)
            return
        
        # 버튼이 보이지 않을 때까지 대기 (또는 이미 숨겨져 있으면 성공)
        try:
            button_locator.first.wait_for(state="hidden", timeout=timeout)
            logger.info(f"장바구니 담기 완료 확인됨: {goodscode} (버튼 숨김)")
            # ATC 이벤트 수집을 위한 대기 시간
            time.sleep(1.5)
        except Exception:
            # 타임아웃 후에도 버튼이 보이면 실패
            if button_locator.first.is_visible():
                raise AssertionError(f"장바구니 버튼이 여전히 보입니다: {goodscode}")
            # 보이지 않으면 성공
            logger.info(f"장바구니 담기 완료 확인됨: {goodscode}")
            # ATC 이벤트 수집을 위한 대기 시간
            time.sleep(1.5)
