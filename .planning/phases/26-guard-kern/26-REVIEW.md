---
phase: 26-guard-kern
reviewed: 2026-09-27T02:14:28Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/mcp_connector/nextcloud/clients/dav.py
  - src/mcp_connector/nextcloud/clients/systemtags.py
  - src/mcp_connector/nextcloud/exclusion.py
  - tests/contract/test_no_destructive_calls.py
  - tests/unit/test_dav_home_entries.py
  - tests/unit/test_exclusion.py
  - tests/unit/test_systemtags_client.py
  - vulture_whitelist.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: resolved
resolved: 2026-09-27
resolution:
  warning_fixed: 4
  info_open: 4
  note: >-
    Alle vier Warnings sind behoben, je Befund ein eigener Commit. Die vier
    Info-Befunde bleiben bewusst offen und dokumentiert; sie waren nicht im
    Auftrag dieser Runde.
fixes:
  WR-01: f80f42b
  WR-02: b3bd94b
  WR-03: 43c3b21
  WR-04: 4e0f43e
gates_after_fixes:
  ruff_check: pass
  ruff_format: pass
  pyright: "0 errors, 0 warnings"
  vulture: pass
  pytest: "4611 passed, 33 skipped (tests/unit tests/contract)"
---

# Phase 26: Code Review Report

**Reviewed:** 2026-09-27T02:14:28Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** resolved (4 Warnings behoben am 2026-09-27; IN-01 bis IN-04 bleiben offen)

## Stand der Behebung

Je Befund ein eigener Commit, die Gates (ruff check, ruff format, pyright, vulture,
pytest tests/unit tests/contract) liefen vor jedem Commit lokal grün; der volle Lauf am
Ende steht bei 4611 passed, 33 skipped.

| Befund | Outcome | Commit |
|--------|---------|--------|
| WR-01 | fixed | `f80f42b` |
| WR-02 | fixed | `b3bd94b` |
| WR-03 | fixed | `43c3b21` |
| WR-04 | fixed | `4e0f43e` |
| IN-01 bis IN-04 | open | dokumentiert, nicht Teil dieser Runde |

Die vier Info-Befunde bleiben unverändert dokumentiert. Sie waren nicht Teil dieser Runde
und sind damit weiterhin offene, benannte Punkte.

## Summary

Gegenstand war der Guard-Kern des kein-ki-Ausschlussfilters: der policy-freie Tag-Client (`systemtags.py`), die ungefilterte href-Normalisierung (`dav.home_entries`) und die Drei-Zustands-Policy (`exclusion.py`) samt Testmatrix und Gate-Anpassungen.

Die im Auftrag genannten Fail-open-Fallen wurden gezielt geprueft und sind alle sauber geloest: die leere REPORT-Antwort mit fremdem href wird `unverifiable` und nie eine leere Menge (exclusion.py:287-292, Test test_a_href_under_a_foreign_prefix_...), "kein Tag" wird nie gecacht (`_store_ids` schreibt nur nicht-leer, Test test_the_cache_stores_positive_results_only), der REPORT geht an die Home-Wurzel statt durch `files_url` (systemtags.home_url, Test mit NC_MCP_FILES_ROOT=/Docs), die REPORT-Auswertung laeuft durch `home_entries` statt `parse_entries` (Sandbox-Vorfahr-Test), und die Capability wird nie befragt (call_count-0-Tests in beiden Suiten). Die Vermutung "nur eine Id je Schreibweise ist fail-open bei gleichnamigen public/restricted-Tags" habe ich gegen den Messbericht der Phase 25 geprueft: Befund K5 belegt live (NC 35), dass der REPORT auf eine Id bereits die Vereinigung exakt gleichnamiger Tags liefert; kein Befund.

Was bleibt, sind vier Warnungen: eine echte Fail-open-Ecke im Tag-Listing (still uebersprungener Eintrag ohne oc:id), eine fehlende Identitaetsbindung des Guards (Cross-User-Risiko bei falscher Verdrahtung in Phase 27), zwei still erlaubende Fehlbedienungspfade von `TagScope.excludes`, und ein tautologischer Counter-Proof im Contract-Gate. Dazu vier Info-Punkte zur Haertung.

## Warnings

### WR-01: list_tags ueberspringt Eintraege ohne oc:id still, das ist die eine fail-open Asymmetrie des Clients

**Outcome:** fixed (`f80f42b`). `list_tags` erkennt die Collection jetzt am href
(`.../systemtags` nach unquote und rstrip) statt an der fehlenden Id; jede andere Response
ohne `oc:id` wirft ValueError, den `load_scope` wie vorgesehen auf `unverifiable` mit
Grund `unparsable` abbildet. Zwei neue Tests: der Client-Test
(`test_list_tags_refuses_a_tag_entry_without_an_id`) und der Guard-Test
(`test_a_listing_entry_without_an_id_is_unverifiable`, kein REPORT geht raus), beide vor
dem Fix rot.

**File:** `src/mcp_connector/nextcloud/clients/systemtags.py:133-135`
**Issue:** Das Tag-Listing skippt jede d:response ohne `oc:id` (`if not tag_id: continue`), um die Collection selbst loszuwerden. Damit verschwindet aber auch jedes echte Tag lautlos, dessen `oc:id` fehlt oder in einem 404-propstat steckt (`xml.parse_multistatus` laesst 404-propstat-Properties weg). Ein kein-ki-Tag, das ein degradiertes Backend oder ein umschreibender Proxy ohne lesbare Id listet, fuehrt so zu `untagged` statt zu `unverifiable`: der Guard glaubt "nichts getaggt" und haelt nichts zurueck. Der REPORT-Pfad ist an derselben Stelle fail-closed (fehlende fileid wirft ValueError, tagged_nodes Zeile 163-164); das Listing ist der einzige Eingang, an dem fehlende Pflichtdaten still toleriert werden. Der Fall braucht eine kaputte Antwort, aber genau dafuer existiert der Zustand `unverifiable`.
**Fix:** Die Collection am href erkennen statt an der fehlenden Id, jede andere Response ohne Ziffern-Id werfen lassen:
```python
for href, props in xml.parse_multistatus(response.content):
    tag_id = props.get(_TAG_ID, "")
    if not tag_id:
        if unquote(urlsplit(href).path).rstrip("/").endswith("/systemtags"):
            continue  # the collection itself carries no oc:id
        raise ValueError(f"Nextcloud listed a tag without an id: {href!r}")
    ...
```
`load_scope` bildet den ValueError bereits auf `unverifiable` mit Grund `unparsable` ab; ein Test analog zu test_a_tagged_node_without_a_file_id_is_unverifiable gehoert dazu.

### WR-02: ExclusionGuard bindet den gecachten Scope nicht an (base_url, user), eine falsch verdrahtete Wiederverwendung liefert den Scope eines fremden Kontos

**Outcome:** fixed (`b3bd94b`). Der Guard trägt jetzt `_key` in `__slots__`, merkt sich
beim ersten `scope()`-Aufruf `(base_url, user)` und wirft bei abweichender Identität hart,
und zwar VOR dem Fastpath, damit ein gecachter Scope nie an fremde Credentials geht;
zwischen Check und Bindung liegt kein await. Test
`test_a_guard_refuses_a_second_identity_instead_of_serving_a_foreign_scope` deckt anderen
User und andere base_url ab und belegt, dass die abgewiesenen Aufrufe das Netz nie
erreichen.

**File:** `src/mcp_connector/nextcloud/exclusion.py:315-328`
**Issue:** `ExclusionGuard.scope(clients)` speichert das Ergebnis der ersten Flight ohne jeden Bezug zu den Credentials, mit denen sie lief. Wird dieselbe Guard-Instanz nacheinander mit zwei verschiedenen `NcClients` (anderer User oder andere base_url) aufgerufen, bekommt der zweite Aufrufer den Scope des ersten: dessen getaggte Pfade und fileids (Informationsabfluss ueber fremde Pfadnamen) oder, schlimmer, ein `untagged` des falschen Kontos (fail-open fuer den eigentlichen Nutzer). Heute existiert kein Aufrufer, der Vertrag "eine Instanz je Tool-Aufruf" steht nur im Docstring; die Verdrahtung passiert erst in Phase 27, und genau gegen deren Fehler schuetzt sich der Kern sonst ueberall (excludes wirft im unverifiable-Zustand, statt auf Disziplin zu setzen). Der modulweite `_tag_ids`-Cache macht es richtig vor: sein Schluessel traegt (base_url, user) genau wegen dieses Verwechslungsrisikos (T-26-11).
**Fix:** Beim ersten Aufruf den Schluessel merken und Divergenz hart ablehnen:
```python
__slots__ = ("_key", "_lock", "_scope")
...
key = (clients.creds.base_url, clients.creds.user)
if self._key is None:
    self._key = key
elif self._key != key:
    raise ValueError("one ExclusionGuard serves exactly one (base_url, user)")
```

### WR-03: TagScope.excludes antwortet bei Fehlbedienung still mit "erlaubt": ohne Argumente und bei relativen Pfaden

**Outcome:** fixed (`43c3b21`). Im aktiven Zustand wirft `excludes` jetzt ValueError bei
beiden Fehlbedienungen (path und fileid beide None; nicht-absoluter Pfad, auch wenn
zusätzlich eine fileid übergeben wurde), die Prüfung steht vor dem fileid-/paths-Match.
`untagged` liefert weiterhin bedingungslos False, der Spurlosigkeits-Test bleibt gültig;
das festgeschriebene `scope.excludes() is False` im aktiven Zustand
(test_an_active_scope_matches_file_ids) ist entfernt und durch zwei Fehlbedienungstests
ersetzt.

**File:** `src/mcp_connector/nextcloud/exclusion.py:165-180`
**Issue:** Zwei Aufruffehler der Phase 27 enden im aktiven Zustand lautlos in `False`, also "nicht zurueckhalten": (a) `excludes()` mit `path=None, fileid=None` gibt False zurueck, das ist sogar per Test festgeschrieben (test_exclusion.py:77, `scope.excludes() is False`). Ein Aufrufer, der die Werte per `entry.get("path")`/`entry.get("fileid")` zieht und wegen eines falschen Keys zweimal None uebergibt, filtert damit nie etwas. (b) Ein relativer Pfad (`"Docs/a.md"` statt `"/Docs/a.md"`) matcht keinen Vorfahren aus `paths`, weil `ancestors` nie bei `/` ankommt und die getaggten Pfade immer mit `/` beginnen; auch das ist ein stilles Erlauben. Der Docstring nennt die Konvention, aber die Phase existiert, weil Konventionen ohne Durchsetzung im Sicherheitskern nicht reichen (dasselbe Argument, mit dem `unverifiable` wirft statt False zu liefern).
**Fix:** Im aktiven Zustand Fehlbedienung werfen statt erlauben:
```python
if path is None and fileid is None:
    raise ValueError("excludes needs a path or a fileid; asking nothing is not allowed")
if path is not None and not path.startswith("/"):
    raise ValueError(f"excludes takes an absolute home path, got {path!r}")
```
Im Zustand `untagged` darf `excludes()` weiterhin False liefern (der Spurlosigkeits-Test bleibt gueltig), die Prüfung gehoert vor den fileid-/paths-Match des aktiven Zweigs.

### WR-04: Der Counter-Proof des Verb-Filters ist in seiner zweiten Haelfte tautologisch und beweist nichts ueber das Gate

**Outcome:** fixed (`4e0f43e`). Die Beweiszeile läuft jetzt durch `_code_lines` plus
`_violations` wie bei den Nadel-Familien: die injizierte DELETE-Zeile wird an die echten
gefilterten Zeilen von dav.py gehängt und der Fund über `_violations` assertet. Dazu die
Gegenprobe, dass das reale dav.py vorher befundfrei ist, was zugleich die
MOVE-Chunk-Assembly-Exemption mit prüft. Die erste Hälfte (Docstring herausgefiltert)
blieb unverändert.

**File:** `tests/contract/test_no_destructive_calls.py:408-409`
**Issue:** `test_the_gate_would_notice_a_destructive_call_in_real_code` haengt die Zeile `await client.request("DELETE", url)` per String-Konkatenation an den gefilterten Text und assertet dann `"DELETE" in with_a_violation`. Dieser Assert ist konstruktionsbedingt immer wahr, denn der String wurde eine Zeile vorher selbst mit dem Wort "DELETE" gebaut; er laeuft weder durch `_code_lines` noch durch `_violations`. Wuerde das Gate morgen jede Zeile mit "DELETE" verschlucken, bliebe dieser Test gruen. Die Nadel-Familien (TABLES/TALK/MAIL) machen es richtig und pruefen ueber `_violations`; nur dieser aelteste Counter-Proof, ausgerechnet der fuer die vier Verben, ist dekorativ. Die erste Haelfte (der Docstring von dav.py ist herausgefiltert) ist in Ordnung.
**Fix:** Die Beweiszeile durch das echte Pruefwerk schicken, mit der bestehenden MOVE-Exemption als Gegenprobe:
```python
relative = "nextcloud/clients/dav.py"
real = _code_lines(SRC / "nextcloud" / "clients" / "dav.py")
findings = _violations(relative, [*real, (10_000, '    await client.request("DELETE", url)')])
assert any("'DELETE'" in finding for finding in findings)
```

## Info

### IN-01: Die home-Prefix-Berechnung steht zweimal in dav.py und kann auseinanderdriften

**File:** `src/mcp_connector/nextcloud/clients/dav.py:473,496`
**Issue:** `parse_entries` und `home_entries` bauen denselben f-String `f"{urlsplit(creds.base_url).path.rstrip('/')}{DAV_FILES_PREFIX}{creds.user}"` unabhaengig voneinander. Aendert jemand nur eine der beiden Stellen (etwa ein Quoting des Users, wie es WR-10 fuer search_scope schon einmal noetig machte), vergleichen Sandbox-Sicht und Guard-Sicht ploetzlich verschiedene Pfadformen, und `excludes` matcht genau auf dieser Ebene.
**Fix:** Eine private Funktion `_home_prefix(creds) -> str`, von beiden aufgerufen.

### IN-02: _home_path_of unquoted den gesamten href-Pfad vor dem Segmentvergleich

**File:** `src/mcp_connector/nextcloud/clients/dav.py:529`
**Issue:** `unquote(urlsplit(href).path)` decodiert auch `%2F` zu einem Segmenttrenner, bevor Prefix-Match und `_plain_path`-Segmentpruefung laufen. Ein korrekt encodierender Nextcloud sendet fuer ein Prozentzeichen `%25`, der Fall traegt heute also nicht; robust waere trotzdem, segmentweise zu unquoten (erst an `/` splitten, dann jedes Segment decodieren), damit ein fehlnormalisierter Server keine Pfadgrenzen verschieben kann.
**Fix:** `"/".join(unquote(seg) for seg in urlsplit(href).path.split("/"))` als Decodierung verwenden.

### IN-03: _plain_path laesst leere Segmente (Doppel-Slash) durch

**File:** `src/mcp_connector/nextcloud/clients/dav.py:520-524`
**Issue:** Verboten sind nur `.` und `..`; ein href mit `//` liefert Pfade wie `//A`, die in der Ausschlussmenge landen koennen, waehrend Datei-Eintraege `/A/...` tragen und deren `ancestors` `//A` nie enthalten. Beide Seiten laufen zwar durch dieselbe Funktion, sodass eine Divergenz einen inkonsistent normalisierenden Server braucht; da ein `None` hier ohnehin fail-closed in `unverifiable` endet, kostet die Haertung nichts.
**Fix:** In `_plain_path` zusaetzlich `"//" in path` ablehnen (nicht per Segmentliste, damit das Home-Root `"/"` gueltig bleibt).

### IN-04: Der TTL-Test patcht das globale time-Modul statt eines Modul-Attributs

**File:** `tests/unit/test_exclusion.py:175-178`
**Issue:** `monkeypatch.setattr(exclusion.time, "monotonic", ...)` patcht `time.monotonic` prozessweit, denn `exclusion.time` ist das stdlib-Modul selbst. Der Test ist synchron und monkeypatch raeumt auf, daher heute harmlos; sobald jemand den Test async macht oder waehrenddessen ein Event-Loop laeuft, misst auch der Loop mit der gefaelschten Uhr.
**Fix:** Entweder die Uhr als Modul-Seam fuehren (`_now = time.monotonic` in exclusion.py und dieses Attribut patchen) oder den Cache-Eintrag wie in test_a_cache_entry_expires_after_the_ttl direkt mit passenden Zeitstempeln vorbelegen, ohne zu patchen.

---

Gepruefte Fail-closed-Pfade ohne Befund (der Vollstaendigkeit halber): Timeout-Budget ueber die ganze Flight mit fail-closed-Abbildung beider Irrtumsrichtungen; httpx.TimeoutException vor httpx.HTTPError gefangen; CancelledError bewusst nicht gefangen und nie gespeichert (Test belegt beides); 412-Automat mit genau einer Neuaufloesung und `_drop_ids` in beiden Stale-Zweigen; gemischte Statusmengen {207, 412} verwerfen auch die 207-Teilmengen und fragen komplett neu; `_report_all` laesst alle Teilanfragen enden, bevor die erste Exception wieder geworfen wird; Single-Flight-Fastpath ohne await zwischen Check und Return; Contract-Gate kennt `_tag_ids` als dritten dokumentierten Cache mit Zaehltest; vulture_whitelist parkt nur `_.is_collection` und `_.excludes` mit belastbarer Begruendung und Testverweis.

_Reviewed: 2026-09-27T02:14:28Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Resolved: 2026-09-27 (4 Warnings behoben, je Befund ein Commit; IN-01 bis IN-04 offen)_
