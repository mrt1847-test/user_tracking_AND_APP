"""
G마켓 홈 페이지 객체
"""
import re
import logging

from pages.base_page import BasePage
from utils.mobile_web_adapter import Page, expect, Locator
from utils.urls import base_url

logger = logging.getLogger(__name__)


class HomePage(BasePage):
    """G마켓 홈 페이지"""
    
    # 선택자 정의
    SEARCH_INPUT = "input[placeholder*='검색']"
    SEARCH_BUTTON = "button[type='submit']"
    LOGIN_BUTTON = "로그인"
    LOGOUT_BUTTON = "text=로그아웃"
    
    def __init__(self, page: Page):
        """
        HomePage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        super().__init__(page)
        self.base_url = base_url()
    
    def navigate(self) -> None:
        """홈 페이지로 이동"""
        logger.info("홈 페이지로 이동")
        self.goto(self.base_url)
    
    def fill_search_input(self, keyword: str) -> None:
        """
        검색어 입력
        
        Args:
            keyword: 검색할 상품명
        """
        logger.debug(f"검색어 입력: {keyword}")
        self.page.fill("input[name='keyword']", keyword)
    
    def click_search_button(self) -> None:
        """검색 버튼 클릭 (fieldset 내 검색 버튼)"""
        logger.debug("검색 버튼 클릭")
        self.page.locator("fieldset").get_by_role("button", name="검색", exact=True).click()
        logger.info("검색 버튼 클릭 완료")
    
    def search_product(self, keyword: str) -> None:
        """
        홈화면에서 특정 keyword로 검색
        검색 버튼 클릭 → 검색어 입력창 노출 대기 → 검색어 입력 → 검색 실행
        
        Args:
            keyword: 검색어
        """
        runtext = f"Home > {keyword} 검색"
        logger.info("%s 시작", runtext)
        # 검색 오픈 버튼: button.link__search 우선, 없으면 role="button" name="검색" 폴백
        search_open = self.page.locator("button.link__search")
        if search_open.count() > 0:
            search_open.first.click()
        else:
            self.page.get_by_role("button", name="검색", exact=True).click()
        # 검색어 입력 영역(span.box__text-field 내 input[name='keyword'])이 뜰 때까지 대기
        search_input = self.page.locator("span.box__text-field input[name='keyword']")
        search_input.wait_for(state="visible", timeout=10000)
        search_input.fill(keyword)
        self.page.locator("fieldset").get_by_role("button", name="검색", exact=True).click()
        logger.info("%s 종료", runtext)
    
    def wait_for_search_results(self, keyword: str | None = None, timeout: int = 30000) -> None:
        """검색 결과 페이지 로드 대기.

        networkidle은 트래킹·폴링 등으로 M웹에서 거의 만족되지 않아 타임아웃이 잦음.
        load 이벤트 후 SearchPage.verify_keyword_element_exists와 동일한 SRP UI를 기준으로 대기.
        """
        logger.debug("검색 결과 로드 대기")
        self.page.wait_for_load_state("load", timeout=timeout)
        if keyword:
            locator = self.page.locator(".box__text-field button.form__input").first
            locator.wait_for(state="visible", timeout=timeout)
            expect(locator).to_contain_text(
                re.compile(re.escape(keyword), re.IGNORECASE), timeout=timeout
            )
    
    def click_login(self) -> None:
        """로그인 버튼 클릭"""
        logger.info("로그인 버튼 클릭")
        login_button = self.page.get_by_text("로그인", exact=True)
        
        # 요소가 실제로 존재하는지 확인
        count = login_button.count()
        if count == 0:
            raise Exception("로그인 버튼을 찾을 수 없습니다")
        logger.debug(f"로그인 버튼 {count}개 발견")
        
        # 요소가 클릭 가능한 상태가 될 때까지 대기
        login_button.wait_for(state="visible", timeout=10000)
        login_button.scroll_into_view_if_needed()
        
        # 요소가 실제로 클릭 가능한지 확인
        is_visible = login_button.is_visible()
        is_enabled = login_button.is_enabled() if hasattr(login_button, 'is_enabled') else True
        logger.debug(f"로그인 버튼 상태 - visible: {is_visible}, enabled: {is_enabled}")
        
        if not is_visible:
            raise Exception("로그인 버튼이 보이지 않습니다")
        
        # 현재 URL 저장 (클릭 전)
        current_url = self.page.url
        logger.debug(f"클릭 전 URL: {current_url}")
        
        # 클릭 시도
        try:
            login_button.click(timeout=5000)
            logger.debug("일반 클릭 성공")
        except Exception as e:
            logger.warning(f"일반 클릭 실패, force 클릭 시도: {e}")
            login_button.click(force=True)
            logger.debug("force 클릭 완료")
        
        # 클릭 후 로그인 페이지로 이동했는지 확인
        try:
            # 로그인 페이지의 입력 필드가 나타날 때까지 대기
            self.page.wait_for_selector("#typeMemberInputId", timeout=5000)
            logger.info("로그인 페이지로 이동 확인됨")
        except Exception as e:
            # URL이 변경되었는지 확인
            new_url = self.page.url
            logger.warning(f"로그인 페이지 요소를 찾을 수 없음. 현재 URL: {new_url}")
            if current_url == new_url:
                raise Exception(f"로그인 버튼 클릭 후 페이지가 변경되지 않았습니다. URL: {new_url}")
        
        logger.info("로그인 버튼 클릭 완료")
    
    def is_logged_in(self) -> bool:
        """
        로그인 상태 확인
        
        Returns:
            로그인되어 있으면 True, 아니면 False
        """
        return self.is_visible("text='로그아웃'", timeout=5000)
    
    def click_logout(self) -> None:
        """로그아웃 버튼 클릭"""
        logger.info("로그아웃 버튼 클릭")
        self.click("text='로그아웃'")

    def click_cart(self) -> None:
        """장바구니 버튼 클릭"""
        logger.info("장바구니 버튼 클릭")
        self.click("[title='장바구니']")

    def click_my_page(self) -> None:
        """마이페이지 버튼 클릭"""
        logger.info("마이페이지 버튼 클릭")
        self.click(".link__myg")

    def click_rvh(self) -> None:
        """RVH 버튼 클릭"""
        logger.info("RVH 버튼 클릭")
        self.click(".link__rvh")

    def _home_section_tab_link(self, section_name: str) -> tuple[str, Locator]:
        """
        `section_name`에 해당하는 홈 섹션 탭 링크(`a.link__tab`)를 찾는다.

        Returns:
            (정규화된 이름, 해당 링크 Locator)

        Raises:
            ValueError: 탭을 찾지 못한 경우
        """
        name = (section_name or "").strip()
        if not name:
            raise ValueError("section_name이 비어 있습니다.")

        tab_links: Locator = self.page.locator("li.list-item__tab a.link__tab")
        by_alt = tab_links.filter(has=self.page.locator(f'img[alt="{name}"]'))
        if by_alt.count() > 0:
            return name, by_alt.first
        by_text = tab_links.filter(has_text=re.compile(f"^{re.escape(name)}$"))
        if by_text.count() == 0:
            raise ValueError(
                f"홈 섹션 탭을 찾을 수 없습니다: {name!r} "
                "(img alt 또는 탭 텍스트와 정확히 일치해야 합니다)"
            )
        return name, by_text.first

    def click_home_section_tab(self, section_name: str) -> None:
        """
        홈 상단 섹션 탭(`li.list-item__tab` > `a.link__tab`)을 클릭한다.

        아이콘형 탭은 `img[alt]`가 section_name 과 일치할 때,
        텍스트형 탭은 링크(하위 span 등)에 보이는 텍스트가 section_name 과 일치할 때 매칭한다.

        Args:
            section_name: 탭 식별 문자열 (예: 슈퍼딜, 이마트몰, 베스트)

        Raises:
            ValueError: 해당 이름의 탭을 찾지 못한 경우
        """
        name, target = self._home_section_tab_link(section_name)

        logger.info("홈 섹션 탭 클릭: %s", name)
        target.wait_for(state="attached", timeout=10000)
        # 가로 스크롤 탭 바: 기본 scroll_into_view_if_needed는 세로 위주로 동작하는 경우가 많아
        # inline: center 로 가로 스크롤 영역 안에서 탭이 뷰포트에 들어오게 한다.
        target.evaluate(
            """el => el.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'auto' })"""
        )
        target.wait_for(state="visible", timeout=5000)
        target.click(timeout=self.timeout)

    def expect_home_section_tab_active(self, section_name: str, timeout: int = None) -> None:
        """
        해당 섹션 탭이 선택된 상태인지 검증한다.

        선택 시 부모 `li.list-item__tab`에 `list-item__tab--active` 클래스가 붙는 동작을 기준으로 한다.

        Args:
            section_name: `click_home_section_tab`과 동일한 식별 문자열
            timeout: 검증 대기 시간(ms). None이면 self.timeout 사용.

        Raises:
            ValueError: 탭을 찾지 못한 경우
            AssertionError: 해당 탭의 li에 active 클래스가 없을 때(Playwright expect)
        """
        _, link = self._home_section_tab_link(section_name)
        parent_li = link.locator("xpath=..")
        timeout_ms = timeout if timeout is not None else self.timeout
        expect(parent_li).to_contain_class("list-item__tab--active", timeout=timeout_ms)

    def wait_for_rvh_page_load(self, timeout: int = None) -> bool:
        """
        RVH 페이지 로드 대기.
        span.desc-txt "쇼핑 히스토리예요." 요소가 보일 때까지 대기한 뒤 표시 여부를 반환한다.

        Args:
            timeout: 타임아웃(ms). None이면 self.timeout 사용.

        Returns:
            요소가 보이면 True, 타임아웃 등으로 실패하면 False.
        """
        timeout = timeout or self.timeout
        logger.debug("RVH 페이지 로드 대기 (span.desc-txt '쇼핑 히스토리예요.')")
        try:
            loc = self.page.locator("span.desc-txt", has_text="쇼핑 히스토리예요.")
            loc.wait_for(state="visible", timeout=timeout)
            visible = loc.is_visible()
            if visible:
                logger.info("RVH 페이지 로드 확인됨")
            return visible
        except Exception as e:
            logger.warning("RVH 페이지 로드 대기 실패: %s", e)
            return False

    def is_recently_viewed_displayed(self, timeout: int = None) -> bool:
        """
        최근 본 내역이 노출되는지 확인.
        strong.list-rvh__date (날짜 헤딩, 예: 2026.02.24 오늘) 요소가 보이면 True.

        Args:
            timeout: 타임아웃(ms). None이면 self.timeout 사용.

        Returns:
            노출되어 있으면 True, 아니면 False.
        """
        timeout = timeout or self.timeout
        logger.debug("최근 본 내역 노출 확인 (strong.list-rvh__date)")
        try:
            loc = self.page.locator("strong.list-rvh__date").first
            loc.wait_for(state="visible", timeout=timeout)
            visible = loc.is_visible()
            if visible:
                logger.info("최근 본 내역 노출 확인됨")
            return visible
        except Exception as e:
            logger.warning("최근 본 내역 노출 확인 실패: %s", e)
            return False

    def get_product_in_module(self):
        """
        모듈 내 상품 요소 찾기
        """
        logger.debug("모듈 내 상품 요소 찾기")
        return self.page.locator(".list-rvh__content-item--product a").first


    def find_module_by_spmc(self, spmc: str, target_index: int = 0) -> Locator:
        """
        spmc 값으로 모듈을 찾는다.

        Args:
            spmc: `data-spm` 속성값(예: today_itemcarousel).
            target_index: 동일 spmc 매칭 요소 중 **0-based** 인덱스(첫 번째=0). feature의 n은 1-based이므로 호출부에서 n-1을 넘긴다.

        1) `[data-spm]` + has_text(spmc) — 노출 텍스트와 spmc가 맞는 경우(또는 하위에 해당 문자열이 있는 경우)
        2) `[data-spm='spmc']` — 속성만으로 DOM에 이미 충분히 있을 때(스크롤 없음)
        3) 위로 부족하면 `scroll_until_selector_appears`로 스크롤하며 탐색
        """
        logger.debug(f"spmc 로 모듈 찾기: {spmc} (0-based index={target_index})")
        nth_index = max(int(target_index), 0)

        by_text = self.page.locator("[data-spm]", has_text=spmc)
        if by_text.count() > nth_index:
            logger.debug("data-spm + has_text 즉시 매칭")
            return by_text.nth(nth_index)

        by_attr = self.page.locator(f"[data-spm='{spmc}']")
        if by_attr.count() > nth_index:
            logger.debug("data-spm 속성 일치로 즉시 매칭 (스크롤 생략)")
            return by_attr.nth(nth_index)

        base_page = BasePage(self.page)
        return base_page.scroll_until_selector_appears(
            f"[data-spm='{spmc}']",
            target_index=nth_index,
        )

    def log_module_visibility_diagnostics(
        self, spmc: str, target_index: int = 0
    ) -> dict:
        """
        Playwright에서만 모듈/썸네일이 안 보이는 등 원인 조사용 로그.

        ``find_module_by_spmc`` 와 동일한 1·2단계 매칭으로 대상 locator 를 고른 뒤,
        카운트·visibility·첫 ``img.image__thumbnail``·모듈 루트의 style/rect/outerHTML 일부를 남긴다.

        Args:
            spmc: ``data-spm`` 식별값 (예: today_shortsdeal).
            target_index: 0-based 인덱스.

        Returns:
            수집한 진단 dict (로거에도 INFO 로 덤프).
        """
        nth_index = max(int(target_index), 0)
        by_text = self.page.locator("[data-spm]", has_text=spmc)
        by_attr = self.page.locator(f"[data-spm='{spmc}']")
        text_count = by_text.count()
        attr_count = by_attr.count()

        if text_count > nth_index:
            module = by_text.nth(nth_index)
            match_mode = "data-spm+has_text"
        elif attr_count > nth_index:
            module = by_attr.nth(nth_index)
            match_mode = "data-spm=attr"
        else:
            module = by_attr.nth(nth_index)
            match_mode = "fallback_attr_nth"

        out: dict = {
            "spmc": spmc,
            "target_index": nth_index,
            "match_mode": match_mode,
            "by_text_count": text_count,
            "by_attr_count": attr_count,
        }

        mod_count = module.count()
        out["module_count"] = mod_count

        module_visible = False
        if mod_count > 0:
            try:
                module_visible = module.first.is_visible()
            except Exception as e:
                out["module_visible_error"] = repr(e)
        out["module_visible"] = module_visible

        if mod_count == 0:
            logger.info(
                "모듈 visibility 진단: DOM 매칭 0건 — %s",
                out,
            )
            return out

        root = module.first
        img = root.locator("img.image__thumbnail").first
        if img.count() > 0:
            try:
                out["thumbnail"] = img.evaluate(
                    """(el) => {
                        const cs = getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return {
                            src: el.src,
                            currentSrc: el.currentSrc,
                            complete: el.complete,
                            naturalWidth: el.naturalWidth,
                            naturalHeight: el.naturalHeight,
                            loading: el.loading,
                            decoding: el.decoding,
                            display: cs.display,
                            visibility: cs.visibility,
                            opacity: cs.opacity,
                            width: rect.width,
                            height: rect.height,
                        };
                    }"""
                )
            except Exception as e:
                out["thumbnail_eval_error"] = repr(e)
        else:
            out["thumbnail"] = None

        try:
            out["module_root"] = root.evaluate(
                """(el) => {
                    const cs = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return {
                        display: cs.display,
                        visibility: cs.visibility,
                        opacity: cs.opacity,
                        width: rect.width,
                        height: rect.height,
                        html: el.outerHTML.slice(0, 500),
                    };
                }"""
            )
        except Exception as e:
            out["module_root_eval_error"] = repr(e)

        logger.info("모듈 visibility 진단: %s", out)
        return out

    def get_button_by_name(self, module_title: str, module: Locator) -> Locator:
        """
        모듈 내 General 버튼/링크를 찾아 뷰포트로 스크롤한 뒤 Locator를 반환한다.
        """
        logger.debug(f"모듈 내 General 요소 찾기: {module_title}")
        if module_title == "today_itemcarousel":
            button = module.locator(".gds-heading__side-action").first
        elif module_title == "today_newlowest":
            button = module.locator(".gds-heading__side-action").first
        elif module_title == "today_campaign":
            button = module.locator(".link__coupon ").first
        elif module_title == "today_hmjfy0":
            button = module.locator(".link__item-feed").first
        else:
            raise ValueError(f"모듈 내 General 요소 찾기 실패: {module_title}")

        try:
            button.scroll_into_view_if_needed(timeout=10000)
        except Exception as e:
            logger.warning("General 요소 scroll_into_view_if_needed 실패: %s", e)
        return button
