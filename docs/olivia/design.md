# MCP Connector "olivia" – fork per il recupero autonomo dei file da claude.ai

Data: 2026-09-29 · Stato: design approvato a voce, in revisione scritta

## 1. Obiettivo

Usando il connettore Nextcloud da claude.ai web e Claude Desktop, Claude deve poter
**recuperare e leggere in autonomia** i file che gli servono (PDF, Word, Excel, immagini),
senza che l'utente intervenga.

**Criterio di successo:** in Claude Desktop, alla richiesta "leggi il PDF X da Nextcloud",
Claude cerca il file, ottiene un link, lo scarica dal proprio ambiente di esecuzione e
risponde sul contenuto. Lo stesso per un file Word.

## 2. Fatti verificati (2026-09-29) su cui poggia il design

| Fatto | Come è stato verificato |
|---|---|
| Il client connettori di Anthropic (claude.ai, Desktop, mobile, Cowork) accetta nei risultati degli strumenti solo testo e immagini | Documentazione "Build an MCP server for Claude" |
| `files_download` del connettore 0.3.2 restituisce il file come embedded resource binaria: in Claude Desktop non arriva | Prova dell'utente in Claude Desktop |
| Il connettore non espone risorse MCP (`resources/list` = 0, nessuna opzione) e in claude.ai le risorse le allega l'utente | Chiamata live al connettore; guida MCP "Connect to remote servers" |
| `web_fetch` rifiuta gli URL ricevuti da un connettore MCP, con o senza token | Prova in Claude Desktop (`PERMISSIONS_ERROR: This URL was not in any prior search or fetch result`) |
| L'**ambiente di esecuzione** di Claude scarica quegli URL, anche con token, da `nextcloud.olivia.casa` via Cloudflare | Prova in Claude Desktop con link di condivisione Nextcloud: 200, PDF identico (SHA-256), token errato 404 |
| Limite di una risposta di strumento in claude.ai/Desktop: ~150.000 caratteri | Documentazione Anthropic |
| Il nome `mcp_connector` compare 155 volte nel codice | `grep` sul sorgente v0.3.2 |

## 3. Decisioni

1. **Fork** di `street1983nk/nextcloud-mcp-connector` (AGPL-3.0) a partire dalla release **v0.3.2**, pubblico su `github.com/aledrosera/nextcloud-mcp-connector`.
2. Si cambiano **solo** quattro comportamenti (§6); tutto il resto resta identico all'originale.
3. Il link di download è **servito dal connettore stesso**; nessuna condivisione Nextcloud.
4. Un link vale **un download completato** oppure scade dopo **10 minuti** (configurabile 1–60).
5. **App separata** `mcp_connector_olivia`, installata accanto all'originale.
6. Rinomina dell'app **automatica in fase di build**, non nel sorgente.
7. Aggiornamenti rispetto all'autore **manuali, su richiesta**.

## 4. Architettura e ciclo di vita

- **Repository:** i nostri cambiamenti sono commit separati sopra il tag `v0.3.2` dell'autore. Aggiornare = ribasare quei commit sulla release nuova.
- **Rinomina:** `scripts/olivia-rename.sh` sostituisce `mcp_connector` con `mcp_connector_olivia` dove indica **l'app** (id in `info.xml`, prefisso dei comandi occ, percorsi `/exapps/...`, testi, nome immagine), sia nel codice sia **nei test**, con le stesse regole. I nomi dei **moduli Python** (`mcp_connector.*`) non cambiano. Lo script è idempotente e gira nel workflow di build prima dei test e di `docker build`.
- **Versione:** `<version>` in `info.xml` resta quella dell'autore (`0.3.2`); il nostro contatore sta solo nel tag git e nell'`<image-tag>` (`0.3.2-olivia.1`), perché una versione con lettere potrebbe non superare la validazione di AppAPI.
- **Immagine:** il workflow `release.yml` dell'autore, modificato da un nostro commit (esegue la rinomina, poi i test, poi la build, e tagga `mcp_connector_olivia` invece del nome scritto a mano), avviato da un tag `v<versione autore>-olivia.<n>` (primo: `v0.3.2-olivia.1`), pubblica l'immagine pubblica `ghcr.io/aledrosera/mcp_connector_olivia:<tag>`, multi-arch come l'originale.
- **Installazione:** `occ app_api:app:register mcp_connector_olivia harp --info-xml <info.xml rinominato> --env NC_MCP_PUBLIC_URL=https://nextcloud.olivia.casa/exapps/mcp_connector_olivia --wait-finish`. Dati propri (volume `nc_app_mcp_connector_olivia_data`, config AppAPI propria).
- **In Claude:** nuovo connettore personalizzato `https://nextcloud.olivia.casa/exapps/mcp_connector_olivia/mcp`, login una volta.
- **Aggiornamenti:** su richiesta dell'utente: rebase, suite completa di test, nuovo tag, reinstallazione.

## 5. Componente "link di download"

### 5.1 Tabella `download_tickets` (file separato `downloads.sqlite3` nello stesso volume persistente, `CREATE TABLE IF NOT EXISTS`; separato da `oauth.sqlite3` per non toccare il database OAuth dell'autore e ridurre i conflitti agli aggiornamenti)

| Colonna | Contenuto |
|---|---|
| `token_hash` (PK) | SHA-256 del token; il token in chiaro non viene mai salvato |
| `authorization_id` | collegamento OAuth che ha creato il link (NULL in modalità AppAPI diretta) |
| `nc_user` | utente Nextcloud |
| `path` | percorso del file nell'area file dell'utente |
| `name`, `content_type`, `size` | dal `stat` WebDAV al momento della creazione |
| `created_at`, `expires_at` | epoch secondi |
| `state` | `ready` \| `in_progress` \| `used` |

### 5.2 Creazione

Chiamata da `files_download` e da `fetch` (file binari), con le credenziali della richiesta:
1. `stat` WebDAV del percorso (esiste, è un file, è leggibile); le cartelle sono rifiutate.
2. Token `secrets.token_urlsafe(32)` (256 bit); si salva l'impronta.
3. Pulizia pigra: si cancellano le righe `used` o scadute da più di 1 ora.
4. Risultato: `https://<public_url>/dl/<token>` con `<public_url>` = `NC_MCP_PUBLIC_URL`.

### 5.3 Rotta pubblica `GET|HEAD /dl/{token}`

Dichiarata in `info.xml` (`^/dl/[A-Za-z0-9_-]{20,}$`, verbi `GET,HEAD`, `PUBLIC`) e montata in `entry_exapp.py`.

- Token sconosciuto, scaduto, `used` o `in_progress` (download concorrente), collegamento OAuth revocato → **404** con corpo identico in tutti i casi.
- `HEAD` → intestazioni (`Content-Type`, `Content-Length`, `Content-Disposition`), **non consuma**.
- `GET`:
  1. transizione atomica `ready → in_progress` (UPDATE condizionato);
  2. ricostruzione delle credenziali: se `authorization_id` è valorizzato, dall'autorizzazione (password d'app decifrata con la data key, stessa logica del middleware OAuth, rispetto della revoca); altrimenti impersonazione AppAPI di `nc_user`;
  3. `GET` WebDAV in **streaming** (nuova funzione `dav.stream_file`), risposta `StreamingResponse` con `Content-Type`, `Content-Length`, `Content-Disposition: attachment; filename*=UTF-8''<nome>`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`;
  4. trasferimento completato → `used`; errore o disconnessione → di nuovo `ready`;
  5. Nextcloud non raggiungibile prima dell'invio → **502**, biglietto di nuovo `ready`.

### 5.4 Configurazione

Nuovo campo del form amministrativo `download_ttl_minutes` (numero, default 10, 1–60) e variabile `NC_MCP_DOWNLOAD_TTL_MINUTES` dichiarata in `info.xml`. Precedenza come per gli altri campi: form > variabile > default. Valori fuori intervallo → default.

### 5.5 Riservatezza

- Nel log di accesso il percorso `/dl/<token>` è mascherato (`/dl/<primi 4 caratteri>…`).
- Registro delle chiamate (se attivo): il "link emesso" è registrato come chiamata di `files_download`/`fetch` dal meccanismo esistente; il "file consegnato" va nel log del container (utente, nome file, token mascherato), non nella catena del registro.
- Tentativi ripetuti: già limitati da HaRP (ban dopo 10 errori in 300 s).

## 6. Modifiche agli strumenti (i nomi restano invariati)

1. **`files_download(path)`** → solo testo: `{path, name, size, content_type, download_url, expires_at, single_use: true, how_to}`; `how_to` = "scarica con l'ambiente di esecuzione (curl -L / requests); web_fetch non apre questo link". Rimossi `offset`, `chunk_bytes` e l'embedded resource.
2. **`fetch`** su file non testuali (PDF, Office, immagini, archivi…) → stessa scheda con `download_url` invece dell'errore; i file di testo restano invariati. I risultati del provider **`findling`** con URL `/f/<id>` diventano id `file:<id>` (fetchabili).
3. **`files_read`**: blocco predefinito **64 KiB** (era 512 KiB); `truncated`/`next_offset` invariati. Test: la risposta JSON resta sotto 150.000 caratteri anche nel caso peggiore di escape.
4. **`fetch`** su eventi: testo con **descrizione** e **luogo**; nome del calendario = nome visualizzato. Su mail: `url` = link diretto al **messaggio** nell'app Mail (formato da verificare sulla versione di Mail installata prima dell'implementazione).

## 7. Errori

| Caso | Comportamento |
|---|---|
| file inesistente / cartella / permesso negato | errori già esistenti del connettore |
| database non disponibile alla creazione | errore esplicito "impossibile creare il link", nessun link restituito |
| link non valido per qualsiasi motivo | 404 identico |
| Nextcloud irraggiungibile prima dello streaming | 502, biglietto di nuovo `ready` |
| interruzione durante lo streaming | connessione chiusa, biglietto di nuovo `ready` |

## 8. Test

- **Suite dell'autore** (122 file) verde sul sorgente del fork e sull'albero rinominato (la rinomina si applica anche ai test).
- **Nuovi test:** biglietti (impronta, scadenza, consumo solo a completamento, rilascio su interruzione, concorrenza, pulizia); rotta `/dl` (404 identico per tutti i casi, `HEAD` non consuma, streaming completo, revoca, mascheramento nel log); `files_download` e `fetch` binario (forma della risposta); mappatura Findling → `file:`; `files_read` sotto 150.000 caratteri; eventi con descrizione e luogo; link alla mail; rinomina (nei punti che identificano l'app – id in `info.xml`, comandi occ, percorsi `/exapps/`, immagine, container `nc_app_`, id dei form – non resta il nome vecchio; nomi dei moduli Python e del logger `mcp_connector` invariati).

## 9. Messa in produzione e accettazione

1. Tag `v0.3.2-olivia.1` → immagine su ghcr.io → installazione di `mcp_connector_olivia` accanto all'originale, con le due regole nginx di discovery OAuth per il nuovo percorso (`/.well-known/oauth-protected-resource/exapps/mcp_connector_olivia/mcp`, `/.well-known/oauth-authorization-server/exapps/mcp_connector_olivia`).
2. Nuovo connettore in Claude Desktop, login.
3. Prove di accettazione con l'utente: PDF cercato e letto in autonomia; file Word; riuso dello stesso link dopo il download (404); link lasciato scadere (404); manifest letto a blocchi; evento con descrizione.
4. L'utente decide se rimuovere l'originale. **Ritorno indietro:** disinstallare `mcp_connector_olivia`; l'originale non viene mai modificato.

## 10. Fuori scope

Download parziali (Range); controllo di modifica del file tra emissione e download; link multi-uso; aggiornamento automatico dal repository dell'autore; correzione del comando occ `exchange:check` (bug dell'autore, non influisce sugli strumenti); risorse MCP.
