from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """
    Modello di una transazione finanziaria per il registro
    """
    id: Optional[int] = None
    date_time: str
    method: str  # "Contanti" oppure "Satispay"
    box_money: Optional[float] = None  # Cassa iniziale prima della transazione (solo contanti)
    description: str
    flow: str  # "Entrata" oppure "Uscita"
    amount: float
    box_money_updated: Optional[float] = None  # Cassa aggiornata (solo contanti)
    receipt_number: int  # Numero progressivo ricevuta (0 se non applicabile)
    telegram_username: str
    telegram_user_id: int
    satispay_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_sheet_row(self) -> List[Any]:
        """
        Converte la transazione in una lista di valori per la riga del foglio di calcolo
        """
        return [
            self.id if self.id is not None else "",
            self.date_time,
            self.method,
            f"{self.box_money:.2f}" if self.box_money is not None else "",
            self.description,
            self.flow,
            f"{self.amount:.2f}",
            f"{self.box_money_updated:.2f}" if self.box_money_updated is not None else "",
            self.receipt_number,
            self.telegram_username,
            str(self.telegram_user_id),
            self.satispay_id or "",
            self.created_at
        ]

    @classmethod
    def sheet_headers(cls) -> List[str]:
        """
        Intestazioni delle colonne nel foglio di calcolo
        """
        return [
            "ID",
            "Data e Ora",
            "Metodo",
            "Cassa Iniziale (€)",
            "Descrizione",
            "Flusso",
            "Importo (€)",
            "Cassa Aggiornata (€)",
            "Numero Ricevuta",
            "Operatore",
            "Telegram ID",
            "ID Satispay",
            "Data Registrazione"
        ]


class CustomCommandDefaults(BaseModel):
    """
    Valori predefiniti configurabili per un comando personalizzato
    """
    date_time: Optional[str] = None  # es: "now"
    method: Optional[str] = None     # es: "Contanti" o "Satispay"
    flow: Optional[str] = None       # es: "Entrata" o "Uscita"
    amount: Optional[float] = None   # es: 1.50
    description: Optional[str] = None
    description_prefix: Optional[str] = None
    description_suffix: Optional[str] = None
    box_money: Optional[float] = None


class CustomCommandConfig(BaseModel):
    """
    Configurazione di un comando personalizzato da file YAML/JSON
    """
    command: str
    description: str
    defaults: CustomCommandDefaults = Field(default_factory=CustomCommandDefaults)


class SatispayPayment(BaseModel):
    """
    Modello per una notifica/dettaglio pagamento Satispay
    """
    id: str
    amount_unit: int  # in centesimi (es. 1000 = 10.00 EUR)
    currency: str = "EUR"
    status: str
    flow: Optional[str] = None  # es: "MATCH_CODE", "REFUND", ecc.
    type: Optional[str] = None  # es: "TO_BUSINESS", "TO_CONSUMER"
    sender_name: Optional[str] = None
    comment: Optional[str] = None
    insert_date: Optional[str] = None

    @property
    def amount_euro(self) -> float:
        return self.amount_unit / 100.0
