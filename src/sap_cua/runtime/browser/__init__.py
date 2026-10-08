"""Playwright browser runtime with explicit origin scope and bounded actions."""

from __future__ import annotations
import io
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image
from sap_cua.types import GUIAction
from sap_cua.security import sanitize_data


def origin(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Only scoped HTTP(S) pages are supported")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{parsed.hostname}:{port}"


class PlaywrightNotInstalledError(ImportError):
    pass


class BrowserExecutor:
    """Fresh browser context. Credentials/cookies never imported from personal profiles.

    The caller owns allowed_origins. Model output cannot expand it. Sensitive
    fields are masked for screenshots; arbitrary page secrets still need review
    before a screenshot becomes training data.
    """

    def __init__(
        self, headless=True, slow_mo=0, screenshot_dir=".sap-cua/screenshots", *, allowed_origins=()
    ):
        self.headless, self.slow_mo = headless, slow_mo
        self.screenshot_dir = Path(screenshot_dir).resolve()
        self.allowed_origins = frozenset(origin(url) for url in allowed_origins)
        self._playwright = self._browser = self._context = self._page = None

    def start(self):
        if not self.allowed_origins:
            raise ValueError("An explicit origin allowlist is required")
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless, slow_mo=self.slow_mo
            )
            self._context = self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                accept_downloads=False,
                service_workers="block",
            )
            self._context.route("**/*", self._route)
            # Browser tasks need HTTP, not WebSockets; block exfiltration channels.
            self._context.route_web_socket("**/*", lambda ws: ws.close())
            self._page = self._context.new_page()
            self._page.set_default_timeout(10000)
            self._context.on("page", lambda page: page.close() if page != self._page else None)
        except Exception:
            self.close()
            raise

    def _route(self, route):
        try:
            allowed = origin(route.request.url) in self.allowed_origins
        except ValueError:
            allowed = False
        route.continue_() if allowed else route.abort("blockedbyclient")

    def _ensure_page(self):
        if self._page is None:
            raise RuntimeError("Browser is not started")

    def _check_scope(self):
        self._ensure_page()
        if origin(self._page.url) not in self.allowed_origins:
            raise PermissionError("Current page is outside the authorized scope")

    def navigate(self, url):
        self._ensure_page()
        if origin(url) not in self.allowed_origins:
            raise PermissionError("Navigation is outside the authorized scope")
        self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._check_scope()

    def click(self, selector, timeout=10000):
        self._check_scope()
        self._page.locator(selector).click(timeout=min(timeout, 10000))

    def type(self, selector, text, timeout=5000):
        self._check_scope()
        if len(text) > 16000:
            raise ValueError("Text exceeds action limit")
        self._page.locator(selector).fill(text, timeout=min(timeout, 10000))

    def observe(self) -> Image.Image:
        self._check_scope()
        masks = [
            self._page.locator(
                "input[type=password], [data-sensitive], input[autocomplete*=password]"
            )
        ]
        return Image.open(io.BytesIO(self._page.screenshot(full_page=False, mask=masks))).convert(
            "RGB"
        )

    def screenshot(self, path):
        destination = Path(path).resolve()
        if not destination.is_relative_to(self.screenshot_dir):
            raise ValueError("Screenshots must be saved inside screenshot_dir")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.observe().save(destination)
        return str(destination)

    def get_dom(self):
        self._check_scope()
        return sanitize_data(self._page.locator("body").aria_snapshot())

    def wait_for(self, selector, timeout=10000, state="visible"):
        self._check_scope()
        self._page.locator(selector).wait_for(state=state, timeout=min(timeout, 10000))

    def execute_gui(self, action: GUIAction):
        self._check_scope()
        kind = action.type.value
        if kind in ("click", "double_click", "right_click"):
            if action.x is None or action.y is None:
                raise ValueError("Click coordinates are required")
            size = self._page.viewport_size
            self._page.mouse.click(
                min(size["width"] - 1, action.x * size["width"]),
                min(size["height"] - 1, action.y * size["height"]),
                button="right" if kind == "right_click" else "left",
                click_count=2 if kind == "double_click" else 1,
            )
        elif kind == "type":
            if action.text is None or len(action.text) > 16000:
                raise ValueError("Invalid text length")
            self._page.keyboard.insert_text(action.text)
        elif kind in ("key_press", "hotkey"):
            keys = action.keys if kind == "hotkey" else [action.key]
            mapping = {
                "ctrl": "Control",
                "command": "Meta",
                "cmd": "Meta",
                "shift": "Shift",
                "alt": "Alt",
                "enter": "Enter",
                "tab": "Tab",
                "esc": "Escape",
                "backspace": "Backspace",
                "delete": "Delete",
                "space": "Space",
                "up": "ArrowUp",
                "down": "ArrowDown",
                "left": "ArrowLeft",
                "right": "ArrowRight",
            }
            if not keys or len(keys) > 3:
                raise ValueError("Invalid key combination")
            normalized = []
            for key in keys:
                if key in mapping:
                    normalized.append(mapping[key])
                elif isinstance(key, str) and len(key) == 1 and key.isalnum():
                    normalized.append(key)
                else:
                    raise ValueError("Unsupported key")
            # Keep URL-bar/devtools/system shortcuts out of model execution.
            if any(k in normalized for k in ("Meta", "Control", "Alt")) and any(
                k.lower() in ("l", "t", "n", "w", "q", "j", "i", "r") for k in normalized
            ):
                raise PermissionError("Browser-control shortcut is not an in-page action")
            self._page.keyboard.press("+".join(normalized))
        else:
            raise ValueError(f"Unsupported browser GUI action: {kind}")
        self._check_scope()
        return {"success": True, "backend": "playwright", "verified": False}

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._playwright:
                self._playwright.stop()
            self._page = self._context = self._browser = self._playwright = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
