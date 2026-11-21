# fox_netmap — Manuale utente

Versione 1.3.x · novembre 2026

> Lingue: [Deutsch](02-benutzerhandbuch.md) · [English](02-benutzerhandbuch.en.md) · [Français](02-benutzerhandbuch.fr.md) · [Español](02-benutzerhandbuch.es.md) · [Italiano](02-benutzerhandbuch.it.md) · [Português](02-benutzerhandbuch.pt.md)

fox_netmap è una mappa di rete interattiva e consultabile per la rete domestica: fino a ~200
dispositivi su più sottoreti/VLAN, con topologia («collegato a»), porte aperte, cronologia,
allarmi ed esportazioni (JSON/CSV/stampa PDF). I dati sono persistenti in SQLite; le scansioni
sono cicliche o manuali.

> Le immagini di questo manuale (`docs/screenshots/*.svg`) sono illustrazioni schematiche
> dell'interfaccia reale (tema scuro): struttura ed elementi corrispondono 1:1 all'app.

**Indice**

1. [Avvio rapido](#1-avvio-rapido)
2. [L'interfaccia](#2-linterfaccia)
3. [Usare la mappa](#3-usare-la-mappa)
4. [Tabella](#4-tabella)
5. [Vista Log](#5-vista-log)
6. [Dettagli del dispositivo](#6-dettagli-del-dispositivo)
7. [Ricerca e filtri](#7-ricerca-e-filtri)
8. [Impostazioni](#8-impostazioni)
9. [Incorporamento (embed, sola lettura)](#9-incorporamento-embed-sola-lettura)
10. [Esportazioni](#10-esportazioni)
11. [Scanner e modello dati](#11-scanner-e-modello-dati)
12. [Topologia («collegato a»)](#12-topologia-collegato-a)
13. [Più siti e IPv6](#13-più-siti-e-ipv6)
14. [Sicurezza](#14-sicurezza)
15. [Esercizio e distribuzione](#15-esercizio-e-distribuzione)
16. [API REST (panoramica)](#16-api-rest-panoramica)
17. [Risoluzione dei problemi](#17-risoluzione-dei-problemi)
18. [Accessibilità](#18-accessibilità)
19. [Glossario](#19-glossario)

---

## 1. Avvio rapido

**Requisiti:** Docker + Docker Compose sull'host (lo scanner necessita di `network_mode: host`
perché ARP/ping funzionino sulla rete reale).

```bash
git clone https://github.com/KaiDeWitzka/fox_netmap.git
cd fox_netmap
# opzionale: creare .env, p. es.
#   NETZ_SUBNETS=192.168.178.0/24,192.168.179.0/24
#   NETZ_FRITZ_URL=http://192.168.178.1:49000
#   NETZ_FRITZ_USER=…   NETZ_FRITZ_PASS=…
docker compose up -d --build
```

- Interfaccia web: **http://localhost:8399**
- Al primo avvio con `NETZ_AUTH_PASS` vuoto viene generata una volta una password casuale e salvata in
  `./data/initial-admin-password.txt` (leggibile solo dal proprietario, non nei log). Login predefinito: `admin`.
  Poi impostare `NETZ_AUTH_PASS`: il file viene eliminato automaticamente.
- La prima scansione parte automaticamente dopo `NETZ_SCAN_INTERVAL` (900 s predefiniti) oppure
  subito tramite **▶ Scan** nell'intestazione.
- I dati sono nel volume `./data` (SQLite `netmap.db`, log `netmap.log`, esportazioni) e
  sopravvivono a `docker compose up -d --build` (ricreazione). **`down -v` elimina i dati!**

> Dopo ogni aggiornamento del codice eseguire sempre `docker compose up -d --build`.

---

## 2. L'interfaccia

![Mappa con gruppi di sottorete e pannello dettagli](screenshots/01-karte.svg)

L'intestazione contiene (da sx a dx): logo/versione, navigazione **Mappa / Tabella / Log**,
ricerca, filtri (categoria, stato, sito), **Solo online**, selettore del layout, esportazioni
(JSON/CSV), **▶ Scan**, stampa (PDF), tema (🌙/☀), **⚙ Impostazioni**, logout.

Cliccando su un dispositivo (o su ⚙) si apre il pannello laterale a destra con le schede
**Dettagli** e **Impostazioni**.

---

## 3. Usare la mappa

- **Zoom/pan:** la rotella zooma, trascinare lo sfondo sposta. Le posizioni dei dispositivi vengono
  salvate (trascinare un nodo è persistente via API).
- **Clic su un dispositivo:** spotlight — il dispositivo e i suoi collegamenti diretti vengono
  evidenziati, il resto si attenua; i dettagli si aprono a destra. Nuovo clic sullo sfondo per
  annullare.
- **«Solo online»:** nasconde i dispositivi offline (persistito in localStorage).
- **«Raggruppa sottoreti»:** i dispositivi vengono raggruppati per sottorete in una cornice
  (etichetta `sottorete · sito (numero)`). Gli archi tra sottoreti diverse vanno da gruppo a gruppo.
- **Comprimi/espandi figli:** nel pannello dettagli di router/switch, un pulsante nasconde tutti
  i dispositivi collegati direttamente; il nodo mostra poi `(+N)`.
- **Layout:** `auto` (fisica, predefinito), `force`, `tree`, `concentric`, `circle`, `grid`;
  **Ripristina** cancella le posizioni salvate.
- Nodi virtuali: **🌐 Internet** (con IP WAN da TR-064, altrimenti «?»), **🏠 Gateway** (se il
  gateway non è nell'elenco) e **📶 wlan:…** per i dispositivi WLAN senza nodo proprio.
- Emoji di categoria sui nodi: 🏠 Router · 🔀 Switch · 🖥 Server/NAS · 💻 Client · 🖨 Stampante ·
  💡 Smart home/IoT · ❓ Sconosciuto.

---

## 4. Tabella

![Tabella](screenshots/02-tabella.svg)

- **Riordina colonne:** trascina una cella di intestazione — l'ordine è salvato (localStorage).
- **Larghezza colonne:** trascina il divisore nell'intestazione — la larghezza è salvata.
- **Ordinamento:** clic su un'intestazione di colonna.
- **Cambia categoria in linea:** menu a discesa nella colonna categoria.
- Host/IP con porte di interfaccia web (80/8080/443/8443) sono resi come link cliccabili
  (http + https, IPv6 tra `[…]`).
- I dispositivi senza MAC (p. es. IP sole dalla sottorete VPN) mostrano «–» come MAC.

---

## 5. Vista Log

![Log](screenshots/04-log.svg)

La vista **Log** mostra `netmap.log` (rotante, 1 MB × 3) con aggiornamento automatico ogni 5 s,
filtro per livello e download del file completo. Lo stesso è offerto da `/api/logs` e
`/api/logs/download`.

---

## 6. Dettagli del dispositivo

A destra, scheda **Dettagli**: categoria (modificabile), IP/MAC/hostname/produttore (OUI), stato,
sottorete, sito, fonte/i della scansione (p. es. `arp,tr064`), «collegato a» (selezionabile
manualmente, vuoto = automatico), porte aperte con nomi di servizio, nota, cronologia
(online/offline/porte) ed eventi. **Salva** persiste categoria/nota/collegamento manuale.

---

## 7. Ricerca e filtri

- **Ricerca:** cerca in hostname, IP, MAC, produttore, nota (filtro live).
- **Filtri:** categoria, stato (online/offline), sito — combinabili, si applicano a mappa e tabella.
- **Solo online:** interruttore rapido nell'intestazione.

---

## 8. Impostazioni

![Impostazioni](screenshots/03-einstellungen.svg)

Tutto ciò che viene modificato qui ha effetto **alla prossima scansione senza riavviare il
contenitore** (i valori env del compose restano i predefiniti per nuove installazioni; vuoto =
predefinito env).

| Campo | Equivalente env | Significato |
|---|---|---|
| Sottoreti | `NETZ_SUBNETS` | separate da virgole, CIDR IPv4 e IPv6 (p. es. `192.168.178.0/24, 2003:db8::/64`) |
| Intervallo / timeout scansione | `NETZ_SCAN_INTERVAL` / `NETZ_SCAN_TIMEOUT` | secondi; intervallo 30–86400 |
| Ambito porte / porte proprie | `NETZ_PORT_TOP` / `NETZ_PORTS` | top N (0 = tutte) o elenco proprio `80,443,…` |
| SNMP attivo / switch / community | `NETZ_SNMP_ENABLED` / `_SWITCHES` / `_COMMUNITY` | tabella CAM + LLDP degli switch (161/udp) |
| TR-064 dispositivo principale / altri endpoint / utente / password | `NETZ_FRITZ_URL` / `_URLS` / `_USER` / `_PASS` | URL o `host:porta`; ripetitori come endpoint extra; la password è **write-only** (GET non la restituisce mai, vuoto = invariato) |
| URL allarme (webhook/Gotify/Ntfy) | `NETZ_NOTIFY_*` | `http(s)://…`; i token restano solo env (`NETZ_NOTIFY_*_TOKEN`) |
| Whitelist | `NETZ_ALARM_WHITELIST` | MAC/IP che non attivano l'allarme «nuovo dispositivo» |
| Siti | `NETZ_SITES` | `Nome:sottorete; …` p. es. `Casa:192.168.178.0/24; Remoto:192.168.179.0/24` |
| Cronologia / retention | `NETZ_HISTORY_HOURS` / `NETZ_DEVICE_RETENTION_DAYS` | cronologia in ore; elimina i dispositivi offline dopo N giorni (0 = mai) |
| Auto-export / intervallo / cartella | `NETZ_AUTO_EXPORT` / `_INTERVAL_HOURS` / `_DIR` | JSON+CSV automatici; intervallo in h (0 = dopo ogni scansione) |
| mDNS | `NETZ_MDNS_ENABLED` | hostname via mDNS PTR come fallback |
| Fallback OUI online / max lookup per scansione / URL API | `NETZ_OUI_ONLINE_ENABLED` / `_MAX` / `_URL` | produttore di MAC sconosciuti cercato online (predefinito `https://api.macvendors.com`), **disattivato per impostazione predefinita** (privacy: i prefissi MAC vengono inviati a terzi), in cache nel DB |
| Login attivo | `NETZ_AUTH_ENABLED` | login di sessione on/off (utente/password restano solo env) |
| Tema / lingua | `NETZ_THEME` / `NETZ_LANG` | dark/light; de/en/fr/es/it/pt |

**Validazione:** input non validi (p. es. `non-un-ip` come sottorete, porta `abc`, webhook senza
`https://`) vengono segnalati subito nel frontend e rifiutati dal backend con HTTP 422.

---

## 9. Incorporamento (embed, sola lettura)

In Impostazioni (**Token di incorporamento**) crea un token — opzionalmente con scadenza e filtri
(sottoreti/categorie). Incorporamento tramite:

```html
<iframe src="https://netmap.example.com/embed?token=ABC123&lang=it" width="100%" height="600"></iframe>
```

L'embed è in sola lettura (nessuna modifica, nessuna impostazione), rispetta i filtri del token e
si può regolare con `?theme=dark|light` e `?lang=…`.

---

## 10. Esportazioni

- **JSON / CSV** nell'intestazione: esportazione completa di tutti i dispositivi (porte, cronologia,
  collegamenti, siti). CSV con separatore a scelta (`/api/export/csv?sep=;`).
- **Stampa → PDF:** vista ottimizzata per la stampa (browser «Salva come PDF»).
- **Auto-export:**
- **PDF (lato server):** pulsante **PDF** nell'intestazione — snapshot della mappa (PNG) + tabella dispositivi come PDF reale via `POST /api/export/pdf` (anche con token, filtri tramite query param). attivabile in Impostazioni; scrive JSON+CSV dopo ogni intervallo nella cartella
  di esportazione (relativa al volume dati, predefinita `exports`).

---

## 11. Scanner e modello dati

Due servizi compose condividono il volume `./data`:

- `netmap` — web/API (porta 8399)
- `netmap-scanner` — `command: ["scanner"]`, `network_mode: host`, cap `NET_RAW`/`NET_ADMIN`

**Fonti per scansione (priorità di unione):** sweep ping + ARP (`/proc/net/arp`) + sonda TCP
(80/443/22/445/8080) per host bloccati in ICMP (p. es. sottorete VPN) → TR-064 (dispositivo
principale + `NETZ_FRITZ_URLS`, unione per IP, ripetitori via `tr064_parent`) → SNMP (CAM/LLDP)
→ mDNS/DNS. Conflitti MAC: vince la MAC ARP. I duplicati (stesso IP) vengono uniti all'avvio.

**Ciclo:** ogni 900 s predefiniti + avvio manuale (▶ Scan). Ogni scansione scrive cronologia
(`device_history`), eventi (`device_events`: online/offline/porte cambiate/nuovo) e attiva
allarmi (webhook/Gotify/Ntfy per nuovo dispositivo — tranne whitelist).

**Retention:** i dispositivi offline vengono eliminati dopo `NETZ_DEVICE_RETENTION_DAYS`
(30 predefiniti, 0 = mai).

---

## 12. Topologia («collegato a»)

Priorità: **manuale** (pannello dettagli) > **SNMP** (CAM+LLDP) > **TR-064** (ripetitori) >
**WLAN** (`wlan:…` se TR-064 indica l'host come WLAN) > **gateway**.
Anche il tipo di collegamento `lan`/`wlan` è salvato. Con i gruppi di sottorete attivi, gli archi
tra sottoreti diverse vanno da gruppo a gruppo.

---

## 13. Più siti e IPv6

Esempio (sito VPN come nella tua rete):

```env
NETZ_SUBNETS=192.168.178.0/24,192.168.179.0/24
NETZ_SITES=Casa:192.168.178.0/24; Remoto:192.168.179.0/24
```

→ filtro sito nell'intestazione, colonna «Sito» nella tabella, etichetta sito nei gruppi di
sottorete, campo `site` nelle esportazioni. La sottorete remota è scoperta via sonda TCP anche
se ICMP è bloccato.

IPv6: basta aggiungere un CIDR v6 alle sottoreti; scoperta nelle reti grandi via NDP + ping del
gateway, più sweep per quelle piccole; gateway-v6 per la topologia; link web come `[2003:db8::10]:8080`.

---

## 14. Sicurezza

- **Dalla v1.5.0:** hash PBKDF2-SHA256 con 600.000 iterazioni (gli hash vecchi vengono aggiornati automaticamente al login successivo); le sessioni scadute vengono rimosse; cookie di sessione `Secure` con HTTPS (`NETZ_COOKIE_SECURE=auto|true|false`); ricerca online del produttore disattivata per impostazione predefinita.
- **Dalla v1.4.1:** tutti i dati di rete e utente vengono codificati in HTML prima della visualizzazione (protezione XSS); header di sicurezza (CSP, `X-Frame-Options`, `Referrer-Policy: no-referrer`) su tutte le risposte; blocco del login per 15 minuti dopo 5 tentativi falliti (IP+utente) o 20 (IP) (HTTP 429).
- `NETZ_EMBED_ANCESTORS` stabilisce quali siti possono incorporare `/embed` in un iframe (predefinito `*`; consigliato: indicare i propri domini).
- Dettagli (in tedesco): [concetto di sicurezza](03-sicherheit.md).
- Login di sessione (PBKDF2, cookie `fox_session`), attivo predefinito; `NETZ_AUTH_ENABLED=false` lo disattiva.
- `NETZ_AUTH_USER`/`NETZ_AUTH_PASS` sono solo env; password vuota → password iniziale casuale in `./data/initial-admin-password.txt` (dalla v1.5.0 non più nei log).
- `GET /api/settings` **non restituisce segreti** (coperto da test): né `auth_pass`, né
  `fritz_pass`, né `notify_*_token`. La password TR-064 è write-only nelle Impostazioni.
- Token di embed: con scadenza, filtrabili, sola lettura; i percorsi API protetti da token sono
  solo `/api/devices`, `/api/device/…`, `/api/export/…`.
- Lo scanner gira con cap minime (`NET_RAW`, `NET_ADMIN`), in sola lettura verso la rete.

---

## 15. Esercizio e distribuzione

```bash
docker compose up -d --build          # dopo ogni aggiornamento (ricrea, i dati restano in ./data)
docker compose logs -f netmap-scanner  # log dello scanner in tempo reale
docker compose down                    # ferma (i dati restano)
docker compose down -v                 # ATTENZIONE: elimina ./data (DB, log, esportazioni)!
```

- Salute: `GET /api/health` → `{ "status": "ok", "version": "1.5.0" }`
- Dalla v1.5.0 i container **non girano più come root**, ma con UID/GID `10001`. L'interfaccia web non ha capability e ha un file system root in sola lettura; lo scanner mantiene solo `NET_RAW` per ping.
- Al primo avvio dopo l'aggiornamento il container assegna automaticamente i file esistenti in `./data` all'UID 10001. Sull'host usare `sudo` per leggerli o aggiungere il proprio utente a un gruppo con GID 10001.
- Healthcheck Docker: `docker compose ps` mostra `healthy`/`unhealthy` (web: `/api/health`, scanner: ciclo di scansione attivo).
- Volumi: `./data:/data` (SQLite WAL, `netmap.log` rotante, `exports/`)
- Porte: `NETMAP_PORT` (host) → 8399 (contenitore)
- Fuso orario: `TZ=Europe/Berlin`
- Release: i tag SemVer `vX.Y.Z` passano da `release.yml` (ruff + pytest + test UI) e creano
  automaticamente una release GitHub.

---

## 16. API REST (panoramica)

| Endpoint | Scopo |
|---|---|
| `GET /api/health` | salute + versione (pubblico) |
| `GET /api/devices?q=&category=&status=&subnet=&site=` | elenco dispositivi, filtrabile |
| `PATCH /api/device/{mac}` | modifica categoria/nota/«collegato a»/posizione |
| `GET /api/device/{mac}` | dettagli (porte/cronologia/eventi) |
| `POST /api/scan` · `GET /api/scan/status` | avvia scansione / stato |
| `GET /api/settings` · `PATCH /api/settings` | leggi impostazioni (senza segreti) / modifica (422 se non valida) |
| `GET/POST /api/tokens` · `DELETE /api/tokens/{id}` | gestisci token di embed |
| `GET /api/export/json` · `GET /api/export/csv?sep=,` | esportazioni |
| `GET /api/logs?lines=200&level=WARNING` · `GET /api/logs/download` | log |
| `GET /api/meta` | IP WAN, gateway, versione, sottoreti (pubblico) |
| `GET /api/sites` · `GET /api/categories` | siti / categorie (pubblico) |
| `POST /api/layout/reset` | cancella le posizioni dei nodi salvate |

Auth: cookie di sessione dopo `POST /api/login`; token di embed al posto della sessione per i
percorsi a token.

---

## 17. Risoluzione dei problemi

| Sintomo | Causa / soluzione |
|---|---|
| «Troppi tentativi falliti» al login | Blocco attivo (HTTP 429). Attendere 15 minuti o riavviare il container (`docker compose restart netmap`). |
| L'embed non appare nell'iframe | `NETZ_EMBED_ANCESTORS` non contiene il sito che incorpora. Aggiungere il dominio ed eseguire `docker compose up -d`. |
| Dispositivo mancante nella sottorete VPN | ICMP bloccato → la sonda TCP interviene automaticamente; visibile nel log (`WARN … TCP probe ok`). Aggiungi la sottorete nelle Impostazioni. |
| Errori TR-064 nel log | il fallback https→http è automatico; controlla URL/utente/password nelle Impostazioni. I fault SOAP sono registrados in chiaro. |
| Switch senza vicini | TL-SG108E ecc. senza SNMP → solo porta 80; imposta la topologia manualmente nel pannello dettagli. |
| Dispositivo «duplicato» | stesso IP con due MAC → vince la MAC ARP, il resto è deduplicato all'avvio. |
| I vecchi dispositivi scompaiono | retention attiva (30 giorni offline predefiniti) — impostare `0` = mai nelle Impostazioni. |
| Mappa illeggibile | attiva «Raggruppa sottoreti» + comprimi i figli di router/switch + prova i layout `tree`/`grid`. |
| Login dimenticato | imposta `NETZ_AUTH_PASS` in compose/.env e `docker compose up -d --build`. |
| Ricominciare da capo | `docker compose down -v && docker compose up -d --build` — elimina il DB! Salva prima le esportazioni. |

La scheda **Log** + `docker compose logs netmap-scanner` mostrano ogni passo della scansione.

---

## 18. Accessibilità

- Navigazione da tastiera: Tab tra intestazione/viste, Invio attiva; anelli di focus visibili.
- Contrasti verificati nei temi scuro/chiaro; lo stato è anche testuale («online/offline»), non solo colore.
- aria-label sui pulsanti solo icona, regione live per i messaggi di stato.
- Obiettivo: piena conformità BITV 2.1 — feedback benvenuti (issue nel repo).

---

## 19. Glossario

- **OUI** — identificazione del produttore tramite i primi 3 byte della MAC (DB locale `app/data/oui_seed.txt`).
- **TR-064** — interfaccia SOAP AVM della FRITZ!Box (elenco host, IP WAN, client WLAN).
- **Tabella CAM** — tabella MAC-port dello switch via SNMP (Q-BRIDGE/BRIDGE-MIB).
- **LLDP** — scoperta dei vicini via SNMP (LLDP-MIB), p. es. `lldpRemChassisId`.
- **Retention** — eliminazione automatica dei dispositivi offline da tempo.
- **Spotlight** — evidenziazione di un dispositivo + i suoi collegamenti diretti sulla mappa.
- **Sito** — un nome per una sottorete (`NETZ_SITES`), p. es. «Remoto» per la rete VPN.

---

*Domande o bug? Apri una issue in `KaiDeWitzka/fox_netmap` — i requisiti sono in
`docs/01-anforderungen.md`.*
