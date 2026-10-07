"""Playwright-based browser executor for SAP-CUA."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PlaywrightNotInstalledError(ImportError):
    """Raised when the ``playwright`` package is not available."""


class BrowserExecutor:
    """Browser executor backed by Playwright (sync API).

    Parameters
    ----------
    headless:
        Run the browser in headless mode.
    slow_mo:
        Delay between Playwright actions (ms) for easier observation.
    screenshot_dir:
        Directory where screenshots are saved.
    """

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        screenshot_dir: str = "/tmp/sap_cua_screenshots",
    ) -> None:
        self.headless = headless
        self.slow_mo = slow_mo
        self.screenshot_dir = screenshot_dir
        self._browser = None
        self._context = None
        self._page = None

    # ─── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the browser and create a fresh context/page."""
        self._check_playwright()
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            slow_mo=self.slow_mo,
        )
        self._page = self._context.new_page()
        logger.info("BrowserExecutor started")

    def close(self) -> None:
        """Close the browser and stop the Playwright process."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if hasattr(self, "_playwright"):
                self._playwright.stop()
        except Exception as exc:
            logger.warning("Error during browser cleanup: %s", exc)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            logger.info("BrowserExecutor closed")

    # ─── Navigation ─────────────────────────────────────────────────────────

    def navigate(self, url: str) -> None:
        """Navigate to *url*.

        Parameters
        ----------
        url:
            Target SAP URL.
        """
        self._ensure_page()
        logger.info("Navigating to %s", url)
        self._page.goto(url, wait_until="networkidle", timeout=60000)

    # ─── Actions ────────────────────────────────────────────────────────────

    def click(self, selector: str, timeout: int = 10000) -> None:
        """Click the element matching *selector*.

        Parameters
        ----------
        selector:
            CSS or text selector.
        timeout:
            Max wait time (ms) for the element to appear.
        """
        self._ensure_page()
        logger.info("Clicking selector: %s", selector)
        self._page.click(selector, timeout=timeout)

    def type(self, selector: str, text: str, timeout: int = 5000) -> None:
        """Type *text* into the element matching *selector*.

        Parameters
        ----------
        selector:
            CSS selector for the input field.
        text:
            Text to type.
        timeout:
            Max wait time (ms) for the element to appear.
        """
        self._ensure_page()
        logger.info("Typing into %s: %s", selector, text[:20])
        self._page.fill(selector, text, timeout=timeout)

    def screenshot(self, path: str) -> str:
        """Capture a screenshot and save it to *path*.

        Returns
        -------
        The absolute path where the screenshot was saved.
        """
        self._ensure_page()
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._page.screenshot(path=path, full_page=False)
        logger.debug("Screenshot saved: %s", path)
        return os.path.abspath(path)

    def get_dom(self) -> str:
        """Return the accessibility tree (human-readable DOM)."""
        self._ensure_page()
        return self._page.accessibility.snapshot() or ""

    def wait_for(
        self, selector: str, timeout: int = 10000, state: str = "visible"
    ) -> None:
        """Wait for an element to match *state*.

        Parameters
        ----------
        selector:
            CSS selector.
        timeout:
            Max wait time (ms).
        state:
            One of ``"visible"``, ``"hidden"``, ``"attached"``, ``"detached"``.
        """
        self._ensure_page()
        logger.info("Waiting for %s to be %s", selector, state)
        self._page.wait_for_selector(selector, state=state, timeout=timeout)

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _check_playwright(self) -> None:
        try:
            import playwright  # noqa: F401
        except ImportError as exc:
            raise PlaywrightNotInstalledError(
                "playwright is required for BrowserExecutor. "
                "Install it with: pip install playwright && playwright install chromium"
            ) from exc

    def _ensure_page(self) -> None:
        if self._page is None:
            raise RuntimeError(
                "BrowserExecutor is not started. Call start() before using."
            )

    # Context manager support
    def __enter__(self) -> BrowserExecutor:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
