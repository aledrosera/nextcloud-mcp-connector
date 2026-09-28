"""The Tables family behind the ``kein-ki`` guard (D-28-14, D-28-18), in all three states.

A Tables link cell that points at a Nextcloud file stores a copy of the file name and of the
file id: ``rows/simple`` answers it as a JSON string ``{"title": <name>, "value":
"<url>/f/<fileid>", "providerId": "files"}`` with PHP-escaped slashes (measured in 28-01),
and an empty link cell as ``null``. A cell of a tagged file answers like an empty one, in
``tables_browse`` level=rows and in ``fetch(table:)`` alike.

No ``patch_untagged`` here: every test mocks the real guard requests through
``guard_routes`` and counts them, because the cheap path (a table without a file link costs
no guard request at all) is part of the contract and not an optimisation.
"""

import json
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import chatgpt, withhold
from mcp_connector.tools import tables as tables_tools

BASE = guard_routes.BASE
USER = guard_routes.USER
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
V2_BASE = f"{BASE}/ocs/v2.php/apps/tables/api/2"
V1_BASE = f"{BASE}/index.php/apps/tables/api/1"
TABLE_URL = f"{V2_BASE}/tables/7"
ROWS_URL = f"{V1_BASE}/tables/7/rows/simple"
DAV_SEARCH = f"{BASE}/remote.php/dav/"
DEGRADED = [withhold.degraded_entry("source")]

TABLES_INSTALLED = {"enabled": True, "version": "2.2.2", "apiVersions": ["1.0", "2.0"]}
TABLE = {"id": 7, "title": "Verweise", "rowsCount": 2, "columnsCount": 2, "isShared": False}

SECRET_NAME = "geheim-mk2122.txt"
SECRET_ID = "901"
OPEN_NAME = "offen.txt"
OPEN_ID = "902"
FOLDER_ID = "800"


@pytest.fixture(autouse=True)
def _fresh_caches() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


def fresh() -> NcClients:
    """One NcClients per tool call, so every call has its own guard."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def link(name: str, fileid: str, provider: str = "files") -> str:
    """One link cell as the app stores it: a JSON string (D-28-18).

    The PHP escaping of the slashes happens on the wire in :func:`mock_tables`, exactly as
    measured in 28-01; the decoded cell carries plain slashes.
    """
    return json.dumps({"title": name, "value": f"{BASE}/f/{fileid}", "providerId": provider})


def mock_tables(mock: respx.MockRouter, rows: list[list[Any]]) -> None:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(
            200, json=envelope({"capabilities": {"core": {}, "tables": TABLES_INSTALLED}})
        )
    )
    mock.get(TABLE_URL).mock(return_value=httpx.Response(200, json=envelope(TABLE)))
    # PHP's json_encode escapes every slash, so the wire carries ``\/`` twice over.
    wire = json.dumps(rows).replace("/", "\\/")
    mock.get(ROWS_URL).mock(
        return_value=httpx.Response(
            200, content=wire.encode(), headers={"Content-Type": "application/json"}
        )
    )


def dav_answer(*entries: tuple[str, str]) -> httpx.Response:
    """A 207 SEARCH answer of paths_of_fileids; each entry is (suffix below the home, fileid)."""
    responses = "".join(
        f"<d:response><d:href>/remote.php/dav/files/{USER}/{suffix}</d:href><d:propstat>"
        f"<d:prop><oc:fileid>{fileid}</oc:fileid><d:resourcetype/></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for suffix, fileid in entries
    )
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">{responses}</d:multistatus>'
    ).encode()
    return guard_routes.listed(body)


async def browse_rows(rows: list[list[Any]], setup: Any = None) -> tuple[dict[str, Any], Any]:
    with respx.mock(assert_all_called=False) as mock:
        mock_tables(mock, rows)
        routes = setup(mock) if setup else None
        answer = await tables_tools.browse(fresh(), level="rows", table_id="7")
    return answer, routes


async def fetch_table(rows: list[list[Any]], setup: Any = None) -> tuple[dict[str, Any], Any]:
    with respx.mock(assert_all_called=False) as mock:
        mock_tables(mock, rows)
        routes = setup(mock) if setup else None
        result = await chatgpt.fetch(fresh(), "table:7")
    return result, routes


def dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def assert_nothing_of_the_secret(value: Any) -> None:
    text = dump(value)
    assert SECRET_NAME not in text
    assert f"f\\\\/{SECRET_ID}" not in text
    assert f"/f/{SECRET_ID}" not in text
    assert SECRET_ID not in text


HEADER = ["Aufgabe", "Verweis"]


def secret_rows() -> list[list[Any]]:
    return [HEADER, ["Baulos 3", link(SECRET_NAME, SECRET_ID)]]


def empty_rows() -> list[list[Any]]:
    return [HEADER, ["Baulos 3", None]]


# --- tables_browse level=rows -----------------------------------------------------------


@pytest.mark.anyio
async def test_a_table_without_a_file_link_costs_no_guard_request() -> None:
    rows = [HEADER, ["Baulos 3", "offen"], ["Siehe /f/123", None]]
    answer, (listing, report) = await browse_rows(rows, lambda m: guard_routes.active(m))

    assert listing.call_count == 0
    assert report.call_count == 0
    assert answer["results"] == [
        {"Aufgabe": "Baulos 3", "Verweis": "offen"},
        {"Aufgabe": "Siehe /f/123", "Verweis": None},
    ]
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_untagged_leaves_every_link_cell_as_it_came() -> None:
    answer, _ = await browse_rows(secret_rows(), guard_routes.untagged)

    cell = answer["results"][0]["Verweis"]
    assert json.loads(cell) == {
        "title": SECRET_NAME,
        "value": f"{BASE}/f/{SECRET_ID}",
        "providerId": "files",
    }
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_tagged_file_link_is_withheld_and_names_nothing() -> None:
    answer, _ = await browse_rows(
        secret_rows(), lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )

    assert answer["results"][0]["Verweis"] is None
    assert answer["results"][0]["Aufgabe"] == "Baulos 3"
    assert_nothing_of_the_secret(answer)
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_link_cell_with_escaped_slashes_inside_is_read_as_well() -> None:
    escaped = link(SECRET_NAME, SECRET_ID).replace("/", "\\/")
    answer, _ = await browse_rows(
        [HEADER, ["a", escaped]],
        lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False)),
    )

    assert answer["results"][0]["Verweis"] is None
    assert_nothing_of_the_secret(answer)


@pytest.mark.anyio
async def test_a_tagged_link_cell_answers_like_an_empty_one() -> None:
    tagged, _ = await browse_rows(
        secret_rows(), lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )
    empty, _ = await browse_rows(empty_rows(), guard_routes.untagged)

    assert dump(tagged) == dump(empty)


@pytest.mark.anyio
async def test_an_untagged_file_link_stays_while_a_tagged_one_goes() -> None:
    rows = [HEADER, ["a", link(OPEN_NAME, OPEN_ID)], ["b", link(SECRET_NAME, SECRET_ID)]]
    answer, _ = await browse_rows(
        rows, lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )

    assert json.loads(answer["results"][0]["Verweis"])["title"] == OPEN_NAME
    assert answer["results"][1]["Verweis"] is None
    assert_nothing_of_the_secret(answer)


@pytest.mark.anyio
async def test_a_link_below_a_tagged_folder_is_withheld_and_one_outside_stays() -> None:
    rows = [HEADER, ["a", link(OPEN_NAME, OPEN_ID)], ["b", link(SECRET_NAME, SECRET_ID)]]

    def setup(mock: respx.MockRouter) -> respx.Route:
        guard_routes.active(mock, ("Gesperrt", FOLDER_ID, True))
        return mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(
                ("Gesperrt/geheim.txt", SECRET_ID), ("Offen/offen.txt", OPEN_ID)
            )
        )

    answer, search = await browse_rows(rows, setup)

    assert search.call_count == 1
    assert json.loads(answer["results"][0]["Verweis"])["title"] == OPEN_NAME
    assert answer["results"][1]["Verweis"] is None
    assert_nothing_of_the_secret(answer)


@pytest.mark.anyio
async def test_an_unresolvable_link_under_a_tagged_folder_is_withheld() -> None:
    def setup(mock: respx.MockRouter) -> None:
        guard_routes.active(mock, ("Gesperrt", FOLDER_ID, True))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=dav_answer())

    answer, _ = await browse_rows(secret_rows(), setup)

    assert answer["results"][0]["Verweis"] is None
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_failing_path_lookup_withholds_every_file_link_and_says_so() -> None:
    rows = [HEADER, ["a", link(OPEN_NAME, OPEN_ID)], ["b", link(SECRET_NAME, SECRET_ID)]]

    def setup(mock: respx.MockRouter) -> None:
        guard_routes.active(mock, ("Gesperrt", FOLDER_ID, True))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=httpx.Response(500))

    answer, _ = await browse_rows(rows, setup)

    assert [row["Verweis"] for row in answer["results"]] == [None, None]
    assert answer["degraded"] == DEGRADED


@pytest.mark.anyio
@pytest.mark.parametrize("outage", ["unverifiable", "stale", "timeout"])
async def test_an_unanswered_check_withholds_every_file_link_and_says_so(outage: str) -> None:
    rows = [
        HEADER,
        ["a", link(OPEN_NAME, OPEN_ID)],
        ["b", link(SECRET_NAME, SECRET_ID)],
        ["c", "freier Text"],
    ]
    answer, _ = await browse_rows(rows, getattr(guard_routes, outage))

    assert [row["Verweis"] for row in answer["results"]] == [None, None, "freier Text"]
    assert answer["degraded"] == DEGRADED
    assert_nothing_of_the_secret(answer)


@pytest.mark.anyio
async def test_foreign_text_and_other_providers_are_not_link_cells() -> None:
    web = link("Webseite", "123", provider="url")
    rows = [HEADER, ["Siehe /f/123", "http://nc.test/f/123"], ["x", web]]
    answer, (listing, report) = await browse_rows(rows, guard_routes.unverifiable)

    assert listing.call_count == 0
    assert report.call_count == 0
    assert answer["results"][0] == {"Aufgabe": "Siehe /f/123", "Verweis": "http://nc.test/f/123"}
    assert json.loads(answer["results"][1]["Verweis"])["providerId"] == "url"
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_file_link_without_a_readable_id_is_withheld_while_a_tag_is_active() -> None:
    raw = json.dumps({"title": SECRET_NAME, "value": "", "providerId": "files"})
    answer, _ = await browse_rows(
        [HEADER, ["a", raw]], lambda m: guard_routes.active(m, ("Docs/x.txt", "1", False))
    )

    assert answer["results"][0]["Verweis"] is None
    assert_nothing_of_the_secret(answer)


@pytest.mark.anyio
async def test_many_link_cells_cost_one_report() -> None:
    rows = [HEADER] + [["r", link(f"datei-{index}.txt", str(1000 + index))] for index in range(8)]
    rows.append(["s", link(SECRET_NAME, SECRET_ID)])
    answer, (listing, report) = await browse_rows(
        rows, lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )

    assert listing.call_count == 1
    assert report.call_count == 1
    assert answer["results"][-1]["Verweis"] is None
    assert answer["count"] == 9


# --- fetch(table:) ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_table_withholds_a_tagged_link_like_an_empty_cell() -> None:
    tagged, _ = await fetch_table(
        secret_rows(), lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )
    empty, _ = await fetch_table(empty_rows(), guard_routes.untagged)

    assert_nothing_of_the_secret(tagged)
    assert dump(tagged) == dump(empty)
    assert "degraded" not in tagged["metadata"]


@pytest.mark.anyio
async def test_fetch_table_in_an_outage_empties_every_link_and_says_so() -> None:
    rows = [HEADER, ["a", link(OPEN_NAME, OPEN_ID)], ["b", link(SECRET_NAME, SECRET_ID)]]
    result, _ = await fetch_table(rows, guard_routes.unverifiable)

    assert_nothing_of_the_secret(result)
    assert OPEN_NAME not in result["text"]
    assert result["metadata"]["degraded"] == withhold.EXCLUSION_UNAVAILABLE


@pytest.mark.anyio
async def test_fetch_table_without_a_link_asks_no_guard() -> None:
    rows = [HEADER, ["Baulos 3", "offen"]]
    result, (listing, report) = await fetch_table(rows, lambda m: guard_routes.active(m))

    assert listing.call_count == 0
    assert report.call_count == 0
    assert "Baulos 3 | offen" in result["text"]
    assert "degraded" not in result["metadata"]


@pytest.mark.anyio
async def test_a_row_of_nothing_but_a_withheld_link_still_counts_as_a_row() -> None:
    rows = [["Verweis"], [link(SECRET_NAME, SECRET_ID)]]
    result, _ = await fetch_table(
        rows, lambda m: guard_routes.active(m, ("Docs/geheim.txt", SECRET_ID, False))
    )

    assert result["metadata"]["rows_shown"] == "1"
    assert_nothing_of_the_secret(result)
