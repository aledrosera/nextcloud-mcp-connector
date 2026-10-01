"""Format detection for files_read_as_markdown: content type first, suffix as fallback."""

import pytest

from mcp_connector.documents import detect
from mcp_connector.errors import ToolError

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@pytest.mark.parametrize(
    ("content_type", "name", "expected"),
    [
        (DOCX, "/Docs/policy.docx", "docx"),
        (XLSX, "/Docs/budget.xlsx", "xlsx"),
        (PPTX, "/Docs/deck.pptx", "pptx"),
        ("application/pdf", "/Docs/scan.pdf", "pdf"),
        ("application/pdf; charset=binary", "/Docs/scan.pdf", "pdf"),
        ("APPLICATION/PDF", "/Docs/scan.pdf", "pdf"),
    ],
)
def test_the_content_type_decides_when_it_is_specific(
    content_type: str, name: str, expected: str
) -> None:
    assert detect.detect(content_type, name) == expected


@pytest.mark.parametrize(
    ("content_type", "name", "expected"),
    [
        ("application/octet-stream", "/Docs/policy.docx", "docx"),
        ("application/zip", "/Docs/budget.XLSX", "xlsx"),
        ("", "/Docs/deck.pptx", "pptx"),
        ("application/octet-stream", "/Docs/scan.pdf", "pdf"),
    ],
)
def test_a_generic_content_type_falls_back_to_the_suffix(
    content_type: str, name: str, expected: str
) -> None:
    assert detect.detect(content_type, name) == expected


def test_the_content_type_wins_over_a_misleading_suffix() -> None:
    assert detect.detect("application/pdf", "/Docs/renamed.docx") == "pdf"


@pytest.mark.parametrize(
    "name",
    ["/Docs/a.docm", "/Docs/a.xlsm", "/Docs/a.pptm", "/Docs/a.doc", "/Docs/a.xls", "/Docs/a.ppt"],
)
def test_macro_and_legacy_types_are_refused_by_name(name: str) -> None:
    with pytest.raises(ToolError) as info:
        detect.detect("application/octet-stream", name)
    assert "not supported" in info.value.message
    assert "docx" in info.value.hint
    assert "pdf" in info.value.hint


def test_an_unknown_type_is_refused_and_the_hint_lists_the_formats() -> None:
    with pytest.raises(ToolError) as info:
        detect.detect("image/png", "/Docs/photo.png")
    assert "image/png" in info.value.message
    assert "docx, xlsx, pptx, pdf" in info.value.hint


def test_supported_format_never_raises() -> None:
    assert detect.supported_format("image/png", "/Docs/photo.png") is None
    assert detect.supported_format("application/pdf", "/x") == "pdf"
    assert detect.supported_format("application/octet-stream", "/Docs/a.docx") == "docx"


def test_the_format_set_is_the_four_of_the_spec() -> None:
    assert frozenset({"docx", "xlsx", "pptx", "pdf"}) == detect.FORMATS
