# DDEV Manager Pro

Tool di gestione grafica per progetti DDEV — scritto in Python/Tkinter.
Avvia, stoppa, monitora e configura automaticamente i tuoi progetti DDEV da un'unica interfaccia.

---

## Avvio rapido

```bash
python3 ddev_starter.py
```

### Requisiti
- Python 3.11+ con `tkinter`
- `ddev` nel PATH (versione 1.25.x)
- `docker` con permessi utente (`sudo usermod -aG docker $USER`, poi logout/login)

---

## Funzionalità

| Funzione | Descrizione |
|---|---|
| **Nuovo progetto** | Dialog guidato con auto-popolamento campi DB dal nome cartella |
| **Start / Stop / Restart** | Avvio con streaming output in tempo reale |
| **Provisioning DB** | Crea automaticamente database, utente e permessi MySQL ad ogni avvio |
| **Adminer** | Apre direttamente sul database del progetto (`?db=NOME`) |
| **PHPMyAdmin** | Auto-scoperta porta dalla variabile `HTTPS_EXPOSE` del container |
| **Debug URL** | Diagnostica completa dei container e delle loro variabili d'ambiente |
| **Poweroff** | Reset completo del router DDEV (`ddev poweroff`) |
| **Dettagli progetto** | Visualizzazione read-only da menu tasto destro → `ℹ️ Dettagli` |
| **Dark/Light Mode** | Persistente tra sessioni |
| **Lock UI** | Tutti i pulsanti si disabilitano durante le operazioni, si riabilitano al termine |

---

## Architettura DDEV (scoperte tecniche chiave)

### Container e rete Docker

Ogni progetto DDEV avvia **container separati** nella stessa rete Docker (`ddev_default`):

```
┌──────────────────────────────────────────────────────────┐
│                  rete: ddev_default                       │
│                                                           │
│  ┌─────────────┐   ┌──────────┐   ┌──────────────────┐  │
│  │   web       │   │   db     │   │ adminer/phpmyadmin│  │
│  │ PHP + nginx │   │ MySQL/   │   │                  │  │
│  │             │   │ MariaDB  │   │ HTTPS_EXPOSE=    │  │
│  │             │   │ :3306    │   │ 9101:8080        │  │
│  └─────────────┘   └──────────┘   └──────────────────┘  │
└──────────────────────────────────────────────────────────┘
         ↑                  ↑                  ↑
    .ddev.site:443    127.0.0.1:PORTA    .ddev.site:9101
    (via Traefik)     (random, host)     (via VIRTUAL_HOST)
```

### Accesso MySQL: dove e come

| Da dove | `host` | Porta |
|---|---|---|
| PHP nel container **web** | `db` | `3306` (Docker DNS interno) |
| Adminer (suo container) | `db` | `3306` |
| Client SQL sul PC host | `127.0.0.1` | porta random → `ddev describe` |
| IDE esterno | `127.0.0.1` | `docker port ddev-PROGETTO-db 3306` |

> ⚠️ **`localhost` NON funziona** dal container web per connettersi a MySQL.
> `localhost` si riferisce al container stesso, non al container `db`.

### Configurazione PHP corretta

```php
$db_host = 'db';               // ← nome container, NON 'localhost' o '127.0.0.1'
$db_port = 3306;
$db_name = 'nomeprogetto';
$db_user = 'nomeprogetto';
$db_pass = 'tuapassword';
```

---

## Discovery URL dei servizi (DDEV 1.25)

In DDEV 1.25, Adminer e PHPMyAdmin **non usano Traefik** né sottodomini.
Usano invece le variabili d'ambiente del container per definire l'esposizione:

```yaml
# da .ddev/.ddev-docker-compose-full.yaml
environment:
  HTTP_EXPOSE: 9100:8080      # HOST_PORT:CONTAINER_PORT
  HTTPS_EXPOSE: 9101:8080
  VIRTUAL_HOST: progetto.ddev.site
```

**URL risultante**: `https://progetto.ddev.site:9101`

Il tool legge queste variabili via:
```bash
docker inspect --format '{{range .Config.Env}}{{.}}\n{{end}}' ddev-NOME-adminer
```

---

## SQL Provisioning automatico

Ad ogni `ddev start` / `ddev restart`, il tool esegue:

```sql
CREATE DATABASE IF NOT EXISTS `nomeprogetto`;
CREATE USER IF NOT EXISTS 'nomeprogetto'@'%' IDENTIFIED BY 'password';
ALTER USER 'nomeprogetto'@'%' IDENTIFIED BY 'password';   -- aggiorna se già esiste
GRANT ALL PRIVILEGES ON `nomeprogetto`.* TO 'nomeprogetto'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```

> **Nota PHPMyAdmin**: i privilegi **globali** mostrano 'N' (normale — l'utente non è root).
> I privilegi **per-database** sono tutti 'Y'. Verificare in: Utenti → modifica → seleziona database.

---

## Adminer: apertura sul database corretto

L'URL di Adminer include il parametro `?db=NOME` per pre-selezionare il database:

```
https://progetto.ddev.site:9101/?server=db&username=db&db=nomeprogetto
```

DDEV usa `ddev-adminer.php` per il login automatico con le credenziali built-in (`db/db/db`).
L'utente DDEV built-in `db` ha accesso a tutti i database del progetto.

---

## Configurazione salvata

Il tool salva la configurazione in `~/.ddev_manager.json`:

```json
{
  "theme": "dark",
  "projects": {
    "nomeprogetto": {
      "path": "/percorso/progetto",
      "tipo": "php",
      "db_name": "nomeprogetto",
      "db_user": "nomeprogetto",
      "db_pass": "password",
      "url": "https://nomeprogetto.ddev.site"
    }
  }
}
```

> In caso di comportamenti anomali, eliminare `~/.ddev_manager.json` per resettare lo stato.

---

## Troubleshooting

### ERR_CONNECTION_REFUSED su Adminer/PMA
Il problema storico era l'assunzione errata che i servizi usassero porte fisse (`:8036`, `:8037`).
La soluzione è leggere `HTTPS_EXPOSE` + `VIRTUAL_HOST` direttamente dalle env vars del container.

```bash
# Diagnostica manuale
docker inspect --format '{{range .Config.Env}}{{.}}\n{{end}}' ddev-PROGETTO-adminer | grep EXPOSE
```

### Permessi Docker negati
```bash
sudo usermod -aG docker $USER
# poi logout e login
```

### Rete DDEV bloccata
Usare il pulsante **⚡ Poweroff** nel tool, oppure:
```bash
ddev poweroff
```

### ddev config blocca il tool
Non eseguire `ddev config` senza argomenti → entra in modalità interattiva e si blocca.
Usare sempre flag espliciti: `ddev config --project-name NOME --project-type php`.

---

## Licenza

Questo progetto è rilasciato sotto licenza [MIT](LICENSE).

---

## Sessione di sviluppo di riferimento

Questa sessione di sviluppo è documentata in Antigravity:
- **Conversation ID**: `38ee6865-bf27-4f9f-9753-33f7275f516c`
- **DDEV version**: 1.25.1
- **Sistema**: Linux (Ubuntu/Debian), Docker compose v5.0.2
