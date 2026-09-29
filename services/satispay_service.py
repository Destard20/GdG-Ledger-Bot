import base64
import email.utils
import hashlib
import json
import logging
from typing import Optional, Dict, Any
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from config import settings
from core.models import SatispayPayment

logger = logging.getLogger(__name__)


class SatispayService:
    """
    Servizio per l'integrazione con Satispay Business API (firma richieste HTTP e parsing notifiche)
    """

    def __init__(self):
        self.is_staging = settings.SATISPAY_STAGING
        self.base_url = (
            "https://staging.authservices.satispay.com"
            if self.is_staging
            else "https://authservices.satispay.com"
        )
        self.key_id = settings.SATISPAY_KEY_ID
        self.private_key = self._load_private_key()

    def _load_private_key(self):
        path = settings.satispay_private_key_path
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        except Exception as e:
            logger.warning(f"Impossibile caricare la chiave privata Satispay da {path}: {e}")
            return None

    def generate_auth_header(self, method: str, path: str, body: bytes = b"") -> Dict[str, str]:
        """
        Genera l'intestazione Authorization conforme allo standard HTTP Signatures di Satispay
        """
        if not self.private_key or not self.key_id:
            raise ValueError("Satispay non configurato: mancano KeyID o chiave privata RSA.")

        date_header = email.utils.formatdate(usegmt=True)
        host_header = self.base_url.replace("https://", "").replace("http://", "").split("/")[0]

        digest_sha256 = hashlib.sha256(body).digest()
        digest_b64 = base64.b64encode(digest_sha256).decode("utf-8")
        digest_header = f"SHA-256={digest_b64}"

        signature_string = (
            f"(request-target): {method.lower()} {path}\n"
            f"host: {host_header}\n"
            f"date: {date_header}\n"
            f"digest: {digest_header}"
        )

        signed_bytes = self.private_key.sign(
            signature_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signed_bytes).decode("utf-8")

        auth_header_value = (
            f'Signature keyId="{self.key_id}", algorithm="rsa-sha256", '
            f'headers="(request-target) host date digest", signature="{signature_b64}"'
        )

        return {
            "Host": host_header,
            "Date": date_header,
            "Digest": digest_header,
            "Authorization": auth_header_value
        }

    async def get_payment(self, payment_id: str) -> Optional[SatispayPayment]:
        """
        Recupera i dettagli di un pagamento tramite API Satispay
        """
        path = f"/g_business/v1/payments/{payment_id}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        if self.private_key and self.key_id:
            auth_headers = self.generate_auth_header("GET", path)
            headers.update(auth_headers)

        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=10.0)
                if res.status_code == 200:
                    data = res.json()
                    return SatispayPayment(
                        id=data.get("id", payment_id),
                        amount_unit=data.get("amount_unit", 0),
                        currency=data.get("currency", "EUR"),
                        status=data.get("status", "UNKNOWN"),
                        flow=data.get("flow"),
                        type=data.get("type"),
                        sender_name=data.get("sender_value") or data.get("consumer_name"),
                        comment=data.get("comment"),
                        insert_date=data.get("insert_date")
                    )
                else:
                    logger.error(f"Errore chiamata Satispay GET payment ({res.status_code}): {res.text}")
                    return None
        except Exception as e:
            logger.error(f"Eccezione durante chiamata Satispay: {e}")
            return None

    def parse_webhook_payload(self, raw_data: Dict[str, Any]) -> SatispayPayment:
        """
        Converte i dati grezzi ricevuti dal webhook in un oggetto SatispayPayment
        """
        payment_id = raw_data.get("id") or raw_data.get("payment_id") or "ID_SCONOSCIUTO"
        amount_unit = raw_data.get("amount_unit")
        if amount_unit is None and "amount" in raw_data:
            amount_unit = int(float(raw_data["amount"]) * 100)
        elif amount_unit is None:
            amount_unit = 0

        sender = (
            raw_data.get("sender_name")
            or raw_data.get("sender_value")
            or raw_data.get("consumer_name")
            or (raw_data.get("sender", {}).get("name") if isinstance(raw_data.get("sender"), dict) else None)
        )

        return SatispayPayment(
            id=payment_id,
            amount_unit=int(amount_unit),
            currency=raw_data.get("currency", "EUR"),
            status=raw_data.get("status", "ACCEPTED"),
            flow=raw_data.get("flow", "MATCH_CODE"),
            type=raw_data.get("type", "TO_BUSINESS"),
            sender_name=sender or "Utente Satispay",
            comment=raw_data.get("comment"),
            insert_date=raw_data.get("insert_date")
        )


satispay_service = SatispayService()
