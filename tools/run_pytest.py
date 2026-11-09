"""Hermetic Hermes test process: environment contains no inherited service credentials."""

import os
import subprocess
import sys

allowed = {
    "PATH",
    "TMPDIR",
    "PYTHONPATH",
    "HERMES_HOME",
    "PYTHONNOUSERSITE",
    "PLAYWRIGHT_NODEJS_PATH",
    "LD_LIBRARY_PATH",
    "HERMES_APRON_BINARY",
    "HERMES_APRON_FRONTEND_DIR",
    "SSL_CERT_FILE",
    "CHROMIUM_EXECUTABLE",
}
env = {name: os.environ[name] for name in allowed if name in os.environ}
env["PYTHONHASHSEED"] = "0"
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *sys.argv[1:]], env=env))
