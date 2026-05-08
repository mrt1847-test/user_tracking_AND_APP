import fnmatch
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

try:
    from selenium.common.exceptions import (
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException as SeleniumTimeoutException,
        WebDriverException,
    )
    from selenium.webdriver import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    try:
        from appium.webdriver.common.appiumby import AppiumBy
    except Exception:  # pragma: no cover - appium may not be installed in unit envs
        AppiumBy = None
except Exception:  # pragma: no cover - lazy failure in environments without selenium
    ActionChains = None
    By = None
    Keys = None
    AppiumBy = None

    class SeleniumTimeoutException(Exception):
        pass

    class NoSuchElementException(Exception):
        pass

    class StaleElementReferenceException(Exception):
        pass

    class WebDriverException(Exception):
        pass


TimeoutError = SeleniumTimeoutException


def _require_selenium() -> None:
    if By is None:
        raise RuntimeError(
            "selenium is required for the Appium mobile web adapter. "
            "Install the runtime dependencies before running UI scenarios."
        )


def _coerce_timeout_ms(timeout: Optional[int], default_ms: int = 30_000) -> int:
    return timeout if timeout is not None else default_ms


def _pattern_matches(value: str, pattern: Any) -> bool:
    if isinstance(pattern, re.Pattern):
        return bool(pattern.search(value or ""))
    pattern_str = str(pattern or "")
    value = value or ""
    if "*" in pattern_str or "?" in pattern_str:
        return fnmatch.fnmatch(value, pattern_str)
    return pattern_str in value


def _text_matches(text: str, matcher: Any, exact: bool = False) -> bool:
    text = text or ""
    if isinstance(matcher, re.Pattern):
        return bool(matcher.search(text))
    target = str(matcher or "")
    if exact:
        return text.strip() == target
    return target in text


def _extract_has_text(selector: str) -> tuple[str, Optional[str]]:
    pattern = re.compile(r":has-text\((['\"])(.*?)\1\)")
    match = pattern.search(selector)
    if not match:
        return selector, None
    text = match.group(2)
    clean = pattern.sub("", selector)
    return clean.strip(), text


def _normalize_selector(selector: str) -> tuple[str, str, Optional[str], bool]:
    raw = (selector or "").strip()
    lowered = raw.lower()
    if lowered.startswith("id="):
        return "id", raw.partition("=")[2].strip(), None, False
    if lowered.startswith(("accessibility=", "a11y=")):
        return "accessibility", raw.partition("=")[2].strip(), None, False
    if lowered.startswith(("android=", "uiautomator=")):
        return "android", raw.partition("=")[2].strip(), None, False
    if lowered.startswith("class="):
        return "class", raw.partition("=")[2].strip(), None, False
    if raw.startswith("xpath"):
        _, _, remainder = raw.partition("=")
        return "xpath", remainder.strip(), None, False
    if raw.startswith("//") or raw.startswith("./") or raw.startswith(".."):
        return "xpath", raw, None, False
    if raw.startswith("text="):
        value = raw[len("text=") :].strip()
        exact = False
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1]
            exact = True
        return "text", "*", value, exact
    clean, pseudo_text = _extract_has_text(raw)
    return "css", clean or "*", pseudo_text, False


def _find_elements(target: Any, kind: str, value: str) -> list[Any]:
    _require_selenium()
    if kind == "xpath":
        return target.find_elements(By.XPATH, value)
    if kind == "text":
        return target.find_elements(By.XPATH, ".//*")
    if kind == "id":
        return target.find_elements(By.ID, value)
    if kind == "class":
        return target.find_elements(By.CLASS_NAME, value)
    if kind == "accessibility":
        by = AppiumBy.ACCESSIBILITY_ID if AppiumBy is not None else "accessibility id"
        return target.find_elements(by, value)
    if kind == "android":
        by = AppiumBy.ANDROID_UIAUTOMATOR if AppiumBy is not None else "-android uiautomator"
        return target.find_elements(by, value)
    return target.find_elements(By.CSS_SELECTOR, value)


def _build_key_name(key: str) -> str:
    key = str(key or "")
    if len(key) == 1:
        return key
    mapping = {
        "Enter": "ENTER",
        "Tab": "TAB",
        "Escape": "ESCAPE",
        "Backspace": "BACKSPACE",
        "Delete": "DELETE",
        "ArrowDown": "ARROW_DOWN",
        "ArrowUp": "ARROW_UP",
        "ArrowLeft": "ARROW_LEFT",
        "ArrowRight": "ARROW_RIGHT",
        "Home": "HOME",
        "End": "END",
        "Space": "SPACE",
    }
    return mapping.get(key, key.upper())


def _webdriver_key(key: str) -> str:
    _require_selenium()
    attr = _build_key_name(key)
    if hasattr(Keys, attr):
        return getattr(Keys, attr)
    return key


def _call_js(driver: Any, script: str, *args: Any) -> Any:
    _require_selenium()
    candidate = (script or "").strip()
    if not candidate:
        return None
    wrapped = candidate
    if "=>" in candidate or candidate.startswith("function") or candidate.startswith("("):
        return driver.execute_script(f"return ({candidate}).apply(null, arguments);", *args)
    return driver.execute_script(candidate, *args)


def _element_identity(element: Any) -> str:
    return getattr(element, "id", None) or str(id(element))


class _WaitMixin:
    def _wait_until(
        self,
        predicate: Callable[[], Any],
        timeout_ms: int,
        interval_s: float = 0.2,
        description: str = "condition",
    ) -> Any:
        deadline = time.monotonic() + max(timeout_ms, 0) / 1000.0
        last_error: Optional[Exception] = None
        while time.monotonic() <= deadline:
            try:
                result = predicate()
                if result:
                    return result
            except Exception as exc:  # pragma: no cover - depends on webdriver timing
                last_error = exc
            time.sleep(interval_s)
        if last_error:
            raise TimeoutError(f"Timed out waiting for {description}: {last_error}") from last_error
        raise TimeoutError(f"Timed out waiting for {description}")


class Locator(_WaitMixin):
    def __init__(
        self,
        session: Any,
        resolver: Callable[[], list[Any]],
        description: str = "",
    ) -> None:
        self._session = session
        self._resolver = resolver
        self._description = description or "locator"

    def _driver(self) -> Any:
        return self._session.driver

    def _resolve_all(self) -> list[Any]:
        self._session.activate()
        try:
            return list(self._resolver())
        except StaleElementReferenceException:
            return list(self._resolver())

    def _resolve_first(self) -> Any:
        elements = self._resolve_all()
        if not elements:
            raise NoSuchElementException(f"No element matched {self._description}")
        return elements[0]

    @property
    def first(self) -> "Locator":
        return self.nth(0)

    def nth(self, index: int) -> "Locator":
        def _resolver() -> list[Any]:
            items = self._resolve_all()
            if index < 0 or index >= len(items):
                return []
            return [items[index]]

        return Locator(self._session, _resolver, f"{self._description}.nth({index})")

    def all(self) -> list["Locator"]:
        return [self.nth(i) for i in range(self.count())]

    def count(self) -> int:
        return len(self._resolve_all())

    def element_handle(self) -> Any:
        try:
            return self._resolve_first()
        except Exception:
            return None

    def locator(self, selector: str, has_text: Any = None, **_: Any) -> "Locator":
        if not (selector or "").strip():
            return self
        kind, value, selector_text, selector_exact = _normalize_selector(selector)

        def _resolver() -> list[Any]:
            results: list[Any] = []
            combined_matcher = has_text if has_text is not None else selector_text
            for base in self._resolve_all():
                found = _find_elements(base, kind, value)
                for item in found:
                    if kind == "text":
                        if not _text_matches(item.text, selector_text, exact=selector_exact):
                            continue
                    if combined_matcher is not None and not _text_matches(
                        item.text, combined_matcher, exact=selector_exact
                    ):
                        continue
                    results.append(item)
            return results

        return Locator(self._session, _resolver, f"{self._description}.locator({selector!r})")

    def get_by_text(self, text: Any, exact: bool = False) -> "Locator":
        return self.locator("*", has_text=text if not exact else None)._filter_text(text, exact=exact)

    def filter(self, has: Any = None, has_text: Any = None, **_: Any) -> "Locator":
        def _resolver() -> list[Any]:
            matched: list[Any] = []
            for item in self._resolve_all():
                if has_text is not None and not _text_matches(item.text, has_text):
                    continue
                if has is not None:
                    try:
                        if hasattr(has, "count") and has.count() <= 0:
                            continue
                    except Exception:
                        continue
                matched.append(item)
            return matched

        return Locator(self._session, _resolver, f"{self._description}.filter(...)")

    def _filter_text(self, text: Any, exact: bool = False) -> "Locator":
        def _resolver() -> list[Any]:
            return [item for item in self._resolve_all() if _text_matches(item.text, text, exact=exact)]

        return Locator(self._session, _resolver, f"{self._description}.text({text!r})")

    def or_(self, other: "Locator") -> "Locator":
        def _resolver() -> list[Any]:
            merged: list[Any] = []
            seen: set[str] = set()
            for item in self._resolve_all() + other._resolve_all():
                key = _element_identity(item)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
            return merged

        return Locator(self._session, _resolver, f"{self._description}.or_({other._description})")

    def wait_for(self, state: str = "visible", timeout: Optional[int] = None) -> "Locator":
        timeout_ms = _coerce_timeout_ms(timeout)

        def _predicate() -> bool:
            elements = self._resolve_all()
            if state == "attached":
                return len(elements) > 0
            if state == "hidden":
                return len(elements) == 0 or not any(item.is_displayed() for item in elements)
            if state == "visible":
                return any(item.is_displayed() for item in elements)
            raise ValueError(f"Unsupported locator wait state: {state}")

        self._wait_until(_predicate, timeout_ms, description=f"{self._description} state={state}")
        return self

    def scroll_into_view_if_needed(self, timeout: Optional[int] = None) -> None:
        self.wait_for(state="attached", timeout=timeout)
        element = self._resolve_first()
        _call_js(self._driver(), "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)

    def click(self, timeout: Optional[int] = None, force: bool = False) -> None:
        self.wait_for(state="attached" if force else "visible", timeout=timeout)
        element = self._resolve_first()
        try:
            if not force:
                self.scroll_into_view_if_needed(timeout=timeout)
            element.click()
        except Exception:
            _call_js(self._driver(), "arguments[0].click();", element)

    def tap(self, timeout: Optional[int] = None, force: bool = False) -> None:
        self.click(timeout=timeout, force=force)

    def hover(self) -> None:
        _require_selenium()
        element = self._resolve_first()
        if ActionChains is None:
            return
        ActionChains(self._driver()).move_to_element(element).perform()

    def fill(self, value: str, timeout: Optional[int] = None) -> None:
        self.wait_for(state="attached", timeout=timeout)
        element = self._resolve_first()
        try:
            element.clear()
        except Exception:
            pass
        element.send_keys(value)

    def press(self, key: str, timeout: Optional[int] = None) -> None:
        self.wait_for(state="attached", timeout=timeout)
        self._resolve_first().send_keys(_webdriver_key(key))

    def check(self, timeout: Optional[int] = None) -> None:
        self.wait_for(state="attached", timeout=timeout)
        element = self._resolve_first()
        if not element.is_selected():
            element.click()

    def uncheck(self, timeout: Optional[int] = None) -> None:
        self.wait_for(state="attached", timeout=timeout)
        element = self._resolve_first()
        if element.is_selected():
            element.click()

    def input_value(self) -> str:
        return self.get_attribute("value") or ""

    def get_attribute(self, name: str) -> Optional[str]:
        return self._resolve_first().get_attribute(name)

    def inner_text(self, timeout: Optional[int] = None) -> str:
        self.wait_for(state="attached", timeout=timeout)
        return self._resolve_first().text

    def text_content(self, timeout: Optional[int] = None) -> str:
        return self.inner_text(timeout=timeout)

    def is_visible(self) -> bool:
        try:
            return any(item.is_displayed() for item in self._resolve_all())
        except Exception:
            return False

    def is_enabled(self) -> bool:
        try:
            return self._resolve_first().is_enabled()
        except Exception:
            return False

    def evaluate(self, script: str, *args: Any) -> Any:
        element = self._resolve_first()
        return _call_js(self._driver(), script, element, *args)

    def bounding_box(self) -> Optional[dict[str, float]]:
        try:
            rect = self._resolve_first().rect
        except Exception:
            return None
        return {
            "x": float(rect.get("x", 0.0)),
            "y": float(rect.get("y", 0.0)),
            "width": float(rect.get("width", 0.0)),
            "height": float(rect.get("height", 0.0)),
        }


class _PageContext(_WaitMixin):
    def __init__(self, session: Any, fixed_handle: Optional[str] = None) -> None:
        self._session = session
        self._fixed_handle = fixed_handle

    @property
    def pages(self) -> list["Page"]:
        if hasattr(self._session, "get_window_handles"):
            handles = self._session.get_window_handles()
        else:
            try:
                handles = list(self._session.driver.window_handles)
            except Exception:
                handles = []
        return [Page(self._session, handle) for handle in handles] or [Page(self._session)]

    def expect_page(self, timeout: Optional[int] = None) -> "_ExpectPage":
        return _ExpectPage(self._session, timeout=_coerce_timeout_ms(timeout))


class _ExpectPage(_WaitMixin):
    def __init__(self, session: Any, timeout: int = 30_000) -> None:
        self._session = session
        self._timeout = timeout
        self._before_handles: list[str] = []
        self.value: Optional[Page] = None

    def __enter__(self) -> "_ExpectPage":
        self._session.activate()
        if hasattr(self._session, "get_window_handles"):
            self._before_handles = self._session.get_window_handles()
        else:
            try:
                self._before_handles = list(self._session.driver.window_handles)
            except Exception:
                self._before_handles = []
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None:
            return

        def _new_handle() -> Optional[str]:
            if hasattr(self._session, "get_window_handles"):
                handles = self._session.get_window_handles()
            else:
                try:
                    handles = list(self._session.driver.window_handles)
                except Exception:
                    handles = []
            for handle in handles:
                if handle not in self._before_handles:
                    return handle
            return None

        if not self._before_handles:
            self.value = Page(self._session)
            return
        handle = self._wait_until(_new_handle, self._timeout, description="new page handle")
        self.value = Page(self._session, handle)


class _ExpectNavigation(_WaitMixin):
    def __init__(self, page: "Page", timeout: int = 30_000, wait_until: str = "load") -> None:
        self._page = page
        self._timeout = timeout
        self._wait_until_state = wait_until
        self._before_url = ""

    def __enter__(self) -> "_ExpectNavigation":
        self._before_url = self._page.url
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None:
            return

        def _navigated() -> bool:
            current = self._page.url
            return current != self._before_url and current != ""

        self._wait_until(_navigated, self._timeout, description="navigation")
        self._page.wait_for_load_state(self._wait_until_state, timeout=self._timeout)


class Page(_WaitMixin):
    def __init__(self, session: Any, window_handle: Optional[str] = None) -> None:
        self._session = session
        self._window_handle = window_handle
        self._default_timeout_ms = 10_000

    @property
    def _driver(self) -> Any:
        return self._session.driver

    def _activate(self) -> None:
        self._session.activate(self._window_handle)

    @property
    def context(self) -> _PageContext:
        return _PageContext(self._session, self._window_handle)

    @property
    def url(self) -> str:
        self._activate()
        try:
            return self._driver.current_url
        except Exception:
            return ""

    def title(self) -> str:
        self._activate()
        try:
            return self._driver.title
        except Exception:
            return ""

    def set_default_timeout(self, timeout: int) -> None:
        self._default_timeout_ms = timeout

    def goto(self, url: str, wait_until: str = "load") -> None:
        self._activate()
        try:
            self._driver.get(url)
        except Exception as exc:
            raise RuntimeError(
                "Cannot navigate by URL in the current native app context. "
                "Ensure the APK exposes a WEBVIEW context or replace this page object "
                "flow with native Appium selectors."
            ) from exc
        self.wait_for_load_state(wait_until)

    def go_back(self, timeout: Optional[int] = None, wait_until: str = "load") -> None:
        self._activate()
        self._driver.back()
        self.wait_for_load_state(wait_until, timeout=timeout)

    def locator(self, selector: str, has_text: Any = None, **_: Any) -> Locator:
        if not (selector or "").strip():
            return Locator(self._session, lambda: [self._driver.find_element(By.TAG_NAME, "html")], "page.root")
        kind, value, selector_text, selector_exact = _normalize_selector(selector)

        def _resolver() -> list[Any]:
            self._activate()
            found = _find_elements(self._driver, kind, value)

            combined_matcher = has_text if has_text is not None else selector_text
            matched: list[Any] = []
            for item in found:
                if kind == "text" and not _text_matches(item.text, selector_text, exact=selector_exact):
                    continue
                if combined_matcher is not None and not _text_matches(
                    item.text, combined_matcher, exact=selector_exact
                ):
                    continue
                matched.append(item)
            return matched

        return Locator(self._session, _resolver, f"page.locator({selector!r})")

    def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> Locator:
        locator = self.locator(selector)
        locator.wait_for(state="attached", timeout=timeout)
        return locator

    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        self.locator(selector).click(timeout=timeout)

    def fill(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        self.locator(selector).fill(value, timeout=timeout)

    def press(self, selector: str, key: str, timeout: Optional[int] = None) -> None:
        self.locator(selector).press(key, timeout=timeout)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        time.sleep(max(timeout_ms, 0) / 1000.0)

    def wait_for_load_state(self, state: str = "load", timeout: Optional[int] = None) -> None:
        timeout_ms = _coerce_timeout_ms(timeout, self._default_timeout_ms)

        def _ready() -> bool:
            self._activate()
            try:
                ready_state = _call_js(self._driver, "return document.readyState;")
            except Exception:
                return True
            if state in {"domcontentloaded", "interactive"}:
                return ready_state in {"interactive", "complete"}
            if state in {"load", "networkidle"}:
                return ready_state == "complete"
            return ready_state in {"interactive", "complete"}

        self._wait_until(_ready, timeout_ms, description=f"document ready state={state}")
        if state == "networkidle":
            time.sleep(0.5)

    def wait_for_url(self, url_pattern: Any, timeout: Optional[int] = None) -> None:
        timeout_ms = _coerce_timeout_ms(timeout, self._default_timeout_ms)

        def _match() -> bool:
            return _pattern_matches(self.url, url_pattern)

        self._wait_until(_match, timeout_ms, description=f"url {url_pattern}")

    def screenshot(self, path: str, timeout: Optional[int] = None) -> None:
        del timeout
        self._activate()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._driver.save_screenshot(str(output))

    def bring_to_front(self) -> None:
        self._activate()

    def is_closed(self) -> bool:
        if self._window_handle is None:
            return False
        try:
            return self._window_handle not in self._driver.window_handles
        except Exception:
            return True

    def close(self) -> None:
        self._activate()
        try:
            self._driver.close()
        except Exception:
            logger.debug("Ignoring close() in native Appium context without browser windows.")

    def expect_navigation(
        self,
        timeout: Optional[int] = None,
        wait_until: str = "load",
    ) -> _ExpectNavigation:
        return _ExpectNavigation(self, timeout=_coerce_timeout_ms(timeout), wait_until=wait_until)

    def on(self, event_name: str, handler: Any) -> None:
        logger.debug("Ignoring page.on(%s) registration in Appium adapter: %s", event_name, handler)

    def remove_listener(self, event_name: str, handler: Any) -> None:
        logger.debug(
            "Ignoring page.remove_listener(%s) in Appium adapter: %s",
            event_name,
            handler,
        )

    def evaluate(self, script: str, *args: Any) -> Any:
        self._activate()
        return _call_js(self._driver, script, *args)

    def get_by_text(self, text: Any, exact: bool = False) -> Locator:
        return self.locator("*", has_text=text if not exact else None)._filter_text(text, exact=exact)

    def get_by_role(self, role: str, name: Any = None, exact: bool = False, **_: Any) -> Locator:
        role_map = {
            "button": "button, input[type='button'], input[type='submit'], a[role='button']",
            "link": "a, [role='link']",
            "textbox": "input, textarea, [role='textbox']",
            "checkbox": "input[type='checkbox'], [role='checkbox']",
        }
        selector = role_map.get(role, f"[role='{role}']")
        loc = self.locator(selector)
        if name is None:
            return loc

        def _resolver() -> list[Any]:
            matched: list[Any] = []
            for item in loc._resolve_all():
                candidates = [
                    item.text,
                    item.get_attribute("aria-label") or "",
                    item.get_attribute("value") or "",
                    item.get_attribute("title") or "",
                ]
                if any(_text_matches(candidate, name, exact=exact) for candidate in candidates):
                    matched.append(item)
            return matched

        return Locator(self._session, _resolver, f"get_by_role({role!r}, {name!r})")

    def get_by_label(self, label: str, exact: bool = False) -> Locator:
        def _resolver() -> list[Any]:
            self._activate()
            labels = self._driver.find_elements(By.TAG_NAME, "label")
            matches: list[Any] = []
            for node in labels:
                if not _text_matches(node.text, label, exact=exact):
                    continue
                target_id = node.get_attribute("for")
                if target_id:
                    matches.extend(self._driver.find_elements(By.ID, target_id))
                else:
                    matches.extend(node.find_elements(By.CSS_SELECTOR, "input, textarea, select"))
            return matches

        return Locator(self._session, _resolver, f"get_by_label({label!r})")

    def get_by_placeholder(self, placeholder: str, exact: bool = False) -> Locator:
        return self.locator("input[placeholder], textarea[placeholder]")._filter_attr(
            "placeholder",
            placeholder,
            exact=exact,
        )

    def get_by_alt_text(self, alt_text: str, exact: bool = False) -> Locator:
        return self.locator("[alt]")._filter_attr("alt", alt_text, exact=exact)

    def get_by_title(self, title: str, exact: bool = False) -> Locator:
        return self.locator("[title]")._filter_attr("title", title, exact=exact)

    def get_by_test_id(self, test_id: str, exact: bool = False) -> Locator:
        return self.locator("[data-testid]")._filter_attr("data-testid", test_id, exact=exact)


def _filter_attr_on_locator(locator: Locator, attr_name: str, value: Any, exact: bool = False) -> Locator:
    def _resolver() -> list[Any]:
        matched: list[Any] = []
        for item in locator._resolve_all():
            attr_value = item.get_attribute(attr_name) or ""
            if _text_matches(attr_value, value, exact=exact):
                matched.append(item)
        return matched

    return Locator(locator._session, _resolver, f"{locator._description}[{attr_name}={value!r}]")


def _locator_filter_attr(self: Locator, attr_name: str, value: Any, exact: bool = False) -> Locator:
    return _filter_attr_on_locator(self, attr_name, value, exact=exact)


setattr(Locator, "_filter_attr", _locator_filter_attr)


class Expectation(_WaitMixin):
    def __init__(self, target: Any) -> None:
        self._target = target

    def _text_of_target(self) -> str:
        if isinstance(self._target, Locator):
            return self._target.inner_text()
        if isinstance(self._target, Page):
            return self._target.title()
        return str(self._target)

    def to_be_visible(self, timeout: Optional[int] = None) -> None:
        if not isinstance(self._target, Locator):
            raise AssertionError("to_be_visible expects a Locator")
        self._target.wait_for(state="visible", timeout=timeout)

    def to_be_attached(self, timeout: Optional[int] = None) -> None:
        if not isinstance(self._target, Locator):
            raise AssertionError("to_be_attached expects a Locator")
        self._target.wait_for(state="attached", timeout=timeout)

    def to_be_in_viewport(self, timeout: Optional[int] = None) -> None:
        if not isinstance(self._target, Locator):
            raise AssertionError("to_be_in_viewport expects a Locator")
        timeout_ms = _coerce_timeout_ms(timeout)

        def _in_viewport() -> bool:
            rect = self._target.bounding_box()
            if not rect:
                return False
            if rect["width"] <= 0 or rect["height"] <= 0:
                return False
            driver = self._target._driver()
            width = float(_call_js(driver, "return window.innerWidth || document.documentElement.clientWidth;") or 0)
            height = float(_call_js(driver, "return window.innerHeight || document.documentElement.clientHeight;") or 0)
            return rect["x"] < width and rect["y"] < height and rect["x"] + rect["width"] > 0 and rect["y"] + rect["height"] > 0

        self._wait_until(_in_viewport, timeout_ms, description="locator in viewport")

    def to_contain_text(self, text: Any, timeout: Optional[int] = None) -> None:
        timeout_ms = _coerce_timeout_ms(timeout)
        self._wait_until(
            lambda: _text_matches(self._text_of_target(), text, exact=False),
            timeout_ms,
            description=f"text containing {text!r}",
        )

    def to_contain_class(self, class_name: str, timeout: Optional[int] = None) -> None:
        if not isinstance(self._target, Locator):
            raise AssertionError("to_contain_class expects a Locator")
        timeout_ms = _coerce_timeout_ms(timeout)

        def _has_class() -> bool:
            classes = self._target.get_attribute("class") or ""
            return class_name in classes.split() or class_name in classes

        self._wait_until(_has_class, timeout_ms, description=f"class {class_name}")

    def to_have_url(self, url_pattern: Any, timeout: Optional[int] = None) -> None:
        if not isinstance(self._target, Page):
            raise AssertionError("to_have_url expects a Page")
        self._target.wait_for_url(url_pattern, timeout=timeout)


def expect(target: Any) -> Expectation:
    return Expectation(target)
