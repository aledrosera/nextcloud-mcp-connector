"""The verdict of ``occ mcp_connector:exclusion:check`` as a pure function (OPS-01).

Every expectation below comes from a decision of phase 29, not from the implementation:

* **D-29-01** the operating mode is named: self service (a public tag) or organisation mode
  (a restricted tag, delegated groups named, no groups meaning administrators only).
* **D-29-02** the result carries counts, tag names and gids, never an object id, a path or
  an account. ``TagFacts`` has no field that could hold one.
* **D-29-03** no ``kein-ki`` tag at all is a note and the verdict stays green; an invisible
  exact tag or a variant without the exact tag is a failure.
* **D-29-09** without an administrator's view, visibility and delegated groups are marked
  ``not_checked`` rather than silently assumed.
* **D-29-10** the exact tag beside a variant stays green with a warning, a variant alone is
  red, and the objects on the variant are counted as unprotected.

"Exact" is whatever ``exclusion.is_exclude_name`` says, because that is the rule the guard
filters with (pitfall P3 of the research): "Kein-KI" is exact and never a variant. Dash
characters are built with ``chr()`` so that this file stays free of them.

Nothing in this file reaches the network; the function under test takes data only.
"""

from dataclasses import fields

import pytest

from mcp_connector.nextcloud import exclusion_audit as ea
from mcp_connector.nextcloud.exclusion_audit import AuditResult, TagFacts
from mcp_connector.oauth import exchange_dryrun

EN_DASH = chr(0x2013)
HYPHEN = chr(0x2010)


def tag(
    name: str,
    *,
    tag_id: str = "1",
    visible: bool = True,
    assignable: bool = True,
    groups: tuple[str, ...] | None = (),
    assigned: int | None = 0,
) -> TagFacts:
    """One tag as the handler would hand it over."""
    return TagFacts(
        id=tag_id,
        name=name,
        visible=visible,
        assignable=assignable,
        groups=groups,
        assigned=assigned,
    )


def outcomes(result: AuditResult) -> dict[str, tuple[str, str | None]]:
    """Step name to (outcome, note), after checking that every step is there in order."""
    assert tuple(s.step for s in result.steps) == ea.STEPS
    return {s.step: (s.outcome, s.note) for s in result.steps}


PUBLIC = tag("kein-ki", tag_id="10", assigned=3)
RESTRICTED = tag("kein-ki", tag_id="11", assignable=False, groups=("ki-verantwortung",), assigned=2)
INVISIBLE = tag("kein-ki", tag_id="12", visible=False, assignable=False, assigned=4)
VARIANT = tag("Kein KI", tag_id="20", assigned=5)
SIMILAR = tag("kien-ki", tag_id="30", assigned=1)
FOREIGN = tag("projekt", tag_id="40", assigned=9)

# --- the normal form ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "skeleton"),
    [
        ("Kein KI", "keinki"),
        ("kein_ki", "keinki"),
        ("kein" + EN_DASH + "ki", "keinki"),
        ("kein" + HYPHEN + "ki", "keinki"),
        ("Kein KI-Training", "keinkitraining"),
    ],
)
def test_tag_skeleton(name: str, skeleton: str) -> None:
    assert ea.tag_skeleton(name) == skeleton


# --- the four kinds -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("kein-ki", ea.KIND_EXACT),
        ("Kein-KI", ea.KIND_EXACT),
        (" kein-ki ", ea.KIND_EXACT),
        ("KEIN-KI", ea.KIND_EXACT),
        ("Kein KI", ea.KIND_VARIANT),
        ("keinki", ea.KIND_VARIANT),
        ("kein_ki", ea.KIND_VARIANT),
        ("kein" + EN_DASH + "ki", ea.KIND_VARIANT),
        ("kein" + HYPHEN + "ki", ea.KIND_VARIANT),
        ("kien-ki", ea.KIND_SIMILAR),
        ("kein-kl", ea.KIND_SIMILAR),
        ("keinkii", ea.KIND_SIMILAR),
        ("Kein KI-Training", ea.KIND_OTHER),
        ("keine-ki-tools", ea.KIND_OTHER),
        ("projekt", ea.KIND_OTHER),
    ],
)
def test_kind_of(name: str, kind: str) -> None:
    assert ea.kind_of(name) == kind


def test_exact_spellings_are_never_variants() -> None:
    """The guard filters these, so calling them a variant would be a false alarm."""
    for name in ("Kein-KI", " kein-ki ", "KEIN-KI"):
        assert ea.kind_of(name) != ea.KIND_VARIANT


# --- access -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("visible", "assignable", "access"),
    [
        (True, True, ea.ACCESS_PUBLIC),
        (True, False, ea.ACCESS_RESTRICTED),
        (False, False, ea.ACCESS_INVISIBLE),
    ],
)
def test_access_of(visible: bool, assignable: bool, access: str) -> None:
    assert ea.access_of(tag("kein-ki", visible=visible, assignable=assignable)) == access


# --- the verdict --------------------------------------------------------------------------


def test_no_tag_is_a_note_and_green() -> None:
    result = ea.audit([FOREIGN], admin_checked=True)
    steps = outcomes(result)
    assert result.checked
    assert result.passed
    assert result.mode == ea.MODE_NONE
    assert result.assigned == 0
    assert steps[ea.STEP_TAG_EXISTS] == (ea.OUTCOME_NOTE, "no_tag")
    for step in (
        ea.STEP_TAG_VISIBLE,
        ea.STEP_NO_VARIANTS,
        ea.STEP_OPERATING_MODE,
        ea.STEP_ASSIGNMENT_COUNT,
    ):
        assert steps[step][0] == ea.OUTCOME_SKIPPED


def test_no_visible_tag_without_admin_never_claims_there_is_none() -> None:
    """Without an admin's view an invisible tag may exist; the note must say "visible"."""
    result = ea.audit([FOREIGN], admin_checked=False)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_NONE
    assert steps[ea.STEP_TAG_EXISTS] == (ea.OUTCOME_NOTE, "no_visible_tag")
    assert steps[ea.STEP_TAG_EXISTS][1] != "no_tag"
    assert steps[ea.STEP_TAG_VISIBLE] == (ea.OUTCOME_NOT_CHECKED, "visibility_not_checked")


def test_public_exact_tag_is_self_service() -> None:
    other = tag("kein-ki", tag_id="13", assigned=4)
    result = ea.audit([PUBLIC, other], admin_checked=True)
    steps = outcomes(result)
    assert result.checked
    assert result.passed
    assert result.mode == ea.MODE_SELF_SERVICE
    assert result.assigned == 7
    assert result.unprotected == 0
    assert all(outcome == ea.OUTCOME_PASSED for outcome, _ in steps.values())


def test_restricted_tag_with_groups_is_organisation_mode() -> None:
    result = ea.audit([RESTRICTED], admin_checked=True)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_ORGANISATION
    assert steps[ea.STEP_OPERATING_MODE] == (ea.OUTCOME_PASSED, None)
    assert result.tags[0].groups == ("ki-verantwortung",)
    assert result.assigned == 2


def test_restricted_tag_without_groups_is_admins_only() -> None:
    result = ea.audit([tag("kein-ki", assignable=False, groups=())], admin_checked=True)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_ORGANISATION
    assert steps[ea.STEP_OPERATING_MODE] == (ea.OUTCOME_NOTE, "admins_only")


def test_public_beside_restricted_is_self_service() -> None:
    """Anyone may set the public tag, so the stricter one does not decide the mode."""
    result = ea.audit([PUBLIC, RESTRICTED], admin_checked=True)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_SELF_SERVICE
    assert steps[ea.STEP_OPERATING_MODE] == (ea.OUTCOME_NOTE, "mixed_access")
    assert result.assigned == 5


def test_invisible_exact_tag_fails_and_its_objects_are_unprotected() -> None:
    result = ea.audit([INVISIBLE], admin_checked=True)
    steps = outcomes(result)
    assert result.checked
    assert not result.passed
    assert result.mode == ea.MODE_MISCONFIGURED
    assert steps[ea.STEP_TAG_VISIBLE][0] == ea.OUTCOME_FAILED
    assert result.unprotected == 4
    assert result.assigned == 0


def test_without_admin_visibility_is_not_checked_and_can_be_green() -> None:
    result = ea.audit([PUBLIC], admin_checked=False)
    steps = outcomes(result)
    assert result.checked
    assert result.passed
    assert not result.admin_checked
    assert steps[ea.STEP_ADMIN_IDENTITY] == (ea.OUTCOME_NOT_CHECKED, "admin_not_named")
    assert steps[ea.STEP_TAG_VISIBLE] == (ea.OUTCOME_NOT_CHECKED, "visibility_not_checked")
    assert result.mode == ea.MODE_SELF_SERVICE


def test_without_admin_groups_are_not_checked() -> None:
    restricted = tag("kein-ki", assignable=False, groups=None, assigned=1)
    result = ea.audit([restricted], admin_checked=False)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_ORGANISATION
    assert steps[ea.STEP_OPERATING_MODE] == (ea.OUTCOME_PASSED, "groups_not_checked")


def test_without_admin_an_invisible_tag_never_decides() -> None:
    """The caller filters them; should one slip through, it is ignored, not judged."""
    result = ea.audit([PUBLIC, INVISIBLE], admin_checked=False)
    assert result.passed
    assert all(t.visible for t in result.tags)


def test_admin_failed_stops_before_anything_is_judged() -> None:
    result = ea.audit([PUBLIC], admin_checked=True, admin_failed=True)
    steps = outcomes(result)
    assert not result.checked
    assert not result.passed
    assert steps[ea.STEP_ADMIN_IDENTITY][0] == ea.OUTCOME_FAILED
    assert all(steps[s][0] == ea.OUTCOME_SKIPPED for s in ea.STEPS[1:])
    assert result.tags == ()
    assert result.assigned is None


def test_unreadable_listing_is_never_no_tag() -> None:
    """T-29-05: an empty list from a failed read must not turn into a green "no tag"."""
    result = ea.audit([], admin_checked=True, listing_ok=False)
    steps = outcomes(result)
    assert not result.checked
    assert not result.passed
    assert steps[ea.STEP_TAG_LISTING_READABLE][0] == ea.OUTCOME_FAILED
    assert all(steps[s][0] == ea.OUTCOME_SKIPPED for s in ea.STEPS[2:])
    assert all(note != "no_tag" for _, note in steps.values())


def test_variant_alone_fails() -> None:
    result = ea.audit([VARIANT], admin_checked=True)
    steps = outcomes(result)
    assert result.checked
    assert not result.passed
    assert result.mode == ea.MODE_MISCONFIGURED
    assert steps[ea.STEP_TAG_EXISTS][0] == ea.OUTCOME_FAILED
    assert steps[ea.STEP_NO_VARIANTS][0] == ea.OUTCOME_FAILED
    assert result.unprotected == 5


def test_variant_beside_exact_tag_warns_but_stays_green() -> None:
    result = ea.audit([PUBLIC, VARIANT], admin_checked=True)
    steps = outcomes(result)
    assert result.passed
    assert result.mode == ea.MODE_SELF_SERVICE
    assert steps[ea.STEP_NO_VARIANTS] == (ea.OUTCOME_NOTE, "variant_beside_exact")
    assert result.assigned == 3
    assert result.unprotected == 5


def test_similar_name_is_a_hint_only() -> None:
    result = ea.audit([PUBLIC, SIMILAR], admin_checked=True)
    steps = outcomes(result)
    assert result.passed
    assert steps[ea.STEP_NO_VARIANTS] == (ea.OUTCOME_PASSED, "similar_name")
    assert result.unprotected == 0


def test_similar_alone_never_changes_the_verdict() -> None:
    assert ea.audit([SIMILAR], admin_checked=True).passed


def test_uncounted_exact_tag_fails() -> None:
    """T-29-05: a count that could not be read is not zero."""
    result = ea.audit([tag("kein-ki", assigned=None)], admin_checked=True)
    steps = outcomes(result)
    assert not result.passed
    assert steps[ea.STEP_ASSIGNMENT_COUNT][0] == ea.OUTCOME_FAILED
    assert result.assigned is None


def test_foreign_tags_never_reach_the_result() -> None:
    result = ea.audit([FOREIGN, VARIANT, PUBLIC, SIMILAR], admin_checked=True)
    names = [t.name for t in result.tags]
    assert "projekt" not in names
    assert names == sorted(names)
    assert set(names) == {"kein-ki", "Kein KI", "kien-ki"}


# --- the shape ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tags", "kwargs"),
    [
        ([], {"admin_checked": True}),
        ([PUBLIC], {"admin_checked": False}),
        ([VARIANT, INVISIBLE], {"admin_checked": True}),
        ([PUBLIC], {"admin_checked": True, "admin_failed": True}),
        ([], {"admin_checked": True, "listing_ok": False}),
    ],
)
def test_every_result_names_all_seven_steps(tags: list[TagFacts], kwargs: dict[str, bool]) -> None:
    result = ea.audit(tags, **kwargs)
    assert tuple(s.step for s in result.steps) == ea.STEPS
    assert len(ea.STEPS) == 7


def test_tag_facts_have_no_field_for_an_object_id() -> None:
    """T-29-06 / D-29-02: there is nowhere to put an id, a path or an account."""
    names = {f.name for f in fields(TagFacts)} | {f.name for f in fields(AuditResult)}
    for forbidden in ("path", "fileid", "object", "object_ids", "user", "account"):
        assert forbidden not in names


def test_outcome_words_are_the_dry_run_words() -> None:
    """One spelling per outcome across both checks; the console relies on it."""
    assert ea.OUTCOME_PASSED is exchange_dryrun.OUTCOME_PASSED
    assert ea.OUTCOME_FAILED is exchange_dryrun.OUTCOME_FAILED
    assert ea.OUTCOME_SKIPPED is exchange_dryrun.OUTCOME_SKIPPED
    assert ea.OUTCOME_NOT_CHECKED is exchange_dryrun.OUTCOME_NOT_CHECKED
    assert ea.OUTCOME_NOTE == "note"
