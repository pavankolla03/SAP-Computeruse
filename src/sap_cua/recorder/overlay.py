"""Floating overlay window for recording control."""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import tkinter as tk
    from tkinter import ttk

    _TK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TK_AVAILABLE = False


class RecorderOverlay:
    """Minimal floating tkinter window for recording control."""

    def __init__(self, title: str = "SAP-CUA Recorder") -> None:
        self.title = title
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._window: tk.Tk | None = None

    def start(self, task_id: str, mode: str) -> None:
        """Show overlay window with task name and status."""

        def _run():
            root = tk.Tk()
            self._window = root
            root.title(self.title)
            root.attributes("-topmost", True)
            root.geometry("380x130")
            root.resizable(False, False)

            ttk.Label(root, text=f"Task: {task_id}", font=("Arial", 10, "bold")).pack(pady=(10, 2))
            self._status_var = tk.StringVar(value=f"Mode: {mode}")
            ttk.Label(root, textvariable=self._status_var).pack(pady=2)
            btn_frame = ttk.Frame(root)
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="PAUSE", command=self._call("on_pause")).grid(row=0, column=0, padx=4)
            ttk.Button(btn_frame, text="STOP", command=self._call("on_stop")).grid(row=0, column=1, padx=4)
            ttk.Button(btn_frame, text="SUCCESS", command=self._call("on_mark_success")).grid(row=0, column=2, padx=4)
            ttk.Button(btn_frame, text="FAILURE", command=self._call("on_mark_failure")).grid(row=0, column=3, padx=4)
            root.mainloop()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def show_controls(self) -> None:
        if self._window is not None:
            self._window.deiconify()

    def update_status(self, status: str) -> None:
        if hasattr(self, "_status_var"):
            self._status_var.set(status)

    def hide(self) -> None:
        if self._window is not None:
            try:
                self._window.withdraw()
            except Exception:
                pass

    def on_pause(self, callback: Callable[[], None]) -> None:
        self._callbacks["on_pause"] = callback

    def on_stop(self, callback: Callable[[], None]) -> None:
        self._callbacks["on_stop"] = callback

    def on_mark_success(self, callback: Callable[[], None]) -> None:
        self._callbacks["on_mark_success"] = callback

    def on_mark_failure(self, callback: Callable[[], None]) -> None:
        self._callbacks["on_mark_failure"] = callback

    def _call(self, key: str) -> Callable[[], None]:
        cb = self._callbacks.get(key, lambda: None)
        return cb
