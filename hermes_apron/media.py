"""Same-origin capability writes without token-bearing HTTP client diagnostics."""

from __future__ import annotations
import asyncio
import contextlib
import re
import ssl
from urllib.parse import urlsplit

from .transport import ProtocolError


def write_target(origin, value):
    try:
        url, site = urlsplit(value), urlsplit(origin)
        if (
            url.scheme != site.scheme
            or url.netloc != site.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
            or not re.fullmatch(r"/write/[A-Za-z0-9_-]{16,128}", url.path)
        ):
            raise ValueError()
        return url
    except TypeError, ValueError:
        raise ProtocolError("Apron write capability is not on the configured origin") from None


async def put(origin, capability, chunks, content_type="text/plain; charset=utf-8", limit=1048576):
    target = write_target(origin, capability)
    writer = None
    try:
        async with asyncio.timeout(300):
            context = ssl.create_default_context() if target.scheme == "https" else None
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    target.hostname,
                    target.port or (443 if context else 80),
                    ssl=context,
                    server_hostname=target.hostname if context else None,
                    limit=8192,
                ),
                5,
            )
            header = f"PUT {target.path} HTTP/1.1\r\nHost: {target.netloc}\r\nContent-Type: {content_type}\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
            writer.write(header.encode("ascii"))
            size = 0
            async for chunk in chunks:
                if not isinstance(chunk, bytes) or len(chunk) > 65536:
                    raise ProtocolError("Apron transfer chunk exceeds bounds")
                size += len(chunk)
                if size > limit:
                    raise ProtocolError("Apron transfer exceeds bounds")
                if chunk:
                    writer.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    await asyncio.wait_for(writer.drain(), 5)
            writer.write(b"0\r\n\r\n")
            await asyncio.wait_for(writer.drain(), 5)
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            status = int(head.split(b" ", 2)[1])
            if not 200 <= status < 300:
                raise ProtocolError("Apron transfer refused; redirects are forbidden")
    except asyncio.CancelledError:
        raise
    except Exception:
        raise ProtocolError("Apron media transfer failed") from None
    finally:
        if writer:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


class Append:
    def __init__(self, origin, capability):
        write_target(origin, capability)
        self.queue = asyncio.Queue(maxsize=8)
        self.task = asyncio.create_task(put(origin, capability, self._chunks()))
        self.finished = False

    async def _chunks(self):
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                return
            yield chunk

    async def write(self, text):
        if self.finished:
            raise ProtocolError("Apron stream ended")
        if self.task.done():
            await self.task
            raise ProtocolError("Apron stream ended")
        async with asyncio.timeout(5):
            await self.queue.put(text.encode())

    async def finish(self):
        if not self.finished:
            self.finished = True
            async with asyncio.timeout(5):
                await self.queue.put(None)
                await self.task

    async def abort(self):
        self.finished = True
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


def read_artifact(directory, file_path, credential_file):
    import os
    from pathlib import Path
    import stat

    root, path = Path(directory), Path(file_path)
    if not directory or path.name.startswith(".") or ".." in path.parts:
        raise ValueError("artifact path denied")
    root = root.absolute()
    if path.absolute().parent != root or path.absolute() == Path(credential_file).absolute():
        raise ValueError("artifact outside the configured flat export directory")
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(directory_fd)
        if info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise ValueError("artifact directory is not private")
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or info.st_uid != os.geteuid()
                or info.st_size > 8 * 1048576
            ):
                raise ValueError("artifact is unsafe or oversized")
            data = file.read(8 * 1048576 + 1)
            if len(data) > 8 * 1048576:
                raise ValueError("artifact exceeds bounds")
            return data, path.name
    finally:
        os.close(directory_fd)


async def single(data):
    for offset in range(0, len(data), 65536):
        yield data[offset : offset + 65536]
