import time
import logging
import json
from pages.base_page import BasePage
from utils.mobile_web_adapter import Page, Locator, expect
from utils.urls import item_base_url, list_url
from typing import Optional

logger = logging.getLogger(__name__)


class ListPage(BasePage):
    def __init__(self, page: Page):
        """
        ListPage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        super().__init__(page)

    def go_to_list_page(self, category_id: str):
        """
        카테고리 리스트 페이지로 이동
        
        Args:
            category_id: 카테고리 ID
        """
        logger.debug(f"LP 페이지 이동: category_id={category_id}")
        list_page_url = list_url(category_id)
        self.page.goto(list_page_url, wait_until="domcontentloaded", timeout=30000)
        logger.info(f"LP 페이지 이동 완료: category_id={category_id}")

    def wait_for_list_page_load(self):
        """
        리스트 페이지 로드 대기
        """
        logger.debug("리스트 페이지 로드 대기")
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)

    def verify_category_id_in_url(self, url: str, category_id: str) -> None:
        """
        URL에 카테고리 ID가 포함되어 있는지 확인 (Assert)
        
        Args:
            url: 확인할 URL
            category_id: 카테고리 ID
        """
        logger.debug(f"URL에 카테고리 ID 포함 확인: {category_id}")
        assert f'category={category_id}' in url, f"카테고리 ID {category_id}가 URL에 포함되어야 합니다"
