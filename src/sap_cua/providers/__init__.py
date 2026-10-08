"""Provider-independent inference contracts. Providers propose; executors act."""

from __future__ import annotations

from typing import Any, Protocol

from sap_cua.types import ModelResponse


class ComputerUseProvider(Protocol):
    name: str

    def observe(self, image: Any) -> dict: ...
    def plan(self, instruction: str, history: list[dict]) -> dict: ...
    def ground(self, instruction: str, image: Any, history: list[dict]) -> ModelResponse: ...
    def act(self, instruction: str, image: Any, history: list[dict]) -> ModelResponse: ...
    def verify_visual_state(self, image: Any, criterion: str) -> dict: ...


class OpenCUAProvider:
    name = "open_cua"

    def __init__(self, **kwargs):
        from sap_cua.model import OpenCUAAdapter

        self.adapter = OpenCUAAdapter(**kwargs)

    def observe(self, image):
        return self.adapter.observe(image)

    def plan(self, instruction, history):
        return self.adapter.plan(instruction, history)

    def ground(self, instruction, image, history):
        return self.adapter.act(instruction, image, history)

    def act(self, instruction, image, history):
        return self.ground(instruction, image, history)

    def verify_visual_state(self, image, criterion):
        return {
            "success": False,
            "reason": "Use an independent DOM/API verifier; action generation is not visual proof",
        }


class ProviderRegistry:
    def __init__(self):
        self.factories = {"open_cua": OpenCUAProvider}

    def register(self, name, factory):
        if name in self.factories:
            raise ValueError("Provider already registered")
        self.factories[name] = factory

    def create(self, name, **kwargs):
        if name not in self.factories:
            raise ValueError(f"Provider {name} has no configured adapter; no result was fabricated")
        return self.factories[name](**kwargs)


class ProviderFallback:
    """Fallback applies to inference only, never to uncertain external writes."""

    def __init__(self, providers):
        self.providers = providers
        self.failures = []

    def ground(self, instruction, image, history):
        self.failures = []
        for provider in self.providers:
            try:
                return provider.ground(instruction, image, history)
            except (RuntimeError, ValueError, ImportError, TimeoutError) as exc:
                self.failures.append({"provider": provider.name, "error": type(exc).__name__})
        raise RuntimeError("All configured grounding providers failed; human escalation required")

    def act(self, instruction, image, history):
        return self.ground(instruction, image, history)


class BudgetedProvider:
    """Reserve a configured upper bound before inference; never infer pricing.

    The caller supplies a model-specific maximum-call price. Failed inference can
    still be billable, so the reservation is charged conservatively on failure.
    """

    def __init__(self, provider, budget, max_call_cost):
        self.provider, self.budget, self.max_call_cost = provider, budget, max_call_cost
        self.name = provider.name
        self.calls = 0

    def ground(self, instruction, image, history):
        import uuid

        reservation = uuid.uuid4().hex
        self.budget.reserve(reservation, self.max_call_cost)
        self.calls += 1
        try:
            return self.provider.ground(instruction, image, history)
        finally:
            self.budget.settle(reservation, self.max_call_cost)

    def act(self, instruction, image, history):
        return self.ground(instruction, image, history)
