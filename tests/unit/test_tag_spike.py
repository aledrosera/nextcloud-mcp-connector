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


@pytest.mark.parametrize("bad", ["7 or 1", "", "-1", "7<", "１"])
def test_report_body_refuses_anything_but_ascii_digits(bad: str) -> None:
    with pytest.raises(ValueError, match="digits"):
        spike.report_body(bad)


# --- summarize ----------------------------------------------------------------------------


def test_summarize_names_the_second_largest_value_honestly() -> None:
    values = [0.1] * 3 + [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 5.0]
    assert len(values) == 15
    stats = spike.summarize(values)
    assert stats["min"] == pytest.approx(0.1)
    assert stats["median"] == pytest.approx(0.5)
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
