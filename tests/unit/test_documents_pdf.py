"""PDF to Markdown: a heading per page, extracted text, refusals for encrypted and oversize."""

import io
from pathlib import Path

import pypdf
import pytest

from mcp_connector.documents import limits
from mcp_connector.documents import pdf as pdf_conv
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "documents" / "sample.pdf"


def test_each_page_becomes_a_heading_with_its_text() -> None:
    text = pdf_conv.to_markdown(FIXTURE.read_bytes())

    assert "## Page 1" in text
    assert "Quarterly Report" in text
    assert "Servers 12" in text
    assert "## Page 2" in text
    assert "Appendix" in text
    assert text.index("## Page 1") < text.index("## Page 2")


def _blank_pdf(pages: int) -> bytes:
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_a_pdf_without_a_text_layer_says_so_at_the_top() -> None:
    text = pdf_conv.to_markdown(_blank_pdf(2))
    first = text.splitlines()[0]
    assert "no text layer" in first
    assert "## Page 1" in text


def _encrypted_pdf(user_password: str) -> bytes:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password=user_password, owner_password="owner")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_an_owner_password_only_pdf_opens() -> None:
    # Bank statements often carry an owner password and an empty user password.
    text = pdf_conv.to_markdown(_encrypted_pdf(""))
    assert "## Page 1" in text


def test_a_pdf_with_a_user_password_is_refused() -> None:
    with pytest.raises(ToolError) as info:
        pdf_conv.to_markdown(_encrypted_pdf("secret"))
    assert "encrypted" in info.value.message
    assert info.value.reason != REASON_GUARD_TRIPPED


def test_too_many_pages_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_conv, "MAX_PAGES", 3)
    with pytest.raises(ToolError) as info:
        pdf_conv.to_markdown(_blank_pdf(4))
    assert info.value.reason == REASON_GUARD_TRIPPED


def test_the_output_stops_at_the_cap_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_CHARS", 40)
    text = pdf_conv.to_markdown(FIXTURE.read_bytes())
    body, _, note = text.rstrip("\n").rpartition("\n")
    assert note == "(output truncated at 40 characters)"
    assert len(body.rstrip("\n")) <= 40
    assert "## Page 2" not in text


def _flate_pdf(decoded: bytes) -> bytes:
    """One page whose content stream inflates to ``decoded``: a few KB on disk."""
    import zlib

    packed = zlib.compress(decoded, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(packed) + packed + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


def test_a_content_stream_above_the_stream_cap_is_refused_before_it_is_parsed() -> None:
    # The reviewer's case: a few-KB PDF whose page inflates to megabytes of drawing
    # operators. Without the cap pypdf parses every operator, at seconds and hundreds
    # of MB per page, and the output cap never triggers because no text comes out.
    operators = b"BT /F1 12 Tf 10 10 Td (x) Tj ET\n" + b"0 0 m 1 1 l S\n" * 400_000
    assert len(operators) > pdf_conv.MAX_STREAM_BYTES
    data = _flate_pdf(operators)
    assert len(data) < 20_000
    with pytest.raises(ToolError) as info:
        pdf_conv.to_markdown(data)
    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "stream" in info.value.message


def test_a_content_stream_below_the_stream_cap_is_read() -> None:
    data = _flate_pdf(b"BT /F1 12 Tf 10 10 Td (hello) Tj ET\n")
    assert "hello" in pdf_conv.to_markdown(data)


def test_the_stream_cap_is_4_mib() -> None:
    assert pdf_conv.MAX_STREAM_BYTES == 4 * 1024 * 1024
