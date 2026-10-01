"""The verdict of ``occ mcp_connector:exclusion:check`` as a pure function (OPS-01).

The handler (plan 29-04) and the live evidence (plan 29-06) only fetch data and shape the
answer; every judgement lives here, without I/O, so that each decision of phase 29 is pinned
by a unit test that needs no Nextcloud.

**"Exact" has one definition.** A tag is exact when :func:`exclusion.is_exclude_name` says
so, because that is the rule the guard filters with (pitfall P3 of the research). A second
spelling of the rule here could call "Kein-KI" a variant while the guard already honours it.
Nextcloud refuses a new tag that differs from an existing one in case only, so case variants
come from old data or direct database writes alone; they are exact all the same.

**Variants are found by equality of a normal form, not by substring.** The skeleton keeps
letters and digits only after NFKC and casefold, so "Kein KI", "kein_ki" and the dash
spellings all fold to ``keinki``, while a legitimate "Kein KI-Training" folds to
``keinkitraining`` and is left alone. A substring search would flag it.

**Similar names are a hint and never a verdict.** One edit away from ``keinki`` also
reaches unrelated words, so a similar name adds a note and changes nothing else.

**Homoglyphs are deliberately not covered.** A Cyrillic letter in place of a Latin one
survives NFKC; no confusables table is carried for that corner (T-29-07, accepted).

The counts handed in are what Nextcloud reports instance wide for a tag, including files in
the trash bin, so a number here is assignments and not reachable files. No object id, path
or account ever reaches this module: :class:`TagFacts` has no field for one (D-29-02).
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ..oauth.exchange_dryrun import (
    OUTCOME_FAILED,
    OUTCOME_NOT_CHECKED,
    OUTCOME_PASSED,
    OUTCOME_SKIPPED,
)
from .exclusion import EXCLUDE_TAG, is_exclude_name

__all__ = [
    "ACCESS_INVISIBLE",
    "ACCESS_PUBLIC",
    "ACCESS_RESTRICTED",
    "KIND_EXACT",
    "KIND_OTHER",
    "KIND_SIMILAR",
    "KIND_VARIANT",
    "MODE_MISCONFIGURED",
    "MODE_NONE",
    "MODE_ORGANISATION",
    "MODE_SELF_SERVICE",
    "OUTCOME_FAILED",
    "OUTCOME_NOTE",
    "OUTCOME_NOT_CHECKED",
    "OUTCOME_PASSED",
    "OUTCOME_SKIPPED",
    "STEPS",
    "STEP_ADMIN_IDENTITY",
    "STEP_ASSIGNMENT_COUNT",
    "STEP_NO_VARIANTS",
    "STEP_OPERATING_MODE",
    "STEP_TAG_EXISTS",
    "STEP_TAG_LISTING_READABLE",
    "STEP_TAG_VISIBLE",
    "AuditResult",
    "AuditStep",
    "TagFacts",
    "access_of",
    "audit",
    "kind_of",
    "tag_skeleton",
]

KIND_EXACT: Final[str] = "exact"
KIND_VARIANT: Final[str] = "variant"
KIND_SIMILAR: Final[str] = "similar"
KIND_OTHER: Final[str] = "other"

ACCESS_PUBLIC: Final[str] = "public"
ACCESS_RESTRICTED: Final[str] = "restricted"
ACCESS_INVISIBLE: Final[str] = "invisible"

MODE_NONE: Final[str] = "none"
MODE_SELF_SERVICE: Final[str] = "self_service"
MODE_ORGANISATION: Final[str] = "organisation"
MODE_MISCONFIGURED: Final[str] = "misconfigured"

#: A finding that does not tip the verdict, with its reason in ``AuditStep.note``.
OUTCOME_NOTE: Final[str] = "note"

STEP_ADMIN_IDENTITY: Final[str] = "admin_identity"
STEP_TAG_LISTING_READABLE: Final[str] = "tag_listing_readable"
STEP_TAG_EXISTS: Final[str] = "tag_exists"
STEP_TAG_VISIBLE: Final[str] = "tag_visible"
STEP_NO_VARIANTS: Final[str] = "no_variants"
STEP_OPERATING_MODE: Final[str] = "operating_mode"
STEP_ASSIGNMENT_COUNT: Final[str] = "assignment_count"

#: Every result names all of these, in this order: a missing line reads as a passed one.
STEPS: Final[tuple[str, ...]] = (
    STEP_ADMIN_IDENTITY,
    STEP_TAG_LISTING_READABLE,
    STEP_TAG_EXISTS,
    STEP_TAG_VISIBLE,
    STEP_NO_VARIANTS,
    STEP_OPERATING_MODE,
    STEP_ASSIGNMENT_COUNT,
)

_RELEVANT: Final[frozenset[str]] = frozenset({KIND_EXACT, KIND_VARIANT, KIND_SIMILAR})


@dataclass(frozen=True, slots=True)
class TagFacts:
    """What the handler read about one tag. Names, flags, gids and a count, nothing else."""

    id: str
    name: str
    visible: bool
    assignable: bool
    #: Delegated gids; ``None`` when not read (no administrator's view).
    groups: tuple[str, ...] | None
    #: Number of ``files`` objects carrying the tag; ``None`` when the count failed.
    assigned: int | None


@dataclass(frozen=True, slots=True)
class AuditStep:
    """One step with its outcome and, where it says more, one machine readable word."""

    step: str
    outcome: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class AuditResult:
    """The verdict. Wording is built by the console, never here."""

    checked: bool
    passed: bool
    mode: str
    #: Sum over exact, visible tags.
    assigned: int | None
    #: Sum over variants and invisible exact tags: objects that look protected and are not.
    unprotected: int | None
    admin_checked: bool
    steps: tuple[AuditStep, ...]
    #: Exact, variant and similar tags only, sorted by name; any other tag never.
    tags: tuple[TagFacts, ...]


def tag_skeleton(name: str) -> str:
    """NFKC, casefold, then letters and digits only (drops blanks, dashes, ``_`` and the like)."""
    folded = unicodedata.normalize("NFKC", name).casefold()
    return "".join(ch for ch in folded if unicodedata.category(ch)[0] in "LN")


#: The normal form every variant shares with the tag name itself, derived and never typed.
_SKELETON: Final[str] = tag_skeleton(EXCLUDE_TAG)


def _distance(a: str, b: str) -> int:
    """Optimal string alignment distance: insert, delete, substitute, swap neighbours."""
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)
    return rows[len(a)][len(b)]


def kind_of(name: str) -> str:
    """``exact`` by the guard's own rule, else ``variant``, ``similar`` or ``other``."""
    if is_exclude_name(name):
        return KIND_EXACT
    skeleton = tag_skeleton(name)
    if skeleton == _SKELETON:
        return KIND_VARIANT
    if _distance(skeleton, _SKELETON) == 1:
        return KIND_SIMILAR
    return KIND_OTHER


def access_of(tag: TagFacts) -> str:
    """Nextcloud's three access levels from the two flags a listing carries."""
    if not tag.visible:
        return ACCESS_INVISIBLE
    return ACCESS_PUBLIC if tag.assignable else ACCESS_RESTRICTED


def _sum(tags: Sequence[TagFacts]) -> int | None:
    """Total of the counts, or ``None`` as soon as one of them is unknown."""
    total = 0
    for tag in tags:
        if tag.assigned is None:
            return None
        total += tag.assigned
    return total


def _stopped(at: str, *, admin_checked: bool) -> AuditResult:
    """A run that fell at ``at``: every step before it held, every step after it skipped."""
    steps: list[AuditStep] = []
    for step in STEPS:
        if step == at:
            steps.append(AuditStep(step, OUTCOME_FAILED))
        elif len(steps) < STEPS.index(at):
            steps.append(_identity_step(admin_checked=admin_checked))
        else:
            steps.append(AuditStep(step, OUTCOME_SKIPPED))
    return AuditResult(
        checked=False,
        passed=False,
        mode=MODE_NONE,
        assigned=None,
        unprotected=None,
        admin_checked=admin_checked,
        steps=tuple(steps),
        tags=(),
    )


def _identity_step(*, admin_checked: bool) -> AuditStep:
    if admin_checked:
        return AuditStep(STEP_ADMIN_IDENTITY, OUTCOME_PASSED)
    return AuditStep(STEP_ADMIN_IDENTITY, OUTCOME_NOT_CHECKED, "admin_not_named")


def _mode_step(visible_exact: Sequence[TagFacts]) -> tuple[str, AuditStep]:
    """The operating mode of the visible exact tags (D-29-01)."""
    if not visible_exact:
        return MODE_NONE, AuditStep(STEP_OPERATING_MODE, OUTCOME_SKIPPED)
    public = [t for t in visible_exact if t.assignable]
    restricted = [t for t in visible_exact if not t.assignable]
    if public:
        if restricted:
            return MODE_SELF_SERVICE, AuditStep(STEP_OPERATING_MODE, OUTCOME_NOTE, "mixed_access")
        return MODE_SELF_SERVICE, AuditStep(STEP_OPERATING_MODE, OUTCOME_PASSED)
    if any(t.groups is None for t in restricted):
        return MODE_ORGANISATION, AuditStep(
            STEP_OPERATING_MODE, OUTCOME_PASSED, "groups_not_checked"
        )
    if not any(t.groups for t in restricted):
        return MODE_ORGANISATION, AuditStep(STEP_OPERATING_MODE, OUTCOME_NOTE, "admins_only")
    return MODE_ORGANISATION, AuditStep(STEP_OPERATING_MODE, OUTCOME_PASSED)


def audit(
    tags: Sequence[TagFacts],
    *,
    admin_checked: bool,
    admin_failed: bool = False,
    listing_ok: bool = True,
) -> AuditResult:
    """Judge the tags of one instance. Always seven steps; ``passed`` false on any failure.

    Without an administrator's view the caller hands in visible tags only; an invisible one
    that slips through is ignored, so the verdict never rests on what was not meant to be
    seen. An unreadable listing is a failure and never "no tag" (T-29-05).
    """
    if admin_failed:
        return _stopped(STEP_ADMIN_IDENTITY, admin_checked=admin_checked)
    if not listing_ok:
        return _stopped(STEP_TAG_LISTING_READABLE, admin_checked=admin_checked)

    seen = [t for t in tags if admin_checked or t.visible]
    kinds = {id(t): kind_of(t.name) for t in seen}
    relevant = sorted((t for t in seen if kinds[id(t)] in _RELEVANT), key=lambda t: (t.name, t.id))
    exact = [t for t in relevant if kinds[id(t)] == KIND_EXACT]
    variants = [t for t in relevant if kinds[id(t)] == KIND_VARIANT]
    similar = [t for t in relevant if kinds[id(t)] == KIND_SIMILAR]
    visible_exact = [t for t in exact if t.visible]
    invisible_exact = [t for t in exact if not t.visible]

    steps = [
        _identity_step(admin_checked=admin_checked),
        AuditStep(STEP_TAG_LISTING_READABLE, OUTCOME_PASSED),
    ]
    visibility_unchecked = AuditStep(
        STEP_TAG_VISIBLE, OUTCOME_NOT_CHECKED, "visibility_not_checked"
    )

    if not exact and not variants:
        steps.append(
            AuditStep(
                STEP_TAG_EXISTS, OUTCOME_NOTE, "no_tag" if admin_checked else "no_visible_tag"
            )
        )
        steps.append(
            AuditStep(STEP_TAG_VISIBLE, OUTCOME_SKIPPED) if admin_checked else visibility_unchecked
        )
        steps.extend(AuditStep(step, OUTCOME_SKIPPED) for step in STEPS[4:])
        return AuditResult(
            checked=True,
            passed=True,
            mode=MODE_NONE,
            assigned=0,
            unprotected=0,
            admin_checked=admin_checked,
            steps=tuple(steps),
            tags=tuple(relevant),
        )

    steps.append(AuditStep(STEP_TAG_EXISTS, OUTCOME_PASSED if exact else OUTCOME_FAILED))

    if not admin_checked:
        steps.append(visibility_unchecked)
    elif not exact:
        steps.append(AuditStep(STEP_TAG_VISIBLE, OUTCOME_SKIPPED))
    else:
        steps.append(
            AuditStep(STEP_TAG_VISIBLE, OUTCOME_FAILED if invisible_exact else OUTCOME_PASSED)
        )

    if variants:
        if exact:
            steps.append(AuditStep(STEP_NO_VARIANTS, OUTCOME_NOTE, "variant_beside_exact"))
        else:
            steps.append(AuditStep(STEP_NO_VARIANTS, OUTCOME_FAILED))
    else:
        steps.append(
            AuditStep(STEP_NO_VARIANTS, OUTCOME_PASSED, "similar_name" if similar else None)
        )

    mode, mode_step = _mode_step(visible_exact)
    steps.append(mode_step)
    if invisible_exact or not exact:
        mode = MODE_MISCONFIGURED

    assigned = _sum(visible_exact)
    unprotected = _sum([*variants, *invisible_exact])
    counted = assigned is not None and unprotected is not None
    steps.append(AuditStep(STEP_ASSIGNMENT_COUNT, OUTCOME_PASSED if counted else OUTCOME_FAILED))

    return AuditResult(
        checked=True,
        passed=all(s.outcome != OUTCOME_FAILED for s in steps),
        mode=mode,
        assigned=assigned,
        unprotected=unprotected,
        admin_checked=admin_checked,
        steps=tuple(steps),
        tags=tuple(relevant),
    )
