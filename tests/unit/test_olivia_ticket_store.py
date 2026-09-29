import sqlite3

import pytest

from mcp_connector.downloads import store

pytestmark = pytest.mark.anyio


def make(tmp_path):
    return store.TicketStore(tmp_path / store.TICKETS_FILENAME)


async def issue(subject, *, now=1000.0, ttl=600):
    return await subject.issue(
        auth_id="auth-1",
        nc_user="alice",
        path="/Docs/scan.pdf",
        name="scan.pdf",
        content_type="application/pdf",
        size=1234,
        ttl_seconds=ttl,
        now=now,
    )


async def test_issue_stores_only_the_hash(tmp_path):
    subject = make(tmp_path)
    token, expires = await issue(subject)
    assert len(token) >= 40
    assert expires == 1600
    raw = (tmp_path / store.TICKETS_FILENAME).read_bytes()
    assert token.encode() not in raw
    rows = (
        sqlite3.connect(tmp_path / store.TICKETS_FILENAME)
        .execute("SELECT token_hash, state FROM download_tickets")
        .fetchall()
    )
    assert rows == [(store.token_hash(token), "ready")]


async def test_claim_is_exclusive_and_release_allows_retry(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    ticket = await subject.claim(token, now=1001)
    assert ticket == store.Ticket(
        "auth-1", "alice", "/Docs/scan.pdf", "scan.pdf", "application/pdf", 1234, 1600
    )
    assert await subject.claim(token, now=1002) is None  # already in progress
    await subject.release(token)
    assert await subject.claim(token, now=1003) is not None  # retry after an interruption


async def test_finish_makes_the_link_unusable(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    assert await subject.claim(token, now=1001) is not None
    await subject.finish(token)
    assert await subject.claim(token, now=1002) is None
    assert await subject.peek(token, now=1002) is None


async def test_expired_and_unknown_tokens_are_refused(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject, ttl=60)
    assert await subject.claim(token, now=1061) is None
    assert await subject.claim("x" * 43, now=1001) is None


async def test_peek_does_not_consume(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    assert await subject.peek(token, now=1001) is not None
    assert await subject.claim(token, now=1002) is not None


async def test_issue_purges_used_and_long_expired_rows(tmp_path):
    subject = make(tmp_path)
    used, _ = await issue(subject, now=1000)
    await subject.claim(used, now=1001)
    await subject.finish(used)
    old, _ = await issue(subject, now=1000, ttl=60)  # expires at 1060
    await issue(subject, now=1060 + store.PURGE_AFTER_SECONDS + 1)
    hashes = {
        h
        for (h,) in sqlite3.connect(tmp_path / store.TICKETS_FILENAME).execute(
            "SELECT token_hash FROM download_tickets"
        )
    }
    assert store.token_hash(used) not in hashes
    assert store.token_hash(old) not in hashes
    assert len(hashes) == 1
