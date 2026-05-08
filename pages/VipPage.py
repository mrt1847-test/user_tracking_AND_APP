import time
import logging
from utils.mobile_web_adapter import expect

logger = logging.getLogger(__name__)

class Vip():
    def __init__(self, page):
        self.page = page

    def select_first_product(self):
        self.page.click("css=ul.search-list > li:first-child a")

    def click_buy_now(self):
        self.page.click("text=바로구매")

    def vip_module_by_title(self, module_title):
        """
        VIP에서 특정 모듈의 타이틀 텍스트를 통해 해당 모듈 노출 확인하고 그 모듈 엘리먼트를 반환
        :param (str) module_title : 모듈 타이틀
        :return: 해당 모듈 element
        :example:
        """
        logger.debug(f'VIP 모듈 검색 시작: module_title={module_title}')
        child = self.page.get_by_text(module_title)
        child.scroll_into_view_if_needed()
        parent = child.locator("xpath=../..")
        target = parent.locator("div.vip-together_carousel > ul > li").nth(0)
        expect(parent).to_be_visible()
        logger.info(f'VIP 모듈 노출 확인 완료: module_title={module_title}')

        return parent

    def assert_item_in_module(self, module_title):
        """
        VIP에서 특정 모듈의 타이틀 텍스트를 통해 해당 모듈내 상품 노출 확인하고 그 상품번호 반환
        :param (str) module_title : 모듈 타이틀
        :return: 해당 모듈 노출 상품 번호, 해당 상품 로케이터
        :example:
        """
        logger.debug(f'VIP 모듈 내 상품 노출 확인 시작: module_title={module_title}')
        child = self.page.get_by_text(module_title)
        parent = child.locator("xpath=../..")
        target = parent.locator("div.vip-together_carousel > ul > li").nth(0).locator("a")
        target.scroll_into_view_if_needed()
        expect(parent).to_be_visible()
        goodscode = target.get_attribute("href").split('=')[-1]
        logger.info(f'VIP 모듈 내 상품 노출 확인 완료: module_title={module_title}, goodscode={goodscode}')

        return {
            "goodscode": goodscode,
            "target": target
        }

    def check_bt_ad_tag(self, parent):
        """
        특정 모듈의 광고 태그 노출 확인
        :param (element) parent : 모듈의 element
        :return: 해당 모듈 노출 광고 상품 번호, 해당 상품 로케이터
        :example:
        """
        logger.debug('BT 광고상품 광고태그 확인 시작')
        total_groups = 3  # 5개씩 3번 → 총 15개
        ad_count = 0  # 광고태그 카운트
        goodscode = None
        target = None

        for group_index in range(total_groups):
            # 현재까지 로드된 상품 가져오기
            products = parent.locator("div.vip-together_carousel > ul > li").all()
            start = group_index * 5
            end = start + 5

            logger.debug(f'{group_index + 1}번째 상품 그룹 확인 시작 (상품 {start+1}~{end}번)')
            for i, product in enumerate(products[start:end], start=start + 1):
                # 광고태그 존재 여부 확인
                ad_tag_locator = product.locator(".box__ad-tag")
                if ad_tag_locator.count() > 0:
                    ad_count += 1
                    goodscode = parent.locator("div.vip-together_carousel > ul > li").nth(ad_count-1).locator("a").get_attribute("href").split('=')[-1]
                    target = parent.locator("div.vip-together_carousel > ul > li").nth(ad_count - 1)
                    logger.debug(f'{i}번째 상품: 광고 태그 존재 (goodscode={goodscode})')
                else:
                    logger.debug(f'{i}번째 상품: 광고 태그 없음')

            # 마지막 그룹이 아니라면 버튼 클릭
            if group_index < total_groups - 1:
                parent.locator("span > button.next").click()
                self.page.wait_for_timeout(2000)  # 로딩 대기

        parent.locator("span > button.prev").click()

        logger.info(f'BT 광고상품 광고태그 확인 완료: 총 {ad_count}개 / 15개, goodscode={goodscode}')

        return {
            "goodscode": goodscode,
            "target": target
        }

    def click_goods(self, goodscode, target):
        """
        특정 상품 번호 아이템 클릭
        :param (str) goodscode : 상품 번호
        :param (str) target : 상품 로케이터
        :return (str) url: 클릭한 상품 url
        :example:
        """
        logger.debug(f'VIP 상품 클릭 시작: goodscode={goodscode}')
        time.sleep(5)
        target.click()
        url = self.page.url
        time.sleep(3)
        logger.info(f'VIP 상품 클릭 완료: goodscode={goodscode}')

        logger.debug(f'VIP 상품 이동 확인 시작: goodscode={goodscode}')
        assert goodscode in url, f"상품 번호 {goodscode}가 URL에 포함되어야 합니다"
        logger.info(f'VIP 상품 이동 확인 완료: goodscode={goodscode}, url={url}')

        return url
