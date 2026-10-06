"""SAPBench evaluation runner."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sap_cua.evaluation.sapbench.generator import generate_benchmark_suite
from sap_cua.model import get_model
from sap_cua.sap.mocks import get_mock_environment
from sap_cua.types import BenchmarkResult, ModelRequest, ModelResponse, TaskDefinition
from sap_cua.services.verifier import run_verifier

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    suite: str = "sapbench-v1"
    runs_per_task: int = 3
    max_steps: int = 20
    max_duration_ms: int = 300_000
    output_dir: str = "results/"
    model_type: str = "mock"
    use_mocks: bool = True
    seed: int = 42


class BenchmarkRunner:
    """Runs SAPBench benchmark against a model."""

    def __init__(self, config: BenchmarkConfig | None = None) -> None:
        self.config = config or BenchmarkConfig()
        self.env = get_mock_environment() if self.config.use_mocks else None
        self.model = get_model(self.config.model_type)
        self.results: list[BenchmarkResult] = []
        self._step_limit = self.config.max_steps

    def run(self) -> dict[str, Any]:
        """Run the full benchmark suite."""
        tasks = generate_benchmark_suite({1: 3, 2: 3, 3: 2, 4: 1, 5: 1})
        logger.info("Running SAPBench %s: %d tasks, %d runs each", self.config.suite, len(tasks), self.config.runs_per_task)
        for task in tasks:
            for run_idx in range(self.config.runs_per_task):
                result = self._run_task(task, run_idx)
                self.results.append(result)
        summary = self._summarize()
        self._save_results(summary)
        return summary

    def _run_task(self, task: TaskDefinition, run_idx: int) -> BenchmarkResult:
        run_id = f"run-{task.task_id}-{run_idx:02d}"
        logger.info("Running %s (run %d/%d)", task.task_id, run_idx + 1, self.config.runs_per_task)
        self.model.reset()
        if self.env:
            self.env.reset()
        actions_taken: list[Any] = []
        success = False
        error = None
        start = time.time()
        try:
            for step in range(self._step_limit):
                response = self.model.act(
                    instruction=task.instruction,
                    image=None,
                    history=[a.model_dump() if hasattr(a, "model_dump") else {} for a in actions_taken],
                )
                actions_taken.append(response)
                if response.gui_action:
                    logger.debug("Step %d: %s at (%.2f, %.2f)", step, response.gui_action.type,
                                 response.gui_action.x or 0, response.gui_action.y or 0)
                if response.confidence > 0.9 and step >= 2:
                    success = True
                    break
        except Exception as exc:
            error = str(exc)
            logger.error("Task %s failed: %s", task.task_id, exc)
        duration_ms = int((time.time() - start) * 1000)
        return BenchmarkResult(
            task_id=task.task_id,
            model=self.config.model_type,
            run_id=run_id,
            success=success,
            steps_taken=len(actions_taken),
            max_steps=self._step_limit,
            duration_ms=duration_ms,
            actions=[],
            error=error,
        )

    def _summarize(self) -> dict[str, Any]:
        if not self.results:
            return {"total_tasks": 0, "success_rate": 0.0}
        total = len(self.results)
        successes = sum(1 for r in self.results if r.success)
        by_level = {}
        for r in self.results:
            level = r.task_id.split("-")[1] if "-" in r.task_id else "unknown"
            by_level.setdefault(level, {"total": 0, "success": 0})
            by_level[level]["total"] += 1
            if r.success:
                by_level[level]["success"] += 1
        return {
            "suite": self.config.suite,
            "model": self.config.model_type,
            "total_runs": total,
            "successes": successes,
            "success_rate": round(successes / total, 4),
            "avg_steps": round(sum(r.steps_taken for r in self.results) / total, 2),
            "avg_duration_ms": round(sum(r.duration_ms for r in self.results) / total, 2),
            "by_level": {
                k: {"rate": round(v["success"] / v["total"], 4) if v["total"] else 0, **v}
                for k, v in by_level.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _save_results(self, summary: dict[str, Any]) -> None:
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results_file = output_dir / f"results-{self.config.suite}-{self.config.model_type}.json"
        with open(results_file, "w") as f:
            json.dump({"summary": summary, "results": [r.model_dump() for r in self.results]}, f, indent=2, default=str)
        logger.info("Results saved to %s", results_file)


def run_benchmark(suite: str = "sapbench-v1", model_type: str = "mock", output_dir: str = "results/", **kwargs: Any) -> dict[str, Any]:
    config = BenchmarkConfig(suite=suite, model_type=model_type, output_dir=output_dir, **kwargs)
    runner = BenchmarkRunner(config)
    return runner.run()
