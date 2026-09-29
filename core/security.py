import logging
from functools import wraps
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes
from config import settings

logger = logging.getLogger(__name__)


def is_chat_allowed(chat_id: int) -> bool:
    """
    Verifica se l'ID della chat Telegram è quello autorizzato nella configurazione
    """
    return chat_id == settings.TELEGRAM_ALLOWED_CHAT_ID


def restricted(func: Callable) -> Callable:
    """
    Decoratore per handler di python-telegram-bot.
    Blocca ed ignora qualsiasi interazione proveniente da una chat non autorizzata.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        if not update.effective_chat:
            return None
        
        chat_id = update.effective_chat.id
        if not is_chat_allowed(chat_id):
            logger.warning(
                f"Accesso negato per la chat {chat_id} (utente {update.effective_user.id if update.effective_user else 'Anonimo'}). Attesa chat {settings.TELEGRAM_ALLOWED_CHAT_ID}"
            )
            # Risponde con messaggio di divieto solo se la chat è privata per non spammare i gruppi
            if update.effective_chat.type == "private":
                await update.effective_chat.send_message(
                    "⛔ Non sei autorizzato ad interagire con questo bot."
                )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper
