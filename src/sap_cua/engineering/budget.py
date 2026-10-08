"""Per-run reservations prevent overspending before provider calls start."""

import math
from decimal import Decimal
from threading import Lock


class Budget:
    def __init__(self, maximum: float):
        if not math.isfinite(maximum) or maximum < 0:
            raise ValueError("Invalid budget")
        self.maximum = Decimal(str(maximum))
        self.spent = Decimal(0)
        self.reserved = Decimal(0)
        self.lock = Lock()
        self.pending = {}

    def reserve(self, id: str, projected: float):
        value = Decimal(str(projected))
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid cost")
        with self.lock:
            if id in self.pending:
                raise ValueError("Duplicate reservation")
            if self.spent + self.reserved + value > self.maximum:
                raise RuntimeError("Task cost budget exceeded")
            self.reserved += value
            self.pending[id] = value

    def settle(self, id: str, actual: float):
        value = Decimal(str(actual))
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid actual cost")
        with self.lock:
            reserved = self.pending.pop(id)
            self.reserved -= reserved
            self.spent += value
            if self.spent + self.reserved > self.maximum:
                raise RuntimeError("Provider exceeded cost reservation; stop further calls")

    def release(self, id: str):
        with self.lock:
            self.reserved -= self.pending.pop(id)
