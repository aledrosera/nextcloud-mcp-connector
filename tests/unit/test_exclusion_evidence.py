"""Unit tests for the state handling of ``scripts/exclusion_evidence.py`` (plan 29-01).

The script is not a package module, so it is loaded from its file path. Nothing here talks
to Docker or a network: ``occ`` and ``run`` are replaced, and only what would change the state
of a maintained instance or put a password into a process list is pinned down
(29-REVIEW IN-07 and IN-08).
"""

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "exclusion_evidence.py"

PASSWORD = "Pw-geheim-7f3a"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("exclusion_evidence", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["exclusion_evidence"] = module
    spec.loader.exec_module(module)
    return module


evidence = _load()


def settings(tmp_path: Path) -> object:
    return evidence.Settings(
        nc="nc",
        exapp="exapp",
        base="http://127.0.0.1:8082",
        admin="admin",
        admin_password=PASSWORD,
        user="alice",
        user_password="a",
        user2="bob",
        user2_password="b",
        raw=tmp_path / "raw.txt",
    )


def fake_instance(
    monkeypatch: pytest.MonkeyPatch, *, config_set: bool, user2_enabled: bool
) -> list[tuple[str, ...]]:
    """An instance without the run's tags and groups; config key and account as given."""
    calls: list[tuple[str, ...]] = []

    def occ(_cfg: object, *argv: str, log: bool = True) -> tuple[int, str]:
        del log
        calls.append(argv)
        if argv[0] == "config:app:get":
            return (0, "true") if config_set else (1, "")
        if argv[0] == "user:info":
            return 0, f"  - enabled: {'true' if user2_enabled else 'false'}"
        if argv[0] == "group:list":
            return 0, "{}"
        return 0, ""

    monkeypatch.setattr(evidence, "occ", occ)
    monkeypatch.setattr(evidence, "tag_list", lambda _cfg: {})
    return calls


# --- IN-07: the run never changes a state it cannot restore --------------------------------


def test_a_clean_instance_passes_the_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_instance(monkeypatch, config_set=False, user2_enabled=True)

    assert evidence.preflight(settings(tmp_path)) == []


def test_a_set_config_key_stops_the_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The cleanup deletes the key; one that existed before would be lost."""
    calls = fake_instance(monkeypatch, config_set=True, user2_enabled=True)

    clash = evidence.preflight(settings(tmp_path))

    assert clash == ["config systemtags restrict_creation_to_admin"]
    assert ("config:app:get", *evidence.CONFIG_KEY) in calls


def test_a_disabled_second_account_stops_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M1c enables the account at its end; one disabled before would come back enabled."""
    fake_instance(monkeypatch, config_set=False, user2_enabled=False)

    assert evidence.preflight(settings(tmp_path)) == ["konto bob nicht aktiv"]


# --- IN-08: the admin password never stands in an argv ------------------------------------


def test_curl_gets_the_password_over_stdin_and_never_in_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[tuple[list[str], str | None]] = []

    def run(argv: Sequence[str], *, stdin: str | None = None) -> tuple[int, str]:
        seen.append((list(argv), stdin))
        return 0, "<ok/>\n207"

    monkeypatch.setattr(evidence, "run", run)
    monkeypatch.setattr(evidence, "_RAW", [tmp_path / "raw.txt"])

    answer = evidence.curl(
        settings(tmp_path),
        "curl -u admin:<passwort> -X PROPPATCH ...",
        ["-X", "PROPPATCH", "http://127.0.0.1:8082/remote.php/dav/systemtags/7"],
        user="admin",
        password=PASSWORD,
    )

    assert answer.status == 207
    ((argv, stdin),) = seen
    assert all(PASSWORD not in arg for arg in argv)
    assert "-u" not in argv
    assert argv[argv.index("--config") + 1] == "-"
    assert stdin == f'user = "admin:{PASSWORD}"\n'
    assert PASSWORD not in (tmp_path / "raw.txt").read_text(encoding="utf-8")


def test_the_curl_config_escapes_quote_and_backslash() -> None:
    assert evidence.curl_credentials("admin", 'a"b\\c') == 'user = "admin:a\\"b\\\\c"\n'
