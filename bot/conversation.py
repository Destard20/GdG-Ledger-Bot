import logging
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from core.models import Transaction, CustomCommandConfig
from core.security import is_chat_allowed
from services.sheets_service import get_sheets_service
from bot.keyboards import (
    get_now_keyboard,
    get_method_keyboard,
    get_box_money_keyboard,
    get_flow_keyboard,
    get_box_updated_keyboard,
    get_receipt_keyboard,
    get_cancel_keyboard,
    CALLBACK_NOW,
    CALLBACK_METHOD_CASH,
    CALLBACK_METHOD_SATISPAY,
    CALLBACK_FLOW_IN,
    CALLBACK_FLOW_OUT,
    CALLBACK_BOX_USE_LAST,
    CALLBACK_BOX_CONFIRM_CALCULATED,
    CALLBACK_RECEIPT_USE_SUGGESTED,
    CALLBACK_RECEIPT_NONE,
    CALLBACK_CANCEL,
)

logger = logging.getLogger(__name__)

# Stati del ConversationHandler
(
    STATE_DATETIME,
    STATE_METHOD,
    STATE_BOX_BEFORE,
    STATE_DESCRIPTION,
    STATE_FLOW,
    STATE_AMOUNT,
    STATE_BOX_AFTER,
    STATE_RECEIPT,
) = range(8)


async def send_msg(update: Update, text: str, reply_markup=None):
    """Helper per inviare o modificare un messaggio in base al tipo di update"""
    if update.callback_query:
        await update.callback_query.answer()
        return await update.effective_chat.send_message(
            text=text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    return await update.effective_chat.send_message(
        text=text, reply_markup=reply_markup, parse_mode="Markdown"
    )
async def advance_or_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Verifica quali campi mancano e pone la domanda successiva, oppure completa la registrazione.
    """
    data = context.user_data.setdefault("tx_data", {})
    sheets = get_sheets_service()

    # 1. Data e Ora
    if "date_time" not in data:
        await send_msg(
            update,
            "📅 *Data e Ora della transazione:*\n"
            "Premi il pulsante per impostare data e ora attuale, oppure invia `/now` "
            "o scrivi manualmente la data (`GG/MM/AAAA HH:MM` o `AAAA-MM-GG HH:MM`).",
            reply_markup=get_now_keyboard(),
        )
        return STATE_DATETIME

    # 2. Metodo (Contanti o Satispay)
    if "method" not in data:
        await send_msg(
            update,
            "💳 *Metodo di pagamento:*\n"
            "Come è stata effettuata la transazione?",
            reply_markup=get_method_keyboard(),
        )
        return STATE_METHOD

    # 3. Cassa Iniziale (solo se Contanti)
    if data.get("method") == "Contanti" and "box_money" not in data:
        last_box = sheets.get_last_box_money()
        context.user_data["suggested_last_box"] = last_box
        await send_msg(
            update,
            f"🪙 *Cassa iniziale (prima della transazione):*\n"
            f"Ultimo saldo contanti rilevato nel registro: *{last_box:.2f} €*\n\n"
            "Premi il pulsante per confermarlo oppure scrivi l'importo manualmente.",
            reply_markup=get_box_money_keyboard(last_box),
        )
        return STATE_BOX_BEFORE

    # 4. Descrizione
    if "description" not in data:
        await send_msg(
            update,
            "📝 *Descrizione della transazione:*\n"
            "Inserisci una breve descrizione della spesa o dell'entrata.",
            reply_markup=get_cancel_keyboard(),
        )
        return STATE_DESCRIPTION

    # 5. Flusso (Entrata o Uscita)
    if "flow" not in data:
        await send_msg(
            update,
            "📊 *Flusso di cassa:*\n"
            "I fondi sono entrati o usciti?",
            reply_markup=get_flow_keyboard(),
        )
        return STATE_FLOW

    # 6. Importo
    if "amount" not in data:
        await send_msg(
            update,
            "💰 *Importo:*\n"
            "Inserisci la cifra in euro (es. `15.50` o `15,50`).",
            reply_markup=get_cancel_keyboard(),
        )
        return STATE_AMOUNT

    # 7. Cassa Aggiornata (solo se Contanti)
    if data.get("method") == "Contanti" and "box_money_updated" not in data:
        box_init = data.get("box_money", 0.0)
        amount = data.get("amount", 0.0)
        flow = data.get("flow", "Entrata")
        calc_box = box_init + amount if flow == "Entrata" else box_init - amount
        context.user_data["suggested_box_after"] = calc_box

        sign = "+" if flow == "Entrata" else "-"
        await send_msg(
            update,
            f"🪙 *Cassa aggiornata (dopo la transazione):*\n"
            f"Saldo calcolato: *{calc_box:.2f} €* ({box_init:.2f} € {sign} {amount:.2f} €)\n\n"
            "Premi il pulsante per confermare il saldo calcolato oppure scrivi il valore reale se differisce.",
            reply_markup=get_box_updated_keyboard(calc_box),
        )
        return STATE_BOX_AFTER

    # 8. Numero Ricevuta
    if "receipt_number" not in data:
        last_receipt = sheets.get_last_receipt_number()
        suggested_receipt = last_receipt + 1
        context.user_data["suggested_receipt"] = suggested_receipt
        await send_msg(
            update,
            f"🧾 *Numero ricevuta:*\n"
            f"Ultima ricevuta registrata: *#{last_receipt}*\n\n"
            f"Premi il pulsante per confermare la numero *#{suggested_receipt}* "
            "oppure scrivi il numero manualmente (scrivi `0` se non applicabile).",
            reply_markup=get_receipt_keyboard(suggested_receipt),
        )
        return STATE_RECEIPT

    # ========================================================
    # Tutti i dati sono completi: Registrazione finale
    # ========================================================
    user = update.effective_user
    username = user.username or user.full_name or "Anonimo"
    user_id = user.id

    tx = Transaction(
        date_time=data["date_time"],
        method=data["method"],
        box_money=data.get("box_money"),
        description=data["description"],
        flow=data["flow"],
        amount=data["amount"],
        box_money_updated=data.get("box_money_updated"),
        receipt_number=data["receipt_number"],
        telegram_username=username,
        telegram_user_id=user_id,
        satispay_id=data.get("satispay_id"),
    )

    try:
        registered_tx = sheets.add_transaction(tx)
    except Exception as e:
        logger.error(f"Errore durante salvataggio su foglio: {e}")
        await send_msg(
            update,
            f"❌ *Errore durante il salvataggio sul foglio di calcolo:*\n`{e}`"
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Messaggio riepilogo inviato in chat
    box_info = ""
    if registered_tx.method == "Contanti":
        b_init = f"{registered_tx.box_money:.2f} €" if registered_tx.box_money is not None else "-"
        b_upd = f"{registered_tx.box_money_updated:.2f} €" if registered_tx.box_money_updated is not None else "-"
        box_info = f"🪙 *Cassa iniziale:* `{b_init}`\n🪙 *Cassa aggiornata:* `{b_upd}`\n"

    flow_emoji = "➕" if registered_tx.flow == "Entrata" else "➖"
    method_emoji = "💵" if registered_tx.method == "Contanti" else "📱"

    summary = (
        "✅ *Transazione Registrata con Successo!*\n\n"
        f"🆔 *ID Transazione:* `#{registered_tx.id}`\n"
        f"📅 *Data:* `{registered_tx.date_time}`\n"
        f"{method_emoji} *Metodo:* `{registered_tx.method}`\n"
        f"📝 *Descrizione:* {registered_tx.description}\n"
        f"{flow_emoji} *Flusso:* `{registered_tx.flow}`\n"
        f"💰 *Importo:* `{registered_tx.amount:.2f} €`\n"
        f"{box_info}"
        f"🧾 *Ricevuta:* `#{registered_tx.receipt_number}`\n"
        f"👤 *Registrato da:* @{registered_tx.telegram_username} (`{registered_tx.telegram_user_id}`)"
    )

    await send_msg(update, summary)
    context.user_data.clear()
    return ConversationHandler.END

async def start_write(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Avvia la registrazione guidata con il comando /write o /w"""
    if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["tx_data"] = {}
    return await advance_or_finish(update, context)


def make_custom_command_starter(config: CustomCommandConfig):
    """Genera l'handler di avvio per una specifica macro/comando personalizzato"""
    async def custom_starter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_chat or not is_chat_allowed(update.effective_chat.id):
            return ConversationHandler.END

        context.user_data.clear()
        data: Dict[str, Any] = {}
        defaults = config.defaults

        # Pre-compila data e ora se impostata a 'now'
        if defaults.date_time:
            if defaults.date_time.lower() == "now":
                data["date_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            else:
                data["date_time"] = defaults.date_time

        # Pre-compila metodo
        if defaults.method:
            data["method"] = defaults.method

        # Pre-compila flusso
        if defaults.flow:
            data["flow"] = defaults.flow

        # Pre-compila importo
        if defaults.amount is not None:
            data["amount"] = float(defaults.amount)

        # Pre-compila o prepara descrizione
        if defaults.description:
            data["description"] = defaults.description
        if defaults.description_prefix:
            context.user_data["desc_prefix"] = defaults.description_prefix
        if defaults.description_suffix:
            context.user_data["desc_suffix"] = defaults.description_suffix

        # Pre-compila cassa
        if defaults.box_money is not None:
            data["box_money"] = float(defaults.box_money)

        context.user_data["tx_data"] = data
        return await advance_or_finish(update, context)

    return custom_starter


async def handle_datetime_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la risposta alla domanda sulla data e ora"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_NOW:
            data["date_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            return await advance_or_finish(update, context)

    text = update.message.text.strip() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)
    if text == "/now":
        data["date_time"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return await advance_or_finish(update, context)

    data["date_time"] = text
    return await advance_or_finish(update, context)


async def handle_method_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la scelta tra Contanti e Satispay"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_METHOD_CASH:
            data["method"] = "Contanti"
            return await advance_or_finish(update, context)
        if query_data == CALLBACK_METHOD_SATISPAY:
            data["method"] = "Satispay"
            return await advance_or_finish(update, context)

    text = update.message.text.strip().lower() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)
    if "contant" in text or "cash" in text:
        data["method"] = "Contanti"
        return await advance_or_finish(update, context)
    if "satispay" in text or "digitale" in text:
        data["method"] = "Satispay"
        return await advance_or_finish(update, context)

    await send_msg(update, "⚠️ Scelta non valida. Premi uno dei pulsanti o digita *Contanti* o *Satispay*.")
    return STATE_METHOD


async def handle_box_before_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento o conferma della cassa iniziale"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_BOX_USE_LAST:
            data["box_money"] = context.user_data.get("suggested_last_box", 0.0)
            return await advance_or_finish(update, context)

    text = update.message.text.strip() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)

    try:
        val = float(text.replace("€", "").replace(",", ".").strip())
        data["box_money"] = val
        return await advance_or_finish(update, context)
    except ValueError:
        await send_msg(update, "⚠️ Inserisci una cifra numerica valida per la cassa (es: `50.00`).")
        return STATE_BOX_BEFORE


async def handle_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento della descrizione"""
    data = context.user_data.setdefault("tx_data", {})
    text = update.message.text.strip() if update.message else ""

    if text == "/cancel":
        return await handle_cancel(update, context)

    prefix = context.user_data.get("desc_prefix", "")
    suffix = context.user_data.get("desc_suffix", "")
    data["description"] = f"{prefix}{text}{suffix}"

    return await advance_or_finish(update, context)

async def handle_flow_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la scelta del flusso di cassa (Entrata o Uscita)"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_FLOW_IN:
            data["flow"] = "Entrata"
            return await advance_or_finish(update, context)
        if query_data == CALLBACK_FLOW_OUT:
            data["flow"] = "Uscita"
            return await advance_or_finish(update, context)

    text = update.message.text.strip().lower() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)
    if "entrat" in text or "in" in text or text == "+":
        data["flow"] = "Entrata"
        return await advance_or_finish(update, context)
    if "uscit" in text or "out" in text or text == "-":
        data["flow"] = "Uscita"
        return await advance_or_finish(update, context)

    await send_msg(update, "⚠️ Scelta non valida. Premi *➕ Entrata* o *➖ Uscita*.")
    return STATE_FLOW


async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento dell'importo"""
    data = context.user_data.setdefault("tx_data", {})
    text = update.message.text.strip() if update.message else ""

    if text == "/cancel":
        return await handle_cancel(update, context)

    try:
        val = float(text.replace("€", "").replace(",", ".").strip())
        if val <= 0:
            await send_msg(update, "⚠️ L'importo deve essere maggiore di zero.")
            return STATE_AMOUNT
        data["amount"] = val
        return await advance_or_finish(update, context)
    except ValueError:
        await send_msg(update, "⚠️ Inserisci una cifra numerica valida per l'importo (es: `12.50`).")
        return STATE_AMOUNT


async def handle_box_after_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce la conferma o inserimento manuale della cassa aggiornata"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_BOX_CONFIRM_CALCULATED:
            data["box_money_updated"] = context.user_data.get("suggested_box_after", 0.0)
            return await advance_or_finish(update, context)

    text = update.message.text.strip() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)

    try:
        val = float(text.replace("€", "").replace(",", ".").strip())
        data["box_money_updated"] = val
        return await advance_or_finish(update, context)
    except ValueError:
        await send_msg(update, "⚠️ Inserisci un importo valido per la cassa aggiornata.")
        return STATE_BOX_AFTER


async def handle_receipt_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gestisce l'inserimento o conferma del numero di ricevuta"""
    data = context.user_data.setdefault("tx_data", {})

    if update.callback_query:
        query_data = update.callback_query.data
        if query_data == CALLBACK_CANCEL:
            return await handle_cancel(update, context)
        if query_data == CALLBACK_RECEIPT_USE_SUGGESTED:
            data["receipt_number"] = context.user_data.get("suggested_receipt", 0)
            return await advance_or_finish(update, context)
        if query_data == CALLBACK_RECEIPT_NONE:
            data["receipt_number"] = 0
            return await advance_or_finish(update, context)

    text = update.message.text.strip() if update.message else ""
    if text == "/cancel":
        return await handle_cancel(update, context)

    if text.isdigit():
        data["receipt_number"] = int(text)
        return await advance_or_finish(update, context)
    else:
        await send_msg(update, "⚠️ Inserisci un numero intero per la ricevuta (oppure `0` se assente).")
        return STATE_RECEIPT


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annulla l'operazione in corso e azzera lo stato"""
    context.user_data.clear()
    await send_msg(update, "❌ Operazione annullata. Nessun dato è stato registrato.")
    return ConversationHandler.END

def build_conversation_handler(custom_commands: Optional[Dict[str, CustomCommandConfig]] = None) -> ConversationHandler:
    """Costruisce il ConversationHandler registrando i comandi base e tutte le macro custom"""
    entry_points = [
        CommandHandler(["write", "w"], start_write),
    ]

    if custom_commands:
        for cmd_name, cmd_cfg in custom_commands.items():
            entry_points.append(
                CommandHandler(cmd_name, make_custom_command_starter(cmd_cfg))
            )

    states = {
        STATE_DATETIME: [
            CallbackQueryHandler(handle_datetime_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_datetime_input),
            CommandHandler("now", handle_datetime_input),
        ],
        STATE_METHOD: [
            CallbackQueryHandler(handle_method_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_method_input),
        ],
        STATE_BOX_BEFORE: [
            CallbackQueryHandler(handle_box_before_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_box_before_input),
        ],
        STATE_DESCRIPTION: [
            CallbackQueryHandler(handle_cancel, pattern=f"^{CALLBACK_CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description_input),
        ],
        STATE_FLOW: [
            CallbackQueryHandler(handle_flow_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_flow_input),
        ],
        STATE_AMOUNT: [
            CallbackQueryHandler(handle_cancel, pattern=f"^{CALLBACK_CANCEL}$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount_input),
        ],
        STATE_BOX_AFTER: [
            CallbackQueryHandler(handle_box_after_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_box_after_input),
        ],
        STATE_RECEIPT: [
            CallbackQueryHandler(handle_receipt_input),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_receipt_input),
        ],
    }

    fallbacks = [
        CommandHandler("cancel", handle_cancel),
        CallbackQueryHandler(handle_cancel, pattern=f"^{CALLBACK_CANCEL}$"),
    ]

    return ConversationHandler(
        entry_points=entry_points,
        states=states,
        fallbacks=fallbacks,
        per_message=False,
    )

