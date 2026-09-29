"""Download tickets: one row per link, only the SHA-256 of the token is kept.

A ticket is ``ready`` until a download starts (``in_progress``); a completed download marks it
``used``, an interrupted one puts it back to ``ready`` so the client can retry until it expires.
The file lives next to ``oauth.sqlite3`` but is a store of its own, so the upstream OAuth schema
stays untouched.
"""

import asyncio
import hashlib
import secrets
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import config

TICKETS_FILENAME = "downloads.sqlite3"
PURGE_AFTER_SECONDS = 3600
STATE_READY = "ready"
STATE_IN_PROGRESS = "in_progress"
STATE_USED = "used"

SCHEMA = """
CREATE TABLE IF NOT EXISTS download_tickets (
  token_hash TEXT PRIMARY KEY,
  auth_id TEXT,
  nc_user TEXT NOT NULL,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  state TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS download_tickets_expiry ON download_tickets(expires_at);
"""

_COLUMNS = "auth_id, nc_user, path, name, content_type, size, expires_at"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Ticket:
    auth_id: str | None
    nc_user: str
    path: str
    name: str
    content_type: str
    size: int
    expires_at: int


def _moment(now: float | None) -> int:
    return int(time.time() if now is None else now)


class TicketStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.executescript(SCHEMA)
        return conn

    async def _run[T](self, work: Callable[[sqlite3.Connection], T]) -> T:
        def call() -> T:
            conn = self._connect()
            try:
                return work(conn)
            finally:
                conn.close()

        return await asyncio.to_thread(call)

    async def issue(
        self,
        *,
        auth_id: str | None,
        nc_user: str,
        path: str,
        name: str,
        content_type: str,
        size: int,
        ttl_seconds: int,
        now: float | None = None,
    ) -> tuple[str, int]:
        moment = _moment(now)
        token = secrets.token_urlsafe(32)
        expires = moment + ttl_seconds

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM download_tickets WHERE state = ? OR expires_at < ?",
                (STATE_USED, moment - PURGE_AFTER_SECONDS),
            )
            conn.execute(
                "INSERT INTO download_tickets (token_hash, auth_id, nc_user, path, name,"
                " content_type, size, created_at, expires_at, state)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token_hash(token),
                    auth_id,
                    nc_user,
                    path,
                    name,
                    content_type,
                    size,
                    moment,
                    expires,
                    STATE_READY,
                ),
            )

        await self._run(work)
        return token, expires

    async def claim(self, token: str, *, now: float | None = None) -> Ticket | None:
        moment = _moment(now)
        digest = token_hash(token)

        def work(conn: sqlite3.Connection) -> Ticket | None:
            changed = conn.execute(
                "UPDATE download_tickets SET state = ? WHERE token_hash = ? AND state = ?"
                " AND expires_at > ?",
                (STATE_IN_PROGRESS, digest, STATE_READY, moment),
            ).rowcount
            if changed != 1:
                return None
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM download_tickets WHERE token_hash = ?",  # noqa: S608
                (digest,),
            ).fetchone()
            return Ticket(*row)

        return await self._run(work)

    async def peek(self, token: str, *, now: float | None = None) -> Ticket | None:
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> Ticket | None:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM download_tickets WHERE token_hash = ? AND state = ?"  # noqa: S608
                " AND expires_at > ?",
                (token_hash(token), STATE_READY, moment),
            ).fetchone()
            return None if row is None else Ticket(*row)

        return await self._run(work)

    async def finish(self, token: str) -> None:
        await self._set_state(token, STATE_USED)

    async def release(self, token: str) -> None:
        await self._set_state(token, STATE_READY)

    async def _set_state(self, token: str, state: str) -> None:
        digest = token_hash(token)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE download_tickets SET state = ? WHERE token_hash = ? AND state = ?",
                (state, digest, STATE_IN_PROGRESS),
            )

        await self._run(work)


def ticket_store(env: Mapping[str, str] | None = None) -> TicketStore:
    return TicketStore(config.persistent_storage(env) / TICKETS_FILENAME)
