"""Excel to Markdown: a heading per sheet and a pipe table of the stored values.

Values, not formulas: ``data_only=True`` reads what the last save cached, which is what a
reader of the sheet sees. Hidden sheets are included, because hiding is not a permission.

The sheet's own ``<dimension>`` is not trusted: a file can declare 16384 columns and make
openpyxl pad every row to that width. The converter resets it and reads at most
:data:`MAX_COLS` columns and :data:`MAX_ROWS` rows per sheet.
"""

import datetime
import io
from typing import Any

from ..errors import REASON_GUARD_TRIPPED, ToolError
from .limits import Output

__all__ = ["MAX_COLS", "MAX_ROWS", "MAX_SHEETS", "to_markdown"]

MAX_SHEETS = 50
MAX_ROWS = 10000
MAX_COLS = 256


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        # openpyxl returns dates as datetimes; a midnight time means a plain date.
        if value.time() == datetime.time():
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return " ".join(str(value).split()).replace("|", "\\|")


def _trim(rows: list[list[str]]) -> list[list[str]]:
    while rows and not any(rows[-1]):
        rows.pop()
    width = 0
    for row in rows:
        for index in range(len(row) - 1, -1, -1):
            if row[index]:
                width = max(width, index + 1)
                break
    return [row[:width] + [""] * (width - len(row[:width])) for row in rows]


def _sheet_lines(rows: list[list[str]]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows):
        lines.append("| " + " | ".join(row) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return lines


def _sheet_markdown(sheet: Any) -> list[str]:
    sheet.reset_dimensions()
    rows: list[list[str]] = []
    omitted = False
    for index, values in enumerate(sheet.iter_rows(max_col=MAX_COLS, values_only=True)):
        if index >= MAX_ROWS:
            omitted = True
            break
        rows.append([_text(value) for value in values])
    rows = _trim(rows)
    out = [f"## {sheet.title}", ""]
    if rows:
        out.extend(_sheet_lines(rows))
    elif not omitted:
        out.append("(empty sheet)")
    if omitted:
        out.append(f"(more than {MAX_ROWS} rows; the rest is omitted)")
    out.append("")
    return out


def to_markdown(data: bytes) -> str:
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        sheets = workbook.worksheets
        if len(sheets) > MAX_SHEETS:
            raise ToolError(
                message=f"The workbook has {len(sheets)} sheets, more than {MAX_SHEETS}.",
                hint="Split the workbook, or use files_download for the raw file.",
                reason=REASON_GUARD_TRIPPED,
            )
        out = Output()
        for sheet in sheets:
            if out.full:
                break
            out.extend(_sheet_markdown(sheet))
    finally:
        workbook.close()
    return out.text()
