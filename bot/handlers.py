import html
import json
import logging
import re
from typing import Optional, Dict
from telegram import Update
from telegram.ext import ContextTypes
from core.security import restricted
from core.models import CustomCommandConfig
from services.sheets_service import get_sheets_service

logger = logging.getLogger(__name__)

SATISPAY_ID_REGEX = re.compile(
    r"(?:ID Satispay:\s*`?([a-zA-Z0-9_\-]+)`?)|(?:`([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`)"
)


def extract_satispay_id_from_text(text: str) -> Optional[str]:
    """Estrae l'ID transazione Satispay dal testo del messaggio a cui si risponde"""
    match = SATISPAY_ID_REGEX.search(text)
    if match:
        return match.group(1) or match.group(2)
    return None


@restricted
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Messaggio di benvenuto del bot"""
    welcome_text = (
        "👋 *Benvenuto nel Ledger Bot!*\n\n"
        "Questo bot ti permette di registrare entrate, uscite e monitorare la cassa "
        "direttamente su Google Sheets, con supporto ai pagamenti Satispay.\n\n"
        "📌 *Comandi principali:*\n"
        "• `/write` (o `/w`) - Avvia la procedura guidata di inserimento transazione\n"
        "• `/help` - Mostra la guida completa e i comandi personalizzati disponibili\n"
        "• `/cancel` - Annulla un inserimento in corso\n"
    )
    await update.effective_chat.send_message(welcome_text, parse_mode="Markdown")


@restricted
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guida dettagliata all'uso del bot"""
    custom_commands: Dict[str, CustomCommandConfig] = context.bot_data.get("custom_commands", {})

    custom_text = ""
    if custom_commands:
        custom_text = "\n⚡ *Macro e comandi veloci disponibili:*\n"
        for cmd_name, cfg in custom_commands.items():
            custom_text += f"• `/{cmd_name}` - {cfg.description}\n"

    help_text = (
        "📖 *Guida all'uso del Ledger Bot*\n\n"
        "🔹 *Registrazione Transazioni:*\n"
        "Usa il comando `/write` (scorciatoia `/w`) per avviare una procedura interattiva.\n"
        "Il bot ti guiderà passo dopo passo ponendo domande su data, metodo (Contanti o Satispay), "
        "saldo cassa, descrizione, flusso (entrata/uscita), importo e ricevuta.\n"
        f"{custom_text}\n"
        "🔹 *Integrazione Satispay:*\n"
        "Quando il bot riceve una notifica di pagamento da Satispay, invia un messaggio in chat.\n"
        "• *Collegamento:* Rispondi (reply) al messaggio Satispay con `/link <id_transazione>` "
        "per associare quell'ID Satispay alla transazione nel foglio di calcolo.\n"
        "• *Scollegamento:* Rispondi con `/unlink` per rimuovere l'ID Satispay da tutte le righe, "
        "oppure con `/unlink <id_transazione>` per scollegarlo solo da una riga specifica.\n"
    )
    await update.effective_chat.send_message(help_text, parse_mode="Markdown")
@restricted
async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Collega un ID Satispay a una riga di transazione del foglio.
    Sintassi: rispondi a una notifica Satispay con /link <id_transazione>
    """
    reply_to = update.message.reply_to_message if update.message else None
    if not reply_to or not reply_to.text:
        await update.effective_chat.send_message(
            "⚠️ *Istruzioni:* Per collegare un pagamento Satispay, rispondi (reply) "
            "al messaggio di notifica Satispay scrivendo:\n`/link <id_transazione>` (es: `/link 12`)",
            parse_mode="Markdown",
        )
        return

    satispay_id = extract_satispay_id_from_text(reply_to.text)
    if not satispay_id:
        await update.effective_chat.send_message(
            "❌ Impossibile rilevare un ID Satispay nel messaggio a cui hai risposto. "
            "Assicurati di rispondere alla notifica di pagamento inviata dal bot.",
            parse_mode="Markdown",
        )
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_chat.send_message(
            "⚠️ Specifica l'ID numerico della transazione del foglio da collegare (es: `/link 15`).",
            parse_mode="Markdown",
        )
        return

    tx_id = int(context.args[0])
    user = update.effective_user
    username = user.username or user.first_name if user else "Anonimo"
    user_id = user.id if user else 0
    logger.info(f"Utente @{username} (ID: {user_id}) ha richiesto collegamento transazione #{tx_id} a Satispay ID: {satispay_id}")
    sheets = get_sheets_service()

    success = sheets.link_satispay_id(tx_id, satispay_id)
    if success:
        await update.effective_chat.send_message(
            f"✅ Transazione `#{tx_id}` collegata con successo all'ID Satispay:\n`{satispay_id}`",
            parse_mode="Markdown",
        )
    else:
        await update.effective_chat.send_message(
            f"❌ Transazione `#{tx_id}` non trovata nel foglio di calcolo.",
            parse_mode="Markdown",
        )


@restricted
async def unlink_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Scollega un ID Satispay dal foglio.
    Sintassi: rispondi a una notifica Satispay con /unlink oppure /unlink <id_transazione>
    """
    reply_to = update.message.reply_to_message if update.message else None
    if not reply_to or not reply_to.text:
        await update.effective_chat.send_message(
            "⚠️ *Istruzioni:* Per scollegare un pagamento Satispay, rispondi (reply) "
            "al messaggio di notifica Satispay scrivendo:\n`/unlink` oppure `/unlink <id_transazione>`",
            parse_mode="Markdown",
        )
        return

    satispay_id = extract_satispay_id_from_text(reply_to.text)
    if not satispay_id:
        await update.effective_chat.send_message(
            "❌ Impossibile rilevare un ID Satispay nel messaggio a cui hai risposto.",
            parse_mode="Markdown",
        )
        return

    tx_id: Optional[int] = None
    if context.args and context.args[0].isdigit():
        tx_id = int(context.args[0])

    user = update.effective_user
    username = user.username or user.first_name if user else "Anonimo"
    user_id = user.id if user else 0
    target_descr = f"transazione #{tx_id}" if tx_id is not None else "tutte le transazioni"
    logger.info(f"Utente @{username} (ID: {user_id}) ha richiesto scollegamento Satispay ID: {satispay_id} da {target_descr}")

    sheets = get_sheets_service()
    count = sheets.unlink_satispay_id(satispay_id, transaction_id=tx_id)

    if count > 0:
        target_str = f"dalla transazione #{tx_id}" if tx_id is not None else "da tutte le transazioni collegate"
        await update.effective_chat.send_message(
            f"✅ ID Satispay `{satispay_id}` scollegato con successo {target_str} (righe aggiornate: {count}).",
            parse_mode="Markdown",
        )
    else:
        await update.effective_chat.send_message(
            f"ℹ️ Nessuna corrispondenza trovata nel foglio per l'ID Satispay `{satispay_id}`.",
            parse_mode="Markdown",
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log degli errori imprevisti"""
    logger.error("Eccezione durante la gestione dell'aggiornamento:", exc_info=context.error)

