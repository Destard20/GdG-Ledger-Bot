from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurazione applicativa del Ledger Bot caricata da file .env
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = "mock_token"
    TELEGRAM_ALLOWED_CHAT_ID: int = 0

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "credentials.json"
    GOOGLE_SPREADSHEET_ID: str = ""
    GOOGLE_WORKSHEET_NAME: str = "Transazioni"
    USE_MOCK_SHEETS: bool = False

    # Satispay
    SATISPAY_KEY_ID: Optional[str] = None
    SATISPAY_PRIVATE_KEY_FILE: str = "satispay_private.pem"
    SATISPAY_STAGING: bool = False

    # Satispay Polling & Database
    SATISPAY_POLL_INTERVAL: int = 10  # Intervallo polling in secondi
    SQLITE_DB_PATH: str = "satispay_history.db"

    # Custom Commands
    CUSTOM_COMMANDS_DIR: str = "custom_commands"

    @property
    def satispay_private_key_path(self) -> Path:
        return Path(self.SATISPAY_PRIVATE_KEY_FILE)

    @property
    def google_credentials_path(self) -> Path:
        return Path(self.GOOGLE_SERVICE_ACCOUNT_FILE)


settings = Settings()
