import json
import os
from pathlib import Path
import subprocess
import tempfile

import pytest


class Runtime(dict):
    def __repr__(self):
        return "Runtime(disposable, redacted)"


@pytest.fixture
def real_server():
    binary = os.environ["HERMES_APRON_BINARY"]
    with tempfile.TemporaryDirectory(prefix="apron-runtime-", dir=os.environ["TMPDIR"]) as tmp:
        root = Path(tmp)
        state = root / "state"
        secret = root / "machine"
        subprocess.run([binary, "machine-secret", "--output", str(secret)], check=True)
        log = (root / "server.log").open("w+", encoding="utf-8")
        extra_frontend = (
            ["--frontend-dir", os.environ["HERMES_APRON_FRONTEND_DIR"]]
            if os.environ.get("HERMES_APRON_FRONTEND_DIR")
            else []
        )
        proc = subprocess.Popen(
            [
                binary,
                "serve",
                "--state-dir",
                str(state),
                "--listen",
                "127.0.0.1:0",
                "--test-loopback",
                "--machine-file",
                str(secret),
                "--rooms",
                "general",
            ]
            + extra_frontend,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
        )
        try:
            # stdout is a single readiness JSON frame, never a credential.
            import select

            ready, _, _ = select.select([proc.stdout], [], [], 20)
            assert ready, "loopback test server did not become ready"
            line = proc.stdout.readline()
            assert line, "server failed to start; inspect disposable log before fixture cleanup"
            url = json.loads(line)["url"]
            yield Runtime(
                {
                    "url": url,
                    "ws": url.replace("http:", "ws:") + "/ws",
                    "token": secret.read_text(encoding="utf-8").strip(),
                    "token_file": str(secret),
                    "state": state,
                    "binary": binary,
                    "root": root,
                    "log": log,
                }
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            log.close()


@pytest.fixture
def invitation(real_server):
    output = real_server["root"] / "invitation"
    subprocess.run(
        [
            real_server["binary"],
            "invite",
            "--state-dir",
            str(real_server["state"]),
            "--output",
            str(output),
        ],
        check=True,
    )
    return output.read_text(encoding="utf-8").strip()


@pytest.fixture(autouse=True)
def register_real_hermes_platform(tmp_path, monkeypatch):
    # Isolated real upstream registry and context; no installed Hermes configuration is read.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-profile"))
    monkeypatch.setenv("HERMES_GATEWAY_LOCK_DIR", str(tmp_path / "gateway-locks"))
    from hermes_cli.plugins import PluginContext, PluginManager
    from hermes_cli.plugins_manifest import PluginManifest
    from hermes_apron.adapter import register

    manager = PluginManager(scope_key=str(tmp_path / "hermes-profile"))
    manifest = PluginManifest(name="hermes-apron", kind="platform", source="user")
    register(PluginContext(manifest, manager))
    yield
