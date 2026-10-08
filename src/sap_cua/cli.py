"""Installable SAP-CUA command line. No silent mock or training fallback."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path.cwd() / ".env", override=False)
    parser = argparse.ArgumentParser(prog="sap-cua")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Open the local workbench")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--data-dir", default=os.getenv("SAP_CUA_DATA_DIR", ".sap-cua"))
    commands.add_parser("doctor", help="Report capabilities and remaining setup")
    download = commands.add_parser("download-model", help="Download the pinned OpenCUA checkpoint")
    download.add_argument("--destination", default=".models/OpenCUA-7B")
    commands.add_parser("browser-install", help="Install Playwright Chromium")
    run = commands.add_parser("run", help="Execute a JSON workflow in an isolated SAP sandbox")
    run.add_argument("workflow", nargs="?")
    run.add_argument("--example", action="store_true")
    run.add_argument("--data-dir", default=".sap-cua")
    ground = commands.add_parser(
        "ground", help="Predict one screenshot action without executing it"
    )
    ground.add_argument("image")
    ground.add_argument("instruction")
    ground.add_argument(
        "--model-path", default=os.getenv("SAP_CUA_MODEL_PATH", ".models/OpenCUA-7B")
    )
    train = commands.add_parser("train", help="Run real LoRA/QLoRA SFT on a local CUDA device")
    train.add_argument("stage", choices=["sft", "qlora"])
    train.add_argument("--dataset", required=True)
    train.add_argument("--model-path", required=True)
    train.add_argument("--output", required=True)
    train.add_argument("--max-steps", type=int, default=100)
    train.add_argument("--validate-only", action="store_true")
    bench = commands.add_parser("benchmark", help="Run the existing mock SAPBench baseline")
    bench.add_argument("--levels", default="1,2,3,4,5")
    inspect = commands.add_parser("inspect", help="Inspect a sanitized JSON artifact")
    inspect.add_argument("path")
    args = parser.parse_args()
    os.environ.setdefault(
        "HF_HOME", str(Path(os.getenv("SAP_CUA_DATA_DIR", ".sap-cua")) / "hf-cache")
    )
    try:
        if args.command == "serve":
            if (
                args.host not in ("127.0.0.1", "localhost", "::1")
                and os.getenv("SAP_CUA_ALLOW_CONTAINER") != "1"
            ):
                parser.error(
                    "The workbench must bind to loopback. Container publishing must bind the host port to 127.0.0.1."
                )
            import uvicorn
            from sap_cua.api.main import create_app

            uvicorn.run(create_app(Path(args.data_dir)), host=args.host, port=args.port)
        elif args.command == "doctor":
            from sap_cua.services.workbench import capabilities

            print(json.dumps(capabilities(), indent=2))
        elif args.command == "download-model":
            from sap_cua.model.opencua import download_model

            print(download_model(args.destination))
        elif args.command == "browser-install":
            import subprocess, sys

            return subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])
        elif args.command == "run":
            from sap_cua.services.workbench import (
                RunStore,
                Workflow,
                example_workflow,
                execute_workflow,
            )

            if not args.example and not args.workflow:
                parser.error("Supply a workflow JSON file or --example")
            data = (
                example_workflow() if args.example else json.loads(Path(args.workflow).read_text())
            )
            result = execute_workflow(Workflow.model_validate(data), RunStore(Path(args.data_dir)))
            print(json.dumps(result, indent=2))
            return 0 if result["success"] else 1
        elif args.command == "ground":
            from PIL import Image
            from sap_cua.model.opencua import OpenCUARuntime

            with Image.open(args.image) as image:
                result = OpenCUARuntime(args.model_path).ground(image, args.instruction)
            print(result.model_dump_json(indent=2))
        elif args.command == "train":
            from sap_cua.training.sft import SFTConfig, SFTTrainer

            config = SFTConfig(
                base_model=args.model_path,
                dataset_path=args.dataset,
                output_dir=args.output,
                max_steps=args.max_steps,
                use_qlora=args.stage == "qlora",
            )
            trainer = SFTTrainer(config)
            print(
                json.dumps(trainer.dry_run() if args.validate_only else trainer.train(), indent=2)
            )
        elif args.command == "benchmark":
            from sap_cua.evaluation.sapbench.runner import BenchmarkRunner, BenchmarkConfig

            result = BenchmarkRunner(
                BenchmarkConfig(
                    model_type="mock",
                    levels=tuple(int(x) for x in args.levels.split(",")),
                    output_dir=str(Path(os.getenv("SAP_CUA_DATA_DIR", ".sap-cua")) / "benchmark"),
                )
            ).run()
            print(json.dumps(result, indent=2, default=str))
        elif args.command == "inspect":
            from sap_cua.security import sanitize_data

            print(json.dumps(sanitize_data(json.loads(Path(args.path).read_text())), indent=2))
        return 0
    except (ValueError, RuntimeError, FileNotFoundError, ImportError) as exc:
        print(f"sap-cua: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
