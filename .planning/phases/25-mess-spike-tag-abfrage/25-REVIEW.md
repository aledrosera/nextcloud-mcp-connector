---
phase: 25-mess-spike-tag-abfrage
reviewed: 2026-09-27T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - scripts/tag_spike.py
  - tests/unit/test_tag_spike.py
  - compose.spike-tags.yml
  - compose.spike-tags-pg.yml
  - vulture_whitelist.py
findings:
  critical: 0
  warning: 7
  info: 7
  total: 14
status: issues_found
---

# Phase 25: Code-Review-Bericht

**Reviewed:** 2026-09-27
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Geprüft wurden das Messwerkzeug `scripts/tag_spike.py` (3260 Zeilen, alle gelesen), seine Unit-Tests, die beiden Wegwerf-Compose-Dateien und die Vulture-Whitelist. Der sicherheitskritische Kern hält der Prüfung stand: alle pro Lauf erzeugten Passwörter und Tokens werden über stdin oder die Prozessumgebung transportiert, nie als Argument; jedes erzeugte Secret wird via `remember_secret` registriert (nachvollzogen für controls, findings, latency, matrix und gegenmessung); `write_protocol` verweigert das Schreiben fail-closed, wenn ein Secret-Wert oder der AppAPI-Header-Name im Protokoll auftaucht; `report_body` lässt nur ASCII-Ziffern in den XML-Body; die Compose-Dateien binden ausschließlich auf Loopback, erzwingen die Passwörter als Pflichtvariablen ohne Default und geben der Datenbank keinen Port. Kein Critical-Befund.

Gefunden wurden sieben Warnings, alle in der Kategorie Messintegrität und Robustheit: das Vermengen von stdout und stderr in `run()` mit mehreren numerisch parsenden Aufrufstellen, eine falsche "ruhte wieder"-Protokollzeile bei Timeout, eine Reihenfolge-Lücke in der Querprüfung der Vorfahren-Bündel, eine unerreichbare "nicht messbar"-Schwellenzeile, ein Notes-Block, der im Negativfall der eigenen Messfrage abstürzt statt "nein" zu protokollieren, Papierkorb-Reste beim Rückbau und ein toter, im Plan aber vorgesehener Access-Log-Beleg.

## Narrative Findings (AI reviewer)

### Warnings

#### WR-01: run() vermengt stdout und stderr, mehrere Aufrufstellen parsen das Gemisch numerisch

**File:** `scripts/tag_spike.py:351` (Ursache), Aufrufstellen `scripts/tag_spike.py:3012`, `scripts/tag_spike.py:3052`, `scripts/tag_spike.py:3155`, `scripts/tag_spike.py:398-399`, `scripts/tag_spike.py:1833-1847`
**Issue:** `run()` gibt `stdout + stderr` als einen String zurück. Das ist für `occ`-Prosa unkritisch (der Docstring von `new_app_password` handhabt es dort bewusst), aber mehrere Stellen parsen das Gemisch strukturell:
- Zeile 3012: `int(docker("info", "--format", "{{.MemTotal}}").strip())`. `docker info` schreibt auf vielen Hosts (gerade WSL2) Warnungen wie "WARNING: No blkio ..." auf stderr. Dann steht hinter der Zahl Text, `int()` wirft `ValueError`, und `gegenmessung` stirbt vor dem Aufbau mit unbehandeltem Traceback (ValueError steht nicht in der except-Liste von `main`).
- Zeilen 3052 und 3155: `docker inspect ... .split(" ")` mit Zugriff auf `[0]` und `[-1]`; eine stderr-Zeile verfälscht `[-1]` und damit den NC35-UNBERUEHRT-Beleg.
- `php()` (Zeile 398-399) nimmt die letzte nicht-leere Zeile als Ergebnis; eine PHP-Deprecation auf stderr kann sich als Ergebnis ausgeben. Die Ziffern-Checks fangen das an einigen, nicht an allen Stellen (der `set_stage`-Split in `block_stages`/`gegen_ballast` verlässt sich auf das Format).
- `spike_dir_exists` (Zeile 1847) prüft `answer.endswith("ja")`; eine stderr-Zeile hinter dem "ja" kippt die Antwort auf "nein" und lässt den Latenzlauf auf stehenden Daten starten.
**Fix:** `run()` soll stdout und stderr getrennt zurückgeben (z. B. NamedTuple) oder mindestens eine Variante `run(..., stdout_only=True)` anbieten; die vier genannten Aufrufstellen auf reines stdout umstellen. Minimal-Fix für Zeile 3012:
```python
finished = subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True, check=True)
total = int(finished.stdout.strip()) / 1024**3
```

#### WR-02: wait_until_idle meldet Ruhe auch dann, wenn die Instanz nach 300 s nie ruhig wurde

**File:** `scripts/tag_spike.py:1948-1960`, Aufrufer `scripts/tag_spike.py:2037-2042` und `scripts/tag_spike.py:2851-2852`
**Issue:** Die Schleife bricht entweder per `break` (wirklich idle) oder per Zeitlimit ab; der Rückgabewert unterscheidet die Fälle nicht. Beide Aufrufer protokollieren danach vorbehaltlos "ruhte nach {waited} s wieder". Läuft die serverseitige Abfrage länger als 300 s (bei 145.000 Ballast-Zuordnungen der erwartete Fall, der Einzellauf auf nc35 brauchte laut Testfixture 249 s), steht eine faktisch falsche Aussage im Messprotokoll, und `long_single_run` startet anschließend gegen eine noch belastete Instanz, misst also zwei REPORTs übereinander. Wenn `cpu_percent` das `docker stats`-Format nicht parsen kann (gibt `None` zurück), tritt derselbe Falschbefund garantiert ein.
**Fix:** Idle-Flag zurückgeben und protokollieren:
```python
async def wait_until_idle(containers=...) -> tuple[float, bool]:
    ...
        if all(...):
            return time.perf_counter() - started, True
        await asyncio.sleep(5)
    return time.perf_counter() - started, False
```
Aufrufer: bei `False` "ruhte NICHT binnen {waited} s" notieren und den Einzellauf überspringen oder als kontaminiert kennzeichnen.

#### WR-03: measure_bundle berechnet answers aus check[0].body, bevor der failed-Guard greift

**File:** `scripts/tag_spike.py:2862-2864`
**Issue:** Reihenfolge-Fehler in der Querprüfung:
```python
failed = [result.status for result in check if result.status != 207]
if answers is None:
    answers = [path for path in tags_by_path(check[0].body, home) if path != listing]
if tagged is None or failed:
    ...
```
Für V1/V2 (answers is None) läuft `tags_by_path(check[0].body, ...)` auch dann, wenn `check[0]` kein 207 ist. `tags_by_path` ruft `xml.parse_root`, und der wirft bei einem Nicht-XML-Fehlerbody (verifiziert in `src/mcp_connector/nextcloud/clients/xml.py:40-54`) einen `ToolError`. Der schlägt bis zu `guarded("vorfahren", ...)` durch und bricht den gesamten Vorfahren-Block ab; alle noch ausstehenden Varianten (V2 bis V4p) gehen verloren, obwohl der Code für genau diesen Fall die "nicht prüfbar"-Zeile vorgesehen hat. Die Schleife darüber (Zeile 2858-2861) prüft den Status korrekt; nur diese eine Stelle nicht.
**Fix:** Den `failed`/`tagged`-Guard vor die answers-Ableitung ziehen oder die Ableitung auf `check[0].status == 207` bedingen:
```python
if answers is None and check[0].status == 207:
    answers = [path for path in tags_by_path(check[0].body, home) if path != listing]
if tagged is None or failed or answers is None:
    note(f"{label} ausgeschlossen=nicht prüfbar ...")
    return
```

#### WR-04: block_threshold unterdrückt die "nicht messbar"-Schwellenzeile, wenn Serie und Einzellauf mit Ballast beide scheitern

**File:** `scripts/tag_spike.py:2304-2308`, betroffener Zweig `scripts/tag_spike.py:2251-2257`
**Issue:** `ballast_threshold` hat einen expliziten Zweig für den Fall, dass weder ein warmer Median noch ein Einzellauf-Wert existiert ("median_warm_5000=nicht messbar (keine Antwort binnen 300 s) ergebnis=ueber"). Im Latenzlauf ist dieser Zweig unerreichbar: `block_threshold` ruft `ballast_threshold` nur, wenn ein Key `stufe5000_ballast*` in `lat.medians` steht, und genau in diesem Fall (Serie ReadTimeout, danach Einzellauf ebenfalls Timeout, `long_single_run` setzt bei Timeout keinen Key, Zeile 1984-1989) steht keiner. Ergebnis: das Protokoll trägt für die schlechteste messbare Lage keine SCHWELLE-D-25-04-Zeile mit Ballast, obwohl der Checkpoint 25-04 genau diese Zeile liest. `gegen_threshold` (Zeile 2974) ruft `ballast_threshold` dagegen bedingungslos, die beiden Pfade verhalten sich unterschiedlich.
**Fix:** Den Guard darauf umstellen, ob der Ballast-Block gelaufen ist, nicht ob er einen Wert lieferte, z. B. ein `lat.ballast_ran: bool = False` in `Latency`, gesetzt am Anfang von `block_ballast`/`measure_with_ballast`, und in `block_threshold`:
```python
if lat.ballast_ran:
    for line in ballast_threshold(lat):
        note(line)
```

#### WR-05: block_notes stürzt im Negativfall der eigenen Messfrage ab, statt "nein" zu protokollieren

**File:** `scripts/tag_spike.py:1041`
**Issue:** `fetched = await notes.get_note(run.client, creds, first_fileid or "0")` holt die Notiz über die fileid. Die Messfrage des Blocks ist gerade, ob Notiz-Id und fileid übereinstimmen. Im Negativfall (Ids verschieden oder `first_fileid == ""`, dann wird "0" angefragt) antwortet die Notes-API 404, `parse_app_json` wirft `ToolError` (verifiziert in `src/mcp_connector/nextcloud/clients/notes.py:70-78`), `guarded` bricht den Block als "BLOCK FAILED | notes" ab, und die Verdict-Zeile "NOTIZ-ID GLEICH FILEID: nein" sowie die zweite Notiz und der REPORT-Teil des Blocks werden nie geschrieben. Das Werkzeug kann das interessanteste Messergebnis nicht berichten.
**Fix:** Den Abruf einzeln absichern und den Fehlstatus als Befund protokollieren:
```python
try:
    fetched = await notes.get_note(run.client, creds, first_fileid or "0")
    same_fetch = str(fetched.get("id", "")) == first_id
except ToolError as failure:
    fetched, same_fetch = {}, False
    row(block, f"GET notes/api/v1/notes/{first_fileid or '0'}", "4xx", f"fehler={failure.message[:120]} dieselbe_notiz=nein")
```

#### WR-06: Rückbau der findings hinterlässt Spike-Reste im Papierkorb, sobald der Papierkorb vorher nicht leer war

**File:** `scripts/tag_spike.py:1734-1759`
**Issue:** Die Notizen werden über die Notes-API gelöscht (Zeile 1734-1740) und der Notes-Kategorieordner per DAV DELETE (Zeile 1751-1754); beides landet im Papierkorb von alice. `trashbin:cleanup` läuft nur, wenn der Papierkorb vor dem Lauf leer war (Zeile 1755-1759), was als Schutz der Nutzerdaten richtig ist, denn `trashbin:cleanup` löscht alles, auch Fremdes. Folge: war der Papierkorb vorher nicht leer, bleiben Spike-Notizen und der Ordner dauerhaft im Papierkorb liegen, und die BASELINE-Zeile "papierkorb gleich=nein" ist bei jedem Folgelauf rot. Der Verstoß gegen die Rückbau-Zusicherung ist sichtbar, aber vermeidbar: für den Hauptordner nutzt der Rückbau bereits `occ files:delete --force --skip-trash`, für den Notes-Ordner nicht.
**Fix:** Den Notes-Ordner denselben Weg gehen lassen wie `/spike25`:
```python
if run.notes_path:
    output = occ(NC_CONTAINER, "files:delete", "--force", "--skip-trash",
                 f"{user}/files/{run.notes_path}/{SPIKE_DIR}", check=False)
```
Die Notes-API-Löschungen davor entfallen dann (der Ordner nimmt die .md-Dateien mit) oder die einzelnen Papierkorb-Einträge werden gezielt über `remote.php/dav/trashbin/{user}/trash/...` gelöscht.

#### WR-07: access_lines ist toter Code, der geplante Access-Log-Beleg des Impersonation-Blocks fehlt, und das Vulture-Gate kann das nicht sehen

**File:** `scripts/tag_spike.py:438-446`
**Issue:** `access_lines` hat in `tag_spike.py` keinen einzigen Aufrufer (grep-verifiziert; nur `impersonation_lines` wird in Zeile 1179 genutzt). Laut 25-PATTERNS.md (Zeile 152) war der Access-Log-Beleg mit Statuscode als Kontrolle des Impersonation-Blocks vorgesehen ("access_lines(since, needles) übernehmen, since = now_stamp() vor dem Block"); `block_impersonation` prüft aber nur `exapp_impersonation.log`, der Apache-Access-Log-Beleg fehlt. Das CI-Gate `uv run vulture src scripts vulture_whitelist.py` schlägt nicht an, weil derselbe Name in `scripts/exchange_evidence.py:766` einen Aufrufer hat; das ist exakt der Namens-Schatten-Mechanismus, den die Whitelist selbst dokumentiert ("get_messages never entered the list, because the name already has a production caller"). Der leere Phase-25-Abschnitt der Whitelist (Zeile 304-313) ist damit formal korrekt, deckt den toten Zweig aber nicht.
**Fix:** Entweder den geplanten Beleg nachziehen (in `block_impersonation` vor den beiden REPORTs `since = now_stamp()`, danach `access_lines(NC_CONTAINER, since, ("REPORT",))` protokollieren) oder die Funktion löschen und die Abweichung vom Plan im Messbericht benennen.

### Info

#### IN-01: Tote Bedingung "ballast_mappings" in block_threshold

**File:** `scripts/tag_spike.py:2304-2306`
**Issue:** `"ballast_mappings" in lat.medians` ist nirgends im Code erfüllbar; kein Pfad schreibt diesen Key (grep-verifiziert, einziges Vorkommen ist diese Zeile). Vermutlich ein Rest eines früheren Entwurfs.
**Fix:** Bedingung entfernen (bzw. im Zuge von WR-04 durch das `ballast_ran`-Flag ersetzen).

#### IN-02: scatter_paths liefert bei nicht teilenden counts mehr als count Pfade

**File:** `scripts/tag_spike.py:2636-2642`
**Issue:** `range(0, 10_000, 10_000 // count)` erzeugt für counts, die 10.000 nicht teilen, mehr als `count` Einträge (z. B. count=3 ergibt 4 Pfade); bei count > 10.000 wirft der Schritt 0 einen ValueError. Aktuell werden nur 20 und 100 verwendet (beide Teiler), der Vertrag "count files" gilt also stillschweigend nur für Teiler von 10.000.
**Fix:** Absichern: `paths = paths[:count]` plus `assert 10_000 % count == 0` oder ein sprechender ValueError.

#### IN-03: KALT-Definition nennt den SQLite-Seitencache auch im PostgreSQL-Lauf

**File:** `scripts/tag_spike.py:2164-2168`
**Issue:** `block_cold` schreibt fest "der OS-Seitencache der SQLite-Datei bleibt warm (Annahme A5)" ins Protokoll; im gegenmessung-Lauf mit `--db pg` ist der Satz sachlich falsch (dort bleiben die PostgreSQL-Caches warm, die es gar nicht als SQLite-Datei gibt).
**Fix:** Text von `lat.db_container` abhängig machen, z. B. "die Datenbank-Caches (SQLite-Datei bzw. PostgreSQL shared_buffers) bleiben warm".

#### IN-04: read_env_file entfernt Randanführungszeichen naiv

**File:** `scripts/tag_spike.py:412-423`
**Issue:** `value.strip().strip('"').strip("'")` entfernt beliebig viele Anführungszeichen an beiden Enden; ein Secret, das selbst mit einem Anführungszeichen beginnt oder endet, würde verstümmelt, und der Secret-Scan suchte dann nach dem falschen Wert. Mit den von `bootstrap_exapp.sh` erzeugten Werten (token_urlsafe) real kein Problem, aber der Scan-Schutz hängt an dieser Annahme.
**Fix:** Nur ein umschließendes Paar entfernen: `if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'": v = v[1:-1]`.

#### IN-05: Der else-Zweig in main führt jeden künftigen Block als findings aus

**File:** `scripts/tag_spike.py:3248-3249`
**Issue:** Die Blockliste existiert doppelt (Tupel `BLOCKS` und die if/elif-Kette). Ein neuer Eintrag in `BLOCKS` ohne zugehöriges elif liefe stillschweigend als `findings` gegen nc35, inklusive Rückbau dort.
**Fix:** Dispatch über ein Mapping `{blockname: runner}` und `BLOCKS = tuple(mapping)` ableiten, oder das else durch `elif options.block == "findings"` plus `raise AssertionError` ersetzen.

#### IN-06: latency-Vorbedingung deutet einen docker-Fehlertext als laufenden Wegwerf-Container

**File:** `scripts/tag_spike.py:2334-2335`
**Issue:** `docker("ps", "-q", ..., check=False)` liefert bei nicht erreichbarem Docker-Daemon die Fehlermeldung als Text; `.strip()` ist dann truthy und der Lauf bricht mit der irreführenden Meldung ab, `nc-spike-tags` laufe noch. Die Richtung ist fail-safe (es wird nichts gemessen), nur die Diagnose stimmt nicht.
**Fix:** Bei check=False zusätzlich auf ein plausibles Container-Id-Format prüfen (nur Hex-Zeilen zählen) oder hier check=True verwenden und den RunFailed sprechen lassen.

#### IN-07: Der secret-scan-Block deckt nur Env-Datei-Secrets und nur raw/ plus Messbericht

**File:** `scripts/tag_spike.py:3166-3183`
**Issue:** Der Commit-Gate-Scan kennt naturgemäß nur die Secrets der Env-Datei plus den abgeleiteten AppAPI-Token; pro Lauf erzeugte Secrets (Wegwerf-Admin, Alice-Passwörter, App-Tokens) sind ausschließlich durch den Schreibzeit-Scan in `write_protocol` gedeckt, und geprüft werden nur `raw/*` und `25-MESSBERICHT.md`, nicht andere Dateien des Phasenordners, die Protokollzeilen zitieren könnten (PLAN, VERIFICATION, SUMMARY). Das ist konstruktionsbedingt und im Docstring angedeutet, sollte aber als Grenze des Gates im Messbericht stehen.
**Fix:** Im Modul-Docstring bzw. Messbericht die Grenze explizit benennen; optional den Scan auf `PHASE_DIR.rglob("*.md")` ausweiten.

---

Positiv geprüft und ohne Befund: die Secret-Registrierung aller fünf Blöcke (jedes erzeugte Passwort und Token läuft durch `remember_secret`, bevor es verwendet wird), der fail-closed-Schreibpfad `write_protocol`, die stdin-Wege `occ_pw`/`php`, die ASCII-Ziffern-Validierung in `report_body`, die parametrisierten Query-Builder-Inserts in den PHP-Snippets, die Loopback-Bindung und die Pflichtvariablen ohne Default in beiden Compose-Dateien, der portlose PostgreSQL-Container, die Vorbedingungen gegen Volume-Wiederverwendung (Pitfall 3) und Doppel-Instanzen (D-25-01) sowie die Unit-Tests, die die reinen Helfer inklusive der 412-, FREMD-href- und Secret-Scan-Fälle korrekt festnageln.

_Reviewed: 2026-09-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
