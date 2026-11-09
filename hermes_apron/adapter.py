"""Native Apron platform adapter; the Hermes gateway remains an authorization boundary."""

import asyncio
import contextlib
import re
import time
import random
from .config import Options, read_secret
from .transport import Transport, ProtocolError, RPCError
from .state import State, CredentialLease
from .media import Append, put, read_artifact, single
from gateway.platforms.event import MessageEvent, MessageType
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult


class ApronAdapter(BasePlatformAdapter):
    supports_code_blocks = True
    REQUIRES_EDIT_FINALIZE = True

    def __init__(self, config):
        super().__init__(config, Platform("apron"))
        self.options = Options.load(config)
        self.bot_id = "hermes"
        self.transport = None
        self.state = None
        self.credential_lease = None
        self.joined = {}
        self.worker = None
        self.streams = {}
        self.outbound_rooms = {}

    def accepts(self, message):
        if not isinstance(message, dict):
            return False
        sender = message.get("from") or {}
        body = message.get("body") or {}
        if not isinstance(sender, dict) or not isinstance(body, dict):
            return False
        actor = sender.get("user_id")
        mentions = body.get("mentions", [])
        roles = sender.get("roles", [])
        if (
            not isinstance(actor, str)
            or not isinstance(message.get("room_id"), str)
            or not isinstance(mentions, list)
            or not all(isinstance(x, str) for x in mentions)
            or not isinstance(roles, list)
            or not all(isinstance(x, str) for x in roles)
        ):
            return False
        text = body.get("text", "")
        return bool(
            actor in self.options.allowed_users
            and actor != self.bot_id
            and "bot" not in sender.get("roles", [])
            and message.get("room_id") in self.options.rooms
            and isinstance(message.get("message_id"), str)
            and message.get("log_id") == message.get("message_id")
            and not message.get("prev_log_id")
            and not message.get("deleted")
            and isinstance(text, str)
            and 0 < len(text.encode()) <= 65536
            and (
                self.bot_id in body.get("mentions", [])
                or message.get("room_id") in self.options.dm_rooms
            )
            and not text.lstrip().startswith(("/", "!approve", "!always", "!deny", "!cancel"))
        )

    async def connect(self, *, is_reconnect=False):
        if self.state is not None:
            await self.disconnect()
        try:
            self.state = State(self.options.state_dir)
            token = await asyncio.to_thread(read_secret, self.options.token_file)
            self.credential_lease = CredentialLease(self.options.endpoint, token)
            self.transport = Transport(
                self.options.endpoint,
                self.options.url,
                token,
                test_loopback=self.options.test_loopback,
            )
            await self.transport.connect()
            self.bot_id = self.transport.you["user_id"]
            await self._rooms()
            await self._recover()
            self.worker = asyncio.create_task(self._supervise())
            self._mark_connected()
            return True
        except ValueError, OSError, ProtocolError:
            await self.disconnect()
            return False

    async def _rooms(self):
        if "rooms" not in self.transport.capabilities:
            self.joined = (
                {"general": {"room_id": "general"}} if "general" in self.options.rooms else {}
            )
            return
        rooms = await self.transport.call("room_list", {"filter": "joined"})
        self.joined = {
            r["room_id"]: r
            for r in rooms.get("joined", [])
            if r.get("room_id") in self.options.rooms
        }

    async def _recover(self):
        if "history" not in self.transport.capabilities:
            return
        for room, record in self.joined.items():
            high = record.get("latest_log_id")
            if high is None:
                raise ProtocolError("Apron room has no recovery boundary")
            checkpoint = self.state.checkpoint(room)
            if checkpoint is None:
                # First installation starts at the current boundary; never runs old chat as tools.
                self.state.advance(room, high)
                continue
            after = int(checkpoint) + 1
            for _ in range(100):
                if after > int(high):
                    break
                page = await self.transport.call(
                    "history", {"room_id": room, "after": str(after), "before": high, "limit": 100}
                )
                low = page.get("history_log_id")
                if low is None or int(low) > after:
                    raise ProtocolError("Apron history gap; operator reconciliation required")
                for message in page.get("messages", []):
                    await self._inbound(message)
                if not page.get("more"):
                    break
                last = int(page["last_log_id"])
                if last < after:
                    raise ProtocolError("Apron history failed to advance")
                after = last + 1
            else:
                raise ProtocolError("Apron recovery backlog exceeds bounds")
            self.state.advance(room, high)

    async def _supervise(self):
        failures = 0
        try:
            while failures < 6:
                started = time.monotonic()
                await self._consume_once()
                if time.monotonic() - started >= 30:
                    failures = 0
                for stream in self.streams.values():
                    await stream.abort()
                self.streams.clear()
                failure = self.transport.failure
                if isinstance(failure, RPCError) and failure.code == -32001:
                    break
                await self.transport.close()
                while failures < 6:
                    delay = min(30, 0.5 * 2**failures) + random.uniform(0, 0.2)
                    if isinstance(failure, RPCError):
                        delay = max(delay, failure.retry_after)
                    failures += 1
                    await asyncio.sleep(delay)
                    try:
                        token = await asyncio.to_thread(read_secret, self.options.token_file)
                        transport = Transport(
                            self.options.endpoint,
                            self.options.url,
                            token,
                            test_loopback=self.options.test_loopback,
                        )
                        await transport.connect()
                        self.transport = transport
                        await self._rooms()
                        await self._recover()
                        self._mark_connected()
                        break
                    except RPCError as error:
                        failure = error
                        if error.code == -32001:
                            failures = 6
                    except ProtocolError, ValueError, OSError:
                        failure = ProtocolError("Apron reconnect failed")
                else:
                    break
        except asyncio.CancelledError:
            raise
        finally:
            self._mark_disconnected()

    async def _consume_once(self):
        try:
            while not self.transport.closed.is_set():
                try:
                    async with asyncio.timeout(0.5):
                        frame = await self.transport.events.get()
                except TimeoutError:
                    continue
                if frame.get("method") == "room_update":
                    for room in frame.get("params", {}).get("left", []):
                        self.joined.pop(room.get("room_id"), None)
                    for room in frame.get("params", {}).get("joined", []):
                        if room.get("room_id") in self.options.rooms:
                            self.joined[room["room_id"]] = room
                elif frame.get("method") == "message":
                    await self._inbound(frame.get("params", {}))
        except asyncio.CancelledError:
            raise
        except ProtocolError, ValueError, TypeError:
            await self.transport.close()
        finally:
            self._mark_disconnected()

    async def _inbound(self, message):
        if not isinstance(message, dict) or message.get("room_id") not in self.joined:
            return
        room = message["room_id"]
        position = message.get("log_id", "")
        if (
            not isinstance(position, str)
            or not position.isascii()
            or not position.isdigit()
            or len(position) > 19
        ):
            raise ProtocolError("Apron invalid log position")
        checkpoint = self.state.checkpoint(room)
        if checkpoint is not None and int(position) <= int(checkpoint):
            return
        if not self.accepts(message):
            self.state.advance(room, position)
            return
        message_id = message["message_id"]
        if not self.state.reserve(room, message_id):
            return
        sender = message["from"]
        text = message["body"]["text"]
        if text.split(" ", 1)[0] in {"!help", "!status", "!new"}:
            text = "/" + text[1:]
        source = self.build_source(
            chat_id=room,
            chat_type="group",
            user_id=sender["user_id"],
            user_name=sender.get("name"),
            chat_name=self.joined[room].get("title", room),
            parent_chat_id=self.joined[room].get("parent_room_id"),
            message_id=message_id,
        )
        event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            user_id=sender["user_id"],
            user_name=sender.get("name"),
            source=source,
            message_id=message_id,
            reply_to_message_id=(message.get("reply_to") or {}).get("message_id"),
        )
        await self.handle_message(event)
        self.state.advance(room, position)

    async def disconnect(self):
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
            self.worker = None
        tasks = list(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for stream in self.streams.values():
            await stream.abort()
        self.streams.clear()
        if self.transport:
            for room in self.joined:
                await self.stop_typing(room)
            await self.transport.close()
            self.transport = None
        if self.state:
            self.state.close()
            self.state = None
        if self.credential_lease:
            self.credential_lease.close()
            self.credential_lease = None
        self._mark_disconnected()

    def _target(self, chat_id, metadata=None):
        room = (metadata or {}).get("thread_id") or str(chat_id)
        if room not in self.options.rooms or room not in self.joined:
            raise ProtocolError("Apron destination not in configured joined rooms")
        if room != str(chat_id) and self.joined[room].get("parent_room_id") != str(chat_id):
            raise ProtocolError("Apron thread parent mismatch")
        return room

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        try:
            room = self._target(chat_id, metadata)
            if not isinstance(content, str) or not 0 < len(content.encode()) <= 65536:
                raise ProtocolError("Apron message exceeds bounds")
            await self._rooms()
            self._target(chat_id, metadata)
            preview = bool((metadata or {}).get("expect_edits"))
            native = preview and "embed:append" in self.transport.capabilities
            if preview and not native and "edit" not in self.transport.capabilities:
                return SendResult(
                    success=False, error="Apron previews unavailable; send completed text"
                )
            content = self._clean_text(content)
            params = {
                "room_id": room,
                "body": {"text": "" if native else content, "format": "markdown"},
            }
            if native:
                params["body"]["embeds"] = [{"kind": "append"}]
            if reply_to:
                params["reply_to"] = {"message_id": str(reply_to)}
            result = await self.transport.call("message", params)
            message_id = result.get("message_id")
            if not isinstance(message_id, str) or not message_id:
                raise ProtocolError("Apron did not confirm message delivery")
            if len(self.outbound_rooms) >= 2048:
                self.outbound_rooms.pop(next(iter(self.outbound_rooms)))
            self.outbound_rooms[message_id] = room
            if native:
                if len(self.streams) >= 8:
                    raise ProtocolError("Apron active stream limit")
                stream = Append(self.options.url, result["embeds"][0]["write_url"])
                self.streams[message_id] = stream
                await stream.write(content)
            return SendResult(success=True, message_id=message_id)
        except ProtocolError, AttributeError:
            return SendResult(success=False, error="Apron send failed or destination denied")

    @staticmethod
    def _clean_text(content):
        return "".join(c for c in content if c in "\n\t" or ord(c) >= 32)

    async def edit_message(self, chat_id, message_id, content, *, finalize=False, metadata=None):
        try:
            room = self._target(chat_id, metadata)
            if self.outbound_rooms.get(message_id) != room:
                raise ProtocolError("Apron edit is not bound to this room")
            if not isinstance(content, str) or len(content.encode()) > 65535:
                raise ProtocolError("Apron edit exceeds bounds")
            content = self._clean_text(content)
            stream = self.streams.get(message_id)
            if stream:
                try:
                    # Apron append's form feed resets just the appended segment.
                    await stream.write("\f" + content)
                    if finalize:
                        await stream.finish()
                        self.streams.pop(message_id, None)
                    return SendResult(success=True, message_id=message_id)
                except ProtocolError, TimeoutError:
                    await stream.abort()
                    self.streams.pop(message_id, None)
                    # Finish the SAME message with an ordinary save if a writer fails.
            if "edit" not in self.transport.capabilities:
                return SendResult(success=False, error="Apron edits unavailable")
            await self.transport.call(
                "message",
                {
                    "room_id": room,
                    "message_id": message_id,
                    "body": {"text": content, "format": "markdown"},
                },
            )
            return SendResult(success=True, message_id=message_id)
        except ProtocolError, AttributeError:
            return SendResult(success=False, error="Apron edit failed")

    async def send_document(
        self, chat_id, file_path, caption=None, reply_to=None, metadata=None, **kwargs
    ):
        try:
            room = self._target(chat_id, metadata)
            data, name = await asyncio.to_thread(
                read_artifact, self.options.artifact_dir, file_path, self.options.token_file
            )
            if "embed:upload" not in self.transport.capabilities:
                return await self.send(
                    room, "Artifact upload unavailable on this server.", reply_to
                )
            result = await self.transport.call(
                "message",
                {
                    "room_id": room,
                    "body": {
                        "text": self._clean_text(str(caption or ""))[:4096],
                        "embeds": [{"kind": "upload", "title": name}],
                    },
                },
            )
            capability = result["embeds"][0]["write_url"]
            await put(
                self.options.url, capability, single(data), "application/octet-stream", 8 * 1048576
            )
            return SendResult(success=True, message_id=result["message_id"])
        except ProtocolError, ValueError, OSError:
            return SendResult(success=False, error="Apron artifact denied or transfer failed")

    async def send_image_file(self, chat_id, file_path, caption=None, **kwargs):
        return await self.send_document(chat_id, file_path, caption, **kwargs)

    async def send_video(self, chat_id, video_path, caption=None, **kwargs):
        return await self.send_document(chat_id, video_path, caption, **kwargs)

    async def send_voice(self, chat_id, audio_path, caption=None, **kwargs):
        return await self.send_document(chat_id, audio_path, caption, **kwargs)

    async def send_typing(self, chat_id, metadata=None):
        if self.transport and "activity" in self.transport.capabilities:
            try:
                await self.transport.notify(
                    "activity", {"room_id": self._target(chat_id, metadata), "typing": 8}
                )
            except ProtocolError:
                pass

    async def stop_typing(self, chat_id):
        if self.transport and "activity" in self.transport.capabilities:
            with contextlib.suppress(ProtocolError):
                await self.transport.notify(
                    "activity", {"room_id": self._target(chat_id), "typing": 0}
                )

    async def send_clarify(
        self, chat_id, question, choices, clarify_id, session_key, metadata=None
    ):
        # Cancel the exact real waiter; merely refusing the UI leaves open-ended
        # prompts armed for an ambiguous next-message intercept in Hermes.
        from tools.clarify_gateway import get_pending, resolve_gateway_clarify, CANCELLED

        pending = get_pending(clarify_id)
        if pending is not None and pending.session_key == session_key:
            resolve_gateway_clarify(clarify_id, CANCELLED)
        if self.transport:
            await self.send(
                chat_id,
                "Clarification cancelled: a verified Apron response transport is not available.",
                metadata=metadata,
            )
        return SendResult(
            success=False,
            error="Apron clarification is disabled pending a verified request/actor hook",
        )

    async def publish_terminal(self, chat_id, summary, *, approved=False):
        # This is a reviewed-summary API, never a raw tool-output hook or shell executor.
        if (
            getattr(self.config, "extra", {}).get("terminal_summary") is not True
            or approved is not True
            or not isinstance(summary, str)
            or len(summary) > 65536
        ):
            return SendResult(success=False, error="Terminal publication disabled")
        try:
            room = self._target(chat_id)
            token = await asyncio.to_thread(read_secret, self.options.token_file)
            summary = summary.replace(token, "[REDACTED]")
            summary = re.sub(
                r"https?://[^\s]+/(?:write|files|live)/[^\s]+", "[REDACTED URL]", summary
            )
            summary = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", summary)
            summary = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", summary)
            summary = self._clean_text(summary).encode()[:16384].decode("utf-8", errors="ignore")
            if "embed:terminal" not in self.transport.capabilities:
                return await self.send(room, "Reviewed summary:\n\n" + summary)
            result = await self.transport.call(
                "message",
                {
                    "room_id": room,
                    "body": {"embeds": [{"kind": "terminal", "title": "Reviewed summary"}]},
                },
            )
            await put(self.options.url, result["embeds"][0]["write_url"], single(summary.encode()))
            return SendResult(success=True, message_id=result["message_id"])
        except ProtocolError, ValueError:
            return SendResult(success=False, error="Apron summary publication failed")

    async def get_chat_info(self, chat_id):
        room = self.joined.get(str(chat_id), {})
        return {"name": room.get("title", str(chat_id)), "type": "group"}


def validate_config(config):
    try:
        Options.load(config)
        return True
    except ValueError, TypeError:
        return False


def check_requirements():
    import importlib.util

    return importlib.util.find_spec("websockets") is not None


def register(ctx):
    from .delivery import standalone_sender

    ctx.register_platform(
        name="apron",
        label="Apron",
        adapter_factory=ApronAdapter,
        check_fn=check_requirements,
        validate_config=validate_config,
        trusted_inbound=False,
        allowed_users_env="APRON_ALLOWED_USERS",
        allowlist_suppresses_pairing=True,
        allow_update_command=False,
        cron_deliver_env_var="APRON_HOME_ROOM",
        standalone_sender_fn=standalone_sender,
        max_message_length=65536,
    )
