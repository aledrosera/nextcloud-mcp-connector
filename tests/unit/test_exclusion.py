"""The exclusion guard core: three states, the segment rule, the name-to-id cache, one flight."""

import json
from collections.abc import Iterator

import pytest

from mcp_connector.nextcloud import exclusion
from mcp_connector.nextcloud.clients import dav, systemtags


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    exclusion.clear_cache()
    yield
    exclusion.clear_cache()


# --- ancestors and the segment rule ------------------------------------------------------


def test_ancestors_lists_the_path_and_every_parent_up_to_the_root() -> None:
    assert exclusion.ancestors("/A/kein/x") == ("/A/kein/x", "/A/kein", "/A", "/")
    assert exclusion.ancestors("/A") == ("/A", "/")
    assert exclusion.ancestors("/") == ("/",)


@pytest.mark.parametrize("path", ["/A/kein", "/A/kein/x", "/A/keine", "/A", "/", "/A/kein/x/y.md"])
@pytest.mark.parametrize("tagged", [{"/A/kein"}, {"/"}, {"/A/keine"}])
def test_ancestors_draws_the_same_boundary_as_the_segment_rule(path: str, tagged: set[str]) -> None:
    by_ancestors = any(a in tagged for a in exclusion.ancestors(path))
    by_within = any(dav.within(path, t) for t in tagged)

    assert by_ancestors == by_within


# --- TagScope ----------------------------------------------------------------------------


def test_an_active_scope_covers_the_tagged_folder_and_below_but_not_a_sibling() -> None:
    scope = exclusion.TagScope("active", paths=frozenset({"/A/kein"}))

    assert scope.excludes(path="/A/kein/x") is True
    assert scope.excludes(path="/A/kein") is True
    assert scope.excludes(path="/A/keine") is False
    assert scope.excludes(path="/A") is False


def test_an_active_scope_matches_file_ids() -> None:
    scope = exclusion.TagScope("active", fileids=frozenset({"957"}))

    assert scope.excludes(fileid="957") is True
    assert scope.excludes(fileid="958") is False
    assert scope.excludes() is False


def test_an_untagged_scope_excludes_nothing_and_leaves_no_trace() -> None:
    scope = exclusion.UNTAGGED
    entries = [
        {"path": "/A/kein", "fileid": "955", "type": "folder"},
        {"path": "/A/doc.md", "fileid": "957", "type": "file", "size": 12},
        {"path": "/", "fileid": "1", "type": "folder"},
    ]

    kept = [e for e in entries if not scope.excludes(path=e["path"], fileid=e["fileid"])]

    assert scope.state == "untagged"
    assert scope.excludes() is False
    assert scope.excludes(path="/A/kein", fileid="955") is False
    assert kept == entries
    assert json.dumps(kept) == json.dumps(entries)


def test_an_unverifiable_scope_refuses_to_answer() -> None:
    scope = exclusion.TagScope("unverifiable", reason="status")

    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes(path="/A")
    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes(fileid="1")
    with pytest.raises(ValueError, match="unverifiable"):
        scope.excludes()


def test_a_scope_is_immutable() -> None:
    with pytest.raises(AttributeError):
        exclusion.UNTAGGED.state = "active"  # type: ignore[misc]


# --- names and ids -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (" kein-ki", True),
        ("KEIN-KI", True),
        ("Kein-KI", True),
        ("kein-ki", True),
        ("kein-ki-alt", False),
        ("keinki", False),
        ("", False),
    ],
)
def test_is_exclude_name_ignores_case_and_surrounding_blanks(name: str, expected: bool) -> None:
    assert exclusion.is_exclude_name(name) is expected


def test_the_tag_name_is_fixed() -> None:
    assert exclusion.EXCLUDE_TAG == "kein-ki"


def test_exclude_tag_ids_keeps_the_lowest_id_per_exact_spelling() -> None:
    tags = [
        systemtags.Tag(id="65", name="kein-ki"),
        systemtags.Tag(id="64", name="kein-ki"),
        systemtags.Tag(id="70", name="projekt"),
        systemtags.Tag(id="67", name="Kein-KI"),
    ]

    assert exclusion.exclude_tag_ids(tags) == ("64", "67")


def test_exclude_tag_ids_sorts_numerically_and_is_empty_without_a_match() -> None:
    tags = [systemtags.Tag(id="100", name="KEIN-KI"), systemtags.Tag(id="9", name="kein-ki")]

    assert exclusion.exclude_tag_ids(tags) == ("9", "100")
    assert exclusion.exclude_tag_ids([systemtags.Tag(id="1", name="projekt")]) == ()


# --- the name-to-id cache ----------------------------------------------------------------


def test_the_cache_stores_positive_results_only() -> None:
    key = ("http://nc.test", "alice")

    exclusion._store_ids(key, ())
    assert exclusion._tag_ids == {}
    assert exclusion._cached_ids(key) is None

    exclusion._store_ids(key, ("64",))
    assert exclusion._cached_ids(key) == ("64",)

    exclusion._drop_ids(key)
    assert exclusion._cached_ids(key) is None
    exclusion._drop_ids(key)  # dropping twice is harmless


def test_a_cache_entry_expires_after_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    key = ("http://nc.test", "alice")
    exclusion._tag_ids[key] = (100.0, ("64",))

    monkeypatch.setattr(exclusion.time, "monotonic", lambda: 100.0 + exclusion.TTL_SECONDS - 1)
    assert exclusion._cached_ids(key) == ("64",)

    monkeypatch.setattr(exclusion.time, "monotonic", lambda: 100.0 + exclusion.TTL_SECONDS)
    assert exclusion._cached_ids(key) is None


def test_clear_cache_drops_every_entry() -> None:
    exclusion._tag_ids[("http://nc.test", "alice")] = (0.0, ("64",))
    exclusion._tag_ids[("http://nc.test", "admin")] = (0.0, ("63",))

    exclusion.clear_cache()

    assert exclusion._tag_ids == {}
