import os
from pathlib import Path
import subprocess
import sys


import yaml


def test_history_audit_ci_has_complete_checkout_history():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/check.yml").read_text())
    audited_jobs = [
        job
        for job in workflow["jobs"].values()
        if any("tools/audit.py" in step.get("run", "") for step in job["steps"])
    ]
    assert audited_jobs, "no CI job exercises the history audit"
    for job in audited_jobs:
        checkout = next(
            step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
        )
        assert checkout.get("with", {}).get("fetch-depth") == 0, (
            "history audit requires baseline and intermediate commits, not a shallow checkout"
        )
        assert checkout["with"].get("persist-credentials") is False


def test_public_build_tools_do_not_inherit_private_variables():
    root = Path(__file__).resolve().parents[1]
    env = {
        "PATH": os.environ["PATH"],
        "TMPDIR": os.environ["TMPDIR"],
        "VITE_PRIVATE_CANARY": "disposable-build-canary",
        "APRON_TEST_TOKEN": "disposable-runtime-canary",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/public_run.py"),
            sys.executable,
            "-c",
            "import os; assert 'VITE_PRIVATE_CANARY' not in os.environ and 'APRON_TEST_TOKEN' not in os.environ, 'SDK inherited private variables'",
        ],
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0, (
        "dependency/build tooling inherited runtime or Vite private variables"
    )
