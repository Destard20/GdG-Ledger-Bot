from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Callback data constants
CALLBACK_NOW = "action:now"
CALLBACK_METHOD_CASH = "method:cash"
CALLBACK_METHOD_SATISPAY = "method:satispay"
CALLBACK_FLOW_IN = "flow:in"
CALLBACK_FLOW_OUT = "flow:out"
CALLBACK_BOX_USE_LAST = "box:use_last"
CALLBACK_BOX_CONFIRM_CALCULATED = "box:confirm_calculated"
CALLBACK_RECEIPT_USE_SUGGESTED = "receipt:use_suggested"
CALLBACK_RECEIPT_NONE = "receipt:none"
CALLBACK_CANCEL = "action:cancel"
CALLBACK_QR_GENERATE = "qr:generate"
CALLBACK_QR_SKIP = "qr:skip"



def get_now_keyboard() -> InlineKeyboardMarkup:
    """Tastiera per impostare la data e ora attuale"""
    buttons = [
        [InlineKeyboardButton("📅 Adesso", callback_data=CALLBACK_NOW)],
        [InlineKeyboardButton("❌ Annulla operazione", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_method_keyboard() -> InlineKeyboardMarkup:
    """Tastiera per selezionare Contanti o Satispay"""
    buttons = [
        [
            InlineKeyboardButton("💵 Contanti", callback_data=CALLBACK_METHOD_CASH),
            InlineKeyboardButton("📱 Satispay", callback_data=CALLBACK_METHOD_SATISPAY)
        ],
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_box_money_keyboard(last_box_money: float) -> InlineKeyboardMarkup:
    """Tastiera per confermare l'ultimo saldo cassa rilevato"""
    buttons = [
        [InlineKeyboardButton(f"✅ Usa saldo attuale ({last_box_money:.2f} €)", callback_data=CALLBACK_BOX_USE_LAST)],
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_flow_keyboard() -> InlineKeyboardMarkup:
    """Tastiera per flusso di cassa Entrata o Uscita"""
    buttons = [
        [
            InlineKeyboardButton("➕ Entrata", callback_data=CALLBACK_FLOW_IN),
            InlineKeyboardButton("➖ Uscita", callback_data=CALLBACK_FLOW_OUT)
        ],
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_box_updated_keyboard(calculated_money: float) -> InlineKeyboardMarkup:
    """Tastiera per confermare il saldo cassa calcolato"""
    buttons = [
        [InlineKeyboardButton(f"✅ Conferma {calculated_money:.2f} €", callback_data=CALLBACK_BOX_CONFIRM_CALCULATED)],
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_receipt_keyboard(suggested_receipt: int) -> InlineKeyboardMarkup:
    """Tastiera per confermare la ricevuta progressiva successiva"""
    buttons = [
        [InlineKeyboardButton(f"✅ Ricevuta #{suggested_receipt}", callback_data=CALLBACK_RECEIPT_USE_SUGGESTED)],
        [InlineKeyboardButton("🚫 Nessuna ricevuta (0)", callback_data=CALLBACK_RECEIPT_NONE)],
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Tastiera con solo pulsante annulla"""
    buttons = [
        [InlineKeyboardButton("❌ Annulla", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_qr_ask_keyboard() -> InlineKeyboardMarkup:
    """Tastiera per chiedere se generare il QR Code Satispay"""
    buttons = [
        [InlineKeyboardButton("📱 Genera QR Code", callback_data=CALLBACK_QR_GENERATE)],
        [InlineKeyboardButton("⏩ Salta e registra subito", callback_data=CALLBACK_QR_SKIP)],
        [InlineKeyboardButton("❌ Annulla operazione", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)


def get_qr_waiting_keyboard() -> InlineKeyboardMarkup:
    """Tastiera durante l'attesa del pagamento del QR Code"""
    buttons = [
        [InlineKeyboardButton("⏩ Salta pagamento e registra", callback_data=CALLBACK_QR_SKIP)],
        [InlineKeyboardButton("❌ Annulla operazione", callback_data=CALLBACK_CANCEL)]
    ]
    return InlineKeyboardMarkup(buttons)

