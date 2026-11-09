#!/usr/bin/env python3
"""Run public dependency tooling without inherited service/Vite credentials or config."""

import os
import subprocess
import sys

ALLOWED = {
    "PATH",
    "TMPDIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "LD_LIBRARY_PATH",
    "LANG",
    "LC_ALL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "UV_PROJECT_ENVIRONMENT",
    "UV_CACHE_DIR",
    "UV_PYTHON",
    "NPM_CONFIG_CACHE",
    "NPM_CONFIG_USERCONFIG",
    "NPM_CONFIG_GLOBALCONFIG",
    "NPM_CONFIG_REGISTRY",
}
env = {name: os.environ[name] for name in ALLOWED if name in os.environ}
env.update(
    {
        "NETRC": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
)
raise SystemExit(subprocess.call(sys.argv[1:], env=env))
