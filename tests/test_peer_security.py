"""Untrusted synthetic peers and real OS-process consumer reservation regressions."""

import asyncio
from contextlib import asynccontextmanager
import json
import os
import secrets
import sys
from types import SimpleNamespace

import websockets

from hermes_apron.adapter import ApronAdapter


@asynccontextmanager
async def peer_server(respond=None, capabilities=()):
    authenticated = []

    async def peer(ws):
        await ws.send(
            json.dumps(
                {
                    "method": "server",
                    "params": {"apron": 10, "auth": ["token"], "capabilities": list(capabilities)},
                }
            )
        )
        async for raw in ws:
            frame = json.loads(raw)
            method = frame["method"]
            if method == "ping":
                await ws.send(json.dumps({"method": "pong"}))
                continue
            if method == "auth":
                authenticated.append(frame["params"]["token"])
                result = {"you": {"user_id": "hermes", "roles": ["bot"]}}
            elif method == "room_list":
                result = {"joined": [{"room_id": "general", "latest_log_id": "1"}]}
            elif method == "history":
                result = {"history_log_id": "0", "messages": [], "more": False}
            else:
                result = {"message_id": "2"}
            if respond is not None:
                result = respond(frame, result)
            await ws.send(json.dumps({"id": frame["id"], "result": result}))
            if isinstance(result, dict) and result.get("emit"):
                await ws.send(json.dumps(result["emit"]))

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        port = host.sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}", authenticated


def adapter_config(tmp_path, url, token=None):
    path = tmp_path / "machine"
    path.write_text(token or secrets.token_urlsafe(32), encoding="utf-8")
    path.chmod(0o600)
    return {
        "url": url,
        "token_file": str(path),
        "allowed_users": [],
        "rooms": ["general"],
        "state_dir": str(tmp_path / "consumer"),
        "test_loopback": True,
    }


CHILD_CONSUMER = """
import asyncio,json,sys,os
from types import SimpleNamespace
from hermes_cli.plugins import PluginContext,PluginManager
from hermes_cli.plugins_manifest import PluginManifest
from hermes_apron.adapter import ApronAdapter,register
register(PluginContext(PluginManifest(name='hermes-apron',kind='platform',source='user'),PluginManager(scope_key=os.environ['HERMES_HOME'])))
async def main():
    adapter=ApronAdapter(SimpleNamespace(extra=json.loads(sys.argv[1])))
    try:
        assert await adapter.connect()
        print('READY',flush=True)
        await asyncio.to_thread(sys.stdin.readline)
    finally:
        await adapter.disconnect()
asyncio.run(main())
"""


async def test_reconnect_rotation_cannot_consume_under_another_credentials_lease(tmp_path):
    from pathlib import Path

    async with peer_server() as (url, authenticated):
        token_a, token_b = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        extra = adapter_config(tmp_path, url, token_a)
        adapter = ApronAdapter(SimpleNamespace(extra=extra))
        child = None
        assert await adapter.connect()
        try:
            Path(extra["token_file"]).write_text(token_b, encoding="utf-8")
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                CHILD_CONSUMER,
                json.dumps({**extra, "state_dir": str(tmp_path / "child")}),
                env={**os.environ, "HERMES_HOME": str(tmp_path / "child-profile")},
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            async with asyncio.timeout(10):
                ready = await child.stdout.readline()
                assert ready == b"READY\n", (await child.stderr.read()).decode()
            assert authenticated.count(token_b) == 1
            await adapter.transport.ws.close()
            worker = adapter.worker
            async with asyncio.timeout(4):
                while not worker.done() and authenticated.count(token_b) < 2:
                    await asyncio.sleep(0.02)
            assert authenticated.count(token_b) == 1, (
                "adapter authenticated rotated credential without its consumer lease"
            )
            assert worker.done() and worker.exception() is None
            assert adapter.fatal_error_code == "credential_changed"
            assert adapter.transport is None and adapter.state is None
            assert adapter.credential_lease is None
            duplicate = ApronAdapter(
                SimpleNamespace(extra={**extra, "state_dir": str(tmp_path / "duplicate")})
            )
            assert await duplicate.connect() is False, "second process reservation was bypassed"
            await duplicate.disconnect()
            child.stdin.write(b"stop\n")
            await child.stdin.drain()
            async with asyncio.timeout(5):
                assert await child.wait() == 0
            child = None
            # Explicit lifecycle restart acquires B's lease before authenticating B.
            assert await adapter.connect()
            assert authenticated[-1] == token_b
        finally:
            await adapter.disconnect()
            if child is not None:
                if child.returncode is None:
                    child.kill()
                await child.communicate()
