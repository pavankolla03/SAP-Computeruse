"""Semantic component insertion against caller-owned selectors and independent DOM checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def read(cls, value):
        if not value or value["width"] <= 0 or value["height"] <= 0:
            raise ValueError("Element has no visible bounds")
        return cls(**value)


def insertion_point(process: Box, anchor: Box, following: Box | None = None):
    if not (
        process.x <= anchor.x <= process.x + process.width
        and process.y <= anchor.y <= process.y + process.height
    ):
        raise ValueError("Anchor is outside integration process")
    x = (
        (anchor.x + anchor.width + following.x) / 2
        if following and following.x > anchor.x + anchor.width
        else anchor.x + anchor.width + 24
    )
    y = anchor.y + anchor.height / 2
    return (
        min(max(x, process.x + 2), process.x + process.width - 2),
        min(max(y, process.y + 2), process.y + process.height - 2),
    )


class ComponentInserter:
    def __init__(self, browser, selectors, *, vision_provider=None, authorize=None):
        self.browser = browser
        self.selectors = selectors
        self.vision_provider = vision_provider
        self.authorize = authorize

    def _vision(self, component, after):
        if self.vision_provider is None or not callable(self.authorize):
            return {
                "success": False,
                "strategy": "dom_drag",
                "needs_vision": True,
                "verified": False,
            }
        from sap_cua.agent.browser_loop import run_browser_task

        result = run_browser_task(
            self.browser,
            self.vision_provider,
            f"Insert {component} immediately after {after}. Use only the component palette and process canvas.",
            verifier=lambda browser: {
                "success": browser._page.locator(self.selectors["component"](component)).count()
                == 1
            },
            authorize=self.authorize,
            max_steps=3,
            max_seconds=120,
        )
        return {**result, "strategy": "computer_use", "verified": result["success"]}

    def add(self, component: str, after: str):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        self.browser._check_scope()
        page = self.browser._page
        s = self.selectors
        # Selectors belong to a tenant-tested adapter, never retrieved instructions.
        existing = s["component"](component)
        if page.locator(existing).count():
            return {"success": True, "strategy": "already_present", "verified": True}
        if s.get("search") and page.locator(s["search"]).count():
            page.locator(s["search"]).fill(component)
            page.locator(s["search_result"](component)).click()
            page.locator(s["insert_after"](after)).click()
            if page.locator(existing).count():
                return {"success": True, "strategy": "search_add", "verified": True}
        process = Box.read(page.locator(s["process"]).bounding_box())
        anchor = Box.read(page.locator(s["component"](after)).bounding_box())
        next_locator = page.locator(s["following"](after))
        following = Box.read(next_locator.bounding_box()) if next_locator.count() else None
        source = Box.read(page.locator(s["palette"](component)).bounding_box())
        x, y = insertion_point(process, anchor, following)
        page.mouse.move(source.x + source.width / 2, source.y + source.height / 2)
        page.mouse.down()
        try:
            page.mouse.move(x, y, steps=15)
        finally:
            page.mouse.up()
        try:
            page.locator(existing).wait_for(state="visible", timeout=3000)
        except PlaywrightTimeout:
            return self._vision(component, after)
        return {"success": True, "strategy": "dom_drag", "verified": True}
