import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException, Query, BackgroundTasks
import uvicorn
from telegram.ext import ApplicationBuilder, CommandHandler
from config import settings
from core.security import is_chat_allowed
from core.models import SatispayPayment
from services.sheets_service import get_sheets_service
from services.satispay_service import satispay_service
from bot.custom_commands import load_custom_commands, build_bot_commands_list
from bot.conversation import build_conversation_handler
from bot.handlers import start_handler, help_handler, link_handler, unlink_handler, error_handler

# Configurazione del logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("GdG-Ledger-Bot")

# Applicazione Telegram globale
telegram_app = None


async def send_satispay_echo(payment: SatispayPayment):
    """
    Invia il messaggio di echo della transazione Satispay nella chat Telegram autorizzata
    """
    if not telegram_app:
        logger.warning("Telegram Bot non pronto, impossibile inviare la notifica Satispay.")
        return

    chat_id = settings.TELEGRAM_ALLOWED_CHAT_ID
    if not chat_id:
        logger.warning("TELEGRAM_ALLOWED_CHAT_ID non configurato.")
        return

    flow_text = "Ricevuto pagamento da" if payment.flow != "REFUND" else "Rimborso verso"
    amount_sign = "+" if payment.flow != "REFUND" else "-"

    echo_text = (
        "🔔 *Notifica Pagamento Satispay*\n\n"
        f"📥 *{flow_text}:* {payment.sender_name or 'Cliente'}\n"
        f"💰 *Importo:* `{amount_sign}{payment.amount_euro:.2f} €`\n"
        f"🆔 *ID Satispay:* `{payment.id}`\n"
        f"📝 *Note:* {payment.comment or 'Nessuna nota'}\n"
        f"⏰ *Data:* {payment.insert_date or 'Adesso'}\n\n"
        "💡 *Per associare questa transazione a una riga del registro, "
        "rispondi a questo messaggio con:*\n`/link <id_transazione>`"
    )

    try:
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=echo_text,
            parse_mode="Markdown"
        )
        logger.info(f"Notifica Satispay {payment.id} inviata alla chat {chat_id}")
    except Exception as e:
        logger.error(f"Errore durante l'invio della notifica Satispay su Telegram: {e}")


# ==========================================
# Inizializzazione FastAPI Webhook Server
# ==========================================
api_app = FastAPI(title="GdG-Ledger-Bot Satispay Webhook Server")


@api_app.get("/health")
async def health_check():
    return {"status": "ok", "service": "GdG-Ledger-Bot"}


@api_app.post("/webhook/satispay")
@api_app.get("/webhook/satispay")
async def satispay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: Optional[str] = Query(None),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
):
    """
    Riceve le chiamate callback da Satispay al verificarsi di un pagamento
    """
    # Verifica del segreto se configurato
    if settings.WEBHOOK_SECRET:
        token = secret or x_webhook_secret
        if token != settings.WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Secret non valido")

    payload: Dict[str, Any] = {}
    if request.method == "POST":
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    # Supporta anche ID passato come parametro query (?id=... o ?payment_id=...)
    query_id = request.query_params.get("id") or request.query_params.get("payment_id")
    if query_id and "id" not in payload:
        payload["id"] = query_id

    payment_id = payload.get("id") or payload.get("payment_id")
    payment: Optional[SatispayPayment] = None

    # Se abbiamo un ID e le credenziali Satispay per interrogare l'API, recuperiamo i dettagli ufficiali
    if payment_id and settings.SATISPAY_KEY_ID:
        payment = await satispay_service.get_payment(str(payment_id))

    # In alternativa costruiamo l'oggetto dai dati presenti nel webhook
    if not payment:
        payment = satispay_service.parse_webhook_payload(payload)

    # Invia la notifica in background su Telegram
    background_tasks.add_task(send_satispay_echo, payment)

    return {"status": "received", "id": payment.id}
@api_app.post("/webhook/satispay/test")
async def satispay_test_webhook(background_tasks: BackgroundTasks, amount: float = 10.0, sender: str = "Mario Rossi"):
    """
    Endpoint per simulare la ricezione di un pagamento Satispay e testare l'echo su Telegram
    """
    payment = SatispayPayment(
        id="test-sat-" + str(asyncio.get_event_loop().time()).replace(".", "")[:8],
        amount_unit=int(amount * 100),
        currency="EUR",
        status="ACCEPTED",
        flow="MATCH_CODE",
        sender_name=sender,
        comment="Test transazione simulata",
        insert_date="Adesso"
    )
    background_tasks.add_task(send_satispay_echo, payment)
    return {"status": "simulated", "payment": payment}


def create_telegram_app():
    """
    Inizializza l'applicazione Telegram con tutti gli handler registrati
    """
    custom_cmds = load_custom_commands()
    logger.info(f"Comandi personalizzati caricati: {list(custom_cmds.keys())}")

    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.bot_data["custom_commands"] = custom_cmds

    # Registra il ConversationHandler principale (/write, /w e custom commands)
    conv_handler = build_conversation_handler(custom_cmds)
    app.add_handler(conv_handler)

    # Registra handler comandi base
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("link", link_handler))
    app.add_handler(CommandHandler("unlink", unlink_handler))

    # Handler errori
    app.add_error_handler(error_handler)

    return app, custom_cmds


async def run_services():
    """
    Avvia contemporaneamente il Telegram Bot (polling) e il server FastAPI (uvicorn)
    """
    global telegram_app

    # Assicura intestazioni sul foglio
    sheets = get_sheets_service()
    try:
        sheets.ensure_headers()
        logger.info("Foglio di calcolo verificato.")
    except Exception as e:
        logger.warning(f"Impossibile verificare intestazioni Google Sheets: {e}")

    telegram_app, custom_cmds = create_telegram_app()

    # Configurazione server Webhook
    server_config = uvicorn.Config(
        app=api_app,
        host=settings.WEBHOOK_HOST,
        port=settings.WEBHOOK_PORT,
        log_level="info"
    )
    server = uvicorn.Server(server_config)

    logger.info("Avvio bot Telegram e server Webhook...")
    async with telegram_app:
        await telegram_app.start()

        # Registra i comandi su Telegram per l'autocompletamento
        try:
            bot_commands = build_bot_commands_list(custom_cmds)
            await telegram_app.bot.set_my_commands(bot_commands)
            logger.info("Comandi registrati con successo con Telegram setMyCommands.")
        except Exception as e:
            logger.warning(f"Impossibile registrare setMyCommands su Telegram: {e}")

        await telegram_app.updater.start_polling()
        logger.info(f"Bot pronto e in ascolto. Webhook server su http://{settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}")

        try:
            await server.serve()
        finally:
            logger.info("Chiusura in corso...")
            await telegram_app.updater.stop()
            await telegram_app.stop()


def main():
    try:
        asyncio.run(run_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot arrestato dall'utente.")


if __name__ == "__main__":
    main()

