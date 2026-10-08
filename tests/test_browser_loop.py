from PIL import Image
from sap_cua.agent.browser_loop import run_browser_task
from sap_cua.types import ModelResponse


class Browser:
    calls = 0

    def observe(self):
        return Image.new("RGB", (112, 112))

    def execute_gui(self, action):
        self.calls += 1
        return {"success": True}


class Model:
    def act(self, *args):
        return ModelResponse(
            intent="CLICK",
            executor="gui",
            gui_action={"type": "click", "x": 0.5, "y": 0.5},
            confidence=1,
        )


def test_browser_never_accepts_model_confidence_as_completion():
    browser = Browser()
    result = run_browser_task(
        browser,
        Model(),
        "test",
        verifier=lambda _: {"success": False},
        authorize=lambda _: True,
        max_steps=2,
    )
    assert browser.calls == 2 and not result["success"]


def test_authorization_precedes_click():
    browser = Browser()
    result = run_browser_task(
        browser, Model(), "test", verifier=lambda _: {"success": True}, authorize=lambda _: False
    )
    assert browser.calls == 0 and not result["success"]


def test_independent_success_stops_loop():
    browser = Browser()
    result = run_browser_task(
        browser, Model(), "test", verifier=lambda _: {"success": True}, authorize=lambda _: True
    )
    assert result["success"] and browser.calls == 1
