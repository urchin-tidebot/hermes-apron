"""Untrusted synthetic peers and real OS-process consumer reservation regressions."""

import asyncio
from contextlib import asynccontextmanager
import json
import os
import secrets
import sys
from types import SimpleNamespace

import websockets
import pytest

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
            wire_result = (
                {key: value for key, value in result.items() if key != "emit"}
                if isinstance(result, dict)
                else result
            )
            await ws.send(json.dumps({"id": frame["id"], "result": wire_result}))
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
            await asyncio.to_thread(Path(extra["token_file"]).write_text, token_b, encoding="utf-8")
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


@pytest.mark.parametrize("user_id", [None, "", 1, [], {}])
async def test_transport_rejects_missing_or_wrong_bot_id(tmp_path, user_id):
    from hermes_apron.transport import Transport, ProtocolError

    fixed = False

    def respond(frame, result):
        if fixed:
            return result
        return {"you": {"roles": ["bot"], **({"user_id": user_id} if user_id is not None else {})}}

    async with peer_server(respond) as (url, _):
        t = Transport(
            url.replace("http", "ws") + "/ws", url, secrets.token_urlsafe(32), test_loopback=True
        )
        try:
            with pytest.raises(ProtocolError):
                await t.connect()
            assert not t.tasks and not t.pending and t.ws is None
        finally:
            await t.close()
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            assert await adapter.connect() is False
            assert adapter.state is None and adapter.credential_lease is None
            fixed = True
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "joined",
    [
        None,
        "bad",
        [None],
        [1],
        [{}],
        [{"room_id": []}],
        [{"room_id": ""}],
        [{"room_id": "general", "title": []}],
        [{"room_id": "general", "parent_room_id": {}}],
        [{"room_id": "general", "latest_log_id": []}],
    ],
)
async def test_bad_room_list_returns_false_and_releases_locks(tmp_path, joined):
    def respond(frame, result):
        return {"joined": joined} if frame["method"] == "room_list" else result

    async with peer_server(respond, ["rooms"]) as (url, _):
        extra = adapter_config(tmp_path, url)
        adapter = ApronAdapter(SimpleNamespace(extra=extra))
        try:
            assert await adapter.connect() is False
            assert (
                adapter.state is None
                and adapter.transport is None
                and adapter.credential_lease is None
            )
            # A corrected peer can use exactly the same OS/state reservations.
            joined_result = [{"room_id": "general"}]
            joined = joined_result
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "messages",
    [
        None,
        "bad",
        [None],
        [1],
        [{}],
        [{"room_id": []}],
        [{"room_id": "general", "log_id": []}],
        [{"room_id": "general", "message_id": "2", "log_id": "2", "from": [], "body": {}}],
        [
            {
                "room_id": "general",
                "message_id": "2",
                "log_id": "2",
                "from": {"user_id": "human"},
                "body": {"text": "x"},
                "reply_to": [],
            }
        ],
    ],
)
async def test_bad_history_returns_false_and_releases_locks(tmp_path, messages):
    from hermes_apron.state import State

    def respond(frame, result):
        if frame["method"] == "room_list":
            return {"joined": [{"room_id": "general", "latest_log_id": "2"}]}
        if frame["method"] == "history":
            return {"history_log_id": "0", "messages": messages, "more": False}
        return result

    async with peer_server(respond, ["rooms", "history"]) as (url, _):
        extra = adapter_config(tmp_path, url)
        state = State(tmp_path / "consumer")
        state.advance("general", "1")
        state.close()
        adapter = ApronAdapter(SimpleNamespace(extra=extra))
        try:
            assert await adapter.connect() is False
            assert (
                adapter.state is None
                and adapter.transport is None
                and adapter.credential_lease is None
            )
            messages = []
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "params",
    [
        None,
        [],
        {"left": [None]},
        {"joined": [None]},
        {"joined": [{"room_id": []}]},
        {"joined": [{"room_id": "general", "title": {}}]},
    ],
)
async def test_bad_room_update_stops_cleanly_without_supervisor_crash(tmp_path, params):
    emitted = False

    def respond(frame, result):
        nonlocal emitted
        if frame["method"] == "room_list" and not emitted:
            emitted = True
            return {**result, "emit": {"method": "room_update", "params": params}}
        return result

    async with peer_server(respond, ["rooms"]) as (url, authenticated):
        extra = adapter_config(tmp_path, url)
        adapter = ApronAdapter(SimpleNamespace(extra=extra))
        try:
            assert await adapter.connect()
            worker = adapter.worker
            async with asyncio.timeout(3):
                await asyncio.shield(worker)
            assert worker.exception() is None
            assert len(authenticated) == 1, "invalid protocol triggered unnecessary retry"
            assert (
                adapter.state is None
                and adapter.transport is None
                and adapter.credential_lease is None
            )
            assert await adapter.connect(), "invalid event leaked a consumer reservation"
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "bad_greeting",
    [
        None,
        [],
        {"apron": 10, "auth": "token"},
        {"apron": 10, "auth": [None]},
        {"apron": 10, "capabilities": [None]},
        {"apron": 10, "ping": "bad"},
        {"apron": 10, "ping": True},
    ],
)
async def test_bad_greeting_is_a_closed_protocol_error(bad_greeting):
    from hermes_apron.transport import Transport, ProtocolError

    async def peer(ws):
        await ws.send(json.dumps({"method": "server", "params": bad_greeting}))
        await ws.wait_closed()

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        url = f"http://127.0.0.1:{host.sockets[0].getsockname()[1]}"
        t = Transport(
            url.replace("http", "ws") + "/ws", url, secrets.token_urlsafe(32), test_loopback=True
        )
        with pytest.raises(ProtocolError):
            await t.connect()
        assert not t.tasks and not t.pending and t.ws is None


@pytest.mark.parametrize(
    "reply",
    [
        {"id": []},
        {"error": None},
        {"error": []},
        {"error": {"code": []}},
        {"error": {"code": -32001, "data": []}},
        {"error": {"code": -32001, "data": {"retry_after": "bad"}}},
        {"result": []},
        {"result": {"you": []}},
    ],
)
async def test_bad_rpc_reply_is_a_closed_protocol_error(reply):
    from hermes_apron.transport import Transport, ProtocolError

    async def peer(ws):
        await ws.send(json.dumps({"method": "server", "params": {"apron": 10, "auth": ["token"]}}))
        auth = json.loads(await ws.recv())
        await ws.send(json.dumps({"id": auth["id"], **reply}))
        await ws.wait_closed()

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        url = f"http://127.0.0.1:{host.sockets[0].getsockname()[1]}"
        t = Transport(
            url.replace("http", "ws") + "/ws", url, secrets.token_urlsafe(32), test_loopback=True
        )
        with pytest.raises(ProtocolError):
            await t.connect()
        assert not t.tasks and not t.pending and t.ws is None


@pytest.mark.parametrize(
    "receipt",
    [
        {},
        {"message_id": []},
        {"message_id": "2", "embeds": None},
        {"message_id": "2", "embeds": [None]},
        {"message_id": "2", "embeds": [{}]},
        {"message_id": "2", "embeds": [{"write_url": []}]},
    ],
)
@pytest.mark.parametrize("operation", ["append", "artifact", "terminal"])
async def test_bad_media_receipts_return_failure(tmp_path, receipt, operation):
    def respond(frame, result):
        return receipt if frame["method"] == "message" else result

    async with peer_server(respond, ["embed:append", "embed:upload", "embed:terminal"]) as (url, _):
        extra = adapter_config(tmp_path, url)
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir(mode=0o700)
        file = artifacts / "fixture.txt"
        file.write_text("disposable fixture", encoding="utf-8")
        file.chmod(0o600)
        extra.update(artifact_dir=str(artifacts), terminal_summary=True)
        adapter = ApronAdapter(SimpleNamespace(extra=extra))
        assert await adapter.connect()
        try:
            if operation == "append":
                result = await adapter.send("general", "preview", metadata={"expect_edits": True})
            elif operation == "artifact":
                result = await adapter.send_document("general", str(file))
            else:
                result = await adapter.publish_terminal(
                    "general", "reviewed fixture", approved=True
                )
            assert result.success is False
            assert not adapter.streams
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize("stage", ["auth", "rooms", "history"])
async def test_malformed_reconnect_cleans_new_transport_and_reservations(
    tmp_path, stage, monkeypatch
):
    from hermes_apron import adapter as adapter_module

    transports = []
    original_transport = adapter_module.Transport

    def capture_transport(*args, **kwargs):
        transport = original_transport(*args, **kwargs)
        transports.append(transport)
        return transport

    monkeypatch.setattr(adapter_module, "Transport", capture_transport)
    auths = 0

    def respond(frame, result):
        nonlocal auths
        if frame["method"] == "auth":
            auths += 1
            if auths == 2 and stage == "auth":
                return {"you": {"roles": ["bot"]}}
        if frame["method"] == "room_list":
            return {
                "joined": [None]
                if auths == 2 and stage == "rooms"
                else [{"room_id": "general", "latest_log_id": str(auths)}]
            }
        if frame["method"] == "history" and auths == 2 and stage == "history":
            return {"history_log_id": "0", "messages": [None]}
        return result

    async with peer_server(respond, ["rooms", "history"]) as (url, _):
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        assert await adapter.connect()
        try:
            await adapter.transport.ws.close()
            worker = adapter.worker
            async with asyncio.timeout(4):
                await asyncio.shield(worker)
            assert worker.exception() is None and auths == 2
            assert len(transports) == 2
            assert all(not t.tasks and not t.pending and t.ws is None for t in transports)
            assert (
                adapter.transport is None
                and adapter.credential_lease is None
                and adapter.state is None
            )
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "message",
    [
        None,
        [],
        {"room_id": []},
        {"room_id": "general", "message_id": [], "log_id": "2", "from": {"user_id": "human"}},
        {
            "room_id": "general",
            "message_id": "2",
            "log_id": "2",
            "from": {"user_id": "human", "name": []},
        },
        {
            "room_id": "general",
            "message_id": "2",
            "log_id": "2",
            "from": {"user_id": "human"},
            "body": {"mentions": {}},
        },
    ],
)
async def test_bad_live_message_stops_without_task_or_lock_leaks(tmp_path, message):
    emitted = False

    def respond(frame, result):
        nonlocal emitted
        if frame["method"] == "room_list" and not emitted:
            emitted = True
            return {**result, "emit": {"method": "message", "params": message}}
        return result

    async with peer_server(respond, ["rooms"]) as (url, _):
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            if await adapter.connect():
                worker = adapter.worker
                async with asyncio.timeout(3):
                    await asyncio.shield(worker)
                assert worker.exception() is None
            assert (
                adapter.transport is None
                and adapter.credential_lease is None
                and adapter.state is None
            )
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize("boundary", [None, 2, [], "bad", "9" * 20])
async def test_bad_recovery_boundary_does_not_poison_checkpoint(tmp_path, boundary):
    from hermes_apron.state import State

    def respond(frame, result):
        if frame["method"] == "room_list":
            return {"joined": [{"room_id": "general", "latest_log_id": boundary}]}
        return result

    async with peer_server(respond, ["rooms", "history"]) as (url, _):
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            assert await adapter.connect() is False
            state = State(tmp_path / "consumer")
            try:
                assert state.checkpoint("general") is None
            finally:
                state.close()
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize("stage", ["rooms", "receipt"])
async def test_standalone_malformed_peer_returns_error(tmp_path, stage):
    from hermes_apron.delivery import standalone_sender

    def respond(frame, result):
        if stage == "rooms" and frame["method"] == "room_list":
            return {"joined": [None]}
        if stage == "receipt" and frame["method"] == "message":
            return {"message_id": []}
        return result

    async with peer_server(respond, ["rooms"]) as (url, _):
        result = await standalone_sender(
            SimpleNamespace(extra=adapter_config(tmp_path, url)), "general", "fixture"
        )
        assert result.get("error") and not result.get("success")


# These values travel as JSON escapes on a real WebSocket. Python's decoder
# accepts them as str, but no such string has a strict UTF-8 representation.
UNICODE_MESSAGE_FIELDS = [
    ("room_id",),
    ("message_id",),
    ("from", "user_id"),
    ("from", "name"),
    ("from", "roles", 0),
    ("body", "text"),
    ("body", "mentions", 0),
    ("reply_to", "message_id"),
]


def unicode_message(field, bad):
    message = {
        "room_id": "general",
        "message_id": "2",
        "log_id": "2",
        "from": {"user_id": "human", "name": "Human", "roles": ["member"]},
        "body": {"text": "authorized fixture", "mentions": ["hermes"]},
        "reply_to": {"message_id": "1"},
    }
    target = message
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = bad
    return message


@pytest.mark.parametrize("bad", ["\ud800", "\udfff"])
@pytest.mark.parametrize("field", UNICODE_MESSAGE_FIELDS)
@pytest.mark.parametrize("stage", ["live", "history"])
async def test_json_surrogate_message_cleans_lifecycle(tmp_path, monkeypatch, bad, field, stage):
    from hermes_apron import adapter as adapter_module
    from hermes_apron.state import State

    transports = []
    original = adapter_module.Transport

    def capture(*args, **kwargs):
        t = original(*args, **kwargs)
        transports.append(t)
        return t

    monkeypatch.setattr(adapter_module, "Transport", capture)
    emitted = False
    fixed = False
    handled = []

    def respond(frame, result):
        nonlocal emitted
        if frame["method"] == "room_list":
            result = {
                "joined": [
                    {"room_id": "general", "latest_log_id": "2" if stage == "history" else "1"}
                ]
            }
        if frame["method"] == "probe" and stage == "live" and not emitted:
            emitted = True
            result["emit"] = {"method": "message", "params": unicode_message(field, bad)}
        if frame["method"] == "history" and stage == "history" and not fixed:
            return {"history_log_id": "0", "messages": [unicode_message(field, bad)]}
        return result

    async with peer_server(respond, ["rooms", "history"]) as (url, authenticated):
        extra = adapter_config(tmp_path, url)
        extra["allowed_users"] = ["human"]
        if stage == "history":
            state = State(tmp_path / "consumer")
            state.advance("general", "1")
            state.close()
        adapter = ApronAdapter(SimpleNamespace(extra=extra))

        async def handle(event):
            handled.append(event)

        adapter.handle_message = handle
        try:
            connected = await adapter.connect()
            if stage == "live":
                assert connected
                worker = adapter.worker
                await adapter.transport.call("probe")
                async with asyncio.timeout(3):
                    await asyncio.shield(worker)
                assert worker.exception() is None
            else:
                assert connected is False
            assert not handled
            assert adapter.fatal_error_code == "invalid_protocol"
            assert len(authenticated) == 1
            assert adapter.transport is None and adapter.state is None
            assert adapter.credential_lease is None
            assert all(not t.tasks and not t.pending and t.ws is None for t in transports)
            fixed = True
            assert await adapter.connect(), "malformed Unicode leaked a reservation"
            assert adapter.fatal_error_code is None
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "stage,field",
    [
        ("auth", ("you", "user_id")),
        ("auth", ("you", "name")),
        ("auth", ("you", "roles", 0)),
        ("room_list", ("joined", 0, "room_id")),
        ("room_list", ("joined", 0, "title")),
        ("room_list", ("joined", 0, "parent_room_id")),
        ("message", ("message_id",)),
        ("message", ("embeds", 0, "write_url")),
    ],
)
async def test_json_surrogate_startup_and_response_fields(tmp_path, stage, field):
    fixed = False

    def respond(frame, result):
        if frame["method"] == "room_list":
            result = {
                "joined": [{"room_id": "general", "title": "Fixture", "parent_room_id": "root"}]
            }
        if frame["method"] == "message":
            result = {"message_id": "2", "embeds": [{"write_url": "/write/fixture"}]}
        if not fixed and frame["method"] == stage:
            target = result
            for key in field[:-1]:
                target = target[key]
            target[field[-1]] = "\ud800"
        return result

    async with peer_server(respond, ["rooms", "embed:append"]) as (url, _):
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            if stage == "message":
                assert await adapter.connect()
                transport = adapter.transport
                result = await adapter.send("general", "preview", metadata={"expect_edits": True})
                assert result.success is False
                worker = adapter.worker
                async with asyncio.timeout(3):
                    await asyncio.shield(worker)
                assert worker.exception() is None
                assert not transport.tasks and not transport.pending and transport.ws is None
            else:
                assert await adapter.connect() is False
            assert adapter.fatal_error_code == "invalid_protocol"
            assert adapter.transport is None and adapter.state is None
            assert adapter.credential_lease is None
            fixed = True
            assert await adapter.connect()
            assert adapter.fatal_error_code is None
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize(
    "raw_value",
    ['"\\ud800"', '{"\\ud800":"key"}', "[" * 20000 + "0" + "]" * 20000, "9" * 5000],
    ids=["surrogate", "surrogate-key", "nesting", "integer-limit"],
)
async def test_peer_conversion_boundary_lifecycle(tmp_path, raw_value):
    fixed = False

    async def peer(ws):
        await ws.send(json.dumps({"method": "server", "params": {"apron": 10, "auth": ["token"]}}))
        auth = json.loads(await ws.recv())
        value = json.dumps({"you": {"user_id": "hermes", "roles": ["bot"]}})
        if not fixed:
            value = '{"you":{"user_id":"hermes","roles":["bot"]},"extra":' + raw_value + "}"
        await ws.send('{"id":' + json.dumps(auth["id"]) + ',"result":' + value + "}")
        await ws.wait_closed()

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        url = f"http://127.0.0.1:{host.sockets[0].getsockname()[1]}"
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            if raw_value.startswith("["):
                # Python 3.14 accepts deeply nested JSON. The scalar walk must
                # stay iterative, without creating a new conversion failure.
                assert await adapter.connect()
                assert not adapter.worker.done() and adapter.fatal_error_code is None
                await adapter.disconnect()
            else:
                assert await adapter.connect() is False
                assert adapter.fatal_error_code == "invalid_protocol"
            assert adapter.transport is None and adapter.state is None
            assert adapter.credential_lease is None
            fixed = True
            assert await adapter.connect()
        finally:
            await adapter.disconnect()


async def test_valid_unicode_scalar_message_is_preserved(tmp_path):
    text = "café 日本語 🌱"
    handled = []

    def respond(frame, result):
        if frame["method"] == "probe":
            return {
                **result,
                "emit": {"method": "message", "params": unicode_message(("body", "text"), text)},
            }
        return result

    async with peer_server(respond, ["rooms"]) as (url, _):
        extra = adapter_config(tmp_path, url)
        extra["allowed_users"] = ["human"]
        adapter = ApronAdapter(SimpleNamespace(extra=extra))

        async def handle(event):
            handled.append(event.text)

        adapter.handle_message = handle
        try:
            assert await adapter.connect()
            await adapter.transport.call("probe")
            async with asyncio.timeout(3):
                while not handled:
                    await asyncio.sleep(0.01)
            assert handled == [text]
            assert not adapter.worker.done() and adapter.fatal_error_code is None
        finally:
            await adapter.disconnect()


@pytest.mark.parametrize("field", ["auth", "capabilities"])
async def test_json_surrogate_greeting_fields(tmp_path, field):
    fixed = False

    async def peer(ws):
        greeting = {"apron": 10, "auth": ["token"], "capabilities": []}
        if not fixed:
            greeting[field] = ["\ud800"]
        await ws.send(json.dumps({"method": "server", "params": greeting}))
        if fixed:
            auth = json.loads(await ws.recv())
            await ws.send(
                json.dumps(
                    {"id": auth["id"], "result": {"you": {"user_id": "hermes", "roles": ["bot"]}}}
                )
            )
        await ws.wait_closed()

    async with websockets.serve(peer, "127.0.0.1", 0) as host:
        url = f"http://127.0.0.1:{host.sockets[0].getsockname()[1]}"
        adapter = ApronAdapter(SimpleNamespace(extra=adapter_config(tmp_path, url)))
        try:
            assert await adapter.connect() is False
            assert adapter.fatal_error_code == "invalid_protocol"
            assert adapter.transport is None and adapter.state is None
            assert adapter.credential_lease is None
            fixed = True
            assert await adapter.connect()
        finally:
            await adapter.disconnect()
