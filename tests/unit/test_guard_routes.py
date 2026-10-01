"""The guard mock helpers do what their names promise, against the real guard of NcClients."""

from collections.abc import Iterator

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials

SECRET = "app-password-test"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    guard_routes.reset()
    yield
    guard_routes.reset()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(guard_routes.BASE, guard_routes.USER, SECRET),
    )


@pytest.mark.anyio
async def test_untagged_mocks_an_untagged_answer(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing = guard_routes.untagged(mock)

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "untagged"
    assert listing.call_count == 1


@pytest.mark.anyio
async def test_active_mocks_the_tagged_nodes(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing, report = guard_routes.active(
            mock, ("A/kein/", "955", True), ("B.md", "957", False)
        )

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "active"
    assert scope.paths == frozenset({"/A/kein", "/B.md"})
    assert scope.fileids == frozenset({"955", "957"})
    assert scope.has_folders is True
    assert listing.call_count == 1
    assert report.call_count == 1


@pytest.mark.anyio
async def test_active_with_files_only_has_no_folders(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        guard_routes.active(mock, ("B.md", "957", False))

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "active"
    assert scope.has_folders is False


@pytest.mark.anyio
async def test_unverifiable_mocks_a_failing_report(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        _listing, report = guard_routes.unverifiable(mock)

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "unverifiable"
    assert report.call_count == 1


@pytest.mark.anyio
async def test_stale_mocks_a_report_that_goes_stale_twice(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        listing, report = guard_routes.stale(mock)

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "unverifiable"
    assert scope.reason == "stale_twice"
    assert listing.call_count == 2
    assert report.call_count == 2


@pytest.mark.anyio
async def test_timeout_mocks_a_report_that_times_out(clients: NcClients) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        _listing, report = guard_routes.timeout(mock)

        scope = await clients.exclusion.scope(clients)

    assert scope.state == "unverifiable"
    assert scope.reason == "timeout"
    assert report.call_count >= 1


@pytest.mark.anyio
async def test_patch_untagged_costs_no_request(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard_routes.patch_untagged(monkeypatch)
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        scope = await clients.exclusion.scope(clients)
        again = await clients.exclusion.scope(clients)

    assert scope.state == "untagged"
    assert again is scope
    assert mock.calls.call_count == 0
