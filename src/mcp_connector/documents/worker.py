"""The conversion worker: one process per document, with an address-space limit.

Started by :func:`mcp_connector.documents.convert` as ``python -m`` with a minimal
environment. It reads one JSON header line (content type and name) and then the file bytes
from stdin, converts in process, and writes one JSON object to stdout: the Markdown and the
format, or the message and hint of a :class:`ToolError` plus a guard flag. Any other failure
ends the process with a non-zero code, and the parent maps that to one refusal.

The address-space limit is set before any parser is imported. lxml builds a DOM several
times the size of its XML and pypdf parses a content stream at tens of times its decoded
size, so a hostile file that passed the directory and stream guards still has a hard
ceiling: it gets a MemoryError here, not an out-of-memory server. RLIMIT_AS is enforced on
Linux, which is where the ExApp runs; on macOS the call is accepted and the kernel ignores
it, and Windows (stdio mode) has no ``resource`` module at all. Both rely on the timeout
alone.
"""

import json
import sys

from ..errors import REASON_GUARD_TRIPPED, ToolError
from . import convert_sync

try:
    import resource
except ImportError:  # Windows has no rlimits; the wall clock in the parent still applies
    resource = None

__all__ = ["MAX_MEMORY_BYTES", "apply_memory_limit", "main"]

MAX_MEMORY_BYTES = 512 * 1024 * 1024


def apply_memory_limit(limit: int = MAX_MEMORY_BYTES) -> bool:
    """Cap this process's address space. ``False`` when the platform cannot."""
    if resource is None or sys.platform == "win32":
        return False
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):
        return False
    return True


def main() -> int:
    apply_memory_limit()
    stdin = sys.stdin.buffer
    header = json.loads(stdin.readline())
    data = stdin.read()
    try:
        result = convert_sync(data, header["content_type"], header["name"])
        payload: dict = {"markdown": result.markdown, "format": result.format}
    except ToolError as exc:
        # A flag, not the reason string: the parent raises through the frozen constants
        # (tests/unit/test_errors_reason.py), and a conversion knows only these two reasons.
        payload = {
            "error": {
                "message": exc.message,
                "hint": exc.hint,
                "guard": exc.reason == REASON_GUARD_TRIPPED,
            }
        }
    sys.stdout.buffer.write(json.dumps(payload).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
