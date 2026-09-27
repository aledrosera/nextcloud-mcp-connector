"""The exclusion guard core: is anything tagged ``kein-ki``, and if so, what (EXCL-02, EXCL-04).

This module turns the two calls of ``clients.systemtags`` into one value, a :class:`TagScope`,
and holds the policy the client deliberately does not know. It withholds nothing itself and
shapes no message; the tool layer of phase 27 does that with the value it gets from here.

Why three states and not a boolean (EXCL-04): "nothing is tagged" and "the question could not
be answered" must never collapse into the same value. ``untagged`` leaves every answer exactly
as it was, ``active`` carries the tagged set, and ``unverifiable`` carries a reason code and
refuses to be read as "allowed": :meth:`TagScope.excludes` raises in that state, so a caller
cannot filter with it by accident.

Why the REPORT outcome decides and not the ``systemtags`` capability (D-25-05): on Nextcloud
32 to 34 the capability is cached in APCu and wrong in both directions for a while after the
app is switched. The answer to the question itself is the only one that counts: 207 is a set,
412 means the id went stale and is looked up exactly once more, everything else is
``unverifiable``.

Why the tagged set is never cached beyond one call and only name to id is (E3, EXCL-02): a
tag added a second ago has to take effect on the next call, so the set is asked for anew by
every guard instance, and a guard lives exactly as long as one tool call. What survives is the
mapping from the tag name to its ids, per ``(base_url, user)``, positive results only: an
account without the tag lists again on every call, so a freshly created tag is never hidden
behind a cached "nothing". The key carries the user because visibility differs: an admin sees
restricted and invisible tags that alice does not, and an admin id handed to alice would only
ever answer 412.

Why one REPORT per spelling: Nextcloud intersects several ``oc:systemtag`` rules in one REPORT
(``array_uintersect``), so two ids in one body ask for "carries both", which silently answers
"nothing" for a node carrying only one of them. Each distinct exact spelling of the name
therefore gets its own REPORT with exactly one id, and the sets are united.

How to read success criterion 2 ("exactly one REPORT per tool call"): per tool call, that is
per guard instance, there is exactly one flight however many parts ask concurrently. Within
it one REPORT goes out per distinct spelling, which on any Nextcloud from 32 on is one unless
old duplicates exist, none goes out when nothing is tagged, plus at most the one re-listing
after a 412.

Known limit: on SQLite with about 140k tag assignments the REPORT takes longer than
``TAG_BUDGET``, so the guard is ``unverifiable`` there by construction (documented in phase 29).

What this module does not have, on purpose: no admin switch and no second path list (D-26-01,
D-26-02), and no configurable tag name. The name is ``kein-ki``, compared case-insensitively
after trimming blanks, and nothing else.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .clients import systemtags

__all__ = [
    "EXCLUDE_TAG",
    "TAG_BUDGET",
    "TTL_SECONDS",
    "UNTAGGED",
    "State",
    "TagScope",
    "Why",
    "ancestors",
    "clear_cache",
    "exclude_tag_ids",
    "is_exclude_name",
]

EXCLUDE_TAG = "kein-ki"

#: Lifetime of a name-to-id entry in seconds. Nextcloud from 32 on refuses to create a second
#: spelling that differs only in case, so a new spelling can only appear through direct
#: database access; this is the longest it stays unseen (assumption A4 of phase 25).
TTL_SECONDS = 60.0

#: The whole flight (listing, REPORTs, one re-listing) has this many seconds. It covers the
#: measured SQLite worst case of 5000 hits (8.1 to 10.6 s) with room to spare, and both ways
#: of being wrong about it end fail-closed: too short is ``unverifiable``, never ``untagged``.
TAG_BUDGET = 15.0

type State = Literal["untagged", "active", "unverifiable"]

#: Internal reason codes of the ``unverifiable`` state. They are not error reasons of the
#: tool contract (``errors.REASONS`` stays frozen); phase 27 decides what the model reads.
type Why = Literal["timeout", "unreachable", "status", "stale_twice", "unparsable", "foreign_href"]

#: (base_url, user) -> (stored_at, one id per distinct spelling). Positive only.
_tag_ids: dict[tuple[str, str], tuple[float, tuple[str, ...]]] = {}


def clear_cache() -> None:
    """Drop every entry. Safe at any time, by construction (D-20)."""
    _tag_ids.clear()


def _cached_ids(key: tuple[str, str]) -> tuple[str, ...] | None:
    """The ids stored for ``key`` if the entry is younger than ``TTL_SECONDS``."""
    cached = _tag_ids.get(key)
    if cached is not None and time.monotonic() - cached[0] < TTL_SECONDS:
        return cached[1]
    return None


def _store_ids(key: tuple[str, str], ids: tuple[str, ...]) -> None:
    """Remember ``ids`` for ``key``, but never an empty result (a new tag must show at once)."""
    if ids:
        _tag_ids[key] = (time.monotonic(), ids)


def _drop_ids(key: tuple[str, str]) -> None:
    """Forget the ids of ``key``; a 412 has just shown them stale."""
    _tag_ids.pop(key, None)


def is_exclude_name(name: str) -> bool:
    """Whether ``name`` spells the exclusion tag, ignoring case and surrounding blanks."""
    return name.strip().casefold() == EXCLUDE_TAG


def exclude_tag_ids(tags: Iterable[systemtags.Tag]) -> tuple[str, ...]:
    """One id per distinct exact spelling of the tag name, sorted by number.

    The spelling is kept exactly as listed, because Nextcloud looks tags up by their exact
    name and already unites tags of identical name there; per spelling the numerically
    lowest id stands for it.
    """
    lowest: dict[str, int] = {}
    for tag in tags:
        if not is_exclude_name(tag.name):
            continue
        number = int(tag.id)
        if tag.name not in lowest or number < lowest[tag.name]:
            lowest[tag.name] = number
    return tuple(str(number) for number in sorted(lowest.values()))


def ancestors(path: str) -> tuple[str, ...]:
    """The path itself and every parent up to ``/``, nearest first.

    ``a in tagged for a in ancestors(p)`` draws the same boundary as ``dav.within(p, t)`` for
    every tagged ``t``, which the unit tests prove; the set lookup only makes it cheap.
    """
    result = [path]
    while path not in ("", "/"):
        path = path.rsplit("/", 1)[0] or "/"
        result.append(path)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class TagScope:
    """The answer to "what is tagged ``kein-ki``" for one tool call, as a value."""

    state: State
    paths: frozenset[str] = frozenset()
    fileids: frozenset[str] = frozenset()
    reason: Why | None = None

    def excludes(self, path: str | None = None, fileid: str | None = None) -> bool:
        """Whether the node at ``path`` or with ``fileid`` has to be withheld.

        ``path`` is an absolute home path as dav entries carry it, not the virtual view
        inside ``NC_MCP_FILES_ROOT``. In the ``unverifiable`` state this raises instead of
        answering, so "could not check" can never be read as "allowed".
        """
        if self.state == "unverifiable":
            raise ValueError(
                "the exclusion scope is unverifiable; the caller must withhold, not ask"
            )
        if self.state == "untagged":
            return False
        if fileid is not None and fileid in self.fileids:
            return True
        return path is not None and any(a in self.paths for a in ancestors(path))


#: The one value every "nothing is tagged" answer shares. Immutable, so not module state.
UNTAGGED = TagScope("untagged")
