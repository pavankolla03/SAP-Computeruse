"""SAP-CUA CLI entry point."""

from __future__ import annotations

import sys

COMMANDS = {
    "run": "Run the SAP-CUA agent on a task",
    "benchmark": "Run SAPBench evaluation",
    "train": "Train the model (sft | qlora | rl)",
    "replay": "Replay a recorded trajectory",
    "inspect": "Inspect a trajectory or benchmark result",
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("SAP-CUA — SAP-Native Computer-Use Agent\n")
        print("Usage: sap-cua <command> [options]\n")
        print("Commands:")
        for cmd, desc in COMMANDS.items():
            print(f"  {cmd:<12} {desc}")
        print("\nRun 'sap-cua <command> --help' for command-specific help.")
        return 0
    cmd = sys.argv[1]
    if cmd == "run":
        from sap_cua.cli_commands import run_command
        return run_command(sys.argv[2:])
    if cmd == "benchmark":
        from sap_cua.cli_commands import benchmark_command
        return benchmark_command(sys.argv[2:])
    if cmd == "train":
        from sap_cua.cli_commands import train_command
        return train_command(sys.argv[2:])
    if cmd == "replay":
        from sap_cua.cli_commands import replay_command
        return replay_command(sys.argv[2:])
    if cmd == "inspect":
        from sap_cua.cli_commands import inspect_command
        return inspect_command(sys.argv[2:])
    print(f"Unknown command: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
