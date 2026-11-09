from types import SimpleNamespace
from hermes_apron.adapter import ApronAdapter


def test_only_allowed_structured_mentions_reach_hermes(tmp_path):
    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": "https://chat.example.test",
                "token_file": str(tmp_path / "machine"),
                "allowed_users": ["allowed"],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
            }
        )
    )
    message = {
        "room_id": "general",
        "message_id": "10",
        "log_id": "10",
        "from": {"user_id": "allowed"},
        "body": {"text": "hello", "mentions": ["hermes"]},
    }
    assert adapter.accepts(message), "authorized structured mention dropped"
    for actor in [None, "", "outsider", "hermes"]:
        assert not adapter.accepts({**message, "from": {"user_id": actor}})
    assert not adapter.accepts({**message, "body": {"text": "@Hermes hello"}})
    assert not adapter.accepts({**message, "prev_log_id": "9"})
    assert not adapter.accepts({**message, "deleted": True})
    assert not adapter.accepts({**message, "room_id": "other"})


async def test_native_send_receipt_from_real_adapter(real_server, tmp_path):
    from hermes_apron.transport import Transport

    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": ["allowed"],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
                "test_loopback": True,
            }
        )
    )
    assert await adapter.connect(), "real Hermes adapter did not connect"
    reader = Transport(
        real_server["ws"], real_server["url"], real_server["token"], test_loopback=True
    )
    try:
        await reader.connect()
        sent = await adapter.send("general", "**Native Markdown**")
        assert sent.success and sent.message_id
        history = await reader.call("history", {"room_id": "general", "limit": 20})
        receipts = [m for m in history.get("messages", []) if m["message_id"] == sent.message_id]
        assert len(receipts) == 1 and receipts[0]["body"]["text"] == "**Native Markdown**"
        assert not (await adapter.send("unconfigured", "must not leak")).success
    finally:
        await adapter.disconnect()
        await reader.close()


async def test_real_human_invocation_with_hermes_handler(real_server, tmp_path):
    import asyncio
    from humans import enrolled_human

    human, identity = await enrolled_human(real_server)
    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": [identity],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
                "test_loopback": True,
            }
        )
    )
    received = asyncio.Event()
    captured = []

    async def handler(event):
        captured.append(event)
        received.set()
        return "deterministic reply"

    adapter.set_message_handler(handler)
    assert await adapter.connect()
    try:
        request = await human.call(
            "message", {"room_id": "general", "body": {"text": "hello", "mentions": ["hermes"]}}
        )
        async with asyncio.timeout(3):
            await received.wait()
        assert len(captured) == 1
        assert captured[0].user_id == identity
        assert captured[0].message_id == request["message_id"]
        assert captured[0].source.chat_id == "general"
    finally:
        await adapter.disconnect()
        await human.ws.close()


async def test_offline_history_recovers_once_after_new_adapter(real_server, tmp_path):
    import asyncio
    from humans import enrolled_human

    human, identity = await enrolled_human(real_server)
    cfg = SimpleNamespace(
        extra={
            "url": real_server["url"],
            "token_file": real_server["token_file"],
            "allowed_users": [identity],
            "rooms": ["general"],
            "state_dir": str(tmp_path),
            "test_loopback": True,
        }
    )
    captured = []

    async def handler(event):
        captured.append(event.message_id)
        return None

    first = ApronAdapter(cfg)
    first.set_message_handler(handler)
    assert await first.connect()
    await first.disconnect()
    sent = await human.call(
        "message",
        {"room_id": "general", "body": {"text": "offline request", "mentions": ["hermes"]}},
    )
    second = ApronAdapter(cfg)
    second.set_message_handler(handler)
    try:
        assert await second.connect()
        async with asyncio.timeout(3):
            while captured != [sent["message_id"]]:
                await asyncio.sleep(0.02)
        await second.disconnect()
        third = ApronAdapter(cfg)
        third.set_message_handler(handler)
        assert await third.connect()
        await asyncio.sleep(0.15)
        await third.disconnect()
        assert captured == [sent["message_id"]]
    finally:
        await second.disconnect()
        await human.ws.close()


async def test_native_append_finishes_same_message(real_server, tmp_path):
    from hermes_apron.transport import Transport

    cfg = SimpleNamespace(
        extra={
            "url": real_server["url"],
            "token_file": real_server["token_file"],
            "allowed_users": [],
            "rooms": ["general"],
            "state_dir": str(tmp_path),
            "test_loopback": True,
        }
    )
    adapter = ApronAdapter(cfg)
    assert await adapter.connect()
    reader = Transport(
        real_server["ws"], real_server["url"], real_server["token"], test_loopback=True
    )
    try:
        await reader.connect()
        sent = await adapter.send("general", "first", metadata={"expect_edits": True})
        assert sent.success
        assert (await adapter.edit_message("general", sent.message_id, "first second")).success
        assert (
            await adapter.edit_message("general", sent.message_id, "revised final", finalize=True)
        ).success
        page = await reader.call("history", {"room_id": "general", "limit": 50})
        messages = [m for m in page.get("messages", []) if m["message_id"] == sent.message_id]
        assert messages[-1]["body"]["text"] == "revised final"
        assert not messages[-1]["body"].get("embeds")
        assert len({m["message_id"] for m in page.get("messages", [])}) == 1
    finally:
        await adapter.disconnect()
        await reader.close()


async def test_native_upload_rejects_traversal_and_reads_back(real_server, tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(mode=0o700)
    path = artifacts / "report.txt"
    path.write_text("bounded artifact", encoding="utf-8")
    path.chmod(0o600)
    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": [],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
                "artifact_dir": str(artifacts),
                "test_loopback": True,
            }
        )
    )
    assert await adapter.connect()
    try:
        uploaded = await adapter.send_document("general", str(path))
        assert uploaded.success
        history = await adapter.transport.call("history", {"room_id": "general", "limit": 20})
        message = [
            m for m in history.get("messages", []) if m["message_id"] == uploaded.message_id
        ][-1]
        assert message["body"]["embeds"][0]["kind"] == "upload"
        assert "url" in message["body"]["embeds"][0]
        assert not (
            await adapter.send_document("general", str(artifacts / ".." / "outside.txt"))
        ).success
        symlink = artifacts / "linked.txt"
        symlink.symlink_to(path)
        assert not (await adapter.send_document("general", str(symlink))).success
    finally:
        await adapter.disconnect()


async def test_standalone_delivery_coexists_with_consumer(real_server, tmp_path):
    from hermes_apron.delivery import standalone_sender

    cfg = SimpleNamespace(
        extra={
            "url": real_server["url"],
            "token_file": real_server["token_file"],
            "allowed_users": [],
            "rooms": ["general"],
            "state_dir": str(tmp_path),
            "test_loopback": True,
        }
    )
    live = ApronAdapter(cfg)
    assert await live.connect()
    try:
        cron = await standalone_sender(cfg, "general", "scheduled delivery")
        assert cron.get("success"), "standalone delivery failed beside live consumer"
        receipt = await live.transport.call("history", {"room_id": "general", "limit": 20})
        assert any(
            m["message_id"] == cron["message_id"] and m["body"]["text"] == "scheduled delivery"
            for m in receipt.get("messages", [])
        )
        assert (await live.send("general", "live consumer remains active")).success
    finally:
        await live.disconnect()


async def test_typing_activity_is_native(real_server, tmp_path):
    import asyncio
    from hermes_apron.transport import Transport

    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": [],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
                "test_loopback": True,
            }
        )
    )
    assert await adapter.connect()
    reader = Transport(
        real_server["ws"], real_server["url"], real_server["token"], test_loopback=True
    )
    try:
        await reader.connect()
        await adapter.send_typing("general")
        async with asyncio.timeout(2):
            while True:
                frame = await reader.events.get()
                if frame.get("method") == "activity" and frame["params"].get("typing"):
                    break
        await adapter.stop_typing("general")
        async with asyncio.timeout(2):
            while True:
                frame = await reader.events.get()
                if frame.get("method") == "activity" and frame["params"].get("typing") == 0:
                    break
    finally:
        await adapter.disconnect()
        await reader.close()


async def test_opt_in_terminal_summary_scrubs_runtime_credential(real_server, tmp_path):
    cfg = SimpleNamespace(
        extra={
            "url": real_server["url"],
            "token_file": real_server["token_file"],
            "allowed_users": [],
            "rooms": ["general"],
            "state_dir": str(tmp_path),
            "test_loopback": True,
            "terminal_summary": True,
        }
    )
    adapter = ApronAdapter(cfg)
    assert await adapter.connect()
    try:
        assert not (
            await adapter.publish_terminal("general", "arbitrary command output", approved=False)
        ).success
        sent = await adapter.publish_terminal(
            "general", "\x1b[31mreviewed\x1b[0m " + real_server["token"], approved=True
        )
        assert sent.success, "approved bounded summary was not published"
        history = await adapter.transport.call("history", {"room_id": "general", "limit": 20})
        serialized = str(history)
        assert real_server["token"] not in serialized
        assert "[REDACTED]" in serialized
    finally:
        await adapter.disconnect()


async def test_standalone_sender_from_separate_process(real_server, tmp_path):
    import asyncio
    import json
    import os
    import sys

    extra = {
        "url": real_server["url"],
        "token_file": real_server["token_file"],
        "allowed_users": [],
        "rooms": ["general"],
        "state_dir": str(tmp_path),
        "test_loopback": True,
        "home_room": "general",
    }
    cfg = SimpleNamespace(extra=extra)
    live = ApronAdapter(cfg)
    assert await live.connect()
    path = tmp_path / "delivery.json"
    path.write_text(json.dumps(extra), encoding="utf-8")
    path.chmod(0o600)
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "hermes_apron.send",
            "--config",
            str(path),
            "--message",
            "separate process delivery",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), 10)
        assert process.returncode == 0
        sent = json.loads(stdout)
        receipt = await live.transport.call("history", {"room_id": "general", "limit": 20})
        assert any(m["message_id"] == sent["message_id"] for m in receipt.get("messages", []))
    finally:
        await live.disconnect()


async def test_reconnect_replaces_transport_with_bounded_retry(real_server, tmp_path):
    import asyncio

    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": [],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
                "test_loopback": True,
            }
        )
    )
    assert await adapter.connect()
    previous = adapter.transport
    try:
        await previous.ws.close()
        async with asyncio.timeout(4):
            while adapter.transport is previous or adapter.transport.closed.is_set():
                await asyncio.sleep(0.02)
        assert (await adapter.send("general", "after reconnect")).success
    finally:
        await adapter.disconnect()


async def test_unsupported_clarification_cancels_exact_real_pending_request(tmp_path):
    from tools.clarify_gateway import register, get_pending

    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": "https://chat.example.test",
                "token_file": str(tmp_path / "machine"),
                "allowed_users": ["allowed"],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
            }
        )
    )
    first = register("fixture-request-one", "fixture-session-one", "question", None)
    second = register("fixture-request-two", "fixture-session-two", "other", None)
    result = await adapter.send_clarify(
        "general", "question", None, first.clarify_id, first.session_key
    )
    assert not result.success
    assert get_pending(first.clarify_id) is None, "unsupported prompt still accepts ambiguous text"
    assert get_pending(second.clarify_id) is second


def test_structured_authority_rejects_scalar_mentions(tmp_path):
    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": "https://chat.example.test",
                "token_file": str(tmp_path / "machine"),
                "allowed_users": ["allowed"],
                "rooms": ["general"],
                "state_dir": str(tmp_path),
            }
        )
    )
    message = {
        "room_id": "general",
        "message_id": "10",
        "log_id": "10",
        "from": {"user_id": "allowed"},
        "body": {"text": "hello", "mentions": "hermes"},
    }
    assert not adapter.accepts(message), "scalar mention was treated as structured authority"


async def test_corrupt_ledger_fails_closed_without_holding_lock(real_server, tmp_path):
    path = tmp_path / "inbox.db"
    path.write_bytes(b"deliberately corrupt database")
    path.chmod(0o600)
    cfg = SimpleNamespace(
        extra={
            "url": real_server["url"],
            "token_file": real_server["token_file"],
            "allowed_users": [],
            "rooms": ["general"],
            "state_dir": str(tmp_path),
            "test_loopback": True,
        }
    )
    first = ApronAdapter(cfg)
    assert await first.connect() is False
    path.unlink()
    second = ApronAdapter(cfg)
    try:
        assert await second.connect(), "failed initialization leaked the consumer lock"
    finally:
        await second.disconnect()


async def test_two_private_rooms_and_child_threads_stay_isolated(real_server, tmp_path):
    import asyncio
    from humans import enrolled_human

    human, identity = await enrolled_human(real_server)
    room_ids = []
    try:
        for index in range(2):
            parent = await human.call(
                "room_set", {"title": f"Private fixture {index}", "private": True}
            )
            parent_id = parent["room_id"]
            child = await human.call(
                "room_set", {"parent_room_id": parent_id, "title": "Fixture thread"}
            )
            room_ids.extend([parent_id, child["room_id"]])
        credentials = human.credentials
        await human.ws.close()
        await asyncio.to_thread(real_server["restart"], ["general", *room_ids])
        human, restored_identity = await enrolled_human(real_server, credentials)
        assert restored_identity == identity
        adapter = ApronAdapter(
            SimpleNamespace(
                extra={
                    "url": real_server["url"],
                    "token_file": real_server["token_file"],
                    "allowed_users": [identity],
                    "rooms": room_ids,
                    "state_dir": str(tmp_path),
                    "test_loopback": True,
                }
            )
        )
        captured = []
        all_received = asyncio.Event()

        async def handler(event):
            captured.append(event)
            if len(captured) == 4:
                all_received.set()
            await all_received.wait()
            return None

        adapter.set_message_handler(handler)
        assert await adapter.connect()
        try:
            for room in room_ids:
                await human.call(
                    "message",
                    {
                        "room_id": room,
                        "body": {"text": "private marker " + room, "mentions": ["hermes"]},
                    },
                )
            async with asyncio.timeout(4):
                await all_received.wait()
            assert {e.source.chat_id for e in captured} == set(room_ids)
            for event in captured:
                assert event.text == "private marker " + event.source.chat_id
                assert (
                    await adapter.send(
                        event.source.chat_id,
                        "reply " + event.source.chat_id,
                        reply_to=event.message_id,
                    )
                ).success
            for room in room_ids:
                history = await human.call("history", {"room_id": room, "limit": 50})
                assert all(m["room_id"] == room for m in history.get("messages", []))
                assert any(
                    m["body"]["text"] == "reply " + room
                    for m in history.get("messages", [])
                    if m.get("body")
                )
        finally:
            await adapter.disconnect()
    finally:
        await human.ws.close()


async def test_same_credential_cannot_start_second_consumer_profile(real_server, tmp_path):
    common = {
        "url": real_server["url"],
        "token_file": real_server["token_file"],
        "allowed_users": [],
        "rooms": ["general"],
        "test_loopback": True,
    }
    first = ApronAdapter(SimpleNamespace(extra={**common, "state_dir": str(tmp_path / "one")}))
    second = ApronAdapter(SimpleNamespace(extra={**common, "state_dir": str(tmp_path / "two")}))
    try:
        assert await first.connect()
        assert await second.connect() is False, (
            "credential admitted duplicate consumers across state directories"
        )
        assert (await first.send("general", "first consumer remains usable")).success
    finally:
        await second.disconnect()
        await first.disconnect()


def test_actual_hermes_plugin_loader_imports_repository_entrypoint(tmp_path):
    from pathlib import Path
    from hermes_cli.plugins import PluginManager
    from hermes_cli.plugins_manifest import PluginManifest

    manager = PluginManager(scope_key=str(tmp_path / "hermes-profile"))
    manifest = PluginManifest(
        name="hermes-apron",
        kind="platform",
        source="user",
        path=str(Path(__file__).resolve().parents[1]),
    )
    # The pinned loader itself performs importlib loading and calls the real PluginContext.
    manager._load_plugin(manifest)
    loaded = manager._plugins.get("hermes-apron")
    assert loaded is not None and loaded.enabled and not loaded.error


def test_profile_scoped_configuration_is_passive_and_cannot_borrow_secret(tmp_path, monkeypatch):
    from agent.secret_scope import set_secret_scope, reset_secret_scope
    from hermes_apron.adapter import validate_config
    from hermes_apron.config import Options

    monkeypatch.setenv("APRON_TOKEN_FILE", str(tmp_path / "wrong-profile"))
    cfg = SimpleNamespace(
        extra={
            "url": "https://chat.example.test",
            "token_file": str(tmp_path / "yaml-profile"),
            "allowed_users": ["fixture-actor"],
            "rooms": ["general"],
            "state_dir": str(tmp_path / "must-not-create"),
        }
    )
    token = set_secret_scope({"APRON_TOKEN_FILE": str(tmp_path / "scoped-profile")})
    try:
        assert Options.load(cfg).token_file == str(tmp_path / "scoped-profile")
        assert validate_config(cfg)
        assert not (tmp_path / "must-not-create").exists()
    finally:
        reset_secret_scope(token)


async def test_edit_is_bound_to_original_room(real_server, tmp_path):
    import asyncio
    from humans import enrolled_human

    provision, _ = await enrolled_human(real_server)
    room = (await provision.call("room_set", {"title": "Second fixture room"}))["room_id"]
    await provision.ws.close()
    await asyncio.to_thread(real_server["restart"], ["general", room])
    adapter = ApronAdapter(
        SimpleNamespace(
            extra={
                "url": real_server["url"],
                "token_file": real_server["token_file"],
                "allowed_users": [],
                "rooms": ["general", room],
                "state_dir": str(tmp_path),
                "test_loopback": True,
            }
        )
    )
    assert await adapter.connect()
    try:
        sent = await adapter.send("general", "original room")
        assert sent.success
        assert not (
            await adapter.edit_message(room, sent.message_id, "cross-room content")
        ).success, "edit moved a message across conversation scopes"
    finally:
        await adapter.disconnect()
        await provision.ws.close()
