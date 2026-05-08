import time
import logging
import json
from pages.base_page import BasePage
from utils.mobile_web_adapter import Page, Locator, expect
from utils.urls import product_url, cart_url, order_complete_url
from typing import Optional

logger = logging.getLogger(__name__)


class OrderPage(BasePage):
    def __init__(self, page: Page):
        """
        OrderPage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        super().__init__(page)

    def go_to_order_complete_page(self,cart_num):
        """
        주문완료 페이지로 이동
        
        Args:
            cart_num: 장바구니 번호
        """
        logger.debug("주문완료 페이지로 이동")
        self.page.goto(order_complete_url(cart_num), wait_until="domcontentloaded", timeout=30000)
        logger.info("주문완료 페이지 이동 완료")

    def is_order_complete_page_displayed(self):
        """
        주문완료 페이지가 표시되었는지 확인
        
        Returns:
            True: 주문완료 페이지가 표시되었음
            False: 주문완료 페이지가 표시되지 않았음
        """
        logger.debug("주문완료 페이지 표시 확인")
        return self.is_visible(".box__title:has-text('주문완료')")
    
    def get_spmc_by_module_title(self, module_title: str) -> str:
        """
        모듈 타이틀로 SPM 코드 가져오기
        
        Args:
            module_title: 모듈 타이틀
        
        Returns:
            SPM 코드
        """
        logger.debug(f"모듈 타이틀로 SPM 코드 가져오기: {module_title}")
        if module_title == "주문완료 BT":
            return "ordercompletebt"
        else:
            raise ValueError(f"모듈 타이틀 {module_title} SPM 코드 확인 불가")

    def find_option_select_button_in_module(self, module: Locator) -> Locator:
        """
        모듈 내 옵션선택 버튼 찾기
        
        Args:
            module: 모듈 Locator 객체
        
        Returns:
            옵션선택 버튼 Locator 객체
        """
        logger.debug(f"모듈 내 옵션선택 버튼 찾기: {module}")
        return module.get_by_text("옵션선택", exact=True).nth(0)

    def get_goodscode_in_product(self, product: Locator) -> str:
        """
        모듈 내 상품 코드 가져오기
        
        Args:
            product: 상품 Locator 객체
        
        Returns:
            상품 코드
        """
        logger.debug(f"모듈 내 상품 코드 가져오기")
        return product.get_attribute("data-montelena-goodscode")

    def check_ad_item_in_order_complete_module(self, modulel_title: str) -> str:
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
            "주문완료 BT": "F",
        }
        
        if modulel_title not in MODULE_AD_CHECK:
            raise ValueError(f"모듈 타이틀 {modulel_title} 확인 불가")
        
        return MODULE_AD_CHECK[modulel_title]

    def check_ad_tag_in_order_complete_product(self, product_locator: Locator) -> str:
        """
        상품 내 광고 태그 노출 확인
        
        Args:
            product_locator: 상품 Locator 객체
        
        Returns:
            "Y", "N"(광고 상품 여부)
        """
        logger.debug(f"상품 내 광고 태그 노출 확인: {product_locator}")
        
        try:
            # 상품 요소의 조상 요소에서 div.box__ads-layer 찾기
            item_container = product_locator.locator("xpath=ancestor::div[contains(@class, 'box__item-container')]")
            ads_layer = item_container.locator("div.box__ads-layer")
            
            if ads_layer.count() > 0:
                logger.debug("광고 태그 발견: Y")
                return "Y"
            else:
                logger.debug("광고 태그 없음: N")
                return "N"
        except Exception as e:
            logger.warning(f"광고 태그 확인 중 오류 발생: {e}")
            return "N"

    def get_atc_button_in_order_complete_module(self, module: Locator, n: Optional[int] = None) -> Locator:
        """
        모듈 내 담기버튼 요소 찾기
        
        Args:
            module: 모듈 Locator 객체
            n: 상품 순서 (1부터 시작, 1=첫 번째, 2=두 번째). None이면 첫 번째 상품 반환
        
        Returns:
            상품 Locator 객체
        """
        if n is not None:
            logger.debug(f"모듈 내 {n}번째 담기버튼 요소 찾기")
            return module.locator(".button__cart", has_text="담기").nth(n - 1)  # 1부터 시작하는 인덱스를 0부터 시작하는 인덱스로 변환
        else:
            logger.debug("모듈 내 첫 번째 담기버튼 요소 찾기")
            return module.locator(".button__cart", has_text="담기").first
