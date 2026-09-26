"""Unit tests for the pure helpers of ``scripts/tag_spike.py`` (phase 25).

The script is not a package module, so it is loaded from its file path. Nothing here talks
to a network or to Docker: the measuring blocks are exercised against the live nc35
topology by the script itself, and only the helpers whose mistakes would silently falsify a
measurement are pinned down here (a 412 read as zero hits, a href dropped as foreign, a
secret written into a protocol).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from lxml import etree

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "tag_spike.py"

OC = "http://owncloud.org/ns"
DAV = "DAV:"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tag_spike", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tag_spike"] = module
    spec.loader.exec_module(module)
    return module


spike = _load()


# --- report_body --------------------------------------------------------------------------


def test_report_body_has_filter_files_root_props_and_one_systemtag_rule() -> None:
    root = etree.fromstring(spike.report_body("7"))
    assert root.tag == f"{{{OC}}}filter-files"
    prop = root.find(f"{{{DAV}}}prop")
    assert prop is not None
    assert [child.tag for child in prop] == [f"{{{OC}}}fileid", f"{{{DAV}}}resourcetype"]
    rules = root.findall(f"{{{OC}}}filter-rules/{{{OC}}}systemtag")
    assert [rule.text for rule in rules] == ["7"]


@pytest.mark.parametrize("bad", ["7 or 1", "", "-1", "7<", chr(0xFF11), chr(0xB2)])
def test_report_body_refuses_anything_but_ascii_digits(bad: str) -> None:
    with pytest.raises(ValueError, match="digits"):
        spike.report_body(bad)


# --- summarize ----------------------------------------------------------------------------


def test_summarize_names_the_second_largest_value_honestly() -> None:
    values = [0.1] * 3 + [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 5.0]
    assert len(values) == 15
    stats = spike.summarize(values)
    assert stats["min"] == pytest.approx(0.1)
    assert stats["median"] == pytest.approx(0.6)
    assert stats["p95_second_largest"] == pytest.approx(1.2)
    assert stats["max"] == pytest.approx(5.0)
    assert set(stats) == {"min", "median", "p95_second_largest", "max"}


@pytest.mark.parametrize("values", [[], [0.3]])
def test_summarize_refuses_fewer_than_two_values(values: list[float]) -> None:
    with pytest.raises(ValueError, match="two"):
        spike.summarize(values)


# --- home_path_of -------------------------------------------------------------------------


def test_home_path_of_strips_the_home_and_the_trailing_slash() -> None:
    home = "/remote.php/dav/files/alice"
    assert spike.home_path_of("/remote.php/dav/files/alice/p/tagged/", home) == "/p/tagged"
    assert spike.home_path_of("/remote.php/dav/files/alice/", home) == "/"


def test_home_path_of_refuses_a_longer_account_name() -> None:
    home = "/remote.php/dav/files/alice"
    assert spike.home_path_of("/remote.php/dav/files/alicexyz/a.txt", home) is None
    assert spike.home_path_of("/remote.php/dav/files/bob/a.txt", home) is None


def test_home_path_of_decodes_url_encoded_segments() -> None:
    home = "/remote.php/dav/files/alice"
    href = "http://127.0.0.1:8082/remote.php/dav/files/alice/Notes/spike25/spike25%20Notiz%20(2).md"
    assert spike.home_path_of(href, home) == "/Notes/spike25/spike25 Notiz (2).md"


# --- read_report / describe_error ---------------------------------------------------------

_MULTISTATUS = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
 <d:response>
  <d:href>/remote.php/dav/files/alice/p/tagged/</d:href>
  <d:propstat><d:prop><oc:fileid>41</oc:fileid>
   <d:resourcetype><d:collection/></d:resourcetype></d:prop>
   <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
 </d:response>
 <d:response>
  <d:href>/remote.php/dav/files/bob/elsewhere.txt</d:href>
  <d:propstat><d:prop><oc:fileid>42</oc:fileid><d:resourcetype/></d:prop>
   <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
 </d:response>
</d:multistatus>"""

_ERROR_412 = b"""<?xml version="1.0" encoding="utf-8"?>
<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">
  <s:exception>Sabre\\DAV\\Exception\\PreconditionFailed</s:exception>
  <s:message>Cannot filter by non-existing tag</s:message>
</d:error>"""


def test_read_report_keeps_every_entry_including_foreign_hrefs() -> None:
    entries = spike.read_report(_MULTISTATUS)
    assert entries == [
        ("/remote.php/dav/files/alice/p/tagged/", "41", True),
        ("/remote.php/dav/files/bob/elsewhere.txt", "42", False),
    ]


def test_read_report_of_an_empty_multistatus_is_empty() -> None:
    body = b'<d:multistatus xmlns:d="DAV:"/>'
    assert spike.read_report(body) == []


def test_describe_error_reads_the_sabre_message() -> None:
    assert spike.describe_error(_ERROR_412) == "Cannot filter by non-existing tag"


def test_describe_error_of_a_non_error_body_says_so() -> None:
    assert spike.describe_error(b"") == "(no body)"
    assert spike.describe_error(b"<html>nope") == "(not XML)"


# --- scan_for_secrets ---------------------------------------------------------------------


def test_scan_for_secrets_reports_every_hit_without_the_value() -> None:
    texts = {
        "raw/a.txt": "line one\nleak s3cr3t-value here\nAUTHORIZATION-APP-API: x\n",
        "raw/b.txt": "clean\ns3cr3t-value again\n",
    }
    findings = spike.scan_for_secrets(texts, {"APP_SECRET": "s3cr3t-value"})
    assert findings == [
        "raw/a.txt:2: APP_SECRET",
        "raw/a.txt:3: AUTHORIZATION-APP-API",
        "raw/b.txt:2: APP_SECRET",
    ]
    assert all("s3cr3t-value" not in finding for finding in findings)


def test_scan_for_secrets_ignores_empty_secret_values() -> None:
    texts = {"raw/a.txt": "nothing to see\n"}
    assert spike.scan_for_secrets(texts, {"AA": "", "BB": "   "}) == []


# --- the findings block -------------------------------------------------------------------


def test_findings_runs_exactly_the_eight_sub_blocks_in_plan_order() -> None:
    assert spike.FINDINGS_BLOCKS == (
        "notes",
        "impersonation",
        "412",
        "unsichtbar",
        "varianten",
        "zielpfad",
        "freigabe",
        "app-aus-35",
    )


def test_parse_tag_id_reads_the_json_of_occ_tag_add() -> None:
    assert spike.parse_tag_id('{"id":17,"name":"kein-ki-spike25","access":"public"}') == "17"
    with pytest.raises(spike.RunFailed):
        spike.parse_tag_id("Tag already exists")


def test_compare_baseline_names_every_field_and_the_verdict() -> None:
    before = {"tags": "[]", "dateien": "275"}
    after = {"tags": "[]", "dateien": "276"}
    assert spike.compare_baseline(before, after) == [
        "BASELINE tags vorher=[] nachher=[] gleich=ja",
        "BASELINE dateien vorher=275 nachher=276 gleich=nein",
    ]


# --- the latency block (plan 25-02) -------------------------------------------------------


def test_threshold_line_near_the_threshold_adds_the_postgres_note() -> None:
    lines = spike.threshold_line(0.8)
    assert lines[0] == "SCHWELLE D-25-04 median_warm_5000=0.800 s schwelle=1.0 s ergebnis=unter"
    assert any("nahe Schwelle" in line for line in lines)


def test_threshold_line_above_the_threshold_says_ueber() -> None:
    lines = spike.threshold_line(1.2)
    assert "ergebnis=ueber" in lines[0]
    assert not any("nahe Schwelle" in line for line in lines)


def test_threshold_line_far_below_says_unter_without_a_note() -> None:
    assert spike.threshold_line(0.3) == [
        "SCHWELLE D-25-04 median_warm_5000=0.300 s schwelle=1.0 s ergebnis=unter"
    ]


def test_threshold_line_names_the_ballast_variant_and_counts_exactly_one_as_unter() -> None:
    lines = spike.threshold_line(1.0, "mit Ballast")
    assert lines[0].startswith("SCHWELLE D-25-04 (mit Ballast) median_warm_5000=1.000 s")
    assert "ergebnis=unter" in lines[0]
    assert len(lines) == 2


def test_span_collapses_equal_values_and_shows_a_range_otherwise() -> None:
    assert spike.span([]) == "-"
    assert spike.span([5000, 5000]) == "5000"
    assert spike.span([3, 1, 2]) == "1..3"


def test_format_series_writes_the_stage_line_in_milliseconds() -> None:
    seconds = [0.010 * (i + 1) for i in range(15)]
    line = spike.format_series("STUFE 100", [207] * 15, [100] * 15, [12345] * 15, seconds)
    assert line == (
        "STUFE 100 status=207 treffer=100 bytes=12345 min=10 median=80 "
        "p95_zweitgroesster=140 max=150 (ms, n=15)"
    )


def test_format_series_shows_a_status_change_inside_the_series() -> None:
    line = spike.format_series("REFERENZ e", [200, 503, 200], [], [10, 10, 20], [0.1, 0.2, 0.3])
    assert "status=200/503" in line
    assert "treffer=-" in line
    assert "bytes=10..20" in line


def test_prepare_context_medians_reads_short_and_full() -> None:
    text = (
        "  wall clock detail='short': min 0.60 s, median 0.72 s, max 3.40 s (3 runs)\n"
        "  wall clock detail='full': min 0.77 s, median 0.81 s, max 1.66 s (3 runs)\n"
        "  leg search: median 0.72 s, max 0.88 s over 3 runs\n"
    )
    assert spike.prepare_context_medians(text) == {"short": 0.72, "full": 0.81}
