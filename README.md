# 📊 GdG-Ledger-Bot

Telegram Bot professionale per la tenuta del registro contabile (Ledger), gestione della cassa contanti e sincronizzazione automatica su **Google Sheets**, con supporto nativo alle notifiche e collegamento dei pagamenti **Satispay Business**.

---

## ✨ Funzionalità Principali

* **Sicurezza Chat Autorizzata**: Il bot risponde unicamente all'ID chat configurato nel file `.env`, ignorando ed isolando ogni comando proveniente da altre chat o utenti non autorizzati.
* **Procedura Guidata `/write` (shortcut `/w`)**:
  * Richiede sequenzialmente: Data e Ora, Metodo (Contanti o Satispay), Cassa iniziale (solo se contanti), Descrizione, Flusso (Entrata/Uscita), Importo, Cassa aggiornata (solo se contanti) e Numero ricevuta.
  * Interfaccia ottimizzata con **pulsanti interattivi (Inline Buttons)**:
    * Pulsante per impostare l'orario attuale (`/now`).
    * Pulsante per selezionare l'ultimo saldo cassa registrato su Google Sheets.
    * Calcolo automatico della cassa aggiornata (Saldo Iniziale ± Importo) con pulsante di conferma rapida o inserimento manuale.
    * Suggerimento progressivo per il numero di ricevuta (Ultimo registrato + 1).
  * Registra l'username e l'ID Telegram dell'operatore per audit e sicurezza.
  * Invia un riepilogo formattato in chat alla conclusione dell'inserimento.
* **Archiviazione Cloud su Google Sheets**:
  * Struttura a colonne ordinata con autoincremento progressivo dell'ID transazione.
  * Supporto a fogli multipli nella stessa cartella di lavoro (tab specificabile da `.env`).
  * Modalità Mock locale (`USE_MOCK_SHEETS=true`) per test immediati anche senza credenziali Google configurate.
* **Integrazione Satispay Business**:
  * Server Webhook integrato (FastAPI) per ricevere notifiche di pagamento in tempo reale ed inviare un *echo* nella chat Telegram.
  * Associazione transazione: rispondi a un messaggio Satispay con `/link <id_transazione>` per salvare l'ID Satispay nella colonna del foglio.
  * Scollegamento: rispondi con `/unlink` (scollega da tutte le transazioni) o `/unlink <id_transazione>`.
* **Macro e Comandi Personalizzati Dinamici**:
  * Cartella dedicata `custom_commands/`: aggiungi file `.yaml` o `.json` per creare macro (es. `/caffe`, `/quota`).
  * Registrazione automatica all'avvio nel menu dei comandi Telegram tramite `setMyCommands`.
  * Supporto a valori predefiniti (`defaults`): data, metodo, flusso, importo fisso, prefissi o suffissi per la descrizione. I campi già impostati vengono saltati automaticamente durante la conversazione.

---

## 📁 Struttura del Progetto

```text
GdG-Ledger-Bot/
├── bot/
│   ├── conversation.py        # Flusso interattivo /write e gestione comandi custom
│   ├── custom_commands.py     # Loader file YAML e generatore comandi Telegram
│   ├── handlers.py            # /start, /help, /link, /unlink ed error handling
│   └── keyboards.py           # Inline Keyboards e bottoni interattivi
├── core/
│   ├── models.py              # Modelli dati Pydantic (Transaction, CustomCommand, SatispayPayment)
│   └── security.py            # Decoratori e filtri di autorizzazione chat
├── services/
│   ├── sheets_service.py      # Servizio Google Sheets (gspread) e Mock locale
│   └── satispay_service.py    # Client API Satispay con HTTP Signatures crittografiche
├── custom_commands/           # Cartella con le definizioni YAML dei comandi custom
│   ├── caffe.yaml
│   └── quota.yaml
├── tests/                     # Suite di test unitari con Pytest
│   ├── conftest.py
│   ├── test_bot_logic.py
│   ├── test_custom_commands.py
│   ├── test_satispay_service.py
│   └── test_sheets_service.py
├── .env.example               # Template variabili d'ambiente
├── .GEMINI.md                 # Guida dettagliata per ottenere credenziali API Google e Satispay
├── main.py                    # Entry point: avvia Telegram Bot e Webhook FastAPI
├── requirements.txt           # Dipendenze Python
├── satispay_setup.py          # Script interattivo per generazione chiavi RSA e scambio KeyID
└── start_tunnel.sh            # Script per avvio automatico Cloudflare Tunnel
```
---

## 🚀 Installazione e Avvio Rapido

### 1. Prerequisiti
* Python 3.10 o superiore.
* Un token bot ottenuto da [@BotFather](https://t.me/BotFather) su Telegram.

### 2. Configurazione Ambiente Virtuale
```bash
# Crea e attiva l'ambiente virtuale
python3 -m venv .venv
source .venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

### 3. Configurazione Variabili d'Ambiente (.env)
Copia il file di esempio `.env.example` in `.env`:
```bash
cp .env.example .env
```
Modifica `.env` con i tuoi valori:
* `TELEGRAM_BOT_TOKEN`: Il token del bot fornito da BotFather.
* `TELEGRAM_ALLOWED_CHAT_ID`: L'ID numerico della chat o gruppo abilitato.
* `USE_MOCK_SHEETS`: Lascia `true` per provare subito il bot in memoria locale senza credenziali Google, oppure `false` una volta configurato Google Sheets.
* Per la guida completa all'ottenimento delle credenziali Google Sheets e Satispay, consulta il file [`.GEMINI.md`](.GEMINI.md).

### 4. Esecuzione dei Test
Puoi verificare l'integrità dell'intero progetto eseguendo:
```bash
pytest -v
```

### 5. Avvio del Bot e del Server Webhook
```bash
python main.py
```

### 6. Esposizione Webhook per Satispay (PC Locale)
In un altro terminale, avvia lo script del tunnel Cloudflare per ottenere un indirizzo HTTPS pubblico:
```bash
./start_tunnel.sh
```
Copia l'URL generato (es: `https://xxxx.trycloudflare.com`) e imposta su Satispay il Webhook URL:
`https://xxxx.trycloudflare.com/webhook/satispay`

---

## ⚙️ Creazione di Comandi Personalizzati (Macro)

Per creare un nuovo comando, crea un file `.yaml` all'interno della cartella `custom_commands/` (es. `custom_commands/pizza.yaml`):

```yaml
command: "pizza"
description: "Registra pizza di gruppo (10€ Contanti)"
defaults:
  date_time: "now"          # Imposta automaticamente data e ora corrente
  method: "Contanti"        # Pre-seleziona Contanti
  flow: "Uscita"            # Uscita fondi
  amount: 10.00             # Importo fisso
  description: "Pizza sociale"
```

Al prossimo riavvio, il bot registrerà automaticamente `/pizza` su Telegram. Quando un utente digiterà `/pizza`, il bot salterà le domande per cui è già presente un default e chiederà unicamente la cassa iniziale/aggiornata e la ricevuta!

---

## 📄 Licenza
Progetto rilasciato ad uso interno sotto licenza MIT.

