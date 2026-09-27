"""The one segment rule (dav.within) and the unfiltered href mapping (dav.home_entries).

home_entries serves the tag REPORT: a tagged ancestor above NC_MCP_FILES_ROOT must stay
visible there, and a href that does not map onto the user's home must arrive as ``None``
instead of vanishing, so the caller can refuse instead of reading an empty set.
"""

import pytest

from mcp_connector import config
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


def multistatus(*hrefs: str) -> bytes:
    """A 207 body with one successful d:response per href, each carrying a file id."""
    responses = "".join(
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>"
        f"<oc:fileid>{index}</oc:fileid><d:resourcetype><d:collection/></d:resourcetype>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for index, href in enumerate(hrefs, start=10)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">{responses}</d:multistatus>'
    ).encode()


@pytest.mark.parametrize(
    ("path", "root", "expected"),
    [
        ("/A/kein/x", "/A/kein", True),
        ("/A/kein", "/A/kein", True),
        ("/A/keine", "/A/kein", False),
        ("/A", "/A/kein", False),
        ("/anything", "/", True),
    ],
)
def test_within_is_the_segment_rule(path: str, root: str, expected: bool) -> None:
    assert dav.within(path, root) is expected


def test_a_tagged_ancestor_above_the_sandbox_is_kept(
    creds: Credentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Shared/KI")
    body = multistatus("/remote.php/dav/files/alice/Shared/")

    entries = dav.home_entries(body, creds)

    assert len(entries) == 1
    path, props = entries[0]
    assert path == "/Shared"
    assert props[f"{{{davxml.OC}}}fileid"] == "10"
    # The same body through the sandboxed parser drops the ancestor: the difference is
    # exactly the missing in_files_root filter.
    assert dav.parse_entries(body, creds) == []


def test_a_foreign_prefix_becomes_none_and_is_not_dropped(creds: Credentials) -> None:
    body = multistatus(
        "/other/remote.php/dav/files/alice/x",
        "/remote.php/dav/files/alice/Docs/",
    )

    entries = dav.home_entries(body, creds)

    assert len(entries) == 2
    assert [path for path, _props in entries] == [None, "/Docs"]


def test_a_longer_account_name_is_not_this_user(creds: Credentials) -> None:
    entries = dav.home_entries(multistatus("/remote.php/dav/files/alicexyz/Docs/"), creds)

    assert [path for path, _props in entries] == [None]


@pytest.mark.parametrize(
    "href",
    [
        "/remote.php/dav/files/alice/A/../B",
        "/remote.php/dav/files/alice/A%5CB",
        "/remote.php/dav/files/alice/A%01B",
        "/remote.php/dav/files/alice/A%7FB",
        "/remote.php/dav/files/alice/./A",
    ],
)
def test_unsafe_segments_become_none(creds: Credentials, href: str) -> None:
    entries = dav.home_entries(multistatus(href), creds)

    assert [path for path, _props in entries] == [None]


def test_the_home_root_maps_to_slash(creds: Credentials) -> None:
    entries = dav.home_entries(multistatus("/remote.php/dav/files/alice/"), creds)

    assert [path for path, _props in entries] == ["/"]


def test_a_base_url_with_a_path_is_honoured() -> None:
    creds = Credentials("http://nc.test/cloud", USER, SECRET)

    entries = dav.home_entries(multistatus("/cloud/remote.php/dav/files/alice/A"), creds)

    assert [path for path, _props in entries] == ["/A"]


def test_the_sandbox_check_still_uses_the_segment_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/A/kein")

    assert dav.in_files_root("/A/kein/x") is True
    assert dav.in_files_root("/A/kein") is True
    assert dav.in_files_root("/A/keine") is False
    assert dav.in_files_root("/A/kein/../x") is False
