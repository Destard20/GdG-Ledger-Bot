import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from config import settings
from core.models import SatispayPayment

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Servizio per la memorizzazione locale su SQLite delle transazioni Satispay
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.SQLITE_DB_PATH
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Inizializza le tabelle del database se non esistono"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS satispay_payments (
                    id TEXT PRIMARY KEY,
                    amount_unit INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    status TEXT NOT NULL,
                    flow TEXT,
                    type TEXT,
                    sender_name TEXT,
                    comment TEXT,
                    insert_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Vista di comodità per interrogazioni dirette su 'payments'
            conn.execute("CREATE VIEW IF NOT EXISTS payments AS SELECT * FROM satispay_payments;")
            conn.commit()
            logger.info(f"Database SQLite inizializzato in: {self.db_path}")

    def is_empty(self) -> bool:
        """Verifica se il database è vuoto (nessun pagamento salvato)"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM satispay_payments;")
            count = cursor.fetchone()[0]
            return count == 0

    def count_payments(self) -> int:
        """Restituisce il numero totale di pagamenti presenti nel database"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM satispay_payments;")
            return cursor.fetchone()[0]

    def has_payment(self, payment_id: str) -> bool:
        """Verifica se un pagamento con un dato ID Satispay è già registrato nel DB"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM satispay_payments WHERE id = ?;", (payment_id,))
            return cursor.fetchone() is not None

    def save_payment(self, payment: SatispayPayment) -> bool:
        """Salva una transazione Satispay nel database se non già presente, o ne aggiorna il mittente"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT sender_name FROM satispay_payments WHERE id = ?;", (payment.id,))
            row = cursor.fetchone()
            if row:
                # Se presente ma senza sender_name, aggiornalo
                if not row["sender_name"] and payment.sender_name:
                    conn.execute("UPDATE satispay_payments SET sender_name = ? WHERE id = ?;", (payment.sender_name, payment.id))
                    conn.commit()
                return False

            conn.execute("""
                INSERT OR IGNORE INTO satispay_payments
                (id, amount_unit, currency, status, flow, type, sender_name, comment, insert_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                payment.id,
                payment.amount_unit,
                payment.currency,
                payment.status,
                payment.flow,
                payment.type,
                payment.sender_name,
                payment.comment,
                payment.insert_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
            logger.info(f"[SQLite] Salvato pagamento Satispay ID: {payment.id} ({payment.amount_euro:.2f}€ - {payment.sender_name})")
            return True

    def get_payment_by_id(self, payment_id: str) -> Optional[SatispayPayment]:
        """Recupera un pagamento dato il suo ID Satispay"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM satispay_payments WHERE id = ?;", (payment_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_recent_payments(self, limit: int = 10) -> List[SatispayPayment]:
        """Recupera gli ultimi N pagamenti registrati nel database (in ordine decrescente dal più recente)"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM satispay_payments
                ORDER BY datetime(insert_date) DESC, created_at DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _parse_input_date(date_str: str) -> str:
        """Normalizza la data di input in formato standard YYYY-MM-DD"""
        cleaned = date_str.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return cleaned

    def get_payments_by_date(self, date_str: str) -> List[SatispayPayment]:
        """
        Recupera tutti i pagamenti registrati in una specifica data.
        Accetta formati come 'DD/MM/YYYY' o 'YYYY-MM-DD'.
        """
        norm_date = self._parse_input_date(date_str)
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM satispay_payments
                WHERE date(insert_date, 'localtime') = ?
                   OR insert_date LIKE ?
                ORDER BY datetime(insert_date) ASC, created_at ASC;
            """, (norm_date, f"{norm_date}%"))
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    def get_payments_by_range(self, start_date_str: str, end_date_str: str) -> List[SatispayPayment]:
        """
        Recupera tutti i pagamenti compresi in un intervallo di date (inclusive).
        Accetta formati come 'DD/MM/YYYY' o 'YYYY-MM-DD'.
        """
        start_norm = self._parse_input_date(start_date_str)
        end_norm = self._parse_input_date(end_date_str)

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM satispay_payments
                WHERE (date(insert_date, 'localtime') BETWEEN ? AND ?)
                   OR (substr(insert_date, 1, 10) BETWEEN ? AND ?)
                ORDER BY datetime(insert_date) ASC, created_at ASC;
            """, (start_norm, end_norm, start_norm, end_norm))
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    def _row_to_model(self, row: sqlite3.Row) -> SatispayPayment:
        return SatispayPayment(
            id=row["id"],
            amount_unit=row["amount_unit"],
            currency=row["currency"],
            status=row["status"],
            flow=row["flow"],
            type=row["type"],
            sender_name=row["sender_name"],
            comment=row["comment"],
            insert_date=row["insert_date"]
        )


db_service = DatabaseService()
