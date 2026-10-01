"""Write the four document fixtures under tests/fixtures/documents.

Run once with ``uv run python scripts/make_document_fixtures.py`` and commit the
output. The script is committed so a reviewer can regenerate the files and diff them.
Every fixture carries the same content: a heading, one paragraph, one table and a
second unit named Appendix, so the converter tests can assert the same strings in all
four formats.
"""

# ruff: noqa: S101  (asserts narrow optional types from the office libraries)

import io
from pathlib import Path

HEADING = "Quarterly Report"
PARAGRAPH = "The figures below are final."
TABLE = [["Item", "Amount"], ["Servers", "12"]]
SECOND = "Appendix"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "documents"


def make_docx() -> bytes:
    import docx

    document = docx.Document()
    document.add_heading(HEADING, level=1)
    document.add_paragraph(PARAGRAPH)
    document.add_paragraph("First point", style="List Bullet")
    table = document.add_table(rows=2, cols=2)
    for r, row in enumerate(TABLE):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    document.add_heading(SECOND, level=2)
    document.add_paragraph("Nothing else.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_xlsx() -> bytes:
    import datetime

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Report"
    sheet.append([HEADING])
    sheet.append([PARAGRAPH])
    for row in TABLE:
        sheet.append(row)
    sheet.append(["Date", datetime.date(2026, 9, 30)])
    second = workbook.create_sheet(SECOND)
    second.append(["Nothing else."])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_pptx() -> bytes:
    import pptx
    from pptx.util import Inches

    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])  # title only
    assert slide.shapes.title is not None
    slide.shapes.title.text = HEADING
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    box.text_frame.text = PARAGRAPH
    shape = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(6), Inches(1))
    for r, row in enumerate(TABLE):
        for c, value in enumerate(row):
            shape.table.cell(r, c).text = value
    notes = slide.notes_slide.notes_text_frame
    assert notes is not None
    notes.text = "Speaker note one."
    second = presentation.slides.add_slide(presentation.slide_layouts[5])
    assert second.shapes.title is not None
    second.shapes.title.text = SECOND
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def make_pdf() -> bytes:
    # pypdf writes pages but not text. A minimal hand-written PDF with two text pages
    # keeps the fixture independent of a rendering library. Offsets are computed below.
    def page(text: str) -> bytes:
        return f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 7 0 R >> >> >>"
    )
    first = page(f"{HEADING} {PARAGRAPH} Item Amount Servers 12")
    objects.append(b"<< /Length %d >>stream\n" % len(first) + first + b"\nendstream")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R "
        b"/Resources << /Font << /F1 7 0 R >> >> >>"
    )
    second = page(f"{SECOND} Nothing else.")
    objects.append(b"<< /Length %d >>stream\n" % len(second) + second + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.docx").write_bytes(make_docx())
    (OUT / "sample.xlsx").write_bytes(make_xlsx())
    (OUT / "sample.pptx").write_bytes(make_pptx())
    (OUT / "sample.pdf").write_bytes(make_pdf())
    for path in sorted(OUT.iterdir()):
        print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
