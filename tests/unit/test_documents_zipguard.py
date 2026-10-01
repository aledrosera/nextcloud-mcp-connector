"""The zip guard in front of the three Office converters: central directory only."""

import io
import zipfile

import pytest

from mcp_connector.documents import zipguard
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_an_ordinary_office_shaped_zip_passes() -> None:
    data = _zip({"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w:document/>"})
    zipguard.check(data, "/Docs/a.docx")


def test_too_many_entries_are_refused_before_inflation() -> None:
    data = _zip({f"e{i}": b"" for i in range(zipguard.MAX_ENTRIES + 1)})
    with pytest.raises(ToolError) as info:
        zipguard.check(data, "/Docs/a.docx")
    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "/Docs/a.docx" in info.value.message


def test_the_declared_total_cap_is_50_mib() -> None:
    # lxml builds a DOM several times the size of the XML; 50 MiB declared is still far
    # beyond any real Office document.
    assert zipguard.MAX_TOTAL_BYTES == 50 * 1024 * 1024


def test_an_oversize_declared_total_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # The guard reads declared sizes, so a small real archive with a patched ceiling
    # proves the comparison without writing 50 MiB to disk.
    monkeypatch.setattr(zipguard, "MAX_TOTAL_BYTES", 10)
    data = _zip({"word/document.xml": b"x" * 11})
    with pytest.raises(ToolError) as info:
        zipguard.check(data, "/Docs/a.docx")
    assert info.value.reason == REASON_GUARD_TRIPPED


def test_a_high_ratio_entry_above_the_floor_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zipguard, "RATIO_FLOOR_BYTES", 1024)
    # 1 MiB of zeros deflates hard.
    data = _zip({"word/document.xml": b"\0" * (1024 * 1024)})
    with pytest.raises(ToolError) as info:
        zipguard.check(data, "/Docs/a.docx")
    assert info.value.reason == REASON_GUARD_TRIPPED


def test_a_high_ratio_entry_below_the_floor_passes() -> None:
    # Real Office XML compresses very well and is small. The ratio rule must not refuse it.
    data = _zip({"word/document.xml": b"<w:p/>" * 20000})
    zipguard.check(data, "/Docs/a.docx")


def test_a_file_that_is_not_a_zip_is_refused_as_damaged() -> None:
    with pytest.raises(ToolError) as info:
        zipguard.check(b"%PDF-1.7 not a zip", "/Docs/a.docx")
    assert "damaged" in info.value.hint.lower() or "open" in info.value.hint.lower()
