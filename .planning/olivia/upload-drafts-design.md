# MCP Connector "olivia" – caricamento di file e bozze email

Data: 2026-09-30 · Stato: design approvato a voce (approccio A), in revisione scritta
Base: fork `mcp_connector_olivia` 0.3.2-olivia.2 (spec precedente: `2026-09-29-mcp-connector-olivia-design.md`)

## 1. Obiettivo

Da claude.ai web e Claude Desktop, Claude deve poter:

1. **salvare in Nextcloud file di qualsiasi formato** creati nel suo ambiente di esecuzione, nel percorso che sceglie, **senza mai sovrascrivere**;
2. **creare bozze email** in Nextcloud Mail, nuove o in risposta a una mail, anche **con allegati presi da Nextcloud**. **Mai inviare.**

**Criterio di successo:** in Claude Desktop, "crea un preventivo in Word e salvalo in /Clienti/Rossi/" fa comparire il file in Nextcloud; "prepara una bozza di risposta a Elena con allegato quel preventivo" fa comparire in Mail la bozza con l'allegato. Nessuna email parte.

## 2. Fatti verificati (2026-09-30) su cui poggia il design

| Fatto | Come è stato verificato |
|---|---|
| WebDAV: `MKCOL` crea una cartella (201) e su una cartella esistente risponde 405 | Prova dal vivo con credenziali AppAPI, cartella di prova poi cancellata |
| WebDAV: un `PUT` in streaming senza `Content-Length` è accettato (201, file intero) | Stessa prova, 1 MB |
| WebDAV: `PUT` con `If-None-Match: *` su un file esistente risponde 412 | Stessa prova |
| Un `PUT` da 1 MB passa intero da Cloudflare e nginx (LXC 104) fino a HaRP | curl dal Mac verso `/exapps/mcp_connector_olivia/dl/…`: 405 di HaRP, riga nel log di nginx |
| Cloudflare accetta al massimo 100 MB per richiesta; nginx `/exapps/` e HaRP hanno timeout 1800 s | Configurazione nota dell'istanza |
| Mail 5.12.2 non dichiara API per le bozze: l'`openapi.json` contiene solo elenco account, cartelle, messaggi, messaggio, grezzo, allegato, `message/send` | Lettura di `apps/mail/openapi.json` |
| La rotta interna `POST /index.php/apps/mail/api/drafts` (quella dell'interfaccia di Mail) crea una bozza locale (201, `id`); senza l'intestazione `OCS-APIRequest: true` risponde 412 "CSRF check failed" | Prova dal vivo: una bozza nuova e una di risposta |
| `inReplyToMessageId` = `Message-ID` dell'originale aggancia la bozza di risposta finché è locale | Stessa prova |
| Il `DraftsJob` di Mail (ogni 5 min) sposta le bozze locali più vecchie di 5 min nella cartella Bozze via IMAP append con flag `\Draft`, con trasporto nullo: nessun SMTP | Codice di `DraftsService::flush` e `MailTransmission::saveLocalDraft`; le 2 bozze di prova sono comparse nella cartella "Drafts" dopo 6 min |
| `saveLocalDraft` non scrive `In-Reply-To`/`References`: dopo lo spostamento su IMAP la bozza di risposta perde l'aggancio | Codice di Mail 5.12.2 e riga in `oc_mail_messages` con `in_reply_to` vuoto |
| Allegati di una bozza: tipi `local`, `message`, `message-attachment`; ogni altro tipo è un file Nextcloud con `fileName` = percorso; un file inesistente viene **scartato in silenzio** | Codice di `AttachmentService::handleAttachments`; prova: 2 allegati richiesti, 1 salvato (PDF da 979 KB) |
| Il messaggio completo (rotta OCS) non contiene `accountId` né `mailboxId`; contiene `to`, `cc`, `from`, `replyTo`, `messageId`, `subject` | Prova dal vivo sul messaggio 140813 |
| Account dell'utente in Mail: `drosera@abnet.it` (id 2) e `alessandro.drosera@gmail.com` (id 3) | Elenco account |
| Nell'account Gmail la cartella bozze configurata in Mail è l'etichetta "Drafts", non "[Gmail]/Bozze" (impostazione dell'utente, non del connettore) | Tabelle `oc_mail_accounts` e `oc_mail_mailboxes` |
| Il test di contratto dell'autore vieta ovunque `/api/drafts`, `/api/outbox`, `/message/send` | `tests/contract/test_no_destructive_calls.py` |
| **Da verificare:** `PUT` dall'ambiente di esecuzione di Claude verso `nextcloud.olivia.casa` (il `GET` è verificato dal 2026-09-29) | Prova da Claude Desktop, da fare prima del rilascio |

## 3. Decisioni

1. **Caricamento con link monouso `PUT`** servito dal connettore (`/ul/<token>`), gemello del download `/dl/<token>`.
2. `files_upload(path, content?)`: con `content` (testo) comportamento invariato; **senza `content` restituisce il link**. **Rimossa la modalità base64 a pezzi** e i suoi sei parametri.
3. Link di caricamento: **30 minuti** fissi, **un caricamento completato**, **massimo 100 MB**, cartelle intermedie create al momento del caricamento, **nessuna sovrascrittura** (controllo all'emissione più `If-None-Match: *` al caricamento).
4. **Nuovo strumento `mail_draft`**: crea solo bozze tramite la rotta interna di Mail; **nessun invio**.
5. Allegati delle bozze: **solo file Nextcloud per percorso**, controllati prima della creazione (esiste, è un file, al massimo 10, totale al massimo 25 MB).
6. Il limite di Mail sull'aggancio delle risposte (perso dopo lo spostamento su IMAP) è **accettato e documentato**; nessuna patch a Mail.
7. Nessuna modifica né cancellazione di bozze o file esistenti.
8. Nel test di contratto dell'autore: **eccezione di una sola riga** per `/api/drafts`, come per gli allegati; `/message/send` e `/api/outbox` restano vietati ovunque.
9. Rilascio `v0.3.2-olivia.3`; aggiornamento dell'installazione con `app:unregister` (senza `--rm-data`) e `app:register`.

## 4. Caricamento di file

### 4.1 Strumento `files_upload(path, content?)`

- **`content` presente:** invariato (testo UTF-8, rifiuto se il file esiste).
- **`content` assente:**
  1. `safe_path(path)`; un percorso che finisce con `/` è rifiutato; `stat` WebDAV: se esiste qualcosa (file o cartella) → errore "esiste già, scegli un altro nome".
  2. Biglietto nello store esistente con percorso `upload:<path>`, TTL 30 min, proprietario = `resolve_ticket_owner(ctx)` (nei deployment senza ExApp lo strumento risponde con lo stesso errore di `files_download`).
  3. Risposta JSON compatta: `path`, `upload_url` (`<NC_MCP_PUBLIC_URL>/ul/<token>`), `method: "PUT"`, `expires_at`, `single_use: true`, `max_bytes: 104857600`, `how_to` = "Upload from your code execution environment: curl -fsS -T <file> <upload_url>. One completed upload; the target must not exist; missing folders are created."
- Descrizione dello strumento aggiornata entro il budget (`scripts/check_tool_budget.py`).

### 4.2 Rotta pubblica `PUT /ul/{token}`

- Dichiarata in `info.xml` (`^/ul/[A-Za-z0-9_-]{20,128}$`, verbo `PUT`, `PUBLIC`, stessi `headers_to_exclude` di `/dl`) e nella copia JSON di `scripts/bootstrap_exapp.sh`; montata in `entry_exapp.py`.
- Token malformato, sconosciuto, scaduto, usato, in corso, collegamento revocato o sospeso → **404** identico (`Not found`).
- Un biglietto il cui percorso non inizia con `upload:` → rilasciato e 404; la rotta `/dl` tratta un biglietto `upload:` allo stesso modo (404, non consumato).
- `Content-Length` dichiarato oltre 100 MB → **413**, biglietto rilasciato.
- Sequenza: claim atomico → credenziali ricostruite come per il download → `MKCOL` di ogni cartella antenata (405 = esiste già) → `PUT` WebDAV in streaming del corpo della richiesta con `If-None-Match: *`, contando i byte (oltre 100 MB: interruzione e 413).
- Esiti:

| Caso | Risposta | Biglietto |
|---|---|---|
| Nextcloud 201/204 | 201 `{"path", "size"}` | usato |
| Nextcloud 412 (file comparso nel frattempo) | 409 `{"error": "exists"}` | bruciato |
| Nextcloud 409 su `MKCOL`/`PUT` (al posto di una cartella c'è un file) | 409 `{"error": "conflict"}` | bruciato |
| Nextcloud 401 (credenziale rifiutata) | 404 | bruciato |
| Nextcloud 403 su `MKCOL`/`PUT` (percorso rifiutato: cartella condivisa in sola lettura, nome bloccato, regola di accesso) | 403 `{"error": "forbidden"}` | bruciato |
| Nextcloud 400 sul `PUT` (nome non valido) | 400 `{"error": "invalid_name"}` | bruciato |
| Nextcloud irraggiungibile o 5xx | 502 | di nuovo utilizzabile |
| Oltre 100 MB | 413 | di nuovo utilizzabile |
| Connessione interrotta dal client | — | di nuovo utilizzabile |

- Un caricamento interrotto non lascia file a metà: Nextcloud scrive un file temporaneo e lo rinomina solo a fine trasferimento.
- Log del container: "upload stored: user=…, path=…, bytes=…, link=xxxx…"; il filtro del log di accesso maschera anche `/ul/`.

## 5. Bozze email

### 5.1 Strumento `mail_draft`

Parametri: `to` (lista di indirizzi, anche "Nome <email>"), `cc`, `bcc` (opzionali), `subject`, `body` (testo semplice), `account` (indirizzo o id, opzionale), `reply_to` (id `mail:<n>`, opzionale), `attachments` (percorsi Nextcloud, opzionale). Annotazione: creazione, non sola lettura.

- **Account:**
  - bozza nuova: se l'utente ha un solo account, quello; altrimenti `account` obbligatorio, e senza di esso l'errore elenca gli account disponibili;
  - risposta: l'account il cui indirizzo (o uno dei suoi alias) compare tra `to`/`cc` dell'originale; se nessuno o più di uno, serve `account`;
  - un `account` indicato che non esiste → errore con l'elenco.
- **Risposta (`reply_to`):** si legge l'originale (`mail_client.get_message`); destinatario predefinito = `replyTo` se presente, altrimenti `from`, se `to` non è indicato; oggetto predefinito "Re: <oggetto>", senza raddoppiare un "Re:"/"R:"/"Fwd:" già presente all'inizio, se `subject` non è indicato; `inReplyToMessageId` = `messageId` dell'originale.
- **Allegati:** per ogni percorso `safe_path` + `stat`: deve esistere ed essere un file; al massimo 10; somma delle dimensioni al massimo 25 MB. Qualsiasi violazione → errore con il nome del file, **prima** di creare la bozza. Nella richiesta a Mail ogni allegato è `{"type": "cloud", "fileName": <percorso>}`.
- **Richiesta a Mail:** una sola, `POST /index.php/apps/mail/api/drafts` con `OCS-APIRequest: true`, corpo con `accountId`, `subject`, `bodyPlain`, `bodyHtml: null`, `editorBody: null`, `isHtml: false`, `smimeSign: false`, `smimeEncrypt: false`, `to`/`cc`/`bcc` come liste `{"label", "email"}`, `attachments`, `aliasId: null`, `inReplyToMessageId`. **Mai `sendAt`.**
- **Controllo dopo la creazione:** se Mail restituisce meno allegati di quelli richiesti, la risposta lo dice (nome dei mancanti), senza cancellare nulla.
- **Risposta dello strumento:** `draft_id`, `account`, `to`, `cc`, `subject`, `attachments` (nomi), `mail_url` (`<base_url>/index.php/apps/mail/`), `note` = "Saved as a draft in Nextcloud Mail and never sent by this server. It moves to the account's Drafts folder within about 10 minutes; a reply keeps its link to the original only until then."
- **Errori:** Mail non installata → errore esistente di `capabilities.require_app`; originale inesistente → errore "messaggio non trovato"; 4xx/5xx di Mail → errore con lo stato, nessun tentativo ripetuto.

### 5.2 Sicurezza

- Il modulo nuovo contiene **una sola rotta di Mail** e solo con `POST`; nessuna rotta di invio, uscita, modifica o cancellazione.
- Test di contratto: eccezione limitata alla riga della costante con `/api/drafts` nel solo file nuovo, con controprova (stessa riga altrove e altre righe dello stesso file restano vietate); `/message/send` e `/api/outbox` restano vietati ovunque.
- Test unitario: la richiesta inviata non contiene mai `sendAt` e nessun'altra rotta di Mail viene chiamata.
- Registro delle chiamate (audit): `mail_draft` registrato con i soli nomi dei parametri, come gli altri strumenti.

## 6. Test

- **Unitari (respx):**
  - caricamento: link emesso solo se il percorso non esiste; PUT completo, interrotto, oltre il limite (dichiarato e reale), file comparso nel frattempo (412 → 409), conflitto di cartella, token sbagliato, link usato, revoca e sospensione, incrocio `/dl` ↔ `/ul`, `MKCOL` delle cartelle antenate, token mascherato nel log;
  - bozze: forma esatta della richiesta, bozza nuova con uno e con due account, risposta con account ricavato, destinatario e oggetto predefiniti, allegato mancante / cartella / troppi / troppo grandi, allegati persi da Mail segnalati, nessun `sendAt`, nessun'altra rotta.
- **Suite completa** dell'autore verde sul sorgente e sull'albero rinominato (CI del rilascio).
- **Dal vivo, prima del rilascio definitivo:**
  - PUT da Claude Desktop (la verifica aperta del §2);
  - caricamento da 1 MB e da 50 MB dal Mac attraverso Cloudflare, secondo caricamento sullo stesso percorso → 409;
  - bozza nuova e bozza di risposta con allegato sull'account Gmail, controllo in Mail e dopo lo spostamento su IMAP;
  - pulizia di file e bozze di prova.

## 7. Messa in produzione e accettazione

1. Tag `v0.3.2-olivia.3` (con `<image-tag>0.3.2-olivia.3</image-tag>`) → immagine e `info.xml` rinominato come asset.
2. `occ app_api:app:unregister mcp_connector_olivia` (senza `--rm-data`) + `occ app_api:app:register … --info-xml <asset> --env NC_MCP_PUBLIC_URL=https://nextcloud.olivia.casa/exapps/mcp_connector_olivia --wait-finish`; il collegamento di Claude Desktop resta valido.
3. Prove di accettazione in Claude Desktop:
   - "crea un documento Word di prova e salvalo in /TEST-MCP/";
   - ripetere sullo stesso percorso (rifiuto);
   - "prepara una bozza di risposta alla mail cauzioni allegando quel documento";
   - "prepara una bozza nuova a me stesso dal mio account Gmail".
4. Pulizia dei dati di prova; aggiornamento della memoria del progetto.

## 8. Fuori scope

Invio di email, pianificazione dell'invio, modifica o cancellazione di bozze e file, bozze HTML, allegati presi da altre mail (`message-attachment`), inoltro di mail, correzione del limite di Mail sull'aggancio delle risposte, caricamenti oltre 100 MB, cambio della cartella bozze dell'account Gmail (impostazione dell'utente).
