import os
from pathlib import Path
import subprocess
import sys


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
