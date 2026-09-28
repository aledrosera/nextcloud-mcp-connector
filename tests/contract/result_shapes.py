"""Building blocks to compare and scan tool answers; a helper module, not a test module.

Two gates of phase 28 read tool answers with the same eyes: the pair tests (GATE-03) compare
the answer for a tagged object with the answer for an object that does not exist, and the
canary (GATE-02) scans every answer for a marker. Both import the functions here, so the
normalisation and the scan exist once.

Why a module and not ``conftest.py``: see ``tool_classes.py``; ``pyproject.toml`` puts
``tests/contract`` on the import path.
"""

import base64
import json
import posixpath
import re
from urllib.parse import unquote

from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextContent,
    TextResourceContents,
)

# Only this many characters of a leaking surface go into a failure message.
_LEAK_EXCERPT = 200
# A segment of a bare fetch id shorter than this is too common to replace safely.
_MIN_SEGMENT = 3


def requested_forms(*values: str) -> tuple[str, ...]:
    """Every form of the requested ids that may appear in an answer, longest first.

    Definition: requested id = the argument, its path prefixes and for fetch the bare id
    ("angefragte Id = das Argument, seine Pfad-Präfixe und für fetch die nackte Id").

    A path (starts with "/") adds every ``dirname`` up to but excluding "/", because a
    ``parent_missing`` error names the parent folder as well (pitfall 6). A fetch id of the
    form ``kind:rest`` adds ``rest`` and every segment of ``rest`` with at least three
    characters.
    """
    forms: set[str] = set()
    for value in values:
        if not value:
            continue
        forms.add(value)
        if value.startswith("/"):
            parent = posixpath.dirname(value.rstrip("/"))
            while parent not in ("", "/"):
                forms.add(parent)
                parent = posixpath.dirname(parent)
        elif ":" in value:
            rest = value.split(":", 1)[1]
            if rest:
                forms.add(rest)
                forms.update(part for part in rest.split(":") if len(part) >= _MIN_SEGMENT)
    return tuple(sorted(forms, key=lambda form: (-len(form), form)))


def normalised(result: CallToolResult, *requested: str) -> str:
    """The whole answer as canonical JSON with every requested form replaced by ``<ID>``.

    The replacement respects word boundaries: "12" never touches "1234" or "size 120". The
    response time is not part of the answer (D-28-12).
    """
    text = json.dumps(
        result.model_dump(mode="json", by_alias=True), sort_keys=True, ensure_ascii=False
    )
    for form in requested_forms(*requested):
        text = re.sub(rf"(?<![0-9A-Za-z]){re.escape(form)}(?![0-9A-Za-z])", "<ID>", text)
    return text


def surfaces(result: CallToolResult) -> list[str]:
    """Every surface of an answer a model can read, decoded (pitfall 5).

    Structured content as JSON, every text part, and for an embedded resource the unquoted
    URI plus its text or its base64-decoded blob.
    """
    out = [json.dumps(result.structured_content or {}, ensure_ascii=False)]
    for part in result.content:
        if isinstance(part, TextContent):
            out.append(part.text)
        elif isinstance(part, EmbeddedResource):
            resource = part.resource
            out.append(unquote(str(resource.uri)))
            if isinstance(resource, TextResourceContents):
                out.append(resource.text)
            elif isinstance(resource, BlobResourceContents):
                out.append(base64.b64decode(resource.blob).decode("utf-8", errors="replace"))
    return out


def leaks(result: CallToolResult, marker: str) -> list[str]:
    """Every surface that contains the marker, cut to 200 characters for the message."""
    return [surface[:_LEAK_EXCERPT] for surface in surfaces(result) if marker in surface]
