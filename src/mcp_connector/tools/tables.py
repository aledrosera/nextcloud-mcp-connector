"""Tables tools: one browse tool with a level, and one create-only write (D-06, D-14).

**One tool, three levels.** ``tables_browse(level=...)`` walks the tables, the columns of a
table and its rows. Three separate tools would cost three slots in every client that limits
them and three schemas in every ``tools/list``, for navigation the model can express in one
enum value. The answer envelope is the same on every level (``level``, ``count``,
``results``), so the model learns one shape instead of three.

**The limit is enforced, not offered.** A row read without a limit returns *every* row of
the table, so a table with 20.000 rows would become one MCP answer (pitfall 1). The default
is :data:`DEFAULT_LIMIT` rows, the ceiling is :data:`MAX_LIMIT`, and a table that has more
rows than the window says so in the answer: ``rowsCount`` next to ``count`` and ``offset``,
plus ``truncated`` and a ``next`` handle. ``rowsCount`` is left out instead of invented when
the app reports none, and a window that came back full is then the evidence that there is
more. Truncation is named here, never silent.

**Two things are explained before they can fail.** A missing or disabled Tables app stops
both tools at the capabilities check, before the first Tables request (SRV-04). And a user
without a write permission on a shared table is refused by this tool with a sentence and a
next step, instead of being walked into a 403 out of Nextcloud's permission middleware. The
middleware stays the authority; the pre-check is only the better error message.

Deliberately absent: update, delete, creating columns or whole tables, importing a scheme
and every share path. The client below has no code for any of it, which is what makes the
create-only annotation of ``tables_create_row`` honest rather than a promise (T-08-11).

**A link cell is a stored copy of a file (D-28-14).** A Tables link column that points at a
Nextcloud file keeps the file name and the file id in the cell itself, so a row read would
name a file tagged ``kein-ki`` without ever touching the file. :func:`screen_links` runs once
per call before any cell is projected, in ``tables_browse`` and in ``fetch(table:)`` alike,
and a cell of a tagged file answers exactly like an empty link cell.
"""

import json
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import httpx

from .. import paging, provider_map
from ..errors import ToolError
from ..nextcloud import NcClients, capabilities
from ..nextcloud.clients import dav
from ..nextcloud.clients import tables as tables_client
from . import marks, withhold

APP = "tables"

#: The ``providerId`` of a link cell that points at a Nextcloud file (D-28-18, measured in
#: 28-01). Every other provider (a web address, a contact) names no file and stays untouched.
_FILES_PROVIDER = "files"

#: The three navigation levels of ``tables_browse``, in the order a model walks them.
LEVELS = ("tables", "columns", "rows")

#: TABLES-01: a row read without an explicit limit reads this many rows and not the table.
DEFAULT_LIMIT = 25
MAX_LIMIT = 200

_LEVEL_HINT = f"Use one of: {', '.join(LEVELS)}."
_TABLE_HINT = "Call tables_browse with level=tables first; it lists the table ids."

#: The way out of a cursor on a level that has none. One sentence and the next step, like every
#: other refusal of this family.
_CURSOR_HINT = (
    "Only level=rows hands out a cursor. Call tables_browse without cursor; the answer says "
    "with truncated that it was cut."
)

#: Column fields that a model needs to interpret a value, and only those. Everything else
#: of a column object (uuid, technicalName, orderWeight, defaults, timestamps) is payload
#: nobody reads.
_COLUMN_LIMITS = (
    "selectionOptions",
    "textMaxLength",
    "numberMin",
    "numberMax",
    "numberDecimals",
    "datetimeDefault",
)

#: The example is part of the hint, because "invalid JSON" without a shape to copy costs a
#: round trip that a single object literal prevents.
_VALUES_HINT = (
    'Pass one JSON object of column titles and values, for example {"Task": "Call back", '
    '"Amount": 12.5}. Call tables_browse with level=columns for the titles and their types.'
)

#: A column object without a numeric id is a deformed answer, and it is the one deformation
#: that would write instead of fail: ``str(None)`` is ``"None"``, the app casts every key with
#: ``(int)``, and ``(int)"None"`` is ``0`` (T-08-15 one level down).
_COLUMN_ID_HINT = (
    "Tables addresses a column by its numeric id, and this answer carried none, so the value "
    "cannot be assigned to a column. Check that the Tables app is enabled and up to date on "
    "that instance, then read the columns again with tables_browse."
)


async def browse(
    clients: NcClients,
    level: str = "tables",
    table_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Walk the user's Tables: the tables, the columns of one table, or its rows.

    A ``cursor`` on the table or the column level is refused rather than ignored, and it is
    refused here, before the capabilities request, so the cheapest mistake costs no request at
    all. Only the row level hands one out, so a handle on either of the other two is either a
    handle of the row level or one somebody invented; answering it with the first page again
    would look like a page that happens to be identical to the previous one, and a model has no
    way to notice that its paging went in a circle (review finding IN-04).
    """
    if level not in LEVELS:
        raise ToolError(message=f"{level!r} is not a Tables level.", hint=_LEVEL_HINT)
    if str(cursor or "").strip() and level != "rows":
        raise ToolError(
            message=f"level={level!r} has no next page, so a cursor cannot be applied here.",
            hint=_CURSOR_HINT,
        )
    capped = min(max(limit, 1), MAX_LIMIT)

    await capabilities.require_app(clients, APP)

    if level == "tables":
        return _envelope(level, await _tables(clients), capped)

    table = str(table_id or "").strip()
    if not table:
        raise ToolError(message=f"level={level!r} needs a table_id.", hint=_TABLE_HINT)

    if level == "columns":
        columns = await tables_client.get_columns(clients.client, clients.creds, table)
        return _envelope(level, [_column(column) for column in columns], capped)

    return await _rows(clients, table, capped, cursor)


async def create_row(clients: NcClients, table_id: str, values: str) -> dict[str, Any]:
    """Add one row to an existing table, addressed by column titles instead of ids.

    ``values`` is a **string** with one compact JSON object, not a mapping parameter. A
    ``dict`` parameter would pull ``additionalProperties`` or ``$defs`` into the input
    schema, and the tool surface of this server forbids ``$defs`` in several places on
    purpose; the precedent in this codebase is the comma string of
    ``unified_search.providers``. The Tables app accepts a JSON string for ``data`` as well
    (K4), so the string does not create a second shape on the way down either.

    Nothing is written before all four refusals have been passed: a missing write
    permission, an unknown title, an ambiguous title and a missing mandatory column. The
    order matters, because each of them is cheaper than the write it prevents.

    Cell values are not type checked here. The accepted shape per column ``type`` and
    ``subtype`` is not fully documented in the app, and a hand rolled validator would be a
    second truth that goes stale with every new column type. A 400 of the app is passed
    through with its own message instead. Verified shapes: a text column takes a JSON
    string, a number column takes a JSON number.

    There is no retry. A timeout does not mean that nothing was written, and no tool of this
    server can remove a duplicated row again, so the answer carries the id of the new row
    and the model can read back instead of repeating (T-08-10).
    """
    await capabilities.require_app(clients, APP)

    wanted = _parse_values(values)
    table = str(table_id or "").strip()

    info = await tables_client.get_table(clients.client, clients.creds, table)
    if not _may_create(info):
        raise ToolError(
            message=f"No permission to add a row to table {table} ({_text(info.get('title'))}).",
            hint=(
                "This table is shared with this account without a create permission. Ask its "
                "owner in Nextcloud for a write permission, or pick a table that tables_browse "
                "reports with can_create."
            ),
        )

    columns = await tables_client.get_columns(clients.client, clients.creds, table)
    data, written = _by_column_id(table, wanted, columns)

    row = await tables_client.create_row(clients.client, clients.creds, table, data=data)
    row_id = row.get("id")
    if row_id in (None, ""):
        raise ToolError(
            message="Nextcloud created the row but reported no id.",
            hint="Look for the row in the Tables app; it was probably created.",
        )

    return {
        "id": row_id,
        "table_id": table,
        "url": tables_client.web_url(clients.creds, table),
        "values_written": written,
    }


def _parse_values(values: str) -> dict[str, Any]:
    """Read the free form parameter, and answer a bad one with a shape to copy."""
    try:
        parsed = json.loads(values or "")
    except json.JSONDecodeError:
        # ``from None``: a decoder traceback would carry the raw parameter into the log and
        # tell the model nothing it can act on.
        raise ToolError(message="values is not valid JSON.", hint=_VALUES_HINT) from None

    if isinstance(parsed, list):
        raise ToolError(message="values must be a JSON object, not a list.", hint=_VALUES_HINT)
    if not isinstance(parsed, dict):
        raise ToolError(
            message="values must be a JSON object of column titles and values.",
            hint=_VALUES_HINT,
        )
    if not parsed:
        raise ToolError(
            message="values is an empty object, so there is nothing to write.",
            hint=_VALUES_HINT,
        )
    return parsed


def _by_column_id(
    table: str, wanted: dict[str, Any], columns: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve column titles against the columns of the instance, or refuse and say why.

    Titles are never guessed and never sent: the keys of the returned mapping are column
    **ids**, because the app casts every key with ``(int)`` and a title would silently become
    the column ``0`` (T-08-15). The comparison is normalised, so "Task" and "task " find the
    same column, and a title that matches two columns ends the call instead of picking one
    of them and writing into the wrong column.

    The normalisation has a mirror case with the same rule (review finding WR-04): two
    **keys** of ``values`` that normalise to the same column, "Task" and "task " in one
    object, would silently overwrite each other in the mapping, and the loser would vanish
    from a **write** without the caller ever seeing an error. Refused before anything is
    resolved, because a silent last wins on a write path is data loss with a healthy looking
    answer.

    The same trap has a second entrance, one level down: a column object without an ``id``
    would produce the key ``"None"``, and ``(int)"None"`` is ``0`` as well. That takes a
    deformed answer of the app, which the rest of this family treats as a real case
    (``_as_list``, ``_as_dict``, ``_path_id``), so it is refused here rather than written.
    """
    by_title: dict[str, list[dict[str, Any]]] = {}
    for column in columns:
        by_title.setdefault(_normalise(column.get("title")), []).append(column)

    known = [_text(column.get("title") or "") for column in columns]
    titles_hint = f"Columns of this table: {', '.join(known) or 'none'}."

    ambiguous: list[str] = []
    unknown: list[str] = []
    data: dict[str, Any] = {}
    written: dict[str, Any] = {}
    seen: dict[str, str] = {}
    for title, value in wanted.items():
        key = _normalise(title)
        if key in seen:
            raise ToolError(
                message=f"values names the column {seen[key]!r} twice (also as {str(title)!r}).",
                hint=(
                    f"{titles_hint} The comparison ignores case and surrounding spaces; "
                    "keep one key per column."
                ),
            )
        seen[key] = str(title)
        matches = by_title.get(key, [])
        if not matches:
            unknown.append(str(title))
            continue
        if len(matches) > 1:
            found = ", ".join(str(column.get("id")) for column in matches)
            ambiguous.append(f"{str(title)!r} (column ids {found})")
            continue
        column = matches[0]
        column_id = column.get("id")
        if not isinstance(column_id, int) or isinstance(column_id, bool):
            raise ToolError(
                message=f"Table {table} answered a column titled {str(title)!r} without a "
                "numeric id.",
                hint=_COLUMN_ID_HINT,
            )
        data[str(column_id)] = value
        written[_text(column.get("title") or title)] = value

    if ambiguous:
        raise ToolError(
            message=f"Table {table} has more than one column with the same title: "
            f"{'; '.join(ambiguous)}.",
            hint=(
                "Tables has no unique constraint on column titles, so this title cannot be "
                "resolved to one column. Rename one of them in the Tables app first; writing "
                "into either of the two would be a guess."
            ),
        )
    if unknown:
        missing_titles = ", ".join(repr(title) for title in unknown)
        raise ToolError(
            message=f"Table {table} has no column titled {missing_titles}.",
            hint=f"{titles_hint} The comparison ignores case and surrounding spaces.",
        )

    filled = {_normalise(title) for title in wanted}
    required = [
        _text(column.get("title") or "")
        for column in columns
        if column.get("mandatory") and _normalise(column.get("title")) not in filled
    ]
    if required:
        raise ToolError(
            message=f"Table {table} needs a value for {', '.join(repr(t) for t in required)}.",
            hint=(
                "These columns are mandatory in Tables, and a row without them is refused by "
                "the app. Add them to values and try again."
            ),
        )
    return data, written


def _normalise(title: Any) -> str:
    """One title as it is compared: trimmed and case folded, never as it is written."""
    return str(title or "").strip().casefold()


async def _tables(clients: NcClients) -> list[dict[str, Any]]:
    """Table ids and sizes, plus whether the user may add a row at all."""
    tables = await tables_client.get_tables(clients.client, clients.creds)
    return [_table(table) for table in tables if not table.get("archived")]


def _table(table: dict[str, Any]) -> dict[str, Any]:
    """Project one table onto the fields a model reads, and drop the rest.

    ``GET /api/2/tables`` answers with the views of every table including their filters and
    sort orders, plus ``columnOrder``, ``sort``, ``ownerDisplayName``, ``createdBy`` and
    ``lastEditBy``. None of that survives here: every key is paid for in every answer.
    """
    entry: dict[str, Any] = {
        "id": table.get("id"),
        "title": _text(table.get("title") or ""),
        "rowsCount": table.get("rowsCount"),
        "columnsCount": table.get("columnsCount"),
        "isShared": bool(table.get("isShared")),
        "can_create": _may_create(table),
    }
    if table.get("emoji"):
        entry["emoji"] = table["emoji"]
    return entry


def _column(column: dict[str, Any]) -> dict[str, Any]:
    """Project one column: what it is called, what it is, and what a value must respect."""
    entry: dict[str, Any] = {
        "id": column.get("id"),
        "title": _text(column.get("title") or ""),
        "type": str(column.get("type") or ""),
        "mandatory": bool(column.get("mandatory")),
    }
    if column.get("subtype"):
        entry["subtype"] = str(column["subtype"])
    for key in _COLUMN_LIMITS:
        value = column.get(key)
        if value is None or value == "" or value == []:
            continue
        # ``selectionOptions`` carries labels somebody typed into the table settings, and a
        # label is foreign text like any cell value (T-08-14).
        entry[key] = _clean(value)
    return entry


async def _rows(clients: NcClients, table: str, limit: int, cursor: str | None) -> dict[str, Any]:
    """Read one window of rows and say how much of the table it is.

    The table itself is read first, for two answers out of one request (K11): ``rowsCount``
    is what turns "there is more" into an observation instead of a guess, and ``title`` is
    what the answer calls the table.

    The rows pass :func:`screen_links` before a single cell is projected (D-28-14): a link
    cell carries its own copy of a file name and a file id, so a tagged file would otherwise
    be named here. When the check could not be answered, every file link is withheld and the
    answer carries the one ``degraded`` entry of this family.
    """
    info = await tables_client.get_table(clients.client, clients.creds, table)

    offset = 0
    if cursor:
        state = paging.decode_cursor(cursor)
        # A handle of another table would silently answer with the wrong page, and the model
        # has no way to notice. Saying so costs one round trip; guessing is a wrong answer.
        paging.check_scope(state, "t", table, "table")
        offset = paging.read_offset(state)

    payload = await tables_client.get_rows_simple(
        clients.client, clients.creds, table, limit=limit, offset=offset
    )
    screened = await screen_links(clients, payload)
    payload = screened.rows
    titles = [_text(cell) for cell in payload[0]] if payload else []
    results = [_row(titles, values) for values in payload[1:]]

    answer: dict[str, Any] = {
        "level": "rows",
        "table": _text(info.get("title") or ""),
        "count": len(results),
        "results": results,
        "offset": offset,
    }
    count = _row_count(info)
    if count is not None:
        answer["rowsCount"] = count
    if screened.unavailable:
        answer["degraded"] = [withhold.degraded_entry("source")]
    # Two ways to know that this window is not the whole table, and the second one is the
    # only one left when the app reported no count: a window that came back full has a next
    # page behind it often enough to say so, and a wrong "there is more" costs one empty
    # page, while a wrong "that was all" is a silent cut.
    #
    # ``results`` guards both of them, and it is not a formality. Tables' row counter drifts,
    # so ``rowsCount`` can still report rows at an offset that answers with nothing. The
    # handle would then carry ``o = offset + 0``, which is the cursor that was just handed
    # in, and a client that follows ``next`` while it is set circles on the same page for
    # ever (T-08-17 one step further).
    more = bool(results) and (
        count > offset + len(results) if count is not None else len(results) == limit
    )
    if more:
        answer["truncated"] = True
        answer["next"] = paging.encode_cursor({"o": offset + len(results), "t": table})
    return answer


@dataclass(frozen=True, slots=True)
class LinkScreenResult:
    """The rows of one ``rows/simple`` answer after the ``kein-ki`` screen, decided once.

    ``rows`` is the payload with every withheld link cell set to ``None``, which is what the
    app itself answers for an empty link cell, so a withheld cell and an empty one cannot be
    told apart. ``unavailable`` says that the check could not be answered and every file link
    was withheld for that reason, so the caller adds its one ``degraded`` entry.
    """

    rows: list[list[Any]]
    unavailable: bool


async def screen_links(clients: NcClients, payload: list[list[Any]]) -> LinkScreenResult:
    """Withhold every link cell that points at a file tagged ``kein-ki`` (D-28-14).

    Public because ``tools/chatgpt.py`` screens ``fetch(table:)`` with the same function; one
    decision for both tools means one truth about which cell stays.

    The title row (the first list) is never touched. The guard is asked only when a value
    row carries a file link at all: a table without one costs no request (the same rule as
    ``talk.file_screen``), and the whole window costs at most one REPORT.

    *   ``untagged``: every cell stays as it came.
    *   ``unverifiable``: every file link cell is withheld, and ``unavailable`` is set.
    *   ``active`` without a tagged folder: the file id decides.
    *   ``active`` with a tagged folder: the file ids are resolved into paths with one
        ``dav.paths_of_fileids`` call. An id that does not resolve is withheld, and a failing
        lookup withholds every file link like the ``unverifiable`` state does.
    *   A file link whose id cannot be read is withheld while a tag is active.

    Tables gets no sandbox of its own, only the tag, like Talk: ``NC_MCP_FILES_ROOT`` does
    not filter link cells, and it only shapes the path lookup when a folder carries the tag
    (an id outside the root then does not resolve and is withheld). Noted for phase 29.
    """
    found: dict[tuple[int, int], str] = {}
    for row_index, values in enumerate(payload[1:], start=1):
        if not isinstance(values, list):
            continue
        for column_index, cell in enumerate(values):
            fileid = _linked_fileid(cell)
            if fileid is not None:
                found[(row_index, column_index)] = fileid
    if not found:
        return LinkScreenResult(payload, unavailable=False)

    scope = await clients.exclusion.scope(clients)
    if scope.state == "untagged":
        return LinkScreenResult(payload, unavailable=False)
    if scope.state == "unverifiable":
        return LinkScreenResult(_blank(payload, found), unavailable=True)

    resolved: dict[str, str] = {}
    if scope.has_folders:
        ask = sorted({fileid for fileid in found.values() if fileid})
        if ask:
            try:
                resolved = await dav.paths_of_fileids(clients.client, clients.creds, ask)
            except (ToolError, httpx.HTTPError, ValueError):
                return LinkScreenResult(_blank(payload, found), unavailable=True)

    hidden: set[tuple[int, int]] = set()
    for position, fileid in found.items():
        if not fileid:
            hidden.add(position)
            continue
        path: str | None = None
        if scope.has_folders:
            path = resolved.get(fileid)
            if path is None:
                hidden.add(position)
                continue
        if scope.excludes(path=path, fileid=fileid):
            hidden.add(position)
    return LinkScreenResult(_blank(payload, hidden), unavailable=False)


def _linked_fileid(value: Any) -> str | None:
    """The file id of a file link cell, ``""`` for one without a readable id, else ``None``.

    The form is the one measured in 28-01 (D-28-18): a JSON string ``{"title": <name>,
    "value": "<url>/f/<fileid>", "providerId": "files"}``, with the slashes PHP-escaped on
    the wire. An object of the same shape counts as well. Anything else is not a file link:
    ``null``, free text that happens to contain ``/f/123``, a link of another provider. The
    file id is read by ``provider_map.file_id``, the one reader of ``/f/<fileid>`` there is.
    """
    link: Any = value
    if isinstance(value, str):
        if not value.lstrip().startswith("{"):
            return None
        try:
            link = json.loads(value)
        except ValueError:
            return None
    if not isinstance(link, dict):
        return None
    if str(link.get("providerId") or "").strip() != _FILES_PROVIDER:
        return None
    target = link.get("value")
    if not isinstance(target, str):
        return ""
    return provider_map.file_id({}, target.replace("\\/", "/").strip())


def _blank(payload: list[list[Any]], positions: Collection[tuple[int, int]]) -> list[list[Any]]:
    """The payload with the cells at ``positions`` (row, column) set to ``None``."""
    if not positions:
        return payload
    rows = [list(values) if isinstance(values, list) else values for values in payload]
    for row_index, column_index in positions:
        rows[row_index][column_index] = None
    return rows


def _row(titles: list[str], values: list[Any]) -> dict[str, Any]:
    """Zip the title row of the compact form onto one row of values.

    The first list of ``rows/simple`` carries the column titles (K8), so it becomes the keys
    of every row object and is never repeated as a row of its own. A row that is shorter than
    the title row keeps empty strings, which is the same "missing value" the app sends.
    """
    row: dict[str, Any] = {}
    for index, title in enumerate(titles):
        value = values[index] if index < len(values) else ""
        row[title] = _clean(value)
    return row


def as_text(title: str, rows: list[list[Any]], total: int) -> list[str]:
    """One table as the few lines that describe it: its name, its size, its first rows.

    The line list is the shape of ``chatgpt._fetch_event``: the title first, then how many rows
    the table has, then the rows themselves. The header row needs no special case, because the
    compact form of the app ships the column titles as its **first** list (K8) and rendering it
    like every other line is what makes the values below it readable.

    The column titles are deliberately not resolved here. They already arrived with the rows, so
    a second call for them would be a round trip for information that is in hand, and an order
    built locally would be a second truth about the order of the app.

    Every cell runs through the marker filter of this module, because a cell value is written by
    whoever may write into that table and is therefore the place where a table could otherwise
    claim to be this server talking (T-08-14, ME-03). The caller cuts and marks **after** this
    function returned, which is what keeps that marker its own.

    ``total`` is the number of rows the table has, and it comes from the caller because only the
    caller read the table object. When it is larger than what this excerpt carries, the second
    line says both numbers: a cut that names itself with the total is the rule of this project,
    and here it is the only thing that turns twenty rows into an excerpt instead of a table.
    """
    shown = max(len(rows) - 1, 0)
    size = f"Rows: {total}"
    if shown < total:
        size = f"{size}, and this excerpt carries the first {shown}"

    lines = [_text(title), size]
    lines.extend(" | ".join(_cell_text(cell) for cell in values) for values in rows)
    return lines


def _cell_text(value: Any) -> str:
    """One cell of the compact form as one readable string, whatever shape it arrived in.

    :func:`_clean` keeps the shape of a value, because the row level of ``tables_browse``
    answers with data. A text line cannot keep it, so the two shapes that are not a scalar are
    rendered rather than repr'd: a multi selection arrives as a list and becomes its values
    separated by a comma, a selection option arrives as an object and becomes compact JSON.
    Both run through :func:`_text` afterwards, so the filter covers the rendered form and not
    only the leaves it was applied to.

    ``None`` becomes the empty string, which is what the app itself sends for a missing value;
    ``str(None)`` would put the word ``None`` into a table cell a person reads.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_cell_text(item) for item in value)
    if isinstance(value, dict):
        return _text(json.dumps(value, ensure_ascii=False))
    return _text(value)


def _row_count(info: dict[str, Any]) -> int | None:
    """The row count of the table, or ``None`` when the app reported no usable one.

    The tempting fallback is "as much as was read so far", and it is the worse answer twice
    over: it reports a table of 100 rows as a table of 25, and the truncation check built on
    it can then never be true, so the cut becomes silent. Leaving the field out says the same
    thing honestly, and the caller has one number less rather than one wrong one.
    """
    count = info.get("rowsCount")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return None
    return count


def _may_create(table: dict[str, Any]) -> bool:
    """Whether this account may add a row to this table (K5).

    The naive read of this question is wrong on the most common case of all. Tables reports
    the permissions of a *share* in ``onSharePermissions``, and ``TableService::
    setIsSharedState`` sets ``Permissions(read: true)`` together with ``isShared = false``
    for a table the caller owns, while Nextcloud's own ``PermissionsService::
    checkPermission`` short circuits on ``userIsElementOwner`` long before it looks at that
    object. A literal ``if not onSharePermissions.create: refuse`` would therefore refuse
    every user on their own table. That is the same trap as ``canCreateBoards`` in phase 1:
    a field that answers a different question than the one being asked.

    So ownership decides first, and only a share really is asked for a create permission.
    ``manage`` counts as well, because a share that may manage the table may write rows.
    """
    permissions = table.get("onSharePermissions")
    permissions = permissions if isinstance(permissions, dict) else {}
    if not table.get("isShared"):
        return True
    return bool(permissions.get("create") or permissions.get("manage"))


def _text(value: Any) -> str:
    """Foreign text on its way into the model context, with our own markers removed.

    Cell values and titles are written by whoever may write to the table, so they are the
    place where a document could otherwise claim to be this server talking (T-08-14).
    """
    return marks.without_marks(str(value))


def _clean(value: Any) -> Any:
    """The same filter for foreign data of any shape, applied down to every leaf string.

    :func:`_text` covers a single string, and a type check around it covers exactly the case
    a fixture happens to have. Tables puts more than strings into a cell: a multi selection
    answers with a list, a selection option is an object whose ``label`` somebody typed into
    the table settings, and both carry text of whoever may write to or manage the table. A
    filter that only looks at the top level string leaves those two shapes as an open door
    for text that claims to be this server talking (T-08-14), and the shape is chosen by the
    writer, not by us. Numbers, booleans and ``None`` are returned unchanged: there is
    nothing in them to remove, and rewriting them into strings would change the answer.
    """
    if isinstance(value, str):
        return marks.without_marks(value)
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    return value


def _envelope(level: str, results: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """One answer shape for all three levels, truncation named instead of silent."""
    kept = results[:limit]
    answer: dict[str, Any] = {"level": level, "count": len(kept), "results": kept}
    if len(results) > len(kept):
        answer["truncated"] = True
    return answer
