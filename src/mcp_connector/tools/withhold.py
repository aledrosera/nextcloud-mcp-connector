"""What every file-bearing tool family shares when it withholds an entry (EXCL-01, SBX-01).

The exclusion guard (``nextcloud.exclusion``) answers what is tagged ``kein-ki``; this module
holds the few pieces the families need to act on that answer the same way everywhere:

*   **One sentence (D-27-05).** :data:`EXCLUSION_UNAVAILABLE` is the reason of every
    ``degraded`` entry, of every single-item refusal and of every refused upload when the
    guard could not answer. One wording means no drift between families and one sentence
    for the documentation.
*   **Silence on success (D-27-03, D-v1.7-02).** A withheld entry leaves no trace: no
    counter, no hint. Only the "could not check" state speaks, with one ``degraded`` entry in
    a list and with :func:`unavailable_error` on a single item, the same for every id, so
    the error itself cannot become an existence oracle.
*   **Sandbox before tag (D-27-04).** A family may drop an entry outside
    ``NC_MCP_FILES_ROOT`` first and count it as before; that reason says nothing about a
    tag. Tag drops are never counted.
*   **Fail-closed on a failed lookup.** When a file id cannot be resolved into a path
    because the lookup itself failed, the entry is withheld like in the "could not check"
    state, never passed through.

:func:`file_refs` reads the file behind a search entry of any provider (files, Findling,
comments, notes), and :func:`needs_paths` says whether the file id alone decides or the
path has to be resolved. Everything here is a pure function or a constant, no module state.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .. import config, provider_map
from ..errors import REASON_GUARD_TRIPPED, ToolError
from ..nextcloud.exclusion import TagScope

#: The one wording of "the exclusion check could not be answered" (D-27-05). It names no
#: path and no id on purpose (pitfall 9): it must read the same for every entry.
EXCLUSION_UNAVAILABLE = (
    "The exclusion check (tag kein-ki) could not be answered, so entries that may carry "
    "file content are withheld."
)

#: The name under which a list family reports the unanswered check in ``degraded``.
DEGRADED_NAME = "exclusion"

UNAVAILABLE_HINT = (
    "Retry in a minute; if it persists, ask an administrator to check the system tags."
)


def unavailable_error() -> ToolError:
    """The refusal of a single item or an upload while the check cannot be answered.

    Takes no argument, so it cannot name the id or the path that was asked for: every call
    builds the identical error.
    """
    return ToolError(
        message=EXCLUSION_UNAVAILABLE,
        hint=UNAVAILABLE_HINT,
        reason=REASON_GUARD_TRIPPED,
    )


def degraded_entry(key: str) -> dict[str, str]:
    """The one ``degraded`` entry of a list family, under that family's own key.

    ``unified_search`` names its sources ``provider``, ``prepare_context`` names them
    ``source``; the entry follows the idiom of the family it lands in.
    """
    return {key: DEGRADED_NAME, "reason": EXCLUSION_UNAVAILABLE}


@dataclass(frozen=True, slots=True)
class FileRef:
    """The file behind one search entry, as far as the entry itself tells.

    ``fileid`` is ASCII digits or ``None``; ``path`` is an absolute home path or ``None``.
    ``file_bearing`` is true when the entry may carry file content at all, even if neither
    value could be read: such an entry has to be resolved or withheld, never passed.
    """

    fileid: str | None
    path: str | None
    file_bearing: bool


def file_refs(base_url: str, provider_id: str, entry: Mapping[str, Any]) -> FileRef:
    """Read the file id and the path of a search entry, for any provider.

    The file id follows ``provider_map.file_id`` (``attributes.fileId``, then ``/f/<id>`` of
    the URL), which covers the files provider, Findling and comments alike; a notes entry
    carries its id, which is the file id of the note, as the last numeric URL segment.
    ``attributes.path`` counts only as a string and only in plain form (no dot segment, no
    empty segment, no backslash, no control character); anything else is ``None`` and the
    file id has to decide.
    """
    raw_attributes = entry.get("attributes")
    attributes: Mapping[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
    url = provider_map.absolute_url(base_url, entry.get("resourceUrl"))
    if provider_id == "notes":
        fileid = provider_map.last_numeric_segment(url)
    else:
        fileid = provider_map.file_id(attributes, url)

    file_bearing = (
        provider_id == "files" or "fileId" in attributes or "path" in attributes or bool(fileid)
    )
    return FileRef(
        fileid=fileid or None,
        path=_plain_home_path(attributes.get("path")),
        file_bearing=file_bearing,
    )


def needs_paths(scope: TagScope) -> bool:
    """Whether file ids have to be resolved into paths before an entry may be kept.

    The sandbox needs the path, and so does a tagged folder (it covers what lies below it).
    Without either, the file id alone decides and the lookup can be saved.
    """
    return config.files_root() != "/" or scope.has_folders


def _plain_home_path(raw: Any) -> str | None:
    """``attributes.path`` as an absolute home path, or ``None`` if it is not plain."""
    if not isinstance(raw, str):
        return None
    path = "/" + raw.strip("/")
    if "//" in path or "\\" in path:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        return None
    if any(segment in (".", "..") for segment in path.split("/")):
        return None
    return path
