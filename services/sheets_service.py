import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from config import settings
from core.models import Transaction

logger = logging.getLogger(__name__)


class SheetsServiceInterface(ABC):
    """
    Interfaccia astratta per il servizio di gestione del registro su foglio di calcolo
    """

    @abstractmethod
    def ensure_headers(self, worksheet_name: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_last_transaction_id(self, worksheet_name: Optional[str] = None) -> int:
        pass

    @abstractmethod
    def get_last_box_money(self, worksheet_name: Optional[str] = None) -> float:
        pass

    @abstractmethod
    def get_last_receipt_number(self, worksheet_name: Optional[str] = None) -> int:
        pass

    @abstractmethod
    def add_transaction(self, transaction: Transaction, worksheet_name: Optional[str] = None) -> Transaction:
        pass

    @abstractmethod
    def link_satispay_id(self, transaction_id: int, satispay_id: str, worksheet_name: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    def unlink_satispay_id(
        self,
        satispay_id: str,
        transaction_id: Optional[int] = None,
        worksheet_name: Optional[str] = None
    ) -> int:
        pass

    @abstractmethod
    def get_transaction_by_id(self, transaction_id: int, worksheet_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        pass


class MockSheetsService(SheetsServiceInterface):
    """
    Implementazione Mock in-memory per test locali e sviluppo senza credenziali Google Sheets
    """

    def __init__(self):
        self.sheets: Dict[str, List[List[Any]]] = {}
        logger.info("Inizializzato MockSheetsService (memoria locale)")

    def _get_sheet_data(self, worksheet_name: Optional[str] = None) -> List[List[Any]]:
        name = worksheet_name or settings.GOOGLE_WORKSHEET_NAME
        if name not in self.sheets:
            self.sheets[name] = [Transaction.sheet_headers()]
        return self.sheets[name]

    def ensure_headers(self, worksheet_name: Optional[str] = None) -> None:
        self._get_sheet_data(worksheet_name)

    def get_last_transaction_id(self, worksheet_name: Optional[str] = None) -> int:
        rows = self._get_sheet_data(worksheet_name)[1:]
        last_id = 0
        for row in rows:
            if len(row) > 0 and str(row[0]).strip().isdigit():
                val = int(row[0])
                if val > last_id:
                    last_id = val
        return last_id

    def get_last_box_money(self, worksheet_name: Optional[str] = None) -> float:
        rows = self._get_sheet_data(worksheet_name)[1:]
        for row in reversed(rows):
            if len(row) > 7 and row[7]:
                try:
                    cleaned = str(row[7]).replace("€", "").replace(",", ".").strip()
                    if cleaned:
                        return float(cleaned)
                except ValueError:
                    continue
        return 0.0

    def get_last_receipt_number(self, worksheet_name: Optional[str] = None) -> int:
        rows = self._get_sheet_data(worksheet_name)[1:]
        last_receipt = 0
        for row in rows:
            if len(row) > 8 and str(row[8]).strip().isdigit():
                val = int(row[8])
                if val > last_receipt:
                    last_receipt = val
        return last_receipt

    def add_transaction(self, transaction: Transaction, worksheet_name: Optional[str] = None) -> Transaction:
        name = worksheet_name or settings.GOOGLE_WORKSHEET_NAME
        sheet = self._get_sheet_data(name)
        new_id = self.get_last_transaction_id(name) + 1
        transaction.id = new_id
        sheet.append(transaction.to_sheet_row())
        logger.info(f"[MockSheets] Aggiunta transazione ID {new_id} al foglio {name}")
        return transaction

    def link_satispay_id(self, transaction_id: int, satispay_id: str, worksheet_name: Optional[str] = None) -> bool:
        sheet = self._get_sheet_data(worksheet_name)
        for row in sheet[1:]:
            if len(row) > 0 and str(row[0]).strip() == str(transaction_id):
                while len(row) <= 11:
                    row.append("")
                row[11] = satispay_id
                return True
        return False

    def unlink_satispay_id(
        self,
        satispay_id: str,
        transaction_id: Optional[int] = None,
        worksheet_name: Optional[str] = None
    ) -> int:
        sheet = self._get_sheet_data(worksheet_name)
        unlinked_count = 0
        for row in sheet[1:]:
            if len(row) > 11 and row[11] == satispay_id:
                if transaction_id is None or str(row[0]).strip() == str(transaction_id):
                    row[11] = ""
                    unlinked_count += 1
        return unlinked_count

    def get_transaction_by_id(self, transaction_id: int, worksheet_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        sheet = self._get_sheet_data(worksheet_name)
        headers = sheet[0]
        for row in sheet[1:]:
            if len(row) > 0 and str(row[0]).strip() == str(transaction_id):
                return {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        return None


class GoogleSheetsService(SheetsServiceInterface):
    """
    Implementazione reale del servizio tramite API di Google Sheets e gspread
    """

    def __init__(self):
        import gspread
        self.gspread = gspread
        self.client = None
        self._init_client()

    def _init_client(self):
        if not settings.google_credentials_path.exists():
            raise FileNotFoundError(
                f"File credenziali Google non trovato in: {settings.GOOGLE_SERVICE_ACCOUNT_FILE}. "
                "Verifica il percorso o imposta USE_MOCK_SHEETS=true nel file .env."
            )
        self.client = self.gspread.service_account(filename=str(settings.google_credentials_path))
        logger.info("Client Google Sheets autenticato con successo")

    @staticmethod
    def _clean_spreadsheet_id(raw_id: str) -> str:
        raw_id = raw_id.strip()
        if "docs.google.com/spreadsheets/d/" in raw_id:
            return raw_id.split("/d/")[1].split("/")[0]
        return raw_id

    def _get_worksheet(self, worksheet_name: Optional[str] = None):
        name = worksheet_name or settings.GOOGLE_WORKSHEET_NAME
        spreadsheet_id = self._clean_spreadsheet_id(settings.GOOGLE_SPREADSHEET_ID)
        spreadsheet = self.client.open_by_key(spreadsheet_id)
        try:
            return spreadsheet.worksheet(name)
        except self.gspread.exceptions.WorksheetNotFound:
            logger.info(f"Foglio '{name}' non trovato. Creazione nuovo foglio...")
            ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
            ws.append_row(Transaction.sheet_headers())
            return ws

    def ensure_headers(self, worksheet_name: Optional[str] = None) -> None:
        ws = self._get_worksheet(worksheet_name)
        first_row = ws.row_values(1)
        if not first_row:
            headers = Transaction.sheet_headers()
            ws.insert_row(headers, 1)
            logger.info(f"Intestazioni inserite nel foglio '{ws.title}'")

    def get_last_transaction_id(self, worksheet_name: Optional[str] = None) -> int:
        ws = self._get_worksheet(worksheet_name)
        col_values = ws.col_values(1)
        last_id = 0
        for val in col_values[1:]:
            if str(val).strip().isdigit():
                num = int(val)
                if num > last_id:
                    last_id = num
        return last_id

    def get_last_box_money(self, worksheet_name: Optional[str] = None) -> float:
        ws = self._get_worksheet(worksheet_name)
        col_values = ws.col_values(8)
        for val in reversed(col_values[1:]):
            if val:
                try:
                    cleaned = str(val).replace("€", "").replace(",", ".").strip()
                    if cleaned:
                        return float(cleaned)
                except ValueError:
                    continue
        return 0.0

    def get_last_receipt_number(self, worksheet_name: Optional[str] = None) -> int:
        ws = self._get_worksheet(worksheet_name)
        col_values = ws.col_values(9)
        last_receipt = 0
        for val in col_values[1:]:
            if str(val).strip().isdigit():
                num = int(val)
                if num > last_receipt:
                    last_receipt = num
        return last_receipt

    def add_transaction(self, transaction: Transaction, worksheet_name: Optional[str] = None) -> Transaction:
        ws = self._get_worksheet(worksheet_name)
        new_id = self.get_last_transaction_id(worksheet_name) + 1
        transaction.id = new_id
        ws.append_row(transaction.to_sheet_row())
        logger.info(f"Transazione #{new_id} registrata su Google Sheets")
        return transaction

    def link_satispay_id(self, transaction_id: int, satispay_id: str, worksheet_name: Optional[str] = None) -> bool:
        ws = self._get_worksheet(worksheet_name)
        col_values = ws.col_values(1)
        target_row = None
        for idx, val in enumerate(col_values, start=1):
            if idx == 1:
                continue
            if str(val).strip() == str(transaction_id):
                target_row = idx
                break

        if target_row is not None:
            ws.update_cell(target_row, 12, satispay_id)
            logger.info(f"Riga {target_row} (ID #{transaction_id}) collegata a Satispay ID {satispay_id}")
            return True
        return False

    def unlink_satispay_id(
        self,
        satispay_id: str,
        transaction_id: Optional[int] = None,
        worksheet_name: Optional[str] = None
    ) -> int:
        ws = self._get_worksheet(worksheet_name)
        col_satispay = ws.col_values(12)
        col_ids = ws.col_values(1)
        unlinked_count = 0

        for idx, val in enumerate(col_satispay, start=1):
            if idx == 1:
                continue
            if str(val).strip() == satispay_id:
                row_id = col_ids[idx - 1] if idx - 1 < len(col_ids) else ""
                if transaction_id is None or str(row_id).strip() == str(transaction_id):
                    ws.update_cell(idx, 12, "")
                    unlinked_count += 1

        logger.info(f"Scollegate {unlinked_count} occorrenze di Satispay ID {satispay_id}")
        return unlinked_count

    def get_transaction_by_id(self, transaction_id: int, worksheet_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        ws = self._get_worksheet(worksheet_name)
        records = ws.get_all_records()
        for rec in records:
            if str(rec.get("ID", "")).strip() == str(transaction_id):
                return rec
        return None


_sheets_service_instance: Optional[SheetsServiceInterface] = None


def get_sheets_service() -> SheetsServiceInterface:
    """
    Ritorna l'istanza configurata del servizio fogli di calcolo (Mock o Reale)
    """
    global _sheets_service_instance
    if _sheets_service_instance is None:
        if settings.USE_MOCK_SHEETS or not settings.GOOGLE_SPREADSHEET_ID or not settings.google_credentials_path.exists():
            logger.info("Utilizzo MockSheetsService (USE_MOCK_SHEETS=true o credenziali assenti)")
            _sheets_service_instance = MockSheetsService()
        else:
            try:
                _sheets_service_instance = GoogleSheetsService()
            except Exception as e:
                logger.error(f"Errore GoogleSheetsService: {e}. Ripiego su MockSheetsService.")
                _sheets_service_instance = MockSheetsService()
    return _sheets_service_instance

