"""Profile-aware, passive configuration. Never provisions identities or reads credential bytes."""

from dataclasses import dataclass
from pathlib import Path
import os
import stat

from gateway.platforms._shared import extra_or_secret
from hermes_constants import get_hermes_home
from .transport import validate_endpoint


def identifiers(value):
    if isinstance(value, str):
        value = [x.strip() for x in value.split(",") if x.strip()]
    if (
        not isinstance(value, list)
        or len(value) > 128
        or any(
            not isinstance(x, str)
            or not x
            or len(x) > 128
            or x == "*"
            or any(c.isspace() or ord(c) < 32 for c in x)
            for x in value
        )
    ):
        raise ValueError("Apron policy requires bounded explicit immutable IDs")
    return frozenset(value)


@dataclass(frozen=True)
class Options:
    url: str
    endpoint: str
    token_file: str
    allowed_users: frozenset
    rooms: frozenset
    dm_rooms: frozenset
    state_dir: Path
    test_loopback: bool = False
    artifact_dir: str = ""

    @classmethod
    def load(cls, config):
        e = getattr(config, "extra", {}) or {}
        url = e.get("url", "")
        endpoint = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/ws"
        test = e.get("test_loopback") is True
        validate_endpoint(endpoint, url, test)
        token_file = extra_or_secret(e, "token_file", "APRON_TOKEN_FILE")
        if not isinstance(token_file, str) or not token_file:
            raise ValueError("Apron needs a profile-scoped runtime token file")
        users = identifiers(extra_or_secret(e, "allowed_users", "APRON_ALLOWED_USERS", []))
        rooms = identifiers(e.get("rooms", []))
        dm = identifiers(e.get("dm_rooms", []))
        if not rooms or not dm.issubset(rooms):
            raise ValueError("Apron needs explicit rooms and a bounded DM policy")
        return cls(
            url,
            endpoint,
            token_file,
            users,
            rooms,
            dm,
            Path(e.get("state_dir") or get_hermes_home() / "apron"),
            test,
            e.get("artifact_dir", ""),
        )


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise ValueError("Apron state must be a private owned directory")


def read_secret(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            info = os.fstat(f.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or info.st_uid != os.geteuid()
            ):
                raise ValueError()
            token = f.read(1025).strip()
            if not 43 <= len(token) <= 1024 or any(c.isspace() for c in token):
                raise ValueError()
            return token
    except OSError, ValueError, UnicodeError:
        raise ValueError("Apron runtime credential file is unavailable or unsafe") from None
