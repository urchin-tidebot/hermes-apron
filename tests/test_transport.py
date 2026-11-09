from hermes_apron.transport import Transport


async def test_real_greeting_and_machine_authentication(real_server):
    t = Transport(real_server["ws"], real_server["url"], real_server["token"], test_loopback=True)
    try:
        await t.connect()
        assert t.you and t.you["user_id"] == "hermes", "native machine auth never completed"
        assert t.you["roles"] == ["bot"]
    finally:
        await t.close()


async def test_out_of_order_rpc_timeout_and_cancellation():
    import asyncio
    import json
    import websockets
    import pytest
    from hermes_apron.transport import ProtocolError

    async def server(ws):
        await ws.send(
            json.dumps(
                {
                    "method": "server",
                    "params": {
                        "apron": 10,
                        "auth": ["token"],
                        "capabilities": ["future:capability"],
                    },
                }
            )
        )
        auth = json.loads(await ws.recv())
        await ws.send(
            json.dumps(
                {"id": auth["id"], "result": {"you": {"user_id": "hermes", "roles": ["bot"]}}}
            )
        )
        first, second = json.loads(await ws.recv()), json.loads(await ws.recv())
        for request in [second, first]:
            await ws.send(
                json.dumps({"id": request["id"], "result": {"method": request["method"]}})
            )
        await ws.wait_closed()

    async with websockets.serve(server, "127.0.0.1", 0) as host:
        port = host.sockets[0].getsockname()[1]
        t = Transport(
            f"ws://127.0.0.1:{port}/ws",
            f"http://127.0.0.1:{port}",
            "x" * 43,
            test_loopback=True,
            timeout=0.15,
        )
        await t.connect()
        try:
            one, two = await asyncio.gather(t.call("one"), t.call("two"))
            assert one["method"] == "one" and two["method"] == "two"
            with pytest.raises(ProtocolError, match="timed out"):
                await t.call("no-reply")
            task = asyncio.create_task(t.call("cancel"))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not t.pending
        finally:
            await t.close()
        assert not t.tasks and not t.pending


async def test_denied_errors_are_redacted_and_not_retried():
    import json
    import websockets
    import pytest
    from hermes_apron.transport import RPCError

    canary = "disposable-secret-canary"
    calls = []

    async def server(ws):
        await ws.send(
            json.dumps(
                {"method": "server", "params": {"apron": 10, "auth": ["token"], "capabilities": []}}
            )
        )
        auth = json.loads(await ws.recv())
        calls.append(auth)
        await ws.send(
            json.dumps(
                {
                    "id": auth["id"],
                    "error": {"code": -32001, "message": canary, "data": {"retry_after": 9999}},
                }
            )
        )
        await ws.wait_closed()

    async with websockets.serve(server, "127.0.0.1", 0) as host:
        port = host.sockets[0].getsockname()[1]
        t = Transport(
            f"ws://127.0.0.1:{port}/ws", f"http://127.0.0.1:{port}", "x" * 43, test_loopback=True
        )
        with pytest.raises(RPCError) as error:
            await t.connect()
        assert canary not in str(error.value) and error.value.retry_after == 60
        assert len(calls) == 1 and not t.tasks


async def test_runtime_invitation_not_in_database_logs_or_binary(real_server, invitation):
    import os
    import stat
    from pathlib import Path

    for file in real_server["state"].iterdir():
        if file.is_file() and (".db" in file.name or file.name == "server.lock"):
            assert invitation.encode() not in file.read_bytes()
    real_server["log"].flush()
    real_server["log"].seek(0)
    captured = real_server["log"].read()
    assert invitation not in captured and real_server["token"] not in captured
    import asyncio

    binary = await asyncio.to_thread(Path(real_server["binary"]).read_bytes)
    assert invitation.encode() not in binary and real_server["token"].encode() not in binary
    assert stat.S_IMODE(os.stat(real_server["token_file"]).st_mode) == 0o600
    assert stat.S_IMODE(real_server["state"].stat().st_mode) == 0o700
    assert stat.S_IMODE((real_server["state"] / "operator.sock").stat().st_mode) == 0o600


async def test_core_only_peer_keeps_completed_text_fallback(tmp_path):
    import json
    from types import SimpleNamespace
    import websockets
    from hermes_apron.adapter import ApronAdapter

    calls = []

    async def peer(ws):
        await ws.send(
            json.dumps(
                {
                    "method": "server",
                    "params": {"apron": 10, "auth": ["token"], "capabilities": ["future:unknown"]},
                }
            )
        )
        async for raw in ws:
            frame = json.loads(raw)
            calls.append(frame["method"])
            if frame["method"] == "auth":
                result = {"you": {"user_id": "hermes", "roles": ["bot"]}}
            elif frame["method"] == "message":
                result = {"message_id": "1"}
            else:
                raise AssertionError("core-only peer received fabricated optional RPC")
            await ws.send(json.dumps({"id": frame["id"], "result": result}))

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        port = host.sockets[0].getsockname()[1]
        token = tmp_path / "machine"
        token.write_text("x" * 43, encoding="utf-8")
        token.chmod(0o600)
        adapter = ApronAdapter(
            SimpleNamespace(
                extra={
                    "url": f"http://127.0.0.1:{port}",
                    "token_file": str(token),
                    "allowed_users": [],
                    "rooms": ["general"],
                    "state_dir": str(tmp_path),
                    "test_loopback": True,
                }
            )
        )
        assert await adapter.connect()
        try:
            assert not (
                await adapter.send("general", "preview", metadata={"expect_edits": True})
            ).success
            assert (await adapter.send("general", "completed answer")).success
            assert calls == ["auth", "message"]
        finally:
            await adapter.disconnect()
