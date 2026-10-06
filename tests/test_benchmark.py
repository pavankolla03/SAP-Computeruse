"""Unit tests for benchmark task generator."""

from __future__ import annotations

import pytest

from sap_cua.evaluation.sapbench.generator import (
    generate_task,
    generate_benchmark_suite,
    TASK_TEMPLATES,
)


def test_generate_basic_task():
    task = generate_task("nav_open_suite")
    assert "Integration Suite" in task.instruction
    assert task.difficulty == 1
    assert task.task_id.startswith("SB-")


def test_generate_package_task():
    task = generate_task("create_package")
    assert "package" in task.instruction.lower()
    assert task.verify is not None


def test_generate_with_seed():
    task1 = generate_task("create_package", seed=42)
    task2 = generate_task("create_package", seed=42)
    assert task1.task_id == task2.task_id


def test_generate_unknown_template():
    with pytest.raises(ValueError):
        generate_task("nonexistent_template")


def test_generate_benchmark_suite():
    suite = generate_benchmark_suite({1: 2, 2: 2, 3: 1})
    assert len(suite) == 5
    level_1 = [t for t in suite if t.task_id.startswith("SB-L1-")]
    assert len(level_1) == 2


def test_all_levels_have_tasks():
    for level in range(1, 6):
        suite = generate_benchmark_suite({level: 1})
        assert len(suite) == 1, f"Level {level} should have at least one task template"