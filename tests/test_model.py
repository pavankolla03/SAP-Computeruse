"""Unit tests for model adapters."""

from __future__ import annotations

import pytest

from sap_cua.model import MockModel, get_model


def test_mock_model_factory():
    model = get_model("mock")
    assert isinstance(model, MockModel)


def test_mock_model_observe():
    model = MockModel()
    result = model.observe(None)
    assert result["mock"] is True


def test_mock_model_act():
    model = MockModel()
    response = model.act("test instruction", image=None, history=[])
    assert response.intent is not None
    assert response.executor is not None
    assert response.confidence > 0


def test_mock_model_reset():
    model = MockModel()
    model.act("first", None, [])
    model.act("second", None, [])
    assert len(model.history) > 0
    model.reset()
    assert len(model.history) == 0
    assert model.get_action() == ""


def test_mock_model_sequence():
    model = MockModel()
    actions = []
    for i in range(6):
        response = model.act(f"step {i}", None, actions)
        actions.append({"action": response.intent})
    assert len(actions) == 6


def test_get_model_unknown_type():
    with pytest.raises(ValueError):
        get_model("unknown_model")


def test_opencua_adapter():
    from sap_cua.model import OpenCUAAdapter
    model = OpenCUAAdapter(model_path="xlangai/OpenCUA-7B", device="cpu")
    response = model.act("test", None, [])
    assert response is not None


def test_uitars_adapter():
    from sap_cua.model import UITARSAdapter
    model = UITARSAdapter(model_path="bytedance/UI-TARS-1.5-7B")
    response = model.act("test", None, [])
    assert response is not None