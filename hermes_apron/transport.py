"""Bounded Apron v10 RPC. Remote errors and URLs never enter diagnostic strings."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from urllib.parse import urlsplit
import ipaddress
import math

from .protocol import ProtocolError, InvalidFrame, record, identifier, string_list

import websockets


class RPCError(ProtocolError):
    def __init__(self, code, retry_after=0):
        self.code = code
        self.retry_after = (
            min(60, max(0, retry_after)) if isinstance(retry_after, (int, float)) else 0
        )
        super().__init__(f"Apron request refused (code {code})")


def validate_endpoint(endpoint, origin, test_loopback=False):
    ws, site = urlsplit(endpoint), urlsplit(origin)
    if (
        ws.username
        or ws.password
        or ws.query
        or ws.fragment
        or site.username
        or site.password
        or site.query
        or site.fragment
        or site.path
        or ws.netloc != site.netloc
        or ws.path != "/ws"
        or not ws.hostname
    ):
        raise ValueError("Apron requires an exact endpoint and same-origin HTTPS")
    if ws.scheme == "wss" and site.scheme == "https":
        return
    loopback = ws.hostname == "localhost"
    with contextlib.suppress(ValueError):
        loopback = ipaddress.ip_address(ws.hostname).is_loopback
    if not (test_loopback and loopback and ws.scheme == "ws" and site.scheme == "http"):
        raise ValueError("insecure Apron transport is restricted to explicit loopback tests")


class Transport:
    def __init__(self, endpoint, origin, token, *, test_loopback=False, timeout=5):
        validate_endpoint(endpoint, origin, test_loopback)
        if not isinstance(token, str) or len(token) < 43:
            raise ValueError("missing runtime machine credential")
        self.endpoint, self.origin, self._token = endpoint, origin, token
        self.timeout = timeout
        self.you = None
        self.server = {}
        self.capabilities = set()
        self.ws = None
        self.events = asyncio.Queue(maxsize=128)
        self.pending = {}
        self.tasks = []
        self.closed = asyncio.Event()
        self.failure = None
        self._counter = 0
        self._prefix = uuid.uuid4().hex
        self._pong = time.monotonic()

    async def connect(self):
        try:
            self.ws = await websockets.connect(
                self.endpoint,
                origin=self.origin,
                proxy=None,
                open_timeout=self.timeout,
                close_timeout=2,
                max_size=262144,
                max_queue=32,
                ping_interval=None,
            )
            async with asyncio.timeout(self.timeout):
                frame = self._decode(await self.ws.recv())
            if frame.get("method") != "server":
                raise InvalidFrame("unsupported Apron greeting")
            self._greeting(frame.get("params", {}))
            if "token" not in self.server.get("auth", []):
                raise ProtocolError("Apron has no token authentication")
            self.tasks.append(asyncio.create_task(self._read()))
            auth = await self.call("auth", {"scheme": "token", "token": self._token})
            self.you = auth.get("you")
            if not isinstance(self.you, dict) or self.you.get("roles") != ["bot"]:
                raise InvalidFrame("runtime credential must identify a non-admin bot")
            identifier(self.you.get("user_id"))
            self.tasks.append(asyncio.create_task(self._heartbeat()))
        except BaseException as exc:
            await self.close()
            if isinstance(exc, (asyncio.CancelledError, ProtocolError)):
                raise
            raise ProtocolError("Apron connection failed") from None

    @staticmethod
    def _decode(raw):
        try:
            if not isinstance(raw, str) or len(raw.encode()) > 262144:
                raise ValueError()
            value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(value, dict):
                raise ValueError()
            if "id" in value and not isinstance(value["id"], str):
                raise ValueError()
            if "method" in value and (not isinstance(value["method"], str) or not value["method"]):
                raise ValueError()
            if "params" in value:
                record(value["params"])
            if "error" in value:
                error = record(value["error"])
                if type(error.get("code")) is not int or not -(2**31) <= error["code"] < 2**31:
                    raise ValueError()
                data = record(error.get("data", {}))
                retry = data.get("retry_after", 0)
                if type(retry) not in (int, float) or (
                    isinstance(retry, float) and not math.isfinite(retry)
                ):
                    raise ValueError()
            return value
        except ValueError, TypeError:
            raise InvalidFrame("invalid Apron frame") from None

    def _greeting(self, params):
        params = record(params)
        if type(params.get("apron")) is not int or params["apron"] != 10:
            raise InvalidFrame("unsupported Apron greeting")
        caps = string_list(params.get("capabilities", []))
        string_list(params.get("auth", []))
        ping = params.get("ping", 30)
        if (
            type(ping) not in (int, float)
            or (isinstance(ping, float) and not math.isfinite(ping))
            or ping <= 0
        ):
            raise InvalidFrame("invalid Apron heartbeat interval")
        self.server = params
        self.capabilities = set(caps)

    async def _read(self):
        try:
            async for raw in self.ws:
                frame = self._decode(raw)
                request_id = frame.get("id")
                if request_id is not None:
                    future = self.pending.get(request_id)
                    if future is not None and not future.done():
                        if "error" in frame:
                            error = frame["error"]
                            future.set_exception(
                                RPCError(
                                    error.get("code"), error.get("data", {}).get("retry_after", 0)
                                )
                            )
                        elif isinstance(frame.get("result"), dict):
                            future.set_result(frame["result"])
                        else:
                            future.set_exception(InvalidFrame("invalid Apron RPC reply"))
                elif "error" in frame:
                    error = frame["error"]
                    raise RPCError(error.get("code"), error.get("data", {}).get("retry_after", 0))
                elif frame.get("method") == "pong":
                    self._pong = time.monotonic()
                elif frame.get("method") == "server":
                    self._greeting(frame.get("params", {}))
                elif frame.get("method"):
                    try:
                        self.events.put_nowait(frame)
                    except asyncio.QueueFull:
                        raise ProtocolError("Apron inbound queue full") from None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = (
                exc if isinstance(exc, ProtocolError) else ProtocolError("Apron connection ended")
            )
        finally:
            self.closed.set()
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(self.failure or ProtocolError("Apron connection ended"))
            if self.ws:
                await self.ws.close()

    async def call(self, method, params=None):
        if self.closed.is_set() or not self.ws:
            raise self.failure or ProtocolError("Apron is disconnected")
        if len(self.pending) >= 32:
            raise ProtocolError("Apron RPC limit reached")
        self._counter += 1
        request_id = f"{self._prefix}-{self._counter}"
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            async with asyncio.timeout(self.timeout):
                await self.ws.send(
                    json.dumps({"method": method, "id": request_id, "params": params or {}})
                )
                return await future
        except TimeoutError:
            raise ProtocolError("Apron request timed out; delivery may be uncertain") from None
        except websockets.exceptions.WebSocketException, OSError:
            raise ProtocolError("Apron connection ended; delivery may be uncertain") from None
        finally:
            self.pending.pop(request_id, None)

    async def notify(self, method, params=None):
        if self.closed.is_set() or not self.ws:
            raise ProtocolError("Apron is disconnected")
        try:
            async with asyncio.timeout(self.timeout):
                await self.ws.send(json.dumps({"method": method, "params": params or {}}))
        except websockets.exceptions.WebSocketException, OSError, TimeoutError:
            raise ProtocolError("Apron notification failed") from None

    async def _heartbeat(self):
        interval = self.server.get("ping", 30)
        interval = min(30, max(1, interval)) if isinstance(interval, (int, float)) else 30
        try:
            while not self.closed.is_set():
                await asyncio.sleep(interval)
                if time.monotonic() - self._pong > 3 * interval + 5:
                    self.failure = ProtocolError("Apron heartbeat timed out")
                    await self.ws.close()
                    return
                await self.notify("ping")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failure = ProtocolError("Apron heartbeat failed")
            await self.ws.close()

    async def close(self):
        self.closed.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        if self.ws:
            await self.ws.close()
            self.ws = None
        for future in self.pending.values():
            if not future.done():
                future.cancel()
        self.pending.clear()
