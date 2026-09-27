# Phase 27: Live-Beweis (Familien-Anschluss und Sandbox-Parität)

**Datum:** 2026-09-27
**Instanz:** nc35 (Nextcloud 35.0.0 laut status.php, SQLite, spreed 25.0.0, Notes 6.1.0), Topologie nc35-nc, nc_app_mcp_connector, nc35-harp, nc35-caddy, nc35-greenmail; Konto alice (kein Admin)
**Kommandos:**

- `set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest tests/integration/test_exclusion_live.py -m integration -s` (Plan 27-07, Erfolgskriterien 1 bis 5, A1)
- `set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest tests/integration/test_ctx_bundle.py -m integration -s` (Plan 27-08, Wanduhr und Request-Kosten)
- `set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest tests/integration/test_exclusion_probe.py -m integration -s` (Proben 27-03 und 27-05)

In der Worktree-Isolation lud ein kleiner Python-Lader dieselbe Env-Datei (`. ./.env.nc35` ist dort gesperrt); das Kommando in den Rohdateien ist das geplante.

**Rohdateien:** `raw/27-03-provider-probe.txt`, `raw/27-04-notes-settings.txt`, `raw/27-05-file-conversation-probe.txt`, `raw/27-07-live.txt`, `raw/27-08-prepare-context.txt`, `raw/27-09-prepare-context.txt` (Lückenplan 27-09), `raw/27-09-exclusion-live.txt` (Live-Beweise 27-07 nach 27-09 erneut), `raw/27-10-prepare-context.txt` (Lückenplan 27-10), `raw/27-10-exclusion-live.txt` (Live-Beweise 27-07 nach 27-10 erneut)

Jede Zahl unten steht in einer dieser Dateien. Maßgeblich für die Kriterien 1 bis 5 ist der letzte vollständige Lauf in `raw/27-07-live.txt` (13:33:38 +0200, Baum `/live27-1dde17e2`); über alle vier Läufe der Datei steht keine einzige Zeile mit `: nein`.

## Erfolgskriterium 1: Dateifamilie und Upload

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| files_list | test_exclusion_live, SC1 | `files_list getaggte Datei und getaggter Ordner fehlen: ja (items=['offen-1dde17e2.txt'])`; `getaggter Ordner wie fehlender Pfad: ja` | getaggte Datei und Ordner fehlen, ein getaggter Ordner antwortet wie ein fehlender Pfad | raw/27-07-live.txt |
| files_search | SC1 | `files_search geheim/a/b/scan/projekt ohne Treffer: ja (count=0)`; `Gegenprobe offen gefunden: ja`; `Laufkennung ohne getaggte Namen: ja` | ja, auch für Dateien unter dem getaggten Ordner | raw/27-07-live.txt |
| files_read, files_download | SC1 | je `wie erfundener Pfad: ja ('File not found: ...')` für geheim, a, b, scan, Projekt; `Gegenprobe offen liefert Inhalt: ja` | ja, byte-gleich zu `dav.not_found` | raw/27-07-live.txt |
| files_upload | SC1 | `files_upload Projekt/neu.txt wie fehlender Elternordner: ja`; `files_upload geheim wie fehlender Elternordner: ja`; `PROPFIND Projekt/neu.txt nicht geschrieben: ja (status=404)`; `PROPFIND geheim unverändert: ja (etag gleich=True)` | ja, der Upload verrät nicht, ob dort etwas liegt; nichts geschrieben | raw/27-07-live.txt |

SC1-Zeilen im maßgeblichen Lauf: 24, alle `ja`.

## Erfolgskriterium 2: Suche, fetch, systemtags, prepare_context

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| unified_search | SC2 | `Laufkennung ohne getaggten Treffer: ja (count=8 providers=['comments', 'files', 'notes'] leaks=[])`; geheim-Name und Projekt-Name `count=0 leaks=[]`; `Gegenprobe offen gefunden: ja` | ja | raw/27-07-live.txt |
| ChatGPT search | SC2 | `chatgpt_search Laufkennung ohne getaggten Treffer: ja (count=8 leaks=[])`; geheim-Name `count=0` | ja | raw/27-07-live.txt |
| fetch mit vorher bekannter fileid | SC2 | `fetch vorher gelesen vor dem Taggen: ja (scope=untagged ...)`; danach `wie unbekannte Id: ja ('This account has no file with the id 22215.')` | ja, auch eine vor dem Taggen gelesene fileid | raw/27-07-live.txt |
| systemtags-Provider | SC2 | `roh=6 roh_mit_attributes=5 antwort=1 ohne_fileId=1 leaks=[]` | ja, die getaggte Menge wird nicht verraten | raw/27-07-live.txt |
| prepare_context | SC2 | `weder Treffer noch Ausschnitt noch Digest-Name getaggt: ja (treffer=8 ausschnitte=2 degraded=['mail', 'file:22220'])` | ja; `file:22220` ist der Ordner der Laufkennung, den fetch als Ordner ablehnt (kein Ausschlussbezug) | raw/27-07-live.txt |
| prepare_context Wanduhr | test_ctx_bundle, Messung 1b | siehe Abschnitt "Wanduhr prepare_context", Unterabschnitt "Nach dem Lückenplan 27-09" | 27-08: drei von vier Zeilen innerhalb, B full 1,047 s überschritten; **nach 27-09: drei von vier Zeilen innerhalb, B full 0,992 s weiterhin überschritten (um 0,022 s)**; **nach 27-10 (Unterabschnitt "Nach dem Lückenplan 27-10"): alle vier Zeilen überschritten, B full 2,163 s, bei gleich hoher Kontrolle mit dem Code vor 27-10 (Host-Drift); Wanduhr in dieser Sitzung nicht entscheidungsfähig, Request-Seite belegt (files-search 3 auf 2)** | raw/27-08-prepare-context.txt, raw/27-09-prepare-context.txt, raw/27-10-prepare-context.txt |

SC2-Zeilen im maßgeblichen Lauf: 10, alle `ja`. Die Wanduhr ist der einzige Teil mit Überschreitung.

## Erfolgskriterium 3: pfadlose Treffer und Notizen

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| comments-Treffer (nur fileid) außerhalb der Root | SC3, `NC_MCP_FILES_ROOT=/live27-<hex>` | `raw=2 urls=['http://127.0.0.1:8082/f/22213'] skipped=1`; ohne Root beide | ja, verschwindet wie ein Pfad-Treffer und zählt in skipped | raw/27-07-live.txt |
| Notizen außerhalb der Root | SC3 | `notes_search ... count=0 skipped=3` | ja | raw/27-07-live.txt |
| getaggte Notiz, Notiz in getaggter Kategorie | SC3 | `notes_search nur die ungetaggte Notiz: ja (ids=['note:22221'])`; notes_read B und G `wie unbekannte Id: ja` | ja (Phase 25 K4: Notiz-Id gleich fileid) | raw/27-07-live.txt |
| notes_create in getaggte Kategorie | SC3 | `wie fehlender Elternordner, nichts geschrieben: ja (... notes=66->66)` | ja | raw/27-07-live.txt |
| Findling-Treffer mit nur fileId | test_findling_sandbox.py | lokal `SKIPPED ... the findling provider is not installed on this instance` | **nicht live belegt**, läuft im CI-Job exapp (siehe "Nicht live belegt") | keine |

SC3-Zeilen im maßgeblichen Lauf: 8, alle `ja`.

## Erfolgskriterium 4: Talk

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Nachricht mit geteilter getaggter Datei | SC4 | `talk_browse messages zeigt die getaggte Freigabe nur als {file}: ja (... name_im_text=False)`; `conversations last_message ohne den Namen: ja (last_message='{file}')`; `fetch message ohne den Namen: ja (text='From: alice\n{file}')` | ja | raw/27-07-live.txt |
| Gegenprobe | SC4 | `Gegenprobe offene Freigabe zeigt den Namen: ja (offen_im_text=True)` | der Platzhalter kommt vom Ausschluss, nicht von einem Formatfehler | raw/27-07-live.txt |
| Datei-Raum der getaggten Datei | SC4 | `Datei-Raum fehlt in conversations: ja (roh_in_liste=True antwort=False)`; `messages wie erfundenes Token: ja` | ja | raw/27-07-live.txt |

SC4-Zeilen im maßgeblichen Lauf: 6, alle `ja`; Aufräumen `CLEANUP SC4 shares left: 0, file conversation still listed: False`.

## Erfolgskriterium 5: nicht beantwortbar und Schweigen

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Listen | SC5, REPORT per respx auf 500 | files_list, notes_search, talk_browse je genau ein Eintrag `{'source': 'exclusion', ...}` | ja | raw/27-07-live.txt |
| Einzelzugriffe | SC5 | files_read (offen und erfunden identisch), files_upload (`PROPFIND=404`), fetch(file): der uniforme Satz `The exclusion check (tag kein-ki) could not be answered, ...` | ja | raw/27-07-live.txt |
| Suche und Bündel | SC5 | unified_search `treffer=0 datei=0 degraded=['exclusion']`; prepare_context `exclusion=1` | ja, genau ein Eintrag | raw/27-07-live.txt |
| ein REPORT je Aufruf | SC5 | `# SC5 injected REPORT 500 answered 9 times` | eine Flight je Tool-Aufruf | raw/27-07-live.txt |
| Schweigen im Erfolgsfall | SC5 | `alle Werkzeuge Schweigen im Erfolgsfall: ja (14 Antworten ohne Zähler/Hinweis, laut={})` | ja | raw/27-07-live.txt |

SC5-Zeilen im maßgeblichen Lauf: 9, alle `ja`.

## Wanduhr prepare_context

**Referenz:** Phase 25 K3 auf nc35 (`.planning/phases/25-mess-spike-tag-abfrage/raw/nc35-prepare-context-baseline.txt`, 26.09.2026): detail='short' Median 0,72 s, detail='full' Median 0,81 s (je 3 Läufe).

**Herleitung der Schwelle (Plan 27-08, verbindlich):**

- Guard-Flight bei gesetztem Tag, seriell und damit konservativ addiert: Tag-Liste 48 ms plus REPORT Stufe 1 59 ms = 0,107 s
- Rauschreserve 0,05 s
- short: 0,72 + 0,107 + 0,05 = 0,877 s, gerundet **0,88 s**
- full: 0,81 + 0,107 + 0,05 = 0,967 s, gerundet **0,97 s**
- Maß: Median über 5 Läufe nach 1 Aufwärmlauf, frisches NcClients mit neuem ExclusionGuard je Aufruf

**Messlauf (27.09.2026, 13:55 +0200):** Szenario A ohne kein-ki-Tag, Szenario B mit kein-ki auf einer Testdatei und einem Testordner (beide tragen das Suchwort "Abnahme" im Namen, der Guard hält also wirklich Treffer zurück). Beide Szenarien laufen auf denselben Testdaten.

```
WANDUHR szenario=A detail=short median=0.786 min=0.761 max=0.816 schwelle=0.88 urteil=innerhalb
WANDUHR szenario=A detail=full median=0.937 min=0.917 max=0.991 schwelle=0.97 urteil=innerhalb
WANDUHR szenario=B detail=short median=0.797 min=0.795 max=0.847 schwelle=0.88 urteil=innerhalb
WANDUHR szenario=B detail=full median=1.047 min=1.000 max=1.079 schwelle=0.97 urteil=ueberschritten
```

| Szenario | detail | Median | Schwelle | Urteil |
|---|---|---|---|---|
| A | short | 0,786 s | 0,88 s | innerhalb |
| A | full | 0,937 s | 0,97 s | innerhalb |
| B | short | 0,797 s | 0,88 s | innerhalb |
| B | full | 1,047 s | 0,97 s | **überschritten** (um 0,077 s) |

**Befund, nicht stiller Pass:** B full liegt 0,077 s über der Schwelle.

Zur Einordnung stehen in derselben Rohdatei zwei Anhänge:

- **Vorlauf** (13:52 +0200, erster Lauf desselben Tests): A short 0,808 innerhalb, A full 1,033 überschritten, B short 0,855 innerhalb, B full 1,072 überschritten.
- **Kontrolle mit dem Code vor Phase 27** (Commit 2f03242, NcClients ohne Guard, gleicher Host, gleiche Instanz, gleicher Nachmittag, drei Läufe): short Median 0,78 / 0,85 / 0,82 s, full Median 0,99 / 1,05 / 1,07 s.

Deutung aus diesen Zahlen:

- Ohne jeden Phase-27-Code liegt full heute bei 0,99 bis 1,07 s, also schon über 0,97 s. Die Referenz 0,81 s vom 26.09. ist auf diesem Host heute nicht mehr der Grundwert; die Drift von Host und Instanz beträgt für full etwa 0,2 s und für short etwa 0,1 s.
- Der Messlauf B full (1,047 s) liegt innerhalb der Kontrollspanne des Codes ohne Guard.
- Der Abstand B minus A im selben Lauf beträgt 0,011 s (short) und 0,110 s (full). Er liegt unter dem eingeplanten Guard-Anteil von 0,107 s plus 0,05 s Rauschreserve. Ein Teil des Abstands in full kommt von den Ausschnitten: in A war ein Ausschnitt der Testordner (fetch lehnt ihn sofort ab), in B wird dieser Treffer zurückgehalten und ein echter Dateiausschnitt gelesen.
- Die obere Grenze `CALENDAR_BUDGET` hielt in allen Läufen; kein Bein lief in sein Budget.

**Offener Entscheid für den Owner:** Schwelle akzeptieren mit Begründung (Host-Drift, belegt durch die Kontrolle), oder Nacharbeit als Lückenplan.

### Nach dem Lückenplan 27-09

**Datum:** 27.09.2026, Messlauf 15:04:31 +0200 (ganze Datei `test_ctx_bundle.py`, 10 passed)

**Kommando:** `set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest tests/integration/test_ctx_bundle.py -m integration -s` (in der Worktree-Isolation über einen kurzen Python-Lader derselben Env-Datei, `PYTHONIOENCODING=utf-8`)

**Was 27-09 geändert hat:** Die Datei-Ausschnitte eines Bündels lösen ihre fileids mit einer gemeinsamen SEARCH auf statt mit einer je Ausschnitt, und `files.read` nimmt den Eintrag dieser SEARCH als `known` statt eines zweiten stat-PROPFIND. Der Guard wird in jedem Zweig gefragt; die Antwort-Bytes sind laut `tests/unit/test_excerpt_batch.py` gleich (Paarvergleich mit dem Weg vor 27-09). Szenarien, 5 Läufe nach 1 Aufwärmlauf, frischer Guard je Aufruf und die Schwellen 0,88 s / 0,97 s sind unverändert.

```
WANDUHR szenario=A detail=short median=0.776 min=0.732 max=0.851 schwelle=0.88 urteil=innerhalb
WANDUHR szenario=A detail=full median=0.919 min=0.877 max=1.011 schwelle=0.97 urteil=innerhalb
WANDUHR szenario=B detail=short median=0.827 min=0.780 max=0.862 schwelle=0.88 urteil=innerhalb
WANDUHR szenario=B detail=full median=0.992 min=0.942 max=1.402 schwelle=0.97 urteil=ueberschritten
```

| Szenario | detail | Median | Schwelle | Urteil |
|---|---|---|---|---|
| A | short | 0,776 s | 0,88 s | innerhalb |
| A | full | 0,919 s | 0,97 s | innerhalb |
| B | short | 0,827 s | 0,88 s | innerhalb |
| B | full | 0,992 s | 0,97 s | **überschritten** (um 0,022 s) |

**Befund, nicht stiller Pass:** B full liegt auch nach 27-09 über der Schwelle, jetzt um 0,022 s statt 0,077 s.

**Wiederholung** desselben Codes (Anhang 1 der Rohdatei, 15:06:19 +0200, nur der Wanduhr-Test): A short 0,795, A full 0,919, B short 0,811 innerhalb; B full 1,028 überschritten.

**Kontrolle Code vor 27-09** (Anhang 2 der Rohdatei; Code von ac479c6, gleicher Host, gleiche Instanz, dieselbe Sitzung, je 5 Läufe; Kontrolle 1 im Worktree vor dem ersten 27-09-Commit, Kontrollen 2 und 3 aus `git archive ac479c6` in ein nicht committetes, danach gelöschtes Verzeichnis):

| Lauf | Zeit | A short | A full | B short | B full |
|---|---|---|---|---|---|
| Kontrolle 1 (vor 27-09) | 14:43 | 0,910 | 0,991 | 0,855 | 1,059 |
| **Messlauf (nach 27-09)** | 15:04 | 0,776 | 0,919 | 0,827 | **0,992** |
| Kontrolle 2 (vor 27-09) | 15:05 | 0,786 | 0,994 | 0,813 | 1,020 |
| Wiederholung (nach 27-09) | 15:06 | 0,795 | 0,919 | 0,811 | 1,028 |
| Kontrolle 3 (vor 27-09) | 15:06 | 0,761 | 1,095 | 0,848 | 1,035 |

**Vergleich B full vorher/nachher:**

- gegen 27-08 (1,047 s): Messlauf 0,992 s, Differenz 0,055 s
- gegen die Kontrollen derselben Sitzung (Median der drei Kontroll-Mediane 1,035 s): Messlauf 0,043 s schneller, Wiederholung 0,007 s schneller
- A full zum Vergleich: Kontrollen 0,991 / 0,994 / 1,095 s, nach 27-09 zweimal 0,919 s, also etwa 0,07 s schneller und beide Male innerhalb

Deutung aus diesen Zahlen:

- In A sind alle drei Ausschnitte Dateien (`ausschnitte=file,file,file`), dort wirkt der Fix voll: eine SEARCH statt drei, kein PROPFIND, etwa 0,07 s.
- In B sind die Ausschnitte `file,file,note`. Die Notiz liest `notes.read`, das bei getaggtem Ordner den Pfad der Notiz mit einer eigenen fileid-SEARCH prüft (Plan 27-04). Diese Kette bleibt nach dem Plan unverändert (Notizen warten nie auf die Sammel-SEARCH und werden nicht in sie aufgenommen). Die Einsparung in B ist deshalb kleiner und liegt in der Größenordnung der Streuung zwischen zwei Läufen desselben Codes (0,992 und 1,028 s). Dass die Notizkette jetzt der längste Ausschnitt in B ist, ist eine Vermutung aus der Request-Zählung, nicht je Bein gemessen.
- Die Schwellen sind nicht angefasst; über 0,97 s ist B full weiterhin ein offener Befund für den Owner.

### Nach dem Lückenplan 27-10

**Datum:** 27.09.2026, Messlauf 15:44:28 +0200 (ganze Datei `test_ctx_bundle.py`, 10 passed), Messlauf 2 um 15:53:39 +0200 (ganze Datei, 10 passed)

**Kommando:** `set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest tests/integration/test_ctx_bundle.py -m integration -s` (in der Worktree-Isolation über einen kurzen Python-Lader derselben Env-Datei, `PYTHONIOENCODING=utf-8`, `PYTHONPATH=src`)

**Was 27-10 geändert hat:** Die Notiz-Ausschnitte eines Bündels mit Datei-Ausschnitt prüfen ihren Pfad in derselben Sammel-SEARCH, die die fileids der Datei-Ausschnitte auflöst, und warten auf sie erst dort, wo `notes.read` den Pfad braucht; die Antwort-Bytes sind laut `tests/unit/test_excerpt_batch.py` gleich (Paarvergleich mit dem Weg vor 27-10). Szenarien, 5 Läufe nach 1 Aufwärmlauf, frischer Guard je Aufruf und die Schwellen 0,88 s / 0,97 s sind unverändert.

```
WANDUHR szenario=A detail=short median=1.620 min=1.394 max=1.994 schwelle=0.88 urteil=ueberschritten
WANDUHR szenario=A detail=full median=1.772 min=1.639 max=1.931 schwelle=0.97 urteil=ueberschritten
WANDUHR szenario=B detail=short median=2.471 min=2.152 max=3.616 schwelle=0.88 urteil=ueberschritten
WANDUHR szenario=B detail=full median=2.163 min=1.208 max=2.194 schwelle=0.97 urteil=ueberschritten
```

| Szenario | detail | Median | Schwelle | Urteil |
|---|---|---|---|---|
| A | short | 1,620 s | 0,88 s | **überschritten** |
| A | full | 1,772 s | 0,97 s | **überschritten** |
| B | short | 2,471 s | 0,88 s | **überschritten** |
| B | full | 2,163 s | 0,97 s | **überschritten** (um 1,193 s) |

**Befund, nicht stiller Pass:** Im maßgeblichen Messlauf liegen alle vier Zeilen über der Schwelle, auch A short (27-09 am selben Tag: 0,776 s). Das ist nicht der Code von 27-10: die Kontrolle mit dem Code vor 27-10 direkt davor (15:42) lag genauso hoch (B full 2,151 s). Der Host war in dieser Sitzung stark gedriftet (Anhang 3 der Rohdatei): der Notes-Provider der Suche brauchte einzeln per curl 0,64 bis 1,06 s (status.php 0,03 s, Datei-Provider 0,07 bis 0,14 s, PHP-Rechenschleife im Container unauffällig). Die Wanduhr ist in dieser Sitzung deshalb nicht entscheidungsfähig, weder für noch gegen 27-10.

**Wiederholungen und Kontrollen** (Anhang 1 und 2 der Rohdatei, abwechselnd, je 5 Läufe nach 1 Aufwärmlauf; Kontrolle = Code von 43c5a9d aus `git archive 43c5a9d` in ein nicht committetes, danach gelöschtes Verzeichnis im Worktree, dort nur der Wanduhr-Test per `-k`; jede Kontroll-LAUF-Zeile B full zeigt `files-search=3`, also wirklich den alten Code):

| Lauf | Zeit | A short | A full | B short | B full |
|---|---|---|---|---|---|
| Kontrolle 1 (vor 27-10) | 15:42 | 1,288 | 2,185 | 2,140 | 2,151 |
| **Messlauf (nach 27-10)** | 15:44 | 1,620 | 1,772 | 2,471 | **2,163** |
| Wiederholung 1 (nach 27-10) | 15:46 | 1,311 | 1,568 | 1,201 | 2,917 |
| Kontrolle 2 (vor 27-10) | 15:47 | 1,767 | 1,926 | 1,746 | 1,971 |
| Wiederholung 2 (nach 27-10) | 15:48 | 1,527 | 1,600 | 1,629 | 1,759 |
| Kontrolle 3 (vor 27-10) | 15:51 | 0,929 | 1,039 | 0,911 | 1,769 |
| Wiederholung 3 (nach 27-10) | 15:52 | 0,863 | 0,967 | 0,799 | 0,963 |
| Kontrolle 4 (vor 27-10) | 15:52 | 0,887 | 0,894 | 0,849 | 0,981 |
| Messlauf 2 (nach 27-10, ganze Datei) | 15:53 | 0,928 | 1,125 | 1,008 | 1,039 |
| Kontrolle 5 (vor 27-10) | 15:54 | 1,442 | 1,749 | 1,310 | 1,130 |
| Wiederholung 4 (nach 27-10) | 15:55 | 1,159 | 1,082 | 1,198 | 1,383 |

**Vergleich B full vorher/nachher:**

- gegen 27-09 (0,992 s): Messlauf 2,163 s, Messlauf 2 1,039 s; in keinem der sechs Läufe nach 27-10 außer Wiederholung 3 (0,963 s) unter 0,97 s
- gegen die Kontrollen derselben Sitzung: Median der sechs Mediane nach 27-10 1,571 s, der fünf Kontroll-Mediane 1,769 s; die Streuung zwischen benachbarten Läufen (bis 1,2 s) ist um ein Vielfaches größer als die erwartete Einsparung (0,03 bis 0,06 s)
- im ruhigsten Fenster (15:51 bis 15:53): Wiederholung 3 mit allen vier Zeilen innerhalb (B full 0,963 s) gegen Kontrolle 4 (B full 0,981 s, A short 0,887 s überschritten); Messlauf 2 kurz danach wieder 1,039 s

Deutung aus diesen Zahlen:

- Belegt ist die Request-Seite: B full liest `file,file,note` jetzt mit `files-search=2` (1 Guard, 1 Sammel-SEARCH) statt 3, 24 bis 25 statt 25 bis 26 Requests, `propfind=0`, `exclusion-report=1` in jeder LAUF-Zeile B, in allen 36 LAUF-Zeilen B full nach 27-10 (Kontrollen durchgehend `files-search=3`).
- Nicht belegt ist die Wanduhr: die Drift des Hosts überdeckt in dieser Sitzung jede Wirkung des Plans. Die Schwellen sind nicht angefasst, es wurde nichts außerhalb des Plans getunt.
- Für eine entscheidungsfähige Zahl braucht es eine Neumessung in einem ruhigen Fenster (Notes-Provider wieder im Bereich von 27-09), wieder abwechselnd mit der Kontrolle.

## Request-Kosten eines Bündels (neu verankert, gemessen)

Kategorien des Guards eigenständig gezählt (Pitfall 7): `exclusion-tags` (PROPFIND /remote.php/dav/systemtags), `exclusion-report` (REPORT auf /remote.php/dav/files/), `files-search` (SEARCH auf die DAV-Wurzel).

| Fall | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| ohne Tag, kalte Caches | test_the_request_cost_of_one_bundle_cold_and_warm | `REQUESTS cold total=23 ... exclusion-tags=1 ...` | eine Tag-Liste, kein REPORT, kein SEARCH | raw/27-08-prepare-context.txt |
| ohne Tag, warme Caches | dasselbe | `REQUESTS warm total=20 ... exclusion-tags=1 ...` | eine Tag-Liste auch warm: eine leere Namensauflösung wird nie gecacht (ein neues Tag muss sofort greifen) | raw/27-08-prepare-context.txt |
| A short | Messung 1b | `requests=20 guard[exclusion-tags=1,exclusion-report=0,files-search=0]` | 1 Guard-Request | raw/27-08-prepare-context.txt |
| A full | Messung 1b | `requests=28 guard[exclusion-tags=1,exclusion-report=0,files-search=3]` | die 3 SEARCH sind die fileid-Auflösungen der drei Ausschnitte durch fetch, nicht der Guard | raw/27-08-prepare-context.txt |
| B short | Messung 1b | Aufwärmlauf `exclusion-tags=1,exclusion-report=1,files-search=1`; danach `requests=21 guard[exclusion-tags=0,exclusion-report=1,files-search=1]` | Tag-Liste nur beim ersten Aufruf (Name-zu-Id-Cache, 60 s), dann 1 REPORT und 1 fileid-SEARCH für pfadlose Treffer | raw/27-08-prepare-context.txt |
| B full | Messung 1b | `requests=29 guard[exclusion-tags=0,exclusion-report=1,files-search=4]` | 1 REPORT, 1 Guard-SEARCH plus 3 Ausschnitt-SEARCH | raw/27-08-prepare-context.txt |

Der Guard kostet damit je Bündel eine Tag-Liste (ohne Tag) oder einen REPORT plus höchstens eine fileid-SEARCH (mit Tag, warmer Cache), nie einen Request je Bein.

**Nach dem Lückenplan 27-09** (Messlauf 15:04:31 +0200, neues Feld `propfind=` zählt PROPFIND unter /remote.php/dav/files/, `ausschnitte=` die gelesenen Arten):

| Fall | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| A full | Messung 1b | `requests=23 guard[exclusion-tags=1,exclusion-report=0,files-search=1] propfind=0 ausschnitte=file,file,file` (vorher 28 Requests, files-search 3) | eine Sammel-SEARCH für drei Datei-Ausschnitte, kein stat-PROPFIND | raw/27-09-prepare-context.txt |
| B full | Messung 1b | `requests=26 guard[exclusion-tags=0,exclusion-report=1,files-search=3] propfind=0 ausschnitte=file,file,note` (einmal 25; vorher 28 bis 29, files-search 4) | 1 REPORT; SEARCH: 1 Guard (pfadlose Treffer), 1 Sammel-SEARCH der zwei Datei-Ausschnitte, 1 Pfadprüfung der Notiz | raw/27-09-prepare-context.txt |

Korrektur der Deutung der 27-08-Zeile B full: Die vier SEARCH dort waren 1 Guard plus 2 Datei-Ausschnitte plus 1 Pfadprüfung des Notiz-Ausschnitts (die Ausschnitte in B sind zwei Dateien und eine Notiz), nicht 3 Ausschnitt-SEARCH. Die Zahl selbst bleibt richtig. Jede Antwort kostet weiterhin höchstens einen REPORT, in jeder LAUF-Zeile B `exclusion-report=1`.

Die Live-Beweise von 27-07 liefen nach Task 1 von 27-09 einmal erneut (`raw/27-09-exclusion-live.txt`, 15:08:32 +0200): 10 passed, 57 Zeilen `: ja`, keine Zeile `: nein`.

**Nach dem Lückenplan 27-10** (Messlauf 15:44:28 +0200 und alle Wiederholungen):

| Fall | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| A full | Messung 1b | `requests=23 guard[exclusion-tags=1,exclusion-report=0,files-search=1] propfind=0 ausschnitte=file,file,file` | unverändert zu 27-09: drei Datei-Ausschnitte, eine Sammel-SEARCH, keine Notiz | raw/27-10-prepare-context.txt |
| B full | Messung 1b | `requests=25 guard[exclusion-tags=0,exclusion-report=1,files-search=2] propfind=0 ausschnitte=file,file,note` (einzelne Läufe 24; vorher 25 bis 26, files-search 3) | 1 REPORT; SEARCH: 1 Guard (pfadlose Treffer), 1 Sammel-SEARCH für beide Datei-Ausschnitte und die Pfadprüfung der Notiz | raw/27-10-prepare-context.txt |

Die Live-Beweise von 27-07 liefen nach Task 1 von 27-10 einmal erneut (`raw/27-10-exclusion-live.txt`, 15:56:08 +0200): 10 passed, 57 Zeilen `: ja`, keine Zeile `: nein`.

## Probe-Befunde

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| talk-message-Klasse | test_exclusion_probe (27-03) | `KLASSE=kein-leak`, `UNTERSCHEIDUNG=keine`; Suche nach Dateiname und Namensstamm 0 Einträge, nach Textwort 1 Eintrag | der talk-message-Provider verrät geteilte Dateinamen nicht, Klasse kein-leak | raw/27-03-provider-probe.txt |
| comments-Form | 27-03 | `COMMENTS_FILEID_AUS=url`; `resourceUrl: "/f/22097"`, `attributes: []`, Pfad in der subline | die fileid steht nur in der URL; der Treffer wird über `file_refs` aufgelöst | raw/27-03-provider-probe.txt |
| Datei-Konversation | 27-05 | `GET /apps/spreed/api/v1/file/22098: HTTP 200 ... "token":"8dhxnjqf"`; v4 `HTTP 404`; `OBJECT_TYPE=file`, `OBJECT_ID_IST_FILEID=ja`, `NAME_IST_DATEINAME=ja` | ein Datei-Raum trägt die fileid als objectId und den Dateinamen als Raumnamen; Route nur unter api/v1 | raw/27-05-file-conversation-probe.txt |
| Notes-settings | 27-04 | `HTTP 200 {"notesPath":"Notes","fileSuffix":".md",...}` | Ablage /Notes, Endung .md, wie im Plan angenommen | raw/27-04-notes-settings.txt |
| A1-Latenz paths_of_fileids | test_exclusion_live, A1 | `n=1: median=27.9 max=28.5`; `n=25: median=29.3 max=30.3`; `n=50: median=30.7 max=31.8` (ms, 5 Läufe nach 1 Aufwärmlauf) | ein Block mit 50 Ids kostet praktisch dasselbe wie eine Id; deckt die in der Schwelle ungemessene fileid-SEARCH innerhalb der Rauschreserve | raw/27-07-live.txt |

## Nicht live belegt

- **Findling-Fall (SBX-01):** `tests/integration/test_findling_sandbox.py` braucht einen echten Findling-Provider. nc35 hat keinen; lokal endet der Lauf mit `SKIPPED ... the findling provider is not installed on this instance; CI installs it with scripts/install_findling.sh`. Der Test ist im CI-Job exapp als Schritt "Findling hits run through sandbox and exclusion (SBX-01)" direkt nach dem Content-hit-Schritt verdrahtet und läuft beim nächsten Push. Bis dahin ist der Findling-Teil von Erfolgskriterium 3 nur durch den gleichartigen comments-Fall (pfadlos, nur fileid) live belegt.

## Merker für Phase 28

- Klassifikations-Freeze: **talk_send ist betroffen** (über `one_room`: Token eines Datei-Raums einer getaggten Datei wird vor dem POST wie ein unbekanntes Token abgewiesen, bei nicht prüfbar mit dem uniformen Fehler).
- Klassifikations-Freeze: **notes_create ist betroffen** (prüft Ablage und Kandidatdatei vor jedem POST).
- **ChatGPT-search trägt kein degraded-Feld;** die exclusion-Degradation steht dort wie jeder andere Providerausfall nicht im Draht. fetch(message) trägt dagegen `metadata["degraded"]`.
- **Provider-cursors** werden unverändert weitergereicht (T-27-25 accept); Kanarientest in Phase 28.

## Merker für Phase 29

- **Upload-Grenzfall-Restorakel:** eine direkt getaggte Datei unter sichtbarem Elternordner bekommt `dav.parent_missing(target)`; die Abweisung unterscheidet sich vom Erfolg (T-27-16 accept).
- **Titel-Sanitisierung bei notes_create:** die Notes-App bildet aus dem Titel den Dateinamen; weicht der Kandidatpfad vom echten Namen ab, wird eine Kollision mit einer getaggten Notiz nicht erkannt (T-27-35 accept).
- **Notizen außerhalb der Root verschwinden** (gemessen: `count=0 skipped=3`); die Doku muss sagen, dass `NC_MCP_FILES_ROOT` auch Notes begrenzt.
- **Talk hat keine Sandbox für Dateinamen:** mit gesetzter Root und getaggtem Ordner bleiben pfadlose Datei-Verweise außerhalb der Root roh (T-27-46 accept).
- **Case-insensitive externe Speicher:** der Präfixvergleich kann einen getaggten Ordner in anderer Schreibweise verfehlen; Einzelzugriffe fangen das über die fileid aus `stat` ab, Teilbäume nicht (27-RESEARCH Pitfall 6, A7).
- **Merker (c) gelöst ohne shield:** der Guard ist erstes gather-Mitglied von prepare_context ohne eigenes Budget statt `asyncio.shield`; jedes Bein fragt den Guard selbst und entscheidet fail-closed.
- Aus 27-08: die Referenz einer Wanduhr-Schwelle muss am selben Tag auf demselben Host mit dem Code ohne das neue Feature gemessen werden, sonst misst die Schwelle die Drift des Hosts.

## Abnahme

Owner-Entscheid 27.09.2026 am Checkpoint 27-08 (wörtlich): "Lückenplan".

Die Überschreitung der Wanduhr-Schwelle (Szenario B, detail=full: Median 1,047 s gegen 0,97 s) wird NICHT akzeptiert. Es wird ein Lückenplan angelegt (/gsd:plan-phase 27 --gaps, Ansatzpunkt laut Checkpoint-Vorlage: fileid-Auflösung seltener aufrufen). Die Phase bleibt offen, bis die Messung unter der Schwelle liegt und die Abnahme erneut vorgelegt wurde. Alle übrigen Befunde (Erfolgskriterien 1-5, Request-Kosten, talk-message kein-leak, Merker für Phase 28/29) standen am Checkpoint nicht in Frage.

Owner-Entscheid 27.09.2026 zu 27-09 (wörtlich): "Zweiter Lückenplan".

Die Restüberschreitung (B full 0,992 s gegen 0,97 s) wird nicht akzeptiert. Nächster Schritt laut Checkpoint-Vorlage: die Pfadprüfung der Notiz in dieselbe Sammel-SEARCH holen (Notiz-Id = fileid, Beleg 25-MESSBERICHT). Die Phase bleibt offen bis zur Neumessung unter der Schwelle und erneuter Abnahme.

Owner-Entscheid 27.09.2026 zu 27-10 (wörtlich): "Neumessung ruhiges Fenster".

Kein weiterer Code-Umbau. Die Wanduhr-Messung vom 27.09. nachmittags ist wegen Host-Drift (Nachbarläufe streuen bis 1,2 s, auch der alte Code lag in den Kontrollen weit über der Schwelle) nicht entscheidungsfähig. Die Messung wird in einem ruhigen Host-Fenster wiederholt, wieder abwechselnd mit der Kontrolle; der Entscheid fällt danach.
