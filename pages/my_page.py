import time
import logging
import json
from pages.base_page import BasePage
from utils.mobile_web_adapter import Page, Locator, expect
from utils.urls import my_url
from typing import Optional

logger = logging.getLogger(__name__)


class MyPage(BasePage):
    def __init__(self, page: Page):
        """
        MyPage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        super().__init__(page)

    def go_to_my_page_by_url(self):
        """
        마이 페이지 URL로 이동
        """
        logger.debug("마이 페이지로 이동")
        self.page.goto(my_url(), wait_until="domcontentloaded", timeout=30000)
        logger.info("v 페이지 이동 완료")

    def is_my_page_displayed(self):
        """
        마이페이지가 표시되었는지 확인
        """
        logger.debug("마이페이지 표시 확인")
        return self.is_visible(".text__title:has-text('주문내역')")

    def click_order_history(self):
        """
        주문내역 메뉴 클릭 (주문 목록 페이지로 이동하는 링크)
        <a href=".../ko/pc/list/all" class="link__menu"><span class="text__menu">주문내역</span></a>
        동일 링크가 2개 있을 수 있어 첫 번째 요소만 클릭.
        """
        logger.info("주문내역 버튼 클릭")
        self.page.locator(".text__title:has-text('주문내역')").first.click()

    def is_order_history_page_displayed(self):
        """
        주문내역 페이지가 표시되었는지 확인
        """
        logger.debug("주문내역 페이지 표시 확인")
        return self.is_visible(".box__title:has-text('주문내역')")

    # 주문내역 상품 썸네일 img 공통 셀렉터 (box__thumbnail은 클래스이므로 앞에 . 필요)
    _ORDER_ITEM_IMG = ".link__item-information a"

    def get_goods_code_from_order_history(self):
        """
        주문내역에서 상품코드 가져오기. 요소가 보이도록 스크롤 후 속성 조회.
        """
        logger.debug("주문내역에서 상품코드 가져오기")
        loc = self.page.locator(self._ORDER_ITEM_IMG).first
        self._scroll_order_item_into_view(loc)
        goodscode = loc.get_attribute("data-montelena-goodscode")
        return goodscode

    def _scroll_order_item_into_view(self, locator: Locator) -> None:
        """주문내역 상품 요소가 뷰포트에 보이도록 스크롤."""
        try:
            locator.scroll_into_view_if_needed(timeout=10000)
        except Exception as e:
            logger.warning(f"scroll_into_view_if_needed 실패, evaluate 스크롤 시도: {e}")
            locator.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")

    def click_atc_in_order_history_by_goodscode(self, goodscode: str):
        """
        주문내역에서 상품코드로 담기버튼 클릭
        """
        logger.debug(f"주문내역에서 상품코드로 담기버튼 탭: {goodscode}")
        self.page.locator(f".button__cart[data-montelena-goodscode='{goodscode}']").tap(timeout=5000)

    def atc_alert_close(self):
        """
        담기 얼럿 닫기
        """
        logger.debug("담기 얼럿 닫기")
        self.page.locator(".button__close[aria-label='레이어 닫기']").click()

    def click_product_in_order_history_by_goodscode(self, goodscode: str):
        """
        주문내역에서 상품코드로 상품 클릭
        """
        logger.debug(f"주문내역에서 상품코드로 상품 탭: {goodscode}")
        loc = self.page.locator(f"{self._ORDER_ITEM_IMG}[data-montelena-goodscode='{goodscode}']").first
        self._scroll_order_item_into_view(loc)
        loc.tap(timeout=5000)

    def click_product_in_order_history_and_wait_new_page(self, goodscode: str) -> Page:
        """
        주문내역에서 상품 클릭하고 새 탭 대기 (SearchPage.click_product_and_wait_new_page와 동일 패턴)

        Args:
            goodscode: 상품코드

        Returns:
            새 탭의 Page 객체
        """
        logger.debug("주문내역 상품 클릭 및 새 탭 대기")
        product_locator = self.page.locator(
            f"{self._ORDER_ITEM_IMG}[data-montelena-goodscode='{goodscode}']"
        ).first
        self._scroll_order_item_into_view(product_locator)

        time.sleep(3)

        try:
            with self.page.context.expect_page(timeout=5000) as new_page_info:
                product_locator.tap(timeout=3000)

            new_page = new_page_info.value
            logger.debug(f"새 탭 생성됨: {new_page.url}")
        except Exception as e:
            logger.warning(f"일반 클릭 실패, 팝업 닫기 후 재시도: {e}")
            try:
                popup_close_button = self.page.locator(".button__popup-close")
                if popup_close_button.count() > 0:
                    try:
                        popup_close_button.first.click(force=True, timeout=2000)
                    except Exception as e:
                        logger.warning(f"팝업 닫기 버튼 클릭 실패: {e}")
                    logger.debug("팝업 닫기 버튼 클릭 완료")
                    time.sleep(2)

                with self.page.context.expect_page(timeout=10000) as new_page_info:
                    product_locator.tap(timeout=3000)

                new_page = new_page_info.value
                logger.debug(f"팝업 닫기 후 새 탭 생성됨: {new_page.url}")
            except Exception as e2:
                logger.error(f"팝업 닫기 후 클릭도 실패: {e2}")
                raise Exception(f"클릭 실패 (일반 클릭: {e}, 팝업 닫기 후 재시도: {e2})")

        new_page.bring_to_front()
        logger.debug("새 탭을 포커스로 가져옴")

        try:
            new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            logger.debug("새 탭 DOM 로드 완료")
        except Exception as e:
            logger.warning(f"domcontentloaded 대기 실패: {e}")
            raise

        max_retries = 5
        for i in range(max_retries):
            current_url = new_page.url
            if current_url and current_url != "about:blank":
                logger.debug(f"새 탭 URL 확인됨: {current_url}")
                break
            if i < max_retries - 1:
                new_page.wait_for_timeout(500)
            else:
                logger.warning(f"새 탭 URL이 about:blank 상태입니다: {current_url}")

        return new_page

    def get_order_history_product_locator(self, goodscode: str) -> Locator:
        """
        주문내역에서 상품코드에 해당하는 상품 Locator 반환 (ad 태그 확인 등에 사용)
        """
        return self.page.locator(
            f"{self._ORDER_ITEM_IMG}[data-montelena-goodscode='{goodscode}']"
        )

    def check_ad_item_in_order_history_module(self, module_title: str) -> str:
        """
        주문내역 등 My 페이지 모듈 내 광고상품 노출 여부 확인
        (SearchPage.check_ad_item_in_srp_lp_module과 형식 통일)

        Args:
            module_title: 모듈 타이틀 (예: "주문내역")

        Returns:
            "Y", "N", 또는 "F" (F인 경우 상품별 check_ad_tag 필요)
        """
        logger.debug(f"주문내역 모듈 내 광고상품 노출 확인: {module_title}")
        MODULE_AD_CHECK = {
            "주문내역": "N",
        }
        if module_title not in MODULE_AD_CHECK:
            raise ValueError(f"모듈 타이틀 {module_title} 확인 불가")
        return MODULE_AD_CHECK[module_title]

    def check_ad_tag_in_order_history_product(self, product_locator: Locator) -> str:
        """
        주문내역 상품 내 광고 태그 노출 확인
        (SearchPage.check_ad_tag_in_srp_lp_product와 형식 통일)

        Args:
            product_locator: 상품 Locator 객체 (주문내역 내 상품)

        Returns:
            "Y" 또는 "N"
        """
        logger.debug("주문내역 상품 내 광고 태그 노출 확인")
        try:
            # 주문내역 상품 컨테이너에서 광고 레이어 등 확인 (DOM 구조에 맞게 추후 구현)
            item_container = product_locator.locator(
                "xpath=ancestor::div[contains(@class, 'box__order-item')]"
            )
            ads_layer = item_container.locator("div.box__ads-layer")
            if ads_layer.count() > 0:
                return "Y"
            return "N"
        except Exception as e:
            logger.warning(f"주문내역 광고 태그 확인 중 오류: {e}")
            return "N"

