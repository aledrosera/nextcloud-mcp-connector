---
phase: 26
slug: guard-kern
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-27
---

# Phase 26: Security

> Sicherheitsvertrag dieser Phase: Bedrohungsregister, akzeptierte Risiken, Prüfspur.

Gegenstand: der policy-freie Tag-Client (`src/mcp_connector/nextcloud/clients/systemtags.py`),
die ungefilterte href-Abbildung und die Segmentregel in `clients/dav.py` sowie die
Drei-Zustands-Policy `src/mcp_connector/nextcloud/exclusion.py`. Geprüft wurde am Code
(Datei:Zeile) und an den Tests, die die jeweilige Mitigation belegen. Stand ist HEAD nach den
Review-Fixes `f80f42b`, `b3bd94b`, `43c3b21`, `4e0f43e`. Der Auditor hat die vier
Beweis-Suiten am 27.09. selbst ausgeführt: `tests/unit/test_exclusion.py`,
`tests/unit/test_systemtags_client.py`, `tests/unit/test_dav_home_entries.py`,
`tests/contract/test_no_destructive_calls.py`, 159 passed (venv des Hauptrepos, Import aus
`src/` geprüft). Nichts ist an Werkzeuge gehängt (Grep `exclusion|systemtags` in `tools/`,
`deps.py`, `nextcloud/__init__.py` ohne Treffer).

---

## Trust Boundaries

| Grenze | Beschreibung | Was sie überquert |
|--------|--------------|-------------------|
| Connector zu Nextcloud DAV | PROPFIND `/systemtags/` und REPORT `oc:filter-files` mit Nutzer-Credentials über den gemeinsamen Client | Basic-Auth je Anfrage, keine Cookies, keine Redirects |
| Nextcloud-Antwort zu Connector | Multistatus-XML, hrefs, Tag-Namen, Ids | unvertraute Eingabe, fail-closed abzubilden |
| Nextcloud-Antwort zu Policy-Schicht | Statuscodes und Knoten werden zu `TagScope` | jeder unerwartete Ausgang ergibt `unverifiable` |
| Prozessweiter Cache `_tag_ids` | überlebt Tool-Aufrufe und Nutzer | nur Name-zu-Id je `(base_url, user)`, keine Menge, keine Credentials |

---

## Threat Register

| Threat ID | Kategorie | Komponente | Disposition | Mitigation und Beleg | Status |
|-----------|-----------|------------|-------------|----------------------|--------|
| T-26-01 | Information Disclosure | `systemtags.filter_files_body` | mitigate | Signatur nimmt genau eine Id (`systemtags.py:89`), genau ein `oc:systemtag`-Element (`:100-101`); `tagged_nodes` baut den Body nur daraus (`:155`). Test zählt die Elemente: `len(rules) == 1` (`tests/unit/test_systemtags_client.py:69-79`), REPORT-Body mit genau `["64"]` (`:92-111`) | closed |
| T-26-02 | Information Disclosure | `dav.home_entries` | mitigate | Kein Sandbox-Aufruf, je `d:response` genau ein Paar, nicht abbildbarer oder unsicherer Pfad wird `None` (`dav.py:483-503`, Prüfung über `_home_path_of` `:527-534` und `_plain_path` `:520-524`); `_active` macht aus `None` `unverifiable` "foreign_href" (`exclusion.py:298-299`). Tests: Vorfahr über der Sandbox bleibt (`tests/unit/test_dav_home_entries.py:53`), fremdes Präfix wird `None` statt Drop (`:70`), `alicexyz` (`:82`), unsichere Segmente (`:98`); Guard-Ebene: fremder href ergibt `foreign_href`, nie leere Menge (`tests/unit/test_exclusion.py:514-537`), Sandbox-Vorfahr wirkt (`:885-906`). Hinweis H-2 | closed |
| T-26-03 | Tampering | `filter_files_body`, `list_tags` | mitigate | Modul-eigenes `_DIGITS = re.compile(r"[0-9]+")` mit derselben Regel wie `dav._DIGITS` (`systemtags.py:43`, vgl. `dav.py:42`), Hinweis H-1; `fullmatch` vor dem Body (`systemtags.py:91-92`), bei Tag-Ids der Liste (`:142-143`) und fileids (`:168-169`); Body nur per lxml (`:93-102`, `:105-114`). Tests: `²`, leer, Leerzeichen, `<` werfen (`test_systemtags_client.py:82-85`), ungültige Id ohne Netzverkehr (`:187-197`), Liste mit Nicht-Ziffern-Id (`:230`), fehlende oder ungerade fileid (`:147`) | closed |
| T-26-04 | Tampering / DoS | Antwort-Parsing | mitigate | `list_tags` parst nur mit `xml.parse_multistatus` (`systemtags.py:136`), `tagged_nodes` über `dav.home_entries` (`:166`), das ebenfalls nur `xml.parse_multistatus` nutzt (`dav.py:498`); Parser mit `resolve_entities=False`, `no_network=True`, `huge_tree=False`, `load_dtd=False` (`xml.py:28-37`), DTD-Ablehnung (`xml.py:55-60`). Test: unparsebarer Body ergibt `ToolError` (`test_systemtags_client.py:175`), im Guard `unparsable` (`test_exclusion.py:482`, `:557`) | closed |
| T-26-05 | Information Disclosure | `systemtags.home_url` | mitigate | Ziel `base_url + DAV_FILES_PREFIX + quote(user)`, nie `dav.files_url` (`systemtags.py:84-86`, genutzt `:158`). Test mit `NC_MCP_FILES_ROOT=/Docs`: URL ist die Home-Wurzel (`test_systemtags_client.py:92-111`); User als ein Segment kodiert (`:116`) | closed |
| T-26-06 | Spoofing | Redirect einer Antwort | mitigate | Gemeinsamer Client `follow_redirects=False`, `NoCookieJar` (`src/mcp_connector/nextcloud/http.py:73-78`), ebenso der Startclient (`entry_exapp.py:429-434`); Gleichheitsprüfung `client.follow_redirects is False` (`tests/unit/test_credentials_http.py:59`). 301 mit `Location` kommt als Wert zurück, `call_count == 1` (`test_systemtags_client.py:160-172`), im Guard `unverifiable` "status" (`test_exclusion.py:389-409`) | closed |
| T-26-07 | Denial of Service | Retry nach 401 | mitigate | Je Funktion genau ein `client.request`, keine Schleife, kein Retry (`systemtags.py:126-134`, `:156-164`). Test: 401 als Wert mit `route.call_count == 1` (`test_systemtags_client.py:160-172`) | closed |
| T-26-08 | Information Disclosure | `exclusion.load_scope` | mitigate | `untagged` nur bei Liste 207 ohne Treffer (`exclusion.py:228-232`), `active` nur bei allen Status 207 und allen hrefs abbildbar (`:249-250`, `:288-302`); Timeout, Netz, `ToolError`, `ValueError` ergeben `unverifiable` (`:209-222`), anderer Status (`:251-252`, `:267`), zweiter 412 (`:263-266`). Testmatrix je Grundcode: status (`test_exclusion.py:389`, `:541`), unreachable/timeout (`:420`, `:436`), timeout per Budget (`:451`), unparsable (`:482`, `:498`, `:557`, `:572`, `:588`), foreign_href (`:514`), stale_twice (`:648`, `:664`) | closed |
| T-26-09 | Information Disclosure | `exclusion._report_all` | mitigate | Ein `tagged_nodes` je Id mit genau dieser Id (`exclusion.py:276-278`), eine Id je Schreibweise (`:126-140`). Handler `by_id` bricht bei mehr als einer Id je Body ab (`test_exclusion.py:288-296`); Variantentest: alice 2 REPORTs (64, 67), admin 3 REPORTs (63, 64, 67) (`:839-879`) | closed |
| T-26-10 | Information Disclosure | `_tag_ids`-Cache | mitigate | `_store_ids` schreibt nur nicht-leer (`exclusion.py:110-113`), Cache hält nur Ids (`:94`), die getaggte Menge lebt nur in der Guard-Instanz (`:322-328`). Tests: leeres Ergebnis nicht gespeichert (`test_exclusion.py:176-188`), untagged hinterlässt `_tag_ids == {}` und zweite Instanz listet neu (`:313-333`), zweiter Tool-Aufruf holt die Menge neu (`:783-803`); Contract-Gate führt `_tag_ids` als dokumentierten Modulzustand (`tests/contract/test_no_destructive_calls.py:289`) | closed |
| T-26-11 | Tampering | `_tag_ids`-Schlüssel | mitigate | Schlüssel `(clients.creds.base_url, clients.creds.user)` (`exclusion.py:239`). Test: admin zuerst, dann alice, PROPFIND 2, getrennte Einträge, jeder REPORT mit eigener Id (`test_exclusion.py:807-834`) | closed |
| T-26-12 | Spoofing | Capability `systemtags` | mitigate | Kein Capabilities-Bezug im Code von `exclusion.py` und `systemtags.py` (Grep: nur Docstrings `exclusion.py:13-14`, `systemtags.py:25`). Tests: Capabilities-Route `call_count == 0` im Client (`test_systemtags_client.py:280-297`) und im Guard bei "systemtags aus", Zustand trotzdem `active` (`test_exclusion.py:366-383`) | closed |
| T-26-13 | Elevation of Privilege | `TagScope.excludes` | mitigate | `unverifiable` wirft `ValueError` (`exclusion.py:177-180`). Test: wirft bei path, fileid und ohne Argumente (`test_exclusion.py:116-124`), auch nach echtem Statusfehler (`:408-409`) | closed |
| T-26-14 | Denial of Service | langsamer REPORT | mitigate | `TAG_BUDGET = 15.0` (`exclusion.py:85`), `asyncio.timeout(TAG_BUDGET)` über die ganze Flight (`:210-211`), `TimeoutError` ergibt `unverifiable` "timeout" (`:212-213`). Test mit Budget 0,01 s: timeout, ein REPORT, Dauer unter 0,5 s (`test_exclusion.py:451-479`) | closed |
| T-26-15 | Denial of Service | Wiederholungen | mitigate | Nach 412 genau ein `_fresh_ids` und ein zweites `_report_all`, danach Ende (`exclusion.py:254-267`); 401/5xx enden sofort in `status` (`:251-252`). Tests: 500/401/403/301 mit REPORT 1 und PROPFIND 1 (`test_exclusion.py:389-409`), 412 zweimal mit REPORT 2 (`:648-661`, `:664-676`), 412 dann 500 (`:679-693`), 412 dann Liste 503 (`:696-709`) | closed |
| T-26-16 | Repudiation / Information Disclosure | Abbruch während der Flight | accept | Siehe A-26-1. Code-Befund stützt die Annahme: `CancelledError` wird nirgends gefangen (Grep ohne Treffer in `exclusion.py`), `_scope` wird erst nach `await load_scope` gesetzt (`exclusion.py:349-350`); Test `guard._scope is None` nach Abbruch, zweite Flight startet (`test_exclusion.py:910-945`) | closed |
| T-26-17 | Information Disclosure | Antwortform im Zustand `untagged` | transfer | Übergabe dokumentiert: GATE-03 "Byte-gleiche Paartests getaggt gegen nicht existent" (`.planning/REQUIREMENTS.md:37`), Phase 28 zugeordnet (`REQUIREMENTS.md:78`, `ROADMAP.md:205`, `:281`). Phase-26-Anteil belegt: `untagged` antwortet bedingungslos `False` (`exclusion.py:181-182`), Beispielliste `==` und `json.dumps`-gleich (`test_exclusion.py:99-113`) | closed |
| T-26-SC | Tampering | Paketinstallationen (26-01, 26-02) | accept | Siehe A-26-2. `git diff --stat 6b8cc97^ HEAD -- pyproject.toml uv.lock` ist leer (vom Auditor ausgeführt) | closed |

*Status: open, closed*
*Disposition: mitigate (Umsetzung nötig), accept (dokumentiertes Risiko), transfer (Dritter bzw. spätere Phase)*

---

## Nach-Plan-Härtungen aus dem Code-Review (positiv verifiziert)

| Befund | Commit | Beleg im Code | Beleg im Test |
|--------|--------|---------------|---------------|
| WR-01 `list_tags` wirft bei Tag ohne lesbare Id | `f80f42b` | Collection am href erkannt, sonst `ValueError` (`systemtags.py:137-141`) | `test_systemtags_client.py:244`; Guard ergibt `unparsable`, kein REPORT (`test_exclusion.py:572`) |
| WR-02 `ExclusionGuard` an `(base_url, user)` gebunden | `b3bd94b` | `_key` in `__slots__`, Bindung vor dem Fastpath, kein await dazwischen (`exclusion.py:322`, `:335-339`) | anderer User und andere base_url werfen, PROPFIND 1 (`test_exclusion.py:755-780`) |
| WR-03 `excludes` wirft bei Fehlbedienung im Zustand `active` | `43c3b21` | beide `None` und relativer Pfad werfen vor dem Match (`exclusion.py:183-186`) | `test_exclusion.py:78-84`, `:87-96` |
| WR-04 Counter-Proof über `_violations` | `4e0f43e` | injizierte DELETE-Zeile läuft durch `_code_lines` und `_violations`, reales dav.py vorher befundfrei (`tests/contract/test_no_destructive_calls.py:407-421`) | Suite grün im Auditor-Lauf |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Begründung | Angenommen von | Datum |
|---------|------------|------------|----------------|-------|
| A-26-1 | T-26-16 | Ein abgebrochener Flight-Halter speichert nichts; der nächste Aufrufer startet eine zweite Flight. Folge ist nur doppelte Last, fail-closed bleibt erhalten. Kein `asyncio.shield` in Phase 26, Neubewertung in Phase 27 bei häufigen Abbrüchen (`deferred-items.md`, Punkt c) | Plan 26-02, bestätigt im Audit 27.09.2026 | 2026-09-27 |
| A-26-2 | T-26-SC | Keine neuen Pakete; lxml und httpx sind bestehende Abhängigkeiten; `pyproject.toml` und `uv.lock` im Phasenzeitraum unverändert | Pläne 26-01 und 26-02, bestätigt im Audit 27.09.2026 | 2026-09-27 |

---

## Threat Flags aus den Summaries

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| kein Abschnitt `## Threat Flags` | 26-01-SUMMARY.md | informativ; die einzige Abweichung mit Sicherheitsbezug (eigenes `_DIGITS`) ist unter T-26-03 und H-1 erfasst |
| "Keine neue Angriffsfläche über das Threat-Register hinaus" | 26-02-SUMMARY.md | informativ; die Ergänzung "zweiter 412 löscht den Cache-Eintrag" verschärft T-26-10 (`exclusion.py:265`) |

Unregistered Flags: keine.

---

## Hinweise (keine offenen Threats)

- **H-1 (T-26-03):** `systemtags.py` nutzt eine modul-eigene Konstante `_DIGITS = re.compile(r"[0-9]+")` statt `dav._DIGITS`, wie im Plan vorgesehen. Die Regel ist zeichengleich (`systemtags.py:43`, `dav.py:42`) und wird überall mit `fullmatch` angewandt; die Mitigation ist damit erfüllt. Restrisiko: zwei Konstanten können auseinanderdriften, ein Test, der beide vergleicht, fehlt.
- **H-2 (T-26-02):** Die offenen Info-Befunde IN-02 (Unquote vor dem Segmentvergleich, `%2F`) und IN-03 (Doppel-Slash in `_plain_path`) aus `26-REVIEW.md` betreffen die href-Normalisierung. Beide brauchen einen fehlerhaft kodierenden Server; der Plan-Anspruch von T-26-02 (kein Sandbox-Drop, nicht Abbildbares wird `None`) ist erfüllt. Empfehlung: IN-02 und IN-03 vor der Verdrahtung in Phase 27 mitnehmen.
- **H-3:** IN-01 (doppelte Home-Präfix-Berechnung) und IN-04 (TTL-Test patcht `time.monotonic` global) sind Wartbarkeitspunkte ohne Threat-Bezug.
- **H-4 (T-26-17):** Die eigentliche Byte-Gleichheit "getaggt gegen nicht existent" ist erst mit GATE-03 in Phase 28 belegt. Die Übertragung ist dokumentiert, der Nachweis dort muss im Audit von Phase 28 geprüft werden.

---

## Security Audit 2026-09-27

| Kennzahl | Wert |
|----------|------|
| Threats gesamt | 18 (T-26-01 bis T-26-17, T-26-SC für beide Pläne gemeinsam geführt) |
| Closed | 18 |
| Open | 0 |
| Disposition | 14 mitigate, 3 accept (T-26-16, T-26-SC), 1 transfer (T-26-17) |
| Testlauf (Auditor) | 4 Suiten, 159 passed |
| Lockfile-Diff | leer (`pyproject.toml`, `uv.lock`) |

Prüfspur: Threat-Register aus `26-01-PLAN.md` und `26-02-PLAN.md`, Code in
`src/mcp_connector/nextcloud/exclusion.py`, `clients/systemtags.py`, `clients/dav.py`,
`clients/xml.py`, `nextcloud/http.py`, `entry_exapp.py`, Tests in den vier Beweis-Suiten,
`26-REVIEW.md`, `deferred-items.md`, `REQUIREMENTS.md`, `ROADMAP.md`. Keine
Implementierungsdatei verändert.

---

## Sign-Off

- [x] Jeder Threat hat eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log
- [x] `threats_open: 0` bestätigt
- [x] `status: verified` im Frontmatter

**Approval:** verified 2026-09-27
