"""Word to Markdown.

Body order is kept. Headers, footers, footnotes, comments and images are not.
The library is imported inside the function so the package imports without the extra.

Two library shortcuts are avoided on purpose. ``row.cells`` repeats a cell once per grid
column it spans, so a crafted ``gridSpan`` turns one cell into 100000; the converter reads
the real ``w:tc`` elements instead. ``paragraph.style`` resolves the style again for every
paragraph; the converter looks each style id up in a map that it builds once.
"""

import io
import re
from collections.abc import Iterable
from typing import Any

from .limits import Output

__all__ = ["MAX_TABLE_COLS", "MAX_TABLE_ROWS", "to_markdown"]

MAX_TABLE_COLS = 256
MAX_TABLE_ROWS = 10000

_HEADING_RE = re.compile(r"^Heading (\d+)$")


def _heading_prefix(style_name: str) -> str:
    if style_name == "Title":
        return "#"
    match = _HEADING_RE.match(style_name)
    if match is None:
        return ""
    return "#" * min(int(match.group(1)), 6)


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _table_lines(rows: Iterable[Iterable[str]]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows):
        cells = [_cell(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
    return lines


def _table_lines_capped(table: Any) -> list[str]:
    """Pipe-table lines from the real cells, with a note for each cap that cut something."""
    from docx.table import _Cell

    rows: list[list[str]] = []
    rows_cut = cols_cut = False
    for index, tr in enumerate(table._tbl.tr_lst):
        if index >= MAX_TABLE_ROWS:
            rows_cut = True
            break
        cells = tr.tc_lst
        cols_cut = cols_cut or len(cells) > MAX_TABLE_COLS
        rows.append([_Cell(tc, table).text for tc in cells[:MAX_TABLE_COLS]])
    lines = _table_lines(rows)
    if rows_cut:
        lines.append(f"(more than {MAX_TABLE_ROWS} rows; the rest of the table is omitted)")
    if cols_cut:
        lines.append(f"(more than {MAX_TABLE_COLS} columns; the rest of each row is omitted)")
    return lines


def to_markdown(data: bytes) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(io.BytesIO(data))
    style_names = {style.style_id: style.name or "" for style in document.styles}
    out = Output()
    for block in document.iter_inner_content():
        if out.full:
            break
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            p_pr = block._p.pPr
            style_id = p_pr.style if p_pr is not None else None
            style = style_names.get(style_id, "") if style_id else ""
            prefix = _heading_prefix(style)
            if prefix:
                out.add(f"{prefix} {text}")
            elif style.startswith("List"):
                out.add(f"- {text}")
            else:
                out.add(text)
            out.add("")
        elif isinstance(block, Table):
            out.extend(_table_lines_capped(block))
            out.add("")
    return out.text()
