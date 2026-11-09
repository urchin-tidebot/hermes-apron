"""Small private inbox ledger: at-most-once dispatch, with explicit crash loss windows."""

import fcntl
import os
import sqlite3

from .config import private_dir


class State:
    def __init__(self, directory):
        private_dir(directory)
        self.lock = os.open(
            directory / "consumer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.lock)
            raise ValueError("Apron consumer already active for this profile state") from None
        try:
            path = directory / "inbox.db"
            if path.exists() and (path.is_symlink() or path.stat().st_mode & 0o077):
                self.close()
                raise ValueError("Apron ledger must be private")
            # Create before SQLite so its journal inherits private permissions.
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            self.db = sqlite3.connect(path, timeout=2)
            self.db.executescript(
                "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS checkpoint(room TEXT PRIMARY KEY, value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS dispatched(room TEXT, message TEXT, PRIMARY KEY(room,message));"
            )
        except OSError, ValueError, sqlite3.Error:
            self.close()
            raise ValueError("Apron ledger is unavailable or corrupt") from None

    def checkpoint(self, room):
        r = self.db.execute("SELECT value FROM checkpoint WHERE room=?", (room,)).fetchone()
        return r[0] if r else None

    def advance(self, room, value):
        old = self.checkpoint(room)
        if old is None or int(value) > int(old):
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO checkpoint VALUES (?,?)", (room, value))

    def reserve(self, room, message):
        if self.db.execute("SELECT COUNT(*) FROM dispatched").fetchone()[0] >= 100000:
            raise ValueError("Apron inbox limit reached; operator reconciliation required")
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO dispatched VALUES (?,?)", (room, message)
            )
        return cursor.rowcount == 1

    def close(self):
        if hasattr(self, "db"):
            self.db.close()
        if getattr(self, "lock", None) is not None:
            os.close(self.lock)
            self.lock = None


class CredentialLease:
    """Use Hermes' OS-user scoped credential reservation, plus same-process exclusion."""

    import threading

    _guard = threading.Lock()
    _held = set()

    def __init__(self, endpoint, token):
        import hashlib
        from gateway.status import acquire_scoped_lock

        self.identity = hashlib.sha256((endpoint + "\0" + token).encode()).hexdigest()
        with self._guard:
            if self.identity in self._held:
                raise ValueError("Apron credential already has a consumer")
            acquired, _ = acquire_scoped_lock(
                "apron", self.identity, metadata={"platform": "apron", "owner_kind": "process"}
            )
            if not acquired:
                raise ValueError("Apron credential already has a consumer")
            self._held.add(self.identity)

    def matches(self, endpoint, token):
        import hashlib
        import hmac

        identity = hashlib.sha256((endpoint + "\0" + token).encode()).hexdigest()
        return hmac.compare_digest(self.identity, identity)

    def close(self):
        from gateway.status_scoped_locks import release_scoped_lock

        with self._guard:
            if self.identity in self._held:
                release_scoped_lock("apron", self.identity)
                self._held.remove(self.identity)
