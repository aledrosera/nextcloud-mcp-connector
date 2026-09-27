"""Mock helpers for the ``kein-ki`` guard; a helper module, not a test module.

Once a tool family asks ``clients.exclusion.scope(clients)``, every call sends a
``PROPFIND /remote.php/dav/systemtags/`` first. A test under ``respx.mock`` without a route
for it fails on that unmocked request, although it asserts behaviour that has nothing to do
with tags. Two kinds of help live here:

*   :func:`patch_untagged` replaces the guard's flight by the ``untagged`` answer without
    any HTTP. The existing family tests use it through an autouse fixture: they assert the
    behaviour without any ``kein-ki`` tag, and that is exactly what it gives them.
*   :func:`untagged`, :func:`active` and :func:`unverifiable` mock the real requests for
    one of the three states, so the ``*_exclusion`` test modules of the family plans prove
    the wiring against the real guard in one line.

Why a module and not ``conftest.py``: ``tests/conftest.py`` imports nothing from
``mcp_connector`` on purpose, and a fixture there would reach every test layer. This module
is imported by name; ``pyproject.toml`` puts ``tests/unit`` on the import path for it.
"""

import httpx
import pytest
import respx

from mcp_connector.nextcloud import exclusion
from mcp_connector.nextcloud.clients import xml as davxml

BASE = "http://nc.test"
USER = "alice"
TAGS = f"{BASE}/remote.php/dav/systemtags/"
HOME = f"{BASE}/remote.php/dav/files/{USER}/"
XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}

#: The id and the name of the exclusion tag in every mocked listing.
KEIN_KI = ("64", "kein-ki")

#: A foreign tag, so an ``untagged`` listing is not simply empty.
OTHER_TAG = ("70", "projekt")


def _multistatus(*responses: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">'
        f"{''.join(responses)}</d:multistatus>"
    ).encode()


def _response(href: str, props: str) -> str:
    return (
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )


def tag_list(*tags: tuple[str, str]) -> bytes:
    """A 207 tag listing: the collection itself (no id) plus one entry per (id, name)."""
    entries = [_response("/remote.php/dav/systemtags/", "<oc:display-name></oc:display-name>")]
    entries += [
        _response(
            f"/remote.php/dav/systemtags/{tag_id}",
            f"<oc:id>{tag_id}</oc:id><oc:display-name>{name}</oc:display-name>",
        )
        for tag_id, name in tags
    ]
    return _multistatus(*entries)


def report_207(*nodes: tuple[str, str, bool], user: str = USER) -> bytes:
    """A 207 REPORT answer; each node is (href suffix below the home, fileid, is_collection)."""
    return _multistatus(
        *(
            _response(
                f"/remote.php/dav/files/{user}/{suffix}",
                f"<oc:fileid>{fileid}</oc:fileid><d:resourcetype>"
                f"{'<d:collection/>' if folder else ''}</d:resourcetype>",
            )
            for suffix, fileid, folder in nodes
        )
    )


def listed(body: bytes) -> httpx.Response:
    return httpx.Response(207, content=body, headers=XML_HEADERS)


def untagged(mock: respx.MockRouter) -> respx.Route:
    """Mock a tag listing without ``kein-ki``: the guard answers ``untagged``, no REPORT."""
    return mock.route(method="PROPFIND", url=TAGS).mock(return_value=listed(tag_list(OTHER_TAG)))


def active(
    mock: respx.MockRouter, *nodes: tuple[str, str, bool]
) -> tuple[respx.Route, respx.Route]:
    """Mock ``kein-ki`` on ``nodes`` (href suffix, fileid, is_collection); returns both routes.

    The routes come back as ``(listing, report)`` so a test can count the requests.
    """
    listing = mock.route(method="PROPFIND", url=TAGS).mock(
        return_value=listed(tag_list(KEIN_KI, OTHER_TAG))
    )
    report = mock.route(method="REPORT", url=HOME).mock(return_value=listed(report_207(*nodes)))
    return listing, report


def unverifiable(mock: respx.MockRouter) -> tuple[respx.Route, respx.Route]:
    """Mock a listing with ``kein-ki`` and a failing REPORT: the guard answers ``unverifiable``."""
    listing = mock.route(method="PROPFIND", url=TAGS).mock(return_value=listed(tag_list(KEIN_KI)))
    report = mock.route(method="REPORT", url=HOME).mock(return_value=httpx.Response(500))
    return listing, report


def patch_untagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every guard answer ``untagged`` without a single request.

    Only the flight is replaced; ``ExclusionGuard.scope`` keeps its identity binding and
    its single-flight lock, so a test still runs the guard code the tools call.
    """

    async def no_tag(_clients: object) -> exclusion.TagScope:
        return exclusion.UNTAGGED

    monkeypatch.setattr(exclusion, "load_scope", no_tag)


def reset() -> None:
    """Drop the process-wide name-to-id cache, so no test sees the ids of another."""
    exclusion.clear_cache()
