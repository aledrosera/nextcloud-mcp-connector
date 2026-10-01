"""Office and PDF documents as Markdown (TOOL-14).

One entry point, :func:`convert`, and four converters behind it. Two rules hold the whole
package together:

* **The parser libraries are optional.** Every converter imports its library inside the
  function, so this package imports without the ``documents`` extra, and a missing library
  becomes one refusal that names the install command instead of an import error at start.
* **No parser exception reaches a client.** Whatever a library raises on a damaged or
  hostile file is mapped to one refusal that names the file and the format. Only the
  exception class is logged, at DEBUG: the message describes the file, and the file is the
  user's.

Conversion is CPU work on sync libraries, and the guards in front of the parsers bound
what a file declares, not what a parser does with it. :func:`convert` therefore runs each
conversion in its own worker process (``worker.py``): the process has an address-space
limit, a wall-clock limit after which it is killed, and a minimal environment without the
server's secrets. :func:`slot` bounds how many conversions run at once, and the caller takes
a slot before the download, so the bytes held for conversion are bounded too.
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from ..errors import REASON_GUARD_TRIPPED, ToolError
from . import detect, docx, pdf, pptx, xlsx, zipguard

__all__ = [
    "INSTALL_HINT",
    "MAX_CONCURRENT",
    "MAX_SOURCE_BYTES",
    "TIMEOUT_SECONDS",
    "WORKER_MODULE",
    "Converted",
    "convert",
    "convert_sync",
    "slot",
]

logger = logging.getLogger(__name__)

MAX_SOURCE_BYTES = 25 * 1024 * 1024
#: Conversions at once. Two keeps a second user's document moving while one converts, and
#: bounds the worker processes and the downloaded bytes to twice the source cap.
MAX_CONCURRENT = 2
#: Wall clock per conversion. A 500-page text PDF converts in a few seconds; a file that
#: needs more than this is being parsed, not read.
TIMEOUT_SECONDS = 30.0
WORKER_MODULE = "mcp_connector.documents.worker"

INSTALL_HINT = (
    'Install the documents extra: pip install "nextcloud-mcp-connector[documents]", '
    "or use the ExApp image, which carries it."
)

_OFFICE = frozenset({"docx", "xlsx", "pptx"})

_DAMAGED_HINT = "Open the file in Nextcloud to check it; it may be damaged or mislabelled."
_TOO_EXPENSIVE_HINT = (
    "This file is too expensive to convert here. Use files_download for its bytes."
)


@dataclass(frozen=True)
class Converted:
    markdown: str
    format: str


def _converter(fmt: str):
    # Looked up at call time, so a test can replace one converter's to_markdown.
    if fmt == "docx":
        return docx.to_markdown
    if fmt == "xlsx":
        return xlsx.to_markdown
    if fmt == "pptx":
        return pptx.to_markdown
    return pdf.to_markdown


def _unreadable(name: str, fmt: str) -> ToolError:
    return ToolError(message=f"{name} could not be read as {fmt}.", hint=_DAMAGED_HINT)


def convert_sync(data: bytes, content_type: str, name: str) -> Converted:
    """Convert in the calling process. The worker calls this; :func:`convert` is the door."""
    fmt = detect.detect(content_type, name)
    try:
        # The guard is inside the try: a malformed archive header can raise more than
        # BadZipFile, and all of it is one refusal. A ToolError passes through.
        if fmt in _OFFICE:
            zipguard.check(data, name)
        markdown = _converter(fmt)(data)
    except ToolError:
        raise
    except ImportError:
        raise ToolError(
            message=f"Reading {fmt} files needs the documents extra, which is not installed.",
            hint=INSTALL_HINT,
        ) from None
    except MemoryError:
        # The worker's address-space limit spoke: a guard, not a damaged file.
        raise ToolError(
            message=f"{name} needs more memory to convert than this server allows.",
            hint=_TOO_EXPENSIVE_HINT,
            reason=REASON_GUARD_TRIPPED,
        ) from None
    except Exception as exc:  # every parser failure is one refusal by design
        logger.debug("%s conversion failed: %s", fmt, type(exc).__name__)
        raise _unreadable(name, fmt) from None
    return Converted(markdown=markdown, format=fmt)


_slots: tuple[asyncio.AbstractEventLoop, asyncio.Semaphore] | None = None


@asynccontextmanager
async def slot() -> AsyncIterator[None]:
    """One of :data:`MAX_CONCURRENT` conversion slots. Take it before the download."""
    global _slots
    loop = asyncio.get_running_loop()
    if _slots is None or _slots[0] is not loop:
        _slots = (loop, asyncio.Semaphore(MAX_CONCURRENT))
    async with _slots[1]:
        yield


def _command() -> list[str]:
    return [sys.executable, "-m", WORKER_MODULE]


#: What the worker needs to start and find the package, and nothing of the server's
#: configuration or secrets. SYSTEMROOT: Python on Windows does not start without it.
_PASSED_THROUGH = ("PATH", "PYTHONPATH", "SYSTEMROOT")


def _environment() -> dict[str, str]:
    return {key: os.environ[key] for key in _PASSED_THROUGH if key in os.environ}


async def _kill(process) -> None:
    """End the worker if it still runs. One that exited at the deadline is not an error."""
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    await process.wait()


async def convert(data: bytes, content_type: str, name: str) -> Converted:
    """Convert in a worker process, bounded in memory and time; the event loop keeps serving."""
    fmt = detect.detect(content_type, name)
    header = json.dumps({"content_type": content_type, "name": name}).encode("utf-8") + b"\n"
    process = await asyncio.create_subprocess_exec(
        *_command(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_environment(),
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(header + data), TIMEOUT_SECONDS)
    except TimeoutError:
        await _kill(process)
        raise ToolError(
            message=f"Converting {name} took longer than {TIMEOUT_SECONDS:g} seconds.",
            hint=_TOO_EXPENSIVE_HINT,
            reason=REASON_GUARD_TRIPPED,
        ) from None
    except BaseException:
        # Cancelled or failed while the worker runs: never leave it behind.
        await _kill(process)
        raise

    if process.returncode != 0:
        logger.debug("%s conversion worker exited with %s", fmt, process.returncode)
        raise _unreadable(name, fmt)
    try:
        payload = json.loads(stdout)
        if "error" in payload:
            error = payload["error"]
            if error["guard"]:
                raise ToolError(error["message"], error["hint"], reason=REASON_GUARD_TRIPPED)
            raise ToolError(error["message"], error["hint"])
        return Converted(markdown=payload["markdown"], format=payload["format"])
    except ToolError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug("%s conversion worker answered badly: %s", fmt, type(exc).__name__)
        raise _unreadable(name, fmt) from None
