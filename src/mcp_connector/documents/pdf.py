"""PDF to Markdown: the text layer per page, no layout reconstruction, no OCR.

pypdf's own limits default to 75 MB per decoded stream. A content stream is parsed operator
by operator at tens of times its decoded size, so this converter lowers the stream limits
to :data:`MAX_STREAM_BYTES`: far above any real text page, far below what would exhaust
the worker. pypdf raises ``LimitReachedError`` when a stream passes it, and that is a
guard refusal, not a damaged file.
"""

import io

from ..errors import REASON_GUARD_TRIPPED, ToolError
from .limits import Output

__all__ = ["MAX_PAGES", "MAX_STREAM_BYTES", "to_markdown"]

MAX_PAGES = 500
MAX_STREAM_BYTES = 4 * 1024 * 1024

_NO_TEXT = "(This PDF has no text layer; it is probably a scan. Nothing could be extracted.)"


def _limits() -> dict[str, int]:
    return {
        "maximum_declared_stream_length": MAX_STREAM_BYTES,
        "array_based_stream_maximum_output_length": MAX_STREAM_BYTES,
        "zlib_maximum_output_length": MAX_STREAM_BYTES,
        "lzw_maximum_output_length": MAX_STREAM_BYTES,
        "run_length_maximum_output_length": MAX_STREAM_BYTES,
        "jbig2_maximum_output_length": MAX_STREAM_BYTES,
        "image_maximum_buffer_size": MAX_STREAM_BYTES,
        "xform_maximum_invocations_per_extraction": 1000,
    }


def to_markdown(data: bytes) -> str:
    import pypdf
    from pypdf.errors import LimitReachedError

    configuration = pypdf.Configuration().with_overwrites(**_limits())
    try:
        with pypdf.apply_configuration(configuration):
            return _extract(pypdf.PdfReader(io.BytesIO(data)))
    except LimitReachedError:
        raise ToolError(
            message=f"The PDF has a stream above {MAX_STREAM_BYTES} decoded bytes.",
            hint="This file is too expensive to convert here. Use files_download for its bytes.",
            reason=REASON_GUARD_TRIPPED,
        ) from None


def _extract(reader) -> str:
    # An owner-password-only PDF (bank statements, for example) opens with the empty user
    # password. Only a PDF that needs a real user password is refused.
    if reader.is_encrypted and not reader.decrypt(""):
        raise ToolError(
            message="The PDF is encrypted.",
            hint=("Remove the password in a PDF tool and upload a copy, then read that one."),
        )
    count = len(reader.pages)
    if count > MAX_PAGES:
        raise ToolError(
            message=f"The PDF has {count} pages, more than {MAX_PAGES}.",
            hint="Split the document, or use files_download for the raw file.",
            reason=REASON_GUARD_TRIPPED,
        )
    out = Output()
    any_text = False
    for number, page in enumerate(reader.pages, start=1):
        if out.full:
            break
        text = (page.extract_text() or "").strip()
        any_text = any_text or bool(text)
        out.add(f"## Page {number}")
        out.add("")
        if text:
            out.add(text)
            out.add("")
    if not any_text:
        return f"{_NO_TEXT}\n\n{out.text()}"
    return out.text()
