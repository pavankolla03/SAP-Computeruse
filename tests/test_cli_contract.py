import json
import os
import subprocess
import sys


def run(*args, cwd):
    result = subprocess.run(
        [sys.executable, "-m", "sap_cua.cli", *args], cwd=cwd, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_installed_cli_workflow_and_benchmark(tmp_path):
    result = run("run", "--example", "--data-dir", str(tmp_path / "runs"), cwd=tmp_path)
    assert result["success"] and result["backend"] == "mock"
    benchmark = run("benchmark", "--levels", "1", cwd=tmp_path)
    assert benchmark["backend"] == "mock" and benchmark["total_runs"] == 9
    assert benchmark["successes"] == 0
    assert run("doctor", cwd=tmp_path)["version"] == "0.2.0"
