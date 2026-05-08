import logging
import time
from pathlib import Path
from typing import Any, Optional

from utils.mobile_web_adapter import Page

logger = logging.getLogger(__name__)


class MobileWebSession:
    """Compatibility session for the native APK Appium runtime.

    The name is intentionally kept because existing fixtures and steps import
    `browser_session.page`. Under the hood this now wraps a native Android app
    driver. If the app exposes a WEBVIEW context, the session automatically
    switches to it so the existing CSS-based page objects can keep working.
    """

    def __init__(
        self,
        driver: Any,
        app_package: Optional[str] = None,
        prefer_webview: bool = True,
        webview_timeout_ms: int = 15_000,
    ) -> None:
        self.driver = driver
        self.app_package = app_package or self._capability("appPackage")
        self.prefer_webview = prefer_webview
        self.webview_timeout_ms = webview_timeout_ms
        self._context_stack: list[str] = []
        self._window_stack: list[str] = []
        self._preferred_webview: Optional[str] = None
        current_context = self.current_context
        if current_context:
            self._context_stack.append(current_context)
        current_handle = self.current_window_handle
        if current_handle:
            self._window_stack.append(current_handle)

    def _capability(self, name: str) -> Optional[str]:
        caps = getattr(self.driver, "capabilities", {}) or {}
        return caps.get(name) or caps.get(f"appium:{name}")

    @property
    def current_context(self) -> Optional[str]:
        try:
            return self.driver.current_context
        except Exception:
            return None

    @property
    def contexts(self) -> list[str]:
        try:
            return list(self.driver.contexts)
        except Exception:
            return []

    @property
    def current_window_handle(self) -> Optional[str]:
        try:
            return self.driver.current_window_handle
        except Exception:
            return None

    def get_window_handles(self) -> list[str]:
        try:
            return list(self.driver.window_handles)
        except Exception:
            return []

    def _switch_context(self, context_name: str, push: bool = True) -> bool:
        try:
            if self.current_context != context_name:
                self.driver.switch_to.context(context_name)
            if push and (not self._context_stack or self._context_stack[-1] != context_name):
                self._context_stack.append(context_name)
            return True
        except Exception as exc:
            logger.debug("Failed to switch Appium context to %s: %s", context_name, exc)
            return False

    def switch_to_native(self, push: bool = True) -> bool:
        return self._switch_context("NATIVE_APP", push=push)

    def switch_to_webview(self, timeout_ms: Optional[int] = None, push: bool = True) -> bool:
        timeout_ms = self.webview_timeout_ms if timeout_ms is None else timeout_ms
        deadline = time.monotonic() + max(timeout_ms, 0) / 1000.0
        while True:
            contexts = self.contexts
            candidates = [name for name in contexts if name != "NATIVE_APP"]
            if self._preferred_webview in candidates:
                return self._switch_context(self._preferred_webview, push=push)
            if candidates:
                package = (self.app_package or "").lower()
                preferred = next(
                    (
                        name
                        for name in candidates
                        if package and package.replace(".", "_") in name.lower().replace(".", "_")
                    ),
                    candidates[0],
                )
                self._preferred_webview = preferred
                return self._switch_context(preferred, push=push)
            if timeout_ms <= 0 or time.monotonic() >= deadline:
                return False
            time.sleep(0.25)

    def wait_for_webview_attach(self, timeout_ms: Optional[int] = None) -> bool:
        """WEBVIEW 컨텍스트가 나타날 때까지 대기만 수행한다."""
        return self.switch_to_webview(timeout_ms=timeout_ms, push=False)

    def activate(self, window_handle: Optional[str] = None) -> None:
        if window_handle:
            try:
                if self.current_window_handle != window_handle:
                    self.driver.switch_to.window(window_handle)
            except Exception as exc:
                logger.debug("Window activation skipped for native Appium session: %s", exc)
        if self.prefer_webview:
            self.switch_to_webview(timeout_ms=0, push=False)

    @property
    def page(self) -> Page:
        return Page(self)

    def page_for_handle(self, handle: str) -> Page:
        return Page(self, handle)

    def activate_app(self) -> None:
        if not self.app_package:
            return
        try:
            self.driver.activate_app(self.app_package)
            return
        except Exception:
            pass
        try:
            self.driver.execute_script("mobile: activateApp", {"appId": self.app_package})
        except Exception as exc:
            logger.debug("activate_app failed for %s: %s", self.app_package, exc)

    def reset(self) -> None:
        self.activate_app()
        if self.prefer_webview:
            self.switch_to_webview(timeout_ms=self.webview_timeout_ms, push=False)
        current_context = self.current_context
        self._context_stack = [current_context] if current_context else []
        current_handle = self.current_window_handle
        self._window_stack = [current_handle] if current_handle else []

    def switch_to(self, page: Any) -> bool:
        handle = getattr(page, "_window_handle", None)
        if handle:
            try:
                if handle not in self.get_window_handles():
                    logger.warning("MobileWebSession: window handle not found: %s", handle)
                    return False
                self.driver.switch_to.window(handle)
                if not self._window_stack or self._window_stack[-1] != handle:
                    self._window_stack.append(handle)
                return True
            except Exception as exc:
                logger.error("MobileWebSession window switch failed: %s", exc)
                return False
        self.activate()
        return True

    def restore(self) -> bool:
        if len(self._window_stack) > 1:
            self._window_stack.pop()
            try:
                self.driver.switch_to.window(self._window_stack[-1])
                return True
            except Exception as exc:
                logger.debug("Window restore skipped: %s", exc)

        if len(self._context_stack) > 1:
            self._context_stack.pop()
            return self._switch_context(self._context_stack[-1], push=False)

        logger.warning("MobileWebSession: no previous window/context to restore.")
        return False

    def get_page_stack(self) -> list[str]:
        out: list[str] = []
        current_context = self.current_context
        for context in self.contexts or ["NATIVE_APP"]:
            if not self._switch_context(context, push=False):
                continue
            try:
                out.append(f"{context}: {self.driver.current_url}")
            except Exception:
                out.append(context)
        if current_context:
            self._switch_context(current_context, push=False)
        return out

    def capture_screenshot(self, path: str) -> str:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.driver.save_screenshot(str(output))
        return str(output)
