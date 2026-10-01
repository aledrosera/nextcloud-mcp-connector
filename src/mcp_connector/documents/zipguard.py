"""Refuse an Office file whose zip directory promises more than this server will inflate.

DOCX, XLSX and PPTX are zip archives, and all three libraries open them through the standard
``zipfile``. One check in front of all three reads the central directory only: entry count,
the sum of declared uncompressed sizes, and the compression ratio of any large entry. Nothing
is inflated before the check passes, so a crafted archive costs one directory read.
"""

import io
import zipfile

from ..errors import REASON_GUARD_TRIPPED, ToolError

__all__ = ["MAX_ENTRIES", "MAX_RATIO", "MAX_TOTAL_BYTES", "RATIO_FLOOR_BYTES", "check"]

MAX_ENTRIES = 2000
#: lxml builds a DOM several times the size of the XML, so the declared total is the memory
#: bound. 50 MiB is still far beyond any real Office document.
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_RATIO = 100
#: The ratio rule applies above this declared size only. Office XML is small and compresses
#: far better than 100:1 in places, and refusing it would refuse ordinary documents.
RATIO_FLOOR_BYTES = 10 * 1024 * 1024

_HINT = "This file is not safe to convert here. Use files_download if you need its bytes."


def check(data: bytes, name: str) -> None:
    """Raise when the archive's own directory exceeds one of the three caps."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, OSError):
        raise ToolError(
            message=f"{name} is not a readable Office file.",
            hint="Open the file in Nextcloud to check it; it may be damaged or renamed.",
        ) from None

    if len(infos) > MAX_ENTRIES:
        raise ToolError(
            message=f"{name} declares {len(infos)} parts, more than {MAX_ENTRIES}.",
            hint=_HINT,
            reason=REASON_GUARD_TRIPPED,
        )
    total = sum(info.file_size for info in infos)
    if total > MAX_TOTAL_BYTES:
        raise ToolError(
            message=f"{name} declares {total} uncompressed bytes, more than {MAX_TOTAL_BYTES}.",
            hint=_HINT,
            reason=REASON_GUARD_TRIPPED,
        )
    for info in infos:
        if info.file_size <= RATIO_FLOOR_BYTES:
            continue
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > MAX_RATIO:
            raise ToolError(
                message=f"{name} contains a part compressed beyond {MAX_RATIO}:1.",
                hint=_HINT,
                reason=REASON_GUARD_TRIPPED,
            )
