"""
Base Page Object 클래스
모든 Page Object의 기본이 되는 클래스
"""
from utils.mobile_web_adapter import Page, Locator, expect
from typing import Any, Optional
from urllib.parse import unquote, parse_qs, urlparse
import logging
import time
import json
import re
logger = logging.getLogger(__name__)


class BasePage:
    """모든 Page Object의 기본 클래스"""
    
    def __init__(self, page: Page):
        """
        BasePage 초기화
        
        Args:
            page: Playwright Page 객체
        """
        self.page = page
        self.timeout = 30000  # 기본 타임아웃 30초
    
    def goto(self, url: str) -> None:
        """
        페이지로 이동
        
        Args:
            url: 이동할 URL
        """
        logger.info(f"페이지 이동: {url}")
        self.page.goto(url, wait_until="domcontentloaded")

    def go_back(self, timeout: Optional[int] = None) -> None:
        """
        이전 페이지로 이동 (브라우저 뒤로가기)
        
        Args:
            timeout: 타임아웃 (기본값: self.timeout)
        """
        timeout = timeout or self.timeout
        logger.info("이전 페이지로 이동")
        self.page.go_back(timeout=timeout, wait_until="domcontentloaded")
        logger.info(f"이전 페이지 이동 완료: {self.page.url}")
    
    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        요소 클릭 (Locator 방식)
        
        Args:
            selector: CSS 선택자 또는 XPath
            timeout: 타임아웃 (기본값: self.timeout)
        """
        timeout = timeout or self.timeout
        logger.debug(f"클릭: {selector}")
        self.page.locator(selector).click(timeout=timeout)
    
    def fill(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """
        입력 필드에 값 입력 (Locator 방식)
        
        Args:
            selector: CSS 선택자 또는 XPath
            value: 입력할 값
            timeout: 타임아웃 (기본값: self.timeout)
        """
        timeout = timeout or self.timeout
        logger.debug(f"입력: {selector} = {value}")
        self.page.locator(selector).fill(value, timeout=timeout)
    
    def get_text(self, selector: str, timeout: Optional[int] = None) -> str:
        """
        요소의 텍스트 가져오기
        
        Args:
            selector: CSS 선택자 또는 XPath
            timeout: 타임아웃 (기본값: self.timeout)
            
        Returns:
            요소의 텍스트
        """
        timeout = timeout or self.timeout
        logger.debug(f"텍스트 가져오기: {selector}")
        return self.page.locator(selector).inner_text(timeout=timeout)
    
    def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> Locator:
        """
        요소가 나타날 때까지 대기
        
        Args:
            selector: CSS 선택자 또는 XPath
            timeout: 타임아웃 (기본값: self.timeout)
            
        Returns:
            Locator 객체
        """
        timeout = timeout or self.timeout
        logger.debug(f"요소 대기: {selector}")
        return self.page.wait_for_selector(selector, timeout=timeout)
    
    def wait_for_url(self, url_pattern: str, timeout: Optional[int] = None) -> None:
        """
        URL이 변경될 때까지 대기
        
        Args:
            url_pattern: URL 패턴 (정규식 또는 문자열)
            timeout: 타임아웃 (기본값: self.timeout)
        """
        timeout = timeout or self.timeout
        logger.debug(f"URL 대기: {url_pattern}")
        self.page.wait_for_url(url_pattern, timeout=timeout)

    def wait_for_module_exposure_increase(
        self,
        tracker: Any,
        baseline_count: Optional[int],
        timeout_s: float = 15.0,
        poll_ms: int = 250,
    ) -> bool:
        """
        섹션 전환 직후 Module Exposure 로그 건수가 baseline 대비 증가할 때까지 대기한다.

        Args:
            tracker: NetworkTracker 객체(또는 get_logs를 제공하는 객체)
            baseline_count: 기준 Module Exposure 건수
            timeout_s: 최대 대기 시간(초)
            poll_ms: 폴링 간격(ms)

        Returns:
            증가를 감지하면 True, 미감지면 False
        """
        if tracker is None or baseline_count is None:
            time.sleep(1)
            return False

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            current = len(tracker.get_logs("Module Exposure"))
            if current > baseline_count:
                logger.info(
                    "섹션 전환 후 Module Exposure 수신: %d건 → %d건",
                    baseline_count,
                    current,
                )
                return True
            self.page.wait_for_timeout(poll_ms)

        logger.warning(
            "섹션 전환 후 %.0fs 안에 Module Exposure가 추가되지 않았습니다(기준 %d건). "
            "해당 탭이 General/Product Exposure만 쏘거나, 노출이 스크롤 이후일 수 있습니다.",
            timeout_s,
            baseline_count,
        )
        return False

    def wait_for_product_exposure_by_goodscode(
        self,
        tracker: Any,
        goodscode: str,
        timeout_s: float = 15.0,
        poll_ms: int = 250,
    ) -> bool:
        """
        상품 클릭 전에 goodscode 기준 Product Exposure 적재를 확인한다.

        - 이미 1건 이상이면 사전 노출로 간주하고 즉시 통과
        - 0건이면 timeout 내 첫 적재(0→1 이상)까지 폴링

        Args:
            tracker: NetworkTracker 객체(또는 get_logs_by_goodscode를 제공하는 객체)
            goodscode: 상품 코드
            timeout_s: 최대 대기 시간(초)
            poll_ms: 폴링 간격(ms)

        Returns:
            이미 적재되어 있었거나 대기 중 수신되면 True, 미수신이면 False
        """
        if tracker is None:
            return False

        baseline_pe = len(tracker.get_logs_by_goodscode(goodscode, "Product Exposure"))
        if baseline_pe > 0:
            logger.info(
                "상품 클릭 전 Product Exposure가 이미 적재됨 (goodscode=%s, %d건). 사전 노출 — 추가 대기 생략",
                goodscode,
                baseline_pe,
            )
            return True

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            current_pe = len(tracker.get_logs_by_goodscode(goodscode, "Product Exposure"))
            if current_pe > baseline_pe:
                logger.info(
                    "상품 클릭 전 Product Exposure 수신 (goodscode=%s): %d건 → %d건",
                    goodscode,
                    baseline_pe,
                    current_pe,
                )
                return True
            self.page.wait_for_timeout(poll_ms)

        logger.warning(
            "상품 클릭 전 %.0fs 안에 goodscode=%s에 대한 Product Exposure가 수신되지 않았습니다(기준 %d건). "
            "트래킹 지연·미발화일 수 있습니다.",
            timeout_s,
            goodscode,
            baseline_pe,
        )
        return False

    def wait_for_general_exposure_increase(
        self,
        tracker: Any,
        baseline_count: Optional[int],
        spm: Any = None,
        timeout_s: float = 15.0,
        poll_ms: int = 250,
    ) -> bool:
        """
        General UI 노출(스크롤) 이후 General.Exposure.Event 적재가 baseline보다 늘어날 때까지 대기한다.

        Args:
            tracker: NetworkTracker (get_logs, get_general_exposure_logs_by_spm)
            baseline_count: 스크롤 직전 시점의 건수(호출부에서 측정). None이면 대기 생략.
            spm: module_config ``general_exposure``에서 추출한 SPM(문자열 또는 문자열 리스트).
                 None이면 전체 General Exposure 건수만 비교한다.
            timeout_s: 최대 대기 시간(초)
            poll_ms: 폴링 간격(ms)

        Returns:
            증가를 감지하면 True, 타임아웃·tracker 없음이면 False
        """
        if tracker is None or baseline_count is None:
            time.sleep(1)
            return False

        def current_ge_count() -> int:
            if not spm:
                return len(tracker.get_logs("General Exposure"))
            if isinstance(spm, str):
                return len(tracker.get_general_exposure_logs_by_spm(spm))
            if isinstance(spm, list):
                return sum(
                    len(tracker.get_general_exposure_logs_by_spm(s))
                    for s in spm
                    if isinstance(s, str) and s
                )
            return len(tracker.get_logs("General Exposure"))

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            cur = current_ge_count()
            if cur > baseline_count:
                logger.info(
                    "General Exposure 적재 증가 감지 (baseline=%d → 현재=%d, spm=%s)",
                    baseline_count,
                    cur,
                    spm,
                )
                return True
            self.page.wait_for_timeout(poll_ms)

        logger.warning(
            "%.0fs 안에 General Exposure가 baseline 대비 증가하지 않았습니다 (baseline=%d, spm=%s). "
            "트래킹 지연·미발화 또는 SPM 불일치일 수 있습니다.",
            timeout_s,
            baseline_count,
            spm,
        )
        return False

    def is_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """
        요소가 보이는지 확인
        
        Args:
            selector: CSS 선택자 또는 XPath
            timeout: 타임아웃 (기본값: self.timeout)
            
        Returns:
            요소가 보이면 True, 아니면 False
        """
        timeout = timeout or self.timeout
        try:
            self.page.locator(selector).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False
    
    def screenshot(self, path: str) -> None:
        """
        스크린샷 저장
        
        Args:
            path: 저장할 경로
        """
        logger.info(f"스크린샷 저장: {path}")
        self.page.screenshot(path=path)
    
    def get_title(self) -> str:
        """
        페이지 제목 가져오기
        
        Returns:
            페이지 제목
        """
        return self.page.title()
    
    def get_url(self) -> str:
        """
        현재 URL 가져오기
        
        Returns:
            현재 URL
        """
        return self.page.url
    
    # ============================================
    # Playwright 역할 기반 및 고급 로케이터 메서드
    # ============================================
    
    def get_by_role(self, role: str, name: str = None, **kwargs) -> Locator:
        """
        역할 기반 로케이터 (가장 권장되는 방법)
        
        Args:
            role: ARIA 역할 (예: "button", "textbox", "link", "heading" 등)
            name: 접근 가능한 이름 (선택사항)
            **kwargs: 추가 옵션 (checked, disabled, exact 등)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_role("button", name="검색").click()
            self.get_by_role("textbox", name="이름").fill("홍길동")
        """
        logger.debug(f"역할 기반 로케이터: role={role}, name={name}")
        return self.page.get_by_role(role, name=name, **kwargs)
    
    def get_by_text(self, text: str, exact: bool = False) -> Locator:
        """
        텍스트 기반 로케이터
        
        Args:
            text: 찾을 텍스트
            exact: 정확히 일치해야 하는지 (기본값: False)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_text("로그인").click()
            self.get_by_text("저장하기", exact=True).click()
        """
        logger.debug(f"텍스트 기반 로케이터: text={text}, exact={exact}")
        return self.page.get_by_text(text, exact=exact)
    
    def get_by_label(self, text: str, exact: bool = False) -> Locator:
        """
        라벨 기반 로케이터
        
        Args:
            text: 라벨 텍스트
            exact: 정확히 일치해야 하는지 (기본값: False)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_label("이메일").fill("test@example.com")
        """
        logger.debug(f"라벨 기반 로케이터: text={text}, exact={exact}")
        return self.page.get_by_label(text, exact=exact)
    
    def get_by_placeholder(self, text: str, exact: bool = False) -> Locator:
        """
        Placeholder 기반 로케이터
        
        Args:
            text: Placeholder 텍스트
            exact: 정확히 일치해야 하는지 (기본값: False)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_placeholder("검색어를 입력하세요").fill("노트북")
        """
        logger.debug(f"Placeholder 기반 로케이터: text={text}, exact={exact}")
        return self.page.get_by_placeholder(text, exact=exact)
    
    def get_by_alt_text(self, text: str, exact: bool = False) -> Locator:
        """
        Alt 텍스트 기반 로케이터 (이미지용)
        
        Args:
            text: Alt 텍스트
            exact: 정확히 일치해야 하는지 (기본값: False)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_alt_text("로고").click()
        """
        logger.debug(f"Alt 텍스트 기반 로케이터: text={text}, exact={exact}")
        return self.page.get_by_alt_text(text, exact=exact)
    
    def get_by_title(self, text: str, exact: bool = False) -> Locator:
        """
        Title 속성 기반 로케이터
        
        Args:
            text: Title 텍스트
            exact: 정확히 일치해야 하는지 (기본값: False)
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_title("도움말").click()
        """
        logger.debug(f"Title 기반 로케이터: text={text}, exact={exact}")
        return self.page.get_by_title(text, exact=exact)
    
    def get_by_test_id(self, test_id: str) -> Locator:
        """
        Test ID 기반 로케이터 (data-testid 속성)
        
        Args:
            test_id: Test ID 값
        
        Returns:
            Locator 객체
        
        Example:
            self.get_by_test_id("search-button").click()
        """
        logger.debug(f"Test ID 기반 로케이터: test_id={test_id}")
        return self.page.get_by_test_id(test_id)
    
    def locator(self, selector: str) -> Locator:
        """
        범용 로케이터 (CSS 선택자, XPath 등)
        
        Args:
            selector: 선택자 (CSS, XPath 등)
        
        Returns:
            Locator 객체
        
        Example:
            self.locator("button.submit").click()
            self.locator("//div[@class='item']").first.click()
        """
        logger.debug(f"범용 로케이터: selector={selector}")
        return self.page.locator(selector)

    def scroll_module_into_view(self, module_locator: Locator) -> None:
        """
        모듈을 뷰포트로 스크롤

        Args:
            module_locator: 모듈 Locator 객체
        """
        logger.debug("모듈 스크롤")
        try:
            module_locator.scroll_into_view_if_needed()
        except Exception as e:
            logger.warning(f"scroll_into_view_if_needed 실패, 강제 스크롤 시도: {e}")
            module_locator.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")

    def scroll_module_into_view_bottom(self, module_locator: Locator) -> None:
        """
        모듈을 뷰포트로 스크롤

        Args:
            module_locator: 모듈 Locator 객체
        """
        logger.debug("모듈 스크롤")
        try:
            module_locator.evaluate("el => el.scrollIntoView({ block: 'end', inline: 'nearest' })")
        except Exception as e:
            logger.warning(f"scroll_into_view_if_needed 실패, 강제 스크롤 시도: {e}")
            module_locator.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")

    def get_module_parent(self, module_locator: Locator, n: int) -> Locator:
        """
        모듈의 n번째 부모 요소 찾기

        Args:
            module_locator: 모듈 Locator 객체
            n: 올라갈 부모 단계 수 (1 이상)

        Returns:
            부모 Locator 객체
        """
        if n < 1:
            raise ValueError("n은 1 이상의 정수여야 합니다.")

        logger.debug(f"모듈 부모 요소 {n}단계 찾기")

        xpath = "xpath=" + "/".join([".."] * n)
        return module_locator.locator(xpath)

    def scroll_product_into_view(self, product_locator: Locator) -> None:
        """
        상품 요소를 뷰포트로 스크롤

        Args:
            product_locator: 상품 Locator 객체
        """
        logger.debug("상품 요소 스크롤")
        try:
            product_locator.scroll_into_view_if_needed()
        except Exception as e:
            logger.warning(f"scroll_into_view_if_needed 실패, 강제 스크롤 시도: {e}")
            product_locator.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")

    def scroll_product_into_view_bottom(self, product_locator: Locator) -> None:
        """
        상품 요소를 뷰포트로 스크롤

        Args:
            product_locator: 상품 Locator 객체
        """
        logger.debug("상품 요소 스크롤")
        try:
            product_locator.scroll_into_view_if_needed()
        except Exception as e:
            logger.warning(f"scroll_into_view_if_needed 실패, 강제 스크롤 시도: {e}")
            product_locator.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'end'})")            

    _SCROLL_LAZY_CONTENT_JS = """
    ({ step, horizontal }) => {
        const apply = (el) => {
            if (!el) return;
            if (horizontal) el.scrollLeft += step;
            else el.scrollTop += step;
        };
        const se = document.scrollingElement || document.documentElement;
        const candidates = [];
        if (se) candidates.push(se);
        const stack = [document.body];
        while (stack.length) {
            const el = stack.pop();
            if (!el) continue;
            for (const c of el.children) stack.push(c);
            const st = getComputedStyle(el);
            const ox = st.overflowX;
            const oy = st.overflowY;
            const canY = !horizontal && (oy === 'auto' || oy === 'scroll' || oy === 'overlay')
                && el.scrollHeight > el.clientHeight + 1;
            const canX = horizontal && (ox === 'auto' || ox === 'scroll' || ox === 'overlay')
                && el.scrollWidth > el.clientWidth + 1;
            if (canY || canX) candidates.push(el);
        }
        let pick = null;
        let maxRemain = -1;
        for (const el of candidates) {
            const remain = horizontal
                ? el.scrollWidth - el.clientWidth
                : el.scrollHeight - el.clientHeight;
            if (remain > maxRemain) {
                maxRemain = remain;
                pick = el;
            }
        }
        if (pick) apply(pick);
    }
    """

    def _scroll_for_lazy_content(
        self,
        scroll_step_px: int,
        horizontal: bool,
        container_selector: Optional[str],
    ) -> None:
        """지연 로딩 콘텐츠를 위해 스크롤한다. window만 쓰지 않고 실제 overflow 영역도 움직인다."""
        if container_selector:
            self.page.evaluate(
                """
                ({ sel, step, horizontal }) => {
                    const el = document.querySelector(sel);
                    if (!el) return;
                    if (horizontal) el.scrollLeft += step;
                    else el.scrollTop += step;
                }
                """,
                {"sel": container_selector, "step": scroll_step_px, "horizontal": horizontal},
            )
            return
        self.page.evaluate(
            self._SCROLL_LAZY_CONTENT_JS,
            {"step": scroll_step_px, "horizontal": horizontal},
        )

    def scroll_until_selector_appears(
        self,
        selector: str,
        target_index: int = 0,
        timeout_ms: int = 7000,
        scroll_step_px: int = 600,
        pause_ms: int = 150,
        container_selector: Optional[str] = None,
        horizontal: bool = False,
    ) -> Locator:
        """
        요소가 DOM에 등장할 때까지 짧은 간격으로 스크롤을 반복한다.

        무한 스크롤/지연 렌더링 페이지에서 "처음엔 DOM에 없다가 스크롤 시 생성"되는
        요소를 기다릴 때 사용한다.

        Args:
            selector: 등장 여부를 확인할 CSS/XPath 선택자
            target_index: selector 매칭 결과 중 목표 인덱스(0-based). 기본 0(첫 번째)
            timeout_ms: 최대 대기 시간(ms). 기본 7000
            scroll_step_px: 1회 스크롤 거리(px)
            pause_ms: 스크롤 후 대기 시간(ms)
            container_selector: 스크롤 컨테이너 선택자(None이면 문서 + 가장 큰 overflow 영역 + 휠 보조)
            horizontal: True면 가로 스크롤, False면 세로 스크롤

        Returns:
            등장한 요소의 Locator(first)

        Raises:
            TimeoutError: timeout 내 요소가 DOM에 등장하지 않은 경우
        """
        if target_index < 0:
            raise ValueError("target_index는 0 이상의 정수여야 합니다.")

        deadline = time.time() + (timeout_ms / 1000.0)
        candidates = self.page.locator(selector)
        target = candidates.nth(target_index)
        axis = "x" if horizontal else "y"
        logger.debug(
            "요소 등장 대기 스크롤 시작: selector=%s, target_index=%s, timeout_ms=%s, step=%spx, axis=%s, container=%s",
            selector, target_index, timeout_ms, scroll_step_px, axis, container_selector
        )

        while time.time() < deadline:
            n = candidates.count()
            if n > target_index:
                logger.debug("요소 DOM 등장 확인: %s (count=%s, need_index=%s)", selector, n, target_index)
                return target
            if n > 0:
                logger.debug(
                    "아직 매칭 부족: selector=%s, count=%s, target_index=%s (동일 data-spm가 페이지에 더 필요할 수 있음)",
                    selector,
                    n,
                    target_index,
                )

            self._scroll_for_lazy_content(scroll_step_px, horizontal, container_selector)
            time.sleep(pause_ms / 1000.0)

        n_final = candidates.count()
        raise TimeoutError(
            f"요소가 timeout 내 DOM에 등장하지 않았습니다: selector={selector!r}, "
            f"target_index={target_index}, timeout_ms={timeout_ms}, "
            f"step={scroll_step_px}, axis={axis}, last_count={n_final}"
        )

    def ensure_locator_in_horizontal_view(
        self,
        target_locator: Locator,
        parent_locator: Optional[Locator] = None,
        timeout_ms: int = 5000,
        pause_ms: int = 120,
    ) -> None:
        """
        대상 요소가 가로 스크롤 컨테이너의 뷰포트 안으로 들어오도록 보정한다.

        - parent_locator가 주어지면 해당 모듈 내부에서 가장 가까운 가로 스크롤 조상을 탐색
        - 없으면 target 기준으로 조상을 탐색
        - 컨테이너를 찾지 못하면 scrollIntoView로 폴백
        """
        deadline = time.time() + (timeout_ms / 1000.0)
        target = target_locator.first

        last_state = None

        while time.time() < deadline:
            try:
                moved = target.evaluate(
                    """
                    (el, root) => {
                        if (!el) return { done: false, reason: "no-element" };

                        const rootNode = root || null;
                        let p = el.parentElement;
                        let scroller = null;
                        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
                        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

                        const canScrollX = (node) => {
                            if (!node) return false;
                            const st = getComputedStyle(node);
                            const ox = st.overflowX;
                            return (ox === 'auto' || ox === 'scroll' || ox === 'overlay')
                                && node.scrollWidth > node.clientWidth + 1;
                        };

                        const getViewportIntersectionRatio = (rect) => {
                            if (!rect || rect.width <= 0 || rect.height <= 0) return 0;
                            const ix = Math.max(
                                0,
                                Math.min(rect.right, viewportWidth) - Math.max(rect.left, 0)
                            );
                            const iy = Math.max(
                                0,
                                Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0)
                            );
                            const intersectionArea = ix * iy;
                            const elementArea = rect.width * rect.height;
                            if (elementArea <= 0) return 0;
                            return intersectionArea / elementArea;
                        };

                        while (p) {
                            if (rootNode && p === rootNode.parentElement) break;
                            if (canScrollX(p)) {
                                scroller = p;
                                break;
                            }
                            if (rootNode && p === rootNode) break;
                            p = p.parentElement;
                        }

                        if (!scroller) {
                            el.scrollIntoView({ block: 'center', inline: 'center' });
                            const r = el.getBoundingClientRect();
                            const viewportRatio = getViewportIntersectionRatio(r);
                            return {
                                done: viewportRatio > 0,
                                reason: "fallback-scrollIntoView",
                                viewportRatio
                            };
                        }

                        const sr = scroller.getBoundingClientRect();
                        const tr = el.getBoundingClientRect();
                        const centerDelta = (tr.left + tr.width / 2) - (sr.left + sr.width / 2);
                        const before = scroller.scrollLeft;
                        scroller.scrollLeft += centerDelta;
                        const after = scroller.scrollLeft;

                        const tr2 = el.getBoundingClientRect();
                        const insideX = tr2.left >= sr.left && tr2.right <= sr.right;
                        const movedPx = Math.abs(after - before);
                        const viewportRatio = getViewportIntersectionRatio(tr2);
                        const done = viewportRatio > 0;
                        return { done, reason: "scroller", moved: movedPx, insideX, viewportRatio };
                    }
                    """,
                    parent_locator.element_handle() if parent_locator else None,
                )

                last_state = moved
                if isinstance(moved, dict) and moved.get("done"):
                    return
            except Exception as e:
                # evaluate 실패 시 기본 스크롤 폴백 (성공 확인 전에는 return 하지 않음)
                logger.debug(f"ensure_locator_in_horizontal_view evaluate 실패: {e}")
                try:
                    target.scroll_into_view_if_needed()
                    viewport_ratio = target.evaluate(
                        """
                        el => {
                            const r = el.getBoundingClientRect();
                            const vw = window.innerWidth || document.documentElement.clientWidth || 0;
                            const vh = window.innerHeight || document.documentElement.clientHeight || 0;
                            if (!r || r.width <= 0 || r.height <= 0) return 0;
                            const ix = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
                            const iy = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
                            const area = r.width * r.height;
                            return area > 0 ? (ix * iy) / area : 0;
                        }
                        """
                    )
                    if viewport_ratio and viewport_ratio > 0:
                        return
                except Exception as fallback_error:
                    logger.debug(f"ensure_locator_in_horizontal_view fallback 실패: {fallback_error}")

            time.sleep(pause_ms / 1000.0)

        raise TimeoutError(
            f"가로 스크롤 보정 실패: timeout_ms={timeout_ms}, last_state={last_state}"
        )

    _VIEWPORT_OVERLAP_JS = """
        el => {
            const r = el.getBoundingClientRect();
            const vw = window.innerWidth || document.documentElement.clientWidth || 0;
            const vh = window.innerHeight || document.documentElement.clientHeight || 0;
            if (!r || r.width <= 0 || r.height <= 0) return 0;
            const ix = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
            const iy = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
            const area = r.width * r.height;
            return area > 0 ? (ix * iy) / area : 0;
        }
    """

    def _viewport_intersection_ratio(self, locator: Locator) -> Optional[float]:
        """뷰포트와 겹치는 면적 비율(0~1). 실패 시 None."""
        try:
            ratio = locator.evaluate(self._VIEWPORT_OVERLAP_JS)
            return float(ratio) if ratio is not None else None
        except Exception:
            return None

    def _is_locator_in_viewport(self, locator: Locator, min_ratio: float = 0.01) -> bool:
        r = self._viewport_intersection_ratio(locator)
        return r is not None and r >= min_ratio

    def swipe_until_target_visible(
        self,
        target: Locator,
        module_locator: Locator,
        max_swipes: int = 6,
        pause_ms: int = 200,
    ) -> bool:
        """
        module_locator 하위 첫 `.swiper` 요소의 `el.swiper.slideNext()`만 사용해 슬라이드를 넘긴다.
        (포인터 드래그/drag_to 없음)
        """
        sw_nodes = module_locator.locator(".swiper")
        if sw_nodes.count() == 0:
            logger.debug("swiper info: module 내 .swiper 없음")
            final_ratio = self._viewport_intersection_ratio(target)
            logger.warning(
                "swipe_until_target_visible 실패 요약: final_ratio=%s, reason=no_.swiper",
                final_ratio,
            )
            return False

        swiper = sw_nodes.first

        for i in range(max_swipes):
            ratio = self._viewport_intersection_ratio(target)
            if ratio is not None and ratio > 0:
                return True

            try:
                move = swiper.evaluate(
                    """
                    el => {
                        const s = el.swiper;
                        if (!s) return { ok: false, reason: "no-swiper" };
                        const before = s.activeIndex;
                        s.slideNext();
                        return {
                            ok: true,
                            before,
                            after: s.activeIndex,
                            isBeginning: s.isBeginning,
                            isEnd: s.isEnd,
                            allowTouchMove: s.allowTouchMove,
                        };
                    }
                    """
                )
            except Exception as e:
                logger.warning("swiper slideNext evaluate 실패: i=%s, error=%s", i, e)
                logger.debug("swiper slideNext 예외 상세", exc_info=True)
                return False

            if isinstance(move, dict) and move.get("ok"):
                before = move.get("before")
                after = move.get("after")
                if before is not None and after is not None and before == after:
                    logger.warning(
                        "swiper activeIndex 변화 없음 (잘못된 .swiper 이거나 다른 구조): "
                        "move[%s]=%s",
                        i,
                        move,
                    )

            self.page.wait_for_timeout(pause_ms)

        final_ok = self._is_locator_in_viewport(target)
        final_ratio = self._viewport_intersection_ratio(target)
        if not final_ok:
            counts = {
                "swiper": module_locator.locator(".swiper").count(),
                "swiper-container": module_locator.locator(".swiper-container").count(),
                "swiper-wrapper": module_locator.locator(".swiper-wrapper").count(),
            }
            sw_box = sw_nodes.first.bounding_box()
            logger.warning(
                "swipe_until_target_visible 실패 요약: final_ratio=%s, descendant_counts=%s, "
                "first_.swiper_bounding_box=%s",
                final_ratio,
                counts,
                sw_box,
            )
        return final_ok

    def get_product_code(self, product_locator: Locator) -> Optional[str]:
        """
        상품 코드 가져오기

        Args:
            product_locator: 상품 Locator 객체

        Returns:
            상품 코드 (data-montelena-goodscode 속성 값)
        """
        logger.debug("상품 코드 가져오기")
        attr_name = "data-montelena-goodscode"
        try:
            value = product_locator.get_attribute(attr_name)
            if value:
                return value
            # 현재 요소에서 못 찾으면 부모 노드에서 찾기
            return product_locator.locator("xpath=..").get_attribute(attr_name)
        except Exception as e:
            logger.warning(f"상품 코드 조회 실패: {e}")
            return None
       
    def get_product_code_in_json(self, product_locator: Locator) -> Optional[str]:
        """
        상품 코드 가져오기

        Args:
            product_locator: 상품 Locator 객체

        Returns:
            상품 코드 (data-montelena-object-origin 속성 값)
        """
        logger.debug("상품 코드 가져오기")
        data_attr = product_locator.get_attribute("data-montelena-object-origin")
       
        try:
            # 2. JSON 파싱
            data_json = json.loads(data_attr)
            goods_code = data_json.get("goodscode")
            
            logger.info(f"상품 코드: {goods_code}")
            return goods_code
        except json.JSONDecodeError:
            logger.error("JSON 파싱 실패")
            return None


    def get_product_by_code(self, goodscode: str) -> Locator:
        """
        상품 번호로 상품 요소 찾기

        Args:
            goodscode: 상품 번호

        Returns:
            상품 Locator 객체
        """
        logger.debug(f"상품 번호로 상품 찾기: {goodscode}")
        return self.page.locator(f'a[data-montelena-goodscode="{goodscode}"]').nth(0)

    def get_by_role_and_click(self, role: str, name: str = None, timeout: Optional[int] = None, **kwargs) -> None:
        """
        역할 기반 로케이터로 요소 찾아서 클릭
        
        Args:
            role: ARIA 역할
            name: 접근 가능한 이름
            timeout: 타임아웃 (기본값: self.timeout)
            **kwargs: 추가 옵션
        """
        timeout = timeout or self.timeout
        logger.debug(f"역할 기반 클릭: role={role}, name={name}")
        self.get_by_role(role, name=name, **kwargs).click(timeout=timeout)
    
    def get_by_role_and_fill(self, role: str, value: str, name: str = None, timeout: Optional[int] = None, **kwargs) -> None:
        """
        역할 기반 로케이터로 입력 필드 찾아서 값 입력
        
        Args:
            role: ARIA 역할 (보통 "textbox")
            value: 입력할 값
            name: 접근 가능한 이름
            timeout: 타임아웃 (기본값: self.timeout)
            **kwargs: 추가 옵션
        """
        timeout = timeout or self.timeout
        logger.debug(f"역할 기반 입력: role={role}, name={name}, value={value}")
        self.get_by_role(role, name=name, **kwargs).fill(value, timeout=timeout)
    
    def get_by_text_and_click(self, text: str, exact: bool = False, timeout: Optional[int] = None) -> None:
        """
        텍스트 기반 로케이터로 요소 찾아서 클릭
        
        Args:
            text: 텍스트
            exact: 정확히 일치해야 하는지
            timeout: 타임아웃 (기본값: self.timeout)
        """
        timeout = timeout or self.timeout
        logger.debug(f"텍스트 기반 클릭: text={text}")
        self.get_by_text(text, exact=exact).click(timeout=timeout)
    
    def click_and_expect_dialog(self, selector: str = None, locator: Locator = None, timeout: Optional[int] = None, accept: bool = True) -> None:
        """
        요소를 클릭하고 얼럿이 나타나는 것을 기대하며 처리 (page.on 방식)
        
        Args:
            selector: 클릭할 요소의 선택자 (selector 또는 locator 중 하나 필수)
            locator: 클릭할 Locator 객체 (selector 또는 locator 중 하나 필수)
            timeout: 타임아웃 (기본값: self.timeout)
            accept: True면 확인 버튼 클릭, False면 취소 버튼 클릭 (기본값: True)
            
        Raises:
            ValueError: selector와 locator 둘 다 제공되지 않은 경우
            TimeoutError: 얼럿이 나타나지 않은 경우
        """
        if selector is None and locator is None:
            raise ValueError("selector 또는 locator 중 하나를 제공해야 합니다.")
        
        timeout = timeout or self.timeout
        action = "수락" if accept else "취소"
        logger.debug(f"얼럿을 기대하며 클릭 (timeout: {timeout}ms, {action})")
        
        # 얼럿 처리용 변수
        dialog_handled = False
        dialog_message = None
        dialog_error = None
        
        def handle_dialog(dialog):
            """얼럿 핸들러"""
            nonlocal dialog_handled, dialog_message
            dialog_message = dialog.message
            logger.debug(f"얼럿 감지됨: {dialog_message}")
            try:
                if accept:
                    dialog.accept()
                    logger.debug(f"얼럿 확인 버튼 클릭: {dialog_message}")
                else:
                    dialog.dismiss()
                    logger.debug(f"얼럿 취소 버튼 클릭: {dialog_message}")
                dialog_handled = True
            except Exception as e:
                nonlocal dialog_error
                dialog_error = e
                logger.error(f"얼럿 처리 중 오류: {e}")
        
        # 얼럿 리스너 등록 (클릭 전에 설정해야 함)
        self.page.on("dialog", handle_dialog)
        
        try:
            # 클릭 실행
            if locator:
                logger.debug("Locator를 사용하여 클릭")
                locator.click(timeout=timeout)
            else:
                logger.debug(f"Selector를 사용하여 클릭: {selector}")
                self.click(selector, timeout=timeout)
            
            logger.debug("클릭 완료, 얼럿 대기 중...")
            
            # 얼럿이 처리될 때까지 대기 (최대 timeout)
            deadline = time.time() + (timeout / 1000.0)
            while time.time() < deadline:
                if dialog_handled:
                    logger.info(f"얼럿 {action} 완료: {dialog_message}")
                    return
                if dialog_error:
                    raise dialog_error
                time.sleep(0.1)  # 100ms 간격으로 체크
            
            # 타임아웃 발생
            if not dialog_handled:
                raise TimeoutError(f"얼럿이 나타나지 않았습니다 (timeout: {timeout}ms)")
                
        except Exception as e:
            logger.error(f"얼럿 처리 중 오류 발생: {e}")
            raise
        finally:
            # 리스너 제거
            try:
                self.page.remove_listener("dialog", handle_dialog)
            except Exception:
                pass  # 리스너가 없을 수 있음
    
    # ============================================
    # URL 파싱 헬퍼 메서드
    # ============================================
    
    def parse_url(self, url: str):
        """
        URL을 파싱하여 ParseResult 객체 반환
        
        Args:
            url: 파싱할 URL
            
        Returns:
            ParseResult 객체
        """
        return urlparse(url)
    
    def parse_query_params(self, url: str):
        """
        URL의 쿼리 파라미터를 파싱하여 딕셔너리로 반환
        
        Args:
            url: 파싱할 URL
            
        Returns:
            쿼리 파라미터 딕셔너리
        """
        parsed_url = urlparse(url)
        return parse_qs(parsed_url.query)
    
    def decode_url(self, encoded_url: str) -> str:
        """
        URL 인코딩된 문자열을 디코딩
        
        Args:
            encoded_url: 인코딩된 URL 문자열
            
        Returns:
            디코딩된 문자열
        """
        return unquote(encoded_url)
    
    # ============================================
    # 네트워크 트래킹 관련 헬퍼 메서드
    # ============================================
    
    @staticmethod
    def wait_until_pdp_pv_collected(tracker, goodscode: str, page: Page, timeout_ms: int = 15000, poll_interval: float = 0.3) -> None:
        """
        PDP PV 로그 수집이 확인될 때까지 폴링
        해당 goodscode에 대한 PDP PV 로그 수신 시 logger.info 출력 후 종료
        
        Args:
            tracker: NetworkTracker 인스턴스
            goodscode: 상품 코드
            page: Playwright Page 객체
            timeout_ms: 타임아웃 (밀리초, 기본값: 15000)
            poll_interval: 폴링 간격 (초, 기본값: 0.3)
        """
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            logs = tracker.get_pdp_pv_logs_by_goodscode(goodscode)
            if logs:
                logger.info(f"PDP PV 수집 확인됨: goodscode={goodscode}")
                return
            time.sleep(poll_interval)
        logger.warning(f"PDP PV 수집 대기 타임아웃 ({timeout_ms}ms): goodscode={goodscode}")
        time.sleep(2)

    def get_module_by_spmc(self, module_spmc: str) -> Locator:
        """
        특정 모듈을 spmc로 찾아 반환
        
        Args:
            module_spmc: 모듈 SPM 코드
        
        Returns:
            모듈 Locator 객체
        """
        logger.debug(f"페이지에서 spmc로 모듈 찾기: {module_spmc}")
        return self.page.locator(f".module-exp-spm-c[data-spm='{module_spmc}']")

    def get_module_by_spmc_in_div(self, module_spmc: str) -> Locator:
        """
        특정 모듈을 spmc로 찾아 반환
        
        Args:
            module_spmc: 모듈 SPM 코드
        
        Returns:
            모듈 Locator 객체
        """
        logger.debug(f"페이지에서 spmc로 모듈 찾기: {module_spmc}")
        return self.page.locator(f"div[data-spm='{module_spmc}']")

    def verify_keyword_in_url(self, page_type: str, timeout: int = 10000) -> None:
        """
        URL에 특정 키워드가 포함되어 있는지 확인 (Assert)
        
        Args:
            page_type: 페이지 타입 ("구매하기", "선물하기")
        """
        keyword = ""
        if "구매하기" in page_type or page_type == "가입신청":
            keyword = "checkout"
        elif "선물하기" in page_type:
            keyword = "gift"
        elif page_type == "상담신청":
            keyword = "cbp"
        else:
            # 시나리오에 정의되지 않은 타입이 들어올 경우
            raise ValueError(f"정의되지 않은 페이지 타입입니다: {page_type}")
        logger.debug(f"URL에 특정 키워드 포함 확인: {keyword}")
        try:
            # re.IGNORECASE를 추가하여 대소문자 구분 없이 더 견고하게 검증합니다.
            expect(self.page).to_have_url(
                re.compile(f".*{keyword}.*", re.IGNORECASE), 
                timeout=timeout
            )
            logger.info(f"URL 검증 성공: {page_type} 페이지 이동 확인 완료")
            
        except AssertionError:
            actual_url = self.page.url
            error_msg = f"URL 검증 실패 | 기대 키워드: {keyword} ({page_type}) | 현재 URL: {actual_url}"
            logger.error(error_msg)
            # record_frontend_failure가 있다면 여기서 호출하면 좋습니다.
            raise AssertionError(error_msg)

    def close_popup(self, wait_seconds: float = 0):
        """
        팝업 닫기

        Args:
            wait_seconds: 팝업이 뜨기 전 대기 시간(초). 0이면 바로 닫기 시도.
        """
        logger.debug("팝업 닫기")
        if wait_seconds and wait_seconds > 0:
            time.sleep(wait_seconds)
        try:
            self.page.locator(".button__popup-close[aria-label='레이어 닫기']").click(force=True, timeout=2000)
        except:
            try:
                self.page.locator(".button__close:has-text('레이어 닫기')").click(force=True, timeout=2000)
            except:
                pass
            pass
        time.sleep(1)
