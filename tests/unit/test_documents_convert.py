"""The dispatcher: format to converter, the extra-missing refusal, one error for any parser."""

import subprocess
import sys
from pathlib import Path

import pytest

from mcp_connector import documents
from mcp_connector.documents import docx as docx_conv
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.mark.anyio
async def test_convert_dispatches_by_format_and_names_it() -> None:
    result = await documents.convert(
        (FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/sample.docx"
    )
    assert result.format == "docx"
    assert result.markdown.startswith("# Quarterly Report")

    pdf = await documents.convert(
        (FIXTURES / "sample.pdf").read_bytes(), "application/pdf", "/Docs/sample.pdf"
    )
    assert pdf.format == "pdf"
    assert "## Page 1" in pdf.markdown


def test_the_zip_guard_runs_for_office_files_and_not_for_pdf() -> None:
    with pytest.raises(ToolError) as info:
        documents.convert_sync(b"not a zip at all", DOCX, "/Docs/a.docx")
    assert "readable Office file" in info.value.message

    # A PDF is not a zip; the guard must not touch it. The parser refuses instead.
    with pytest.raises(ToolError) as info:
        documents.convert_sync(b"not a pdf", "application/pdf", "/Docs/a.pdf")
    assert "could not be read as pdf" in info.value.message


def test_a_parser_exception_becomes_one_refusal_naming_file_and_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_data: bytes) -> str:
        raise ValueError("internal detail that must not leak")

    monkeypatch.setattr(docx_conv, "to_markdown", boom)
    with pytest.raises(ToolError) as info:
        documents.convert_sync((FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/a.docx")
    assert info.value.message == "/Docs/a.docx could not be read as docx."
    assert "internal detail" not in str(info.value)
    assert "Open the file in Nextcloud" in info.value.hint


def test_a_guard_refusal_passes_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(_data: bytes) -> str:
        raise ToolError(message="x", hint="y", reason=REASON_GUARD_TRIPPED)

    monkeypatch.setattr(docx_conv, "to_markdown", refuse)
    with pytest.raises(ToolError) as info:
        documents.convert_sync((FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/a.docx")
    assert info.value.message == "x"
    assert info.value.hint == "y"
    assert info.value.reason == REASON_GUARD_TRIPPED


def test_without_the_extra_the_refusal_names_the_install_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An entry of None in sys.modules makes ``import docx`` raise ImportError,
    # which is what a missing package does.
    for name in ("docx", "openpyxl", "pptx", "pypdf"):
        monkeypatch.setitem(sys.modules, name, None)

    with pytest.raises(ToolError) as info:
        documents.convert_sync((FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/a.docx")
    assert "documents extra" in info.value.message
    assert "nextcloud-mcp-connector[documents]" in info.value.hint


def test_the_package_imports_without_the_extra() -> None:
    # A fresh interpreter is the honest test: re-importing in this process would replace
    # mcp_connector.documents under the other tests. None in sys.modules makes the import
    # of each library raise ImportError, which is what a missing package does.
    code = (
        "import sys\n"
        "for name in ('docx', 'openpyxl', 'pptx', 'pypdf'):\n"
        "    sys.modules[name] = None\n"
        "import mcp_connector.documents as documents\n"
        "assert hasattr(documents, 'convert')\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed command, the code is a constant
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
