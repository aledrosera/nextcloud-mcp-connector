# Phase 25: Mess-Spike Tag-Abfrage - Pattern Map

**Mapped:** 2026-09-26
**Files analyzed:** 7 (neu/geändert) plus 1 unverändert genutzte Messdatei
**Analogs found:** 6 / 7

## File Classification

| Neue/geänderte Datei | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `compose.spike-tags.yml` | config | request-response (Wegwerf-Instanz) | `compose.test.yml` | exact |
| `scripts/tag_spike.py` | utility (Messskript) | batch + request-response | `scripts/exchange_evidence.py` | exact |
| `scripts/tag_spike.py`, Teil Instanz-Bootstrap 32-34 (wait_for_install, alice, App-Passwort) | utility | batch (occ) | `scripts/bootstrap_test_nc.sh` | role-match (Bash, nach Python portieren) |
| `scripts/tag_spike.py`, Teil REPORT/PROPFIND/Notes unter Basic + AppAPI | utility | request-response | `tests/integration/test_exapp_dav_matrix.py`, `src/mcp_connector/nextcloud/clients/dav.py`, `clients/notes.py` | exact (Aufrufform) |
| `scripts/tag_spike.py`, Teil Wanduhr + Protokoll + Secret-Prüfung | utility | transform | `tests/integration/test_ctx_bundle.py` | exact |
| PHP-Einmal-Snippets (`setObjectIdsForTag`, Varianten-Insert, Mapping-Zähler) | utility | batch (DB) | keins (nur stdin-Transport aus `exchange_evidence.py`) | no analog |
| `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` (+ `raw/`) | doc (Messbericht) | file-I/O | `docs/exchange-evidence.md` | exact (Format), Ablage intern (D-25-06) |
| Checkpoint-Task im letzten Plan | plan task | event (Owner-Entscheid) | `.planning/milestones/v1.6-phases/24-audit-anschluss-und-nachweis/24-09-PLAN.md` Task 1 | exact |
| `tests/integration/test_ctx_bundle.py` | test | request-response | wird **unverändert** genutzt (`-s -k wall_clock`, `NC_MCP_E2E_*`-Exports, siehe RESEARCH Pattern 4) | n/a |

Bedingt: `vulture_whitelist.py` nur anfassen, falls vulture im neuen Skript etwas meldet (alle Funktionen werden aus `main()` gerufen, also voraussichtlich nicht nötig; jede Zeile dort braucht eine Begründung, Kopf der Datei Zeilen 1-12).

---

## Pattern Assignments

### `compose.spike-tags.yml` (config, Wegwerf-Instanz)

**Analog:** `compose.test.yml` (39 Zeilen, komplett übernehmen)

**Kopfkommentar-Muster** (Zeilen 1-13): Nutzungszeilen `up -d --wait` / `down -v`, Begründung SQLite, Hinweis "Wegwerf-Credentials, nur Loopback". Für die Spike-Datei ergänzen: "`down -v` ist Pflicht zwischen Versionen (sonst Upgrade-Lauf 32 nach 33, RESEARCH Pitfall 3)" und "offizielles Image statt nextcloud-docker-dev, weil docker-dev einen Branch klont und keinen Release misst".

**Kern** (Zeilen 14-39):
```yaml
services:
  nextcloud:
    image: nextcloud:34-apache
    container_name: nc-mcp-test
    ports:
      # Loopback only (WR-06): with the default admin password and the bruteforce guard
      # disabled at bootstrap, a 0.0.0.0 binding would expose a trivially ownable
      # instance to the developer's or runner's LAN.
      - "127.0.0.1:${NC_TEST_PORT:-8080}:80"
    environment:
      SQLITE_DATABASE: nextcloud
      NEXTCLOUD_ADMIN_USER: "${NC_TEST_ADMIN_USER:-admin}"
      NEXTCLOUD_ADMIN_PASSWORD: "${NC_TEST_ADMIN_PASSWORD:-admin-test-pw}"
      NEXTCLOUD_TRUSTED_DOMAINS: "localhost 127.0.0.1"
    healthcheck:
      # status.php answers as soon as the web server is up. That is not the same as
      # "installed", so the bootstrap script polls `occ status` before it does any work.
      test: ["CMD", "php", "-r", "exit(file_get_contents('http://localhost/status.php') ? 0 : 1);"]
      interval: 5s
      timeout: 5s
      retries: 40
    volumes:
      - nextcloud-test-data:/var/www/html
volumes:
  nextcloud-test-data:
```
**Abweichungen (aus RESEARCH Pattern 1):** `name: nc-mcp-spike-tags` (eigener Projektname wie `compose.nc35.yml` Zeile 40 `name: nc-mcp-nc35`), `image: "nextcloud:${NC_SPIKE_TAG:?set NC_SPIKE_TAG, e.g. 32.0.15-apache}"` (Pflichtvariable, kein Default), `container_name: nc-spike-tags`, Port fest `127.0.0.1:8083:80`, Volume `nc-spike-tags-data`. Kommentar-Stil "numbered differences" wie `compose.nc35.yml` Zeilen 9-35.

---

### `scripts/tag_spike.py` (utility, batch + request-response)

**Analog:** `scripts/exchange_evidence.py` (782 Zeilen)

**Modul-Docstring-Muster** (Zeilen 1-33): Frage der Messung, Aufrufzeile (`uv run --no-sync python scripts/... --env-file .env.nc35`), "What this run does not put on disk". Übernehmen, Inhalt: Messliste Phase 25, Rückbau-Garantie, keine Secrets im Protokoll.

**Imports + Konstanten** (Zeilen 35-68, 101): stdlib zuerst, dann Fremdpakete, dann Projekt; Container als Modulkonstanten.
```python
import argparse
import asyncio
...
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: The containers of the Nextcloud 35 topology this run measures against.
NC_CONTAINER = "nc35-nc"
EXAPP_CONTAINER = "nc_app_mcp_connector"
...
BASE_URL = "http://127.0.0.1:8082"
```
Abweichung: für REPORT/PROPFIND **`httpx`** (nicht `httpx2`) importieren, weil `Credentials.auth()` ein `httpx.Auth` liefert (`credentials.py` Zeile 13, 43-55). Zusätzlich `from statistics import median`, `from lxml import etree`, `from mcp_connector.nextcloud.clients import xml`, `from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials`. Spike-Konstanten: `SPIKE_CONTAINER = "nc-spike-tags"`, `SPIKE_BASE_URL = "http://127.0.0.1:8083"`, Tag-Präfix `kein-ki-spike25` (Anti-Pattern "nie exakt `kein-ki`").

**Fehlerklasse + Zeitstempel + Abschnitte** (Zeilen 114-125):
```python
class RunFailed(RuntimeError):
    """A step did not answer the way a measuring run needs it to."""

def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def section(title: str) -> None:
    print(f"\n== {title} ==")
```

**Subprocess/docker/occ-Kern** (Zeilen 128-152), wörtlich übernehmen, `occ` um Container-Parameter erweitern (nc35 vs. nc-spike-tags):
```python
def run(argv: Sequence[str], *, stdin: str | None = None, check: bool = True) -> str:
    """One external command, no shell, fixed argument list, output as text."""
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv), input=stdin, capture_output=True, text=True, check=False,
    )
    if check and finished.returncode != 0:
        raise RunFailed(
            f"{' '.join(argv[:4])} exited {finished.returncode}: "
            f"{(finished.stderr or finished.stdout).strip()[:400]}"
        )
    return (finished.stdout or "") + (finished.stderr or "")

def docker(*argv: str, stdin: str | None = None, check: bool = True) -> str:
    return run(["docker", *argv], stdin=stdin, check=check)

def occ(*argv: str, check: bool = True) -> str:
    return docker("exec", "-u", "www-data", NC_CONTAINER, "php", "occ", *argv, check=check).strip()
```
Löst nebenbei RESEARCH Pitfall 1 (MSYS-Pfadumbiegung): `subprocess` ruft `docker` direkt. CR aus Ausgaben strippen (`.replace("\r", "")`).

**Env-Datei lesen, nie drucken** (Zeilen 155-166): `read_env_file(path)` wörtlich übernehmen; liefert `APP_ID`, `APP_SECRET`, `APP_VERSION`, `NC_MCP_URL`, `NC_MCP_TEST_USER`, `NC_MCP_TEST_APP_PASSWORD` aus `.env.nc35`.

**Payload/Skript über stdin statt argv** (Zeilen 223-248, Muster `register`): Snippet als `sh -c` mit Positionsargumenten, Nutzdaten auf stdin. Genau diese Form für die PHP-Snippets verwenden:
```python
output = docker(
    "exec", "-i", "-u", "www-data", NC_CONTAINER,
    "sh", "-c", snippet, "sh", APP_ID, DAEMON_NAME,
    stdin=json.dumps(payload, separators=(",", ":")),
)
```
Für PHP: `docker("exec", "-i", "-u", "www-data", "-w", "/var/www/html", container, "php", "--", tag_id, str(count), sub, stdin=PHP_SET_TAG_OBJECTS)`.

**Blöcke, die nicht abbrechen** (Zeilen 654-659):
```python
async def guarded(work: Coroutine[Any, Any, None]) -> None:
    """One block, and its failure reported as a measured outcome instead of as an abort."""
    try:
        await work
    except Exception as failure:
        print(f"BLOCK FAILED | {type(failure).__name__}: {str(failure)[:200]}")
```
Begründung übernehmen (Zeilen 626-630): ein Lauf, der an der ersten Überraschung stoppt, hinterlässt die Topologie verändert.

**Serverseitiger Impersonations-Beleg** (Zeilen 569-583): `impersonation_lines(needles)` wörtlich übernehmen (`tail -n 400 /var/www/html/data/exapp_impersonation.log`, Filter auf Marker); für REPORT nach `"method":"REPORT"` und `"user":"alice"` filtern.

**Access-Log mit Statuscode** (Zeilen 557-566): `access_lines(since, needles)` übernehmen, `since = now_stamp()` vor dem Block.

**Topologie-Kopf** (Zeilen 603-618): `topology()` übernehmen, ergänzen um `occ status`, `occ config:system:get dbtype`, `docker stats --no-stream` (RESEARCH Pattern 4 Messbedingungen).

**main + try/finally-Rückbau** (Zeilen 687-778): argparse mit `--env-file`, danach alles Zustandsändernde in `try`, Rückbau im `finally`. Kommentar Zeilen 735-741 erklärt, warum **alles** zwischen Aufbau und Rückbau im `try` stehen muss (WR-24-06). Für Phase 25 im `finally`: `app:enable systemtags` (Pitfall 6), Tags `kein-ki-spike25*`/`spike25-fill-*` löschen, Share löschen, `files:delete --force --skip-trash alice/files/spike25`, Notizen per API löschen, Baseline-Vergleich als letzte Zeile. Für die Matrix: `docker compose -f compose.spike-tags.yml down -v` im `finally` je Version. Unterbefehle (`--block nc35|latency|matrix`) sind Ermessen; `--keep-armed`-Äquivalent (`--keep-data`) nur als bewusste Ausnahme.

---

### `scripts/tag_spike.py`, Teil Instanz-Bootstrap 32-34

**Analog:** `scripts/bootstrap_test_nc.sh`

**wait_for_install** (Zeilen 65-78), nach Python portieren (60 x 5 s, `occ status` enthält `installed: true`):
```bash
wait_for_install() {
  local attempt
  for attempt in $(seq 1 60); do
    if occ status 2>/dev/null | grep "installed: true" >/dev/null; then
      echo "nextcloud: installed"; return 0
    fi
    echo "waiting for the Nextcloud installation to finish (${attempt}/60)"
    sleep 5
  done
  ...
}
```
Hinweis: Foreground-`sleep` ist im Skript unkritisch (`time.sleep` in Python).

**Passwort nur über stdin** (Zeilen 44-58, `occ_stdin` + `occ_pw`):
```bash
occ_pw() {
  local password="$1"; shift
  printf '%s' "$password" |
    occ_stdin 'OC_PASS="$(cat)"; export OC_PASS; exec php occ "$@"' "$@"
}
```
Python-Form: `docker("exec", "-i", "-u", "www-data", SPIKE_CONTAINER, "sh", "-c", 'OC_PASS="$(cat)"; export OC_PASS; exec php occ "$@"', "sh", "user:add", "--password-from-env", "alice", stdin=password)`. Passwort mindestens 10 Zeichen (Kommentar Zeilen 22-23).

**App-Passwort parsen** (Zeilen 217-230): letzte nicht-leere Zeile, CR strippen, Länge >= 20 prüfen. `--name spike25` statt `mcp-test`.

**Bruteforce aus** (Zeilen 278-283): `occ config:system:set auth.bruteforce.protection.enabled --value=false --type=boolean`, nur auf der Wegwerf-Instanz.

---

### `scripts/tag_spike.py`, Teil REPORT/PROPFIND/Notes (Basic + AppAPI)

**Analog 1:** `tests/integration/test_exapp_dav_matrix.py`

**AppAPI-Credentials** (Zeilen 61-79):
```python
return NcClients(
    client=httpx.AsyncClient(follow_redirects=False, timeout=30.0),
    creds=Credentials(
        base_url=normalize_base_url(exapp_env["base_url"]),
        user=user,
        secret=exapp_env["app_secret"],
        mode=MODE_APPAPI,
        app_id=exapp_env["app_id"],
        app_version=exapp_env["app_version"],
        aa_version=exapp_env["aa_version"],
    ),
)
```
Im Skript ohne `NcClients`: nur `Credentials(...)` plus eigener `httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(60.0))`. `aa_version` aus `env.get("AA_VERSION", "")` (fehlt in `.env.nc35`, RESEARCH Pattern 2).

**Kontrolle a: Identität** (Zeilen 96-101): `ocs.ocs_get(client, creds, "/cloud/user")` + `ocs.parse_ocs(...)`, `data["id"] == "alice"`. Als **allererster** Schritt (Pitfall 11: veraltetes `APP_SECRET`).

**Kontrolle b: falsches Secret** (Zeilen 131-143): `{**env, "app_secret": "0" * 64}` muss `!= 200` liefern.

**Kontrolle c:** Log-Zeile, siehe `impersonation_lines` oben.

**Analog 2:** `src/mcp_connector/nextcloud/clients/dav.py`

**Body per lxml** (Zeilen 131-140), Vorlage für `report_body(tag_id)` aus RESEARCH Pattern 2:
```python
def _stat_body() -> bytes:
    """Build the PROPFIND body with lxml; never with an f-string (threat T-01-11)."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in _STAT_PROPS:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```

**Aufrufform** (Zeilen 146-153):
```python
response = await client.request(
    "PROPFIND",
    files_url(creds, target),
    headers={"Depth": "0", "Content-Type": "application/xml"},
    content=_stat_body(),
    auth=creds.auth(),
)
```
Für REPORT: Methode `"REPORT"`, **eigene** `home_url(creds, sub)` statt `files_url` (Zeilen 125-128 biegen über `safe_path` auf `NC_MCP_FILES_ROOT` um; Anti-Pattern in RESEARCH). Kein `_check(...)`: Status und `s:message` roh protokollieren (Pitfall 8, 412 nie als "0 Treffer").

**Href-Normalisierung** (Zeilen 493-502), als Muster für den eigenen Leser (nicht `parse_entries` benutzen, das verwirft Einträge außerhalb der Sandbox, Zeilen 466-480):
```python
def _home_path_of(href: str, home: str) -> str | None:
    raw = unquote(urlsplit(href).path)
    if not raw.startswith(home):
        return None
    rest = raw[len(home) :]
    if rest and not rest.startswith("/"):
        # "alicexyz" starts with "alice" but is a different account.
        return None
    return rest.rstrip("/") or "/"
```
Für die Freigabe-Grenze (REPORT als bob) `home` mit bob bilden und nicht-passende hrefs **protokollieren statt verwerfen**.

**Multistatus lesen:** `xml.parse_multistatus(body)` (`clients/xml.py` Zeilen 65-94) für `oc:fileid`/`d:resourcetype`; für `nc:system-tags` `xml.parse_root(body)` (Zeilen 40-62), weil `_value_of` (Zeilen 104-109) bei strukturierten Props nur Kind-Tagnamen liefert. 412-Antworten sind `d:error`, nicht Multistatus: `parse_multistatus` wirft dort `ToolError`, also vorher auf Status prüfen.

**Analog 3:** `src/mcp_connector/nextcloud/clients/notes.py`

**Notes anlegen/lesen direkt wiederverwenden** (Zeilen 70-100):
```python
async def create_note(client, creds, *, title: str, content: str, category: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, "content": content}
    if category:
        body["category"] = category
    response = await client.post(
        api_url(creds, "/notes"), json=body,
        headers={**_HEADERS, "Content-Type": "application/json"}, auth=creds.auth(),
    )
    return _as_note(ocs.parse_app_json(response, what="the new note"))
```
`get_note(client, creds, note_id)` für Schritt 4 aus RESEARCH Pattern 5. `settings` und `DELETE /notes/{id}` gibt es im Client nicht: roh mit `api_url(creds, "/settings")` bzw. `api_url(creds, f"/notes/{id}")` und `headers=_HEADERS`-Form nachbauen. fileid unabhängig per eigenem PROPFIND ermitteln (Pitfall 9: zwei unabhängige Wege).

---

### `scripts/tag_spike.py`, Teil Wanduhr, Protokoll, Secret-Prüfung

**Analog:** `tests/integration/test_ctx_bundle.py`

**Messschleife** (Zeilen 312-338):
```python
for _ in range(RUNS):
    started = time.perf_counter()
    bundle = await context_tools.prepare_context(alice, query=MEASUREMENT_QUERY, detail=detail)
    timings.append(time.perf_counter() - started)
...
rows[detail] = {"min": min(timings), "median": float(median(timings)), "max": max(timings)}
```
Für Phase 25: 3 Aufwärmläufe verwerfen, `N = 15` warm, `N = 3` kalt (nach `apachectl -k graceful` + 5 s); zusätzlich p95 (zweitgrößter Wert, ehrlich benennen), Bytes, Trefferzahl, Status (RESEARCH Pattern 4).

**Protokoll-Memo** (Zeilen 126-134) und Zeilenform (Zeilen 345-349):
```python
_protocol: list[str] = []

def note(line: str) -> None:
    _protocol.append(line)
```
Zeilenformat nach RESEARCH "Code Examples": `f"{now_stamp()} | {block} | {command} | HTTP {status}{timing} | {raw[:300]}"`.

**Referenzkonstanten als Code, nicht Prosa** (Zeilen 95-99): `REFERENCE_SHORT = 0.84` usw.; analog `THRESHOLD_SECONDS = 1.0` (D-25-04) als Konstante, Vergleich gegen Median warm bei 5000.

**Secret-Gate über das Protokoll** (Zeilen 752-764), als Abschlussprüfung im Skript übernehmen, bevor `raw/` geschrieben wird:
```python
blob = "\n".join(_protocol)
assert secret not in blob, "the measurement protocol carries the app secret"
assert "AUTHORIZATION-APP-API" not in blob, "the protocol carries an auth header name"
assert os.environ.get("NC_MCP_TEST_APP_PASSWORD", "\0") not in blob
```
Im Skript als `raise RunFailed(...)` statt `assert` (ruff `S101`).

**Endzustand lesen statt annehmen** (Zeilen 767-787): letzte Protokollzeilen = Baseline-Vergleich (Tag-Liste, Dateizahl alice, Papierkorb, Mapping-Zeilen) plus Topologie.

---

### PHP-Einmal-Snippets (no analog)

Kein PHP im Repo. Inhalt aus RESEARCH Pattern 3 (`setObjectIdsForTag`) und Pattern 6 (Varianten-Insert) übernehmen. Transport nach `exchange_evidence.py` `register` (stdin, Argumente hinter `--`, Zeilen 223-248). Empfehlung: als Modulkonstanten-Strings in `scripts/tag_spike.py` (dann unter ruff/pyright, keine lose `.php`-Datei im Repo). Erster Lauf als Smoke-Test mit 1 Datei (Annahme A2); Rückfall DAV-`PUT systemtags-relations/files/{fileid}/{tagid}`.

---

### `25-MESSBERICHT.md` (+ `raw/`) (doc, intern)

**Analog:** `docs/exchange-evidence.md`

**Kopfblock** (Zeilen 1-12):
```markdown
# Token Exchange Two Account Evidence (EXCH-07, AUDIT-07)

**Status:** done, with one refuted expectation (measurement 4)
**Measured:** 2026-09-24
**Nextcloud version:** 35.0.0 (build 35.0.0.10)
**AppAPI version:** 35.0.0
**Deploy daemon:** HaRP, over the `compose.nc35.yml` topology (Caddy on `127.0.0.1:8082`)
**App version:** `mcp_connector` 0.2.1, deployed from the loopback registry
**Scope:** ...
```
Für Phase 25 auf Deutsch (Projektkommunikation, echte Umlaute, keine Em-Dashes): Status, Gemessen, NC-Versionen (32.0.15/33.0.9/34.0.4/35.0.0, Version of record = `occ status`), DB (`sqlite3`), Topologie, Umfang.

**Aufbau je Abschnitt** (Zeilen 21-23, 41-53, 67-77): "Alles unten ist Rohausgabe von `scripts/...`", dann Codeblock mit `== section ==`-Kopf aus dem Skript, dann Deutung. Abweichungen vom Rohformat ausdrücklich benennen (Zeilen 25-33).

**Zusätzlich (D-25-06, CONTEXT "Messbericht-Stil"):** Befundtabelle `Befund | Kommando | Rohwert | Deutung`, eine Zeile je Einzelbefund aus RESEARCH Pattern 6; Satz zur Image-Wahl (offizielles Image statt docker-dev); Grenzen (SQLite-Kollation, A3; Nebenbefund 35.0.1-amd64). Ablage nur in `.planning/phases/25-mess-spike-tag-abfrage/`, nichts nach `docs/`.

---

### Checkpoint-Task (Owner-Entscheid, D-25-05)

**Analog:** `.planning/milestones/v1.6-phases/24-audit-anschluss-und-nachweis/24-09-PLAN.md` Task 1 (Zeilen 103-144)

```xml
<task type="checkpoint:decision" gate="blocking">
  <name>Task 1: ...</name>
  <files>-</files>
  <read_first> ... </read_first>
  <decision>...</decision>
  <context>...</context>
  <options>
    <option id="..."><name>...</name><pros>...</pros><cons>...</cons></option>
  </options>
  <action>Lege dem Entwickler die Optionen vor und halte die Antwort fest. Trage die gewählte Form danach im SUMMARY dieses Plans als Entscheidung mit Datum ein ...</action>
  <verify><automated>grep -c "..." .../XX-SUMMARY.md</automated></verify>
```
Für Phase 25 drei Entscheide in einem Checkpoint: Notes-Befund (EXCL-05 bauen oder dokumentiert vertagen), App-aus (Fail-closed-Auslöser), Latenz gegen 1 s (Batch-Design bestätigt oder Cache/engerer Zielpfad). Kurzformat: Befundliste mit Empfehlung, Antwort in einem Satz.

---

## Shared Patterns

### Secrets nie in argv, nie im Protokoll
**Source:** `scripts/bootstrap_test_nc.sh` Zeilen 37-58, `scripts/exchange_evidence.py` Zeilen 223-248, `credentials.py` Zeilen 57-61 (maskiertes `repr`), `test_ctx_bundle.py` Zeilen 752-764
**Apply to:** alle occ-Aufrufe mit Passwort, PHP-Snippets, Protokollfunktion, Messbericht (vor Commit grep auf `APP_SECRET`-Wert)

### Blockweise messen, Fehler als Messergebnis
**Source:** `scripts/exchange_evidence.py` Zeilen 621-659 (`measure` + `guarded`)
**Apply to:** jeder Messblock in `tag_spike.py`

### Rückbau im finally
**Source:** `scripts/exchange_evidence.py` Zeilen 735-778
**Apply to:** `app:disable systemtags`-Block, Datenaufbau nc35, jede Matrix-Version (`down -v`)

### Nicht-Admin als Messidentität, Kontrollen zuerst
**Source:** `tests/integration/test_exapp_dav_matrix.py` Zeilen 104-143 (Kontrollen), 152-159 (`cloud/user`)
**Apply to:** alle Tag-Messungen (alice), admin nur als benannter Gegenfall

### XML nur per lxml und gehärtetem Parser
**Source:** `dav.py` Zeilen 131-140, `clients/xml.py` Zeilen 28-62
**Apply to:** REPORT-/PROPFIND-Bodies und -Antworten

### Qualitätsgates für `scripts/`
**Source:** `pyproject.toml` (ruff `exclude = [".planning"]` Zeile 64, pyright `include = ["src", "scripts", "tests"]` Zeile 80), `vulture_whitelist.py` Kopf Zeilen 1-12
**Apply to:** `scripts/tag_spike.py`: `ruff check .`, `ruff format --check .`, `PYRIGHT_PYTHON_FORCE_VERSION=latest` pyright, `vulture src scripts vulture_whitelist.py`; `# noqa: S603`-Kommentar wie `exchange_evidence.py` Zeile 130

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| PHP-Snippets (`setObjectIdsForTag`, Varianten-Insert, Mapping-Zähler) | utility | batch (DB) | Kein PHP im Repo; Inhalt aus RESEARCH Pattern 3/6, nur der stdin-Transport hat ein Analog |

## Metadata

**Analog search scope:** `scripts/`, `compose*.yml`, `tests/integration/`, `src/mcp_connector/nextcloud/`, `docs/`, `.planning/milestones/v1.6-phases/24-*`
**Files scanned:** 14
**Pattern extraction date:** 2026-09-26
