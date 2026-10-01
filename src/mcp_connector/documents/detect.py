"""Which converter a file belongs to: the content type decides, the suffix is the fallback.

Nextcloud reports the four types reliably for files uploaded through its own clients. Files
that arrived through a sync of a foreign tool sometimes carry ``application/octet-stream``
or ``application/zip``, and then the suffix is the only evidence left. A specific content
type wins over a suffix, because a renamed file is more common than a mislabelled one.
"""

from ..errors import ToolError

__all__ = ["FORMATS", "detect", "supported_format"]

FORMATS: frozenset[str] = frozenset({"docx", "xlsx", "pptx", "pdf"})

_BY_TYPE: dict[str, str] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/pdf": "pdf",
}

_BY_SUFFIX: dict[str, str] = {f".{fmt}": fmt for fmt in FORMATS}

# Not refused because they are dangerous to read, but because none of the four libraries
# reads them: the macro variants carry a different package layout and the legacy binary
# formats are a different file format altogether.
_UNSUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {".docm", ".xlsm", ".pptm", ".doc", ".xls", ".ppt"}
)

_GENERIC_TYPES: frozenset[str] = frozenset({"", "application/octet-stream", "application/zip"})

_FORMAT_HINT = "Supported formats: docx, xlsx, pptx, pdf. Use files_download for anything else."


def _base_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _suffix(name: str) -> str:
    tail = name.rsplit("/", 1)[-1]
    dot = tail.rfind(".")
    return tail[dot:].lower() if dot >= 0 else ""


def supported_format(content_type: str, name: str) -> str | None:
    """The format of this file, or ``None`` when no converter takes it. Never raises."""
    base = _base_type(content_type or "")
    if base in _BY_TYPE:
        return _BY_TYPE[base]
    if base in _GENERIC_TYPES:
        return _BY_SUFFIX.get(_suffix(name))
    return None


def detect(content_type: str, name: str) -> str:
    """The format of this file, or a refusal that says why there is none."""
    found = supported_format(content_type, name)
    if found is not None:
        return found
    suffix = _suffix(name)
    if suffix in _UNSUPPORTED_SUFFIXES:
        raise ToolError(
            message=f"{name} is a {suffix} file, which is not supported.",
            hint=_FORMAT_HINT,
        )
    shown = _base_type(content_type or "") or "an unknown type"
    raise ToolError(message=f"{name} is {shown}, which is not supported.", hint=_FORMAT_HINT)
