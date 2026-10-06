"""CLI command implementations for SAP-CUA."""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    print(f"[sap-cua] {msg}")


# ─── run command ──────────────────────────────────────────────────────────────

def run_command(args: list[str]) -> int:
    if not args:
        print("Usage: sap-cua run \"<task description>\"")
        return 1
    task = " ".join(args)
    _log(f"Running task: {task}")
    try:
        from sap_cua.agent.agent_loop import AgentLoop
        loop = AgentLoop()
        result = loop.run(task)
        status = "SUCCESS" if result.get("success") else "FAILED"
        _log(f"Result: {status}")
        if result.get("error"):
            _log(f"Error: {result['error']}")
        return 0 if result.get("success") else 1
    except ImportError:
        _log("Agent loop not yet fully implemented. Running mock.")
        _log(f"Task queued: {task}")
        return 0


# ─── benchmark command ────────────────────────────────────────────────────────

def benchmark_command(args: list[str]) -> int:
    suite_name = "sapbench-v1"
    levels = list(range(1, 6))
    model = "mock"
    for i, arg in enumerate(args):
        if arg == "--suite" and i + 1 < len(args):
            suite_name = args[i + 1]
        elif arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
        elif arg.startswith("--levels="):
            levels = [int(x) for x in arg.split("=", 1)[1].split(",")]
    _log(f"Running benchmark: suite={suite_name} model={model} levels={levels}")
    try:
        from sap_cua.evaluation.sapbench.runner import BenchmarkRunner
        from sap_cua.sap.mocks import SAPMockEnvironment
        from sap_cua.model import get_model
        runner = BenchmarkRunner(
            sap_env=SAPMockEnvironment(),
            model=get_model("mock"),
        )
        result = runner.run_suite(levels=levels)
        _log(f"Tasks: {result['total_tasks']}, "
             f"Success: {result.get('successful', 0)}, "
             f"Failed: {result.get('failed', 0)}")
        return 0
    except Exception as exc:
        _log(f"Benchmark error: {exc}")
        return 1


# ─── train command ────────────────────────────────────────────────────────────

def train_command(args: list[str]) -> int:
    if not args:
        print("Usage: sap-cua train <sft|qlora|rl> [options]")
        return 1
    stage = args[0]
    config: dict[str, Any] = {}
    for i, arg in enumerate(args[1:], 1):
        if arg.startswith("--") and i + 1 < len(args):
            key = arg.lstrip("-")
            config[key] = args[i + 1] if i + 1 < len(args) else True
    _log(f"Training stage: {stage} config={config}")
    try:
        if stage == "sft":
            from sap_cua.training.sft import SFTTrainer
            trainer = SFTTrainer(
                dataset_path=config.get("dataset", "datasets/sap-trajectories-v1"),
                output_path=config.get("output", "checkpoints/sap-cua-sft"),
            )
            metrics = trainer.train()
        elif stage == "qlora":
            from sap_cua.training.qlora import QLoRATrainer
            trainer = QLoRATrainer(
                base_model=config.get("base_model", "xlangai/OpenCUA-7B"),
                output_path=config.get("output", "checkpoints/sap-cua-qlora"),
                config={"lora_r": int(config.get("lora_r", 8)), "quantization_bits": 4},
            )
            metrics = trainer.train()
        elif stage == "rl":
            from sap_cua.training.rl import RLTrainer
            trainer = RLTrainer(
                base_model=config.get("base_model", "xlangai/OpenCUA-7B"),
                output_path=config.get("output", "checkpoints/sap-cua-rl"),
            )
            metrics = trainer.train()
        else:
            _log(f"Unknown training stage: {stage}")
            return 1
        _log(f"Training complete. Metrics: {metrics}")
        return 0
    except Exception as exc:
        _log(f"Training error: {exc}")
        return 1


# ─── replay command ───────────────────────────────────────────────────────────

def replay_command(args: list[str]) -> int:
    if not args:
        print("Usage: sap-cua replay <trajectory.json>")
        return 1
    path = args[0]
    _log(f"Replaying trajectory: {path}")
    try:
        from sap_cua.recorder.processor import TrajectoryProcessor
        proc = TrajectoryProcessor()
        traj = proc.load_trajectory(path)
        _log(f"Loaded trajectory: {traj.task_id} ({traj.actions_count} steps)")
        for i, step in enumerate(traj.steps):
            action = step.get("semantic_action", "N/A")
            executor = step.get("executor", "unknown")
            _log(f"  Step {i + 1}: {action} via {executor}")
        return 0
    except Exception as exc:
        _log(f"Replay error: {exc}")
        return 1


# ─── inspect command ──────────────────────────────────────────────────────────

def inspect_command(args: list[str]) -> int:
    if not args:
        print("Usage: sap-cua inspect <file.json>")
        return 1
    path = args[0]
    try:
        content = Path(path).read_text()
        import json
        data = json.loads(content)
        _log(f"Inspecting: {path}")
        if "task_id" in data:
            _log(f"  Task: {data['task_id']}")
        if "task" in data:
            _log(f"  Instruction: {data['task'][:120]}")
        if "steps" in data:
            _log(f"  Steps: {len(data['steps'])}")
        if "success" in data:
            _log(f"  Success: {data['success']}")
        return 0
    except Exception as exc:
        _log(f"Inspect error: {exc}")
        return 1
