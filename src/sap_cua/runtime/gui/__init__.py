"""Platform-native GUI executor (pyautogui / Quartz / Quartz CGEvent)."""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


# Detect available backends.
try:
    import pyautogui  # type: ignore
    _HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None  # type: ignore
    _HAS_PYAUTOGUI = False

_HAS_QUARTZ = False
if sys.platform == "darwin":
    try:
        import Quartz  # type: ignore
        import AppKit  # type: ignore
        _HAS_QUARTZ = True
    except ImportError:
        pass

_HAS_WIN = False
if sys.platform == "win32":
    try:
        import ctypes  # noqa: F401
        _HAS_WIN = True
    except ImportError:
        pass


class GUIBackendError(RuntimeError):
    """Raised when no GUI backend is available."""


class GUIExecutor:
    """Cross-platform GUI executor.

    Backends are selected in order of preference:
    - pyautogui (cross-platform)
    - Quartz (macOS, via PyObjC)
    - ctypes / Win32 (Windows)
    - Xlib (Linux, if explicitly required — not bundled here)
    """

    def __init__(
        self,
        backend: str = "auto",
        screen_width: int | None = None,
        screen_height: int | None = None,
    ) -> None:
        self.backend = self._select_backend(backend)
        self.screen_width = screen_width or self._get_screen_width()
        self.screen_height = screen_height or self._get_screen_height()
        logger.info("GUIExecutor using backend: %s", self.backend)

    # ─── Coordinate helpers ─────────────────────────────────────────────────

    def _denormalize(self, x: float, y: float) -> tuple[int, int]:
        """Convert normalized 0-1 coordinates to absolute pixels."""
        return (
            max(0, min(self.screen_width, int(round(x * self.screen_width)))),
            max(0, min(self.screen_height, int(round(y * self.screen_height)))),
        )

    # ─── Public actions ────────────────────────────────────────────────────

    def click(self, x: float, y: float, button: str = "left") -> None:
        """Click at normalized (x, y)."""
        px, py = self._denormalize(x, y)
        logger.debug("click(%s, %s) → (%d, %d)", x, y, px, py)
        if self.backend == "pyautogui":
            pyautogui.click(px, py, button=button)
        elif self.backend == "quartz":
            self._quartz_click(px, py, button=button)
        else:
            raise GUIBackendError(f"No backend for click: {self.backend}")

    def drag(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> None:
        """Drag from (x1, y1) to (x2, y2) using normalized coords."""
        sx, sy = self._denormalize(x1, y1)
        ex, ey = self._denormalize(x2, y2)
        logger.debug("drag(%s,%s)→(%s,%s) pixels=(%d,%d)→(%d,%d)", x1, y1, x2, y2, sx, sy, ex, ey)
        if self.backend == "pyautogui":
            pyautogui.moveTo(sx, sy)
            pyautogui.dragTo(ex, ey, duration=0.25, button="left")
        elif self.backend == "quartz":
            self._quartz_drag(sx, sy, ex, ey)
        else:
            raise GUIBackendError(f"No backend for drag: {self.backend}")

    def type(self, text: str, interval: float = 0.0) -> None:
        """Type a string using the current keyboard layout."""
        if self.backend == "pyautogui":
            pyautogui.typewrite(text, interval=interval)
        elif self.backend == "quartz":
            self._quartz_type(text)
        else:
            raise GUIBackendError(f"No backend for type: {self.backend}")

    def key_combo(self, keys: list[str]) -> None:
        """Press a hotkey combination (e.g. ``["ctrl", "s"]``)."""
        if self.backend == "pyautogui":
            pyautogui.hotkey(*keys)
        elif self.backend == "quartz":
            self._quartz_hotkey(keys)
        else:
            raise GUIBackendError(f"No backend for hotkey: {self.backend}")

    def screenshot(self, path: str | None = None) -> str:
        """Capture the current screen. Returns the saved path."""
        if self.backend == "pyautogui":
            img = pyautogui.screenshot()
            if path:
                img.save(path)
                return path
            return "<pyautogui-screenshot>"
        elif self.backend == "quartz":
            return self._quartz_screenshot(path)
        else:
            raise GUIBackendError(f"No backend for screenshot: {self.backend}")

    def scroll(self, direction: str, amount: int = 3) -> None:
        """Scroll in *direction* (``"up"`` / ``"down"`` / ``"left"`` / ``"right"``)."""
        if self.backend == "pyautogui":
            dy = amount if direction == "up" else -amount if direction == "down" else 0
            dx = amount if direction == "right" else -amount if direction == "left" else 0
            pyautogui.scroll(dy) if dy else pyautogui.hscroll(dx)
        elif self.backend == "quartz":
            self._quartz_scroll(direction, amount)
        else:
            raise GUIBackendError(f"No backend for scroll: {self.backend}")

    # ─── Backend selection ─────────────────────────────────────────────────

    def _select_backend(self, requested: str) -> str:
        if requested != "auto":
            if requested == "pyautogui" and not _HAS_PYAUTOGUI:
                raise GUIBackendError("pyautogui requested but not installed")
            if requested == "quartz" and not _HAS_QUARTZ:
                raise GUIBackendError("Quartz requested but PyObjC not available")
            return requested

        if _HAS_PYAUTOGUI:
            return "pyautogui"
        if _HAS_QUARTZ:
            return "quartz"
        raise GUIBackendError(
            "No GUI backend available. Install pyautogui "
            "(`pip install pyautogui`) or use macOS Quartz via PyObjC."
        )

    def _get_screen_width(self) -> int:
        if self.backend == "pyautogui":
            return pyautogui.size().width
        if self.backend == "quartz":
            return int(Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()).size.width)
        return 1920

    def _get_screen_height(self) -> int:
        if self.backend == "pyautogui":
            return pyautogui.size().height
        if self.backend == "quartz":
            return int(Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()).size.height)
        return 1080

    # ─── macOS Quartz helpers ───────────────────────────────────────────────

    def _quartz_click(self, x: int, y: int, button: str = "left") -> None:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        down_event = Quartz.CGEventCreateMouseEvent(
            None,
            Quartz.kCGEventLeftMouseDown,
            (x, y),
            Quartz.kCGMouseButtonLeft,
        )
        up_event = Quartz.CGEventCreateMouseEvent(
            None,
            Quartz.kCGEventLeftMouseUp,
            (x, y),
            Quartz.kCGMouseButtonLeft,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_event)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_event)

    def _quartz_drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        down_event = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDown, (x1, y1), Quartz.kCGMouseButtonLeft
        )
        move_event = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseDragged, (x2, y2), Quartz.kCGMouseButtonLeft
        )
        up_event = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventLeftMouseUp, (x2, y2), Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_event)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_event)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_event)

    def _quartz_type(self, text: str) -> None:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        for ch in text:
            event = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(event, len(ch), ch)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _quartz_hotkey(self, keys: list[str]) -> None:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        # Simple implementation: just press the last key.
        # Production code would track modifier flags.
        key = keys[-1]
        event = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _quartz_scroll(self, direction: str, amount: int) -> None:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        dy = amount if direction == "up" else -amount if direction == "down" else 0
        event = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, dy
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def _quartz_screenshot(self, path: str | None) -> str:
        if not _HAS_QUARTZ:
            raise GUIBackendError("Quartz not available")
        from Quartz import CGImage  # type: ignore  # noqa: F401
        display_id = Quartz.CGMainDisplayID()
        image = Quartz.CGDisplayCreateImage(display_id)
        if path is None:
            path = "/tmp/sap_cua_screenshot.png"
        # Save the CGImage to a file via NSBitmapImageRep
        from AppKit import NSBitmapImageRep, NSPNGFileType  # type: ignore
        rep = NSBitmapImageRep.alloc().initWithCGImage_(image)
        data = rep.representationUsingType_properties_(NSPNGFileType, {})
        with open(path, "wb") as fh:
            fh.write(data)
        return path
