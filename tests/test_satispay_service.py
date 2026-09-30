from services.satispay_service import SatispayService
from satispay_setup import generate_rsa_keypair


def test_parse_webhook_payload():
    service = SatispayService()
    raw = {
        "id": "pay-12345",
        "amount_unit": 2550,
        "currency": "EUR",
        "status": "ACCEPTED",
        "sender_name": "Mario Rossi",
        "comment": "Quota iscrizione",
        "insert_date": "2026-09-29T20:00:00Z"
    }

    payment = service.parse_webhook_payload(raw)
    assert payment.id == "pay-12345"
    assert payment.amount_unit == 2550
    assert payment.amount_euro == 25.50
    assert payment.sender_name == "Mario Rossi"
    assert payment.comment == "Quota iscrizione"


def test_parse_webhook_payload_amount_fallback():
    service = SatispayService()
    raw = {
        "id": "pay-fallback",
        "amount": 10.50,
        "consumer_name": "Anna Bianchi"
    }
    payment = service.parse_webhook_payload(raw)
    assert payment.id == "pay-fallback"
    assert payment.amount_unit == 1050
    assert payment.amount_euro == 10.50
    assert payment.sender_name == "Anna Bianchi"


def test_rsa_key_generation():
    private_pem, public_pem = generate_rsa_keypair(key_size=2048)
    assert "-----BEGIN PRIVATE KEY-----" in private_pem
    assert "-----END PRIVATE KEY-----" in private_pem
    assert "-----BEGIN PUBLIC KEY-----" in public_pem
    assert "-----END PUBLIC KEY-----" in public_pem


import tempfile
import pytest
from unittest.mock import AsyncMock
from core.models import SatispayPayment
from services.db_service import DatabaseService


@pytest.mark.asyncio
async def test_poll_new_payments_behavior(monkeypatch):
    service = SatispayService()

    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        test_db = DatabaseService(tmp.name)
        monkeypatch.setattr("services.db_service.db_service", test_db)

        p1 = SatispayPayment(id="sat_1", amount_unit=1000, status="ACCEPTED", sender_name="User1", insert_date="2026-09-30T10:00:00Z")
        p2 = SatispayPayment(id="sat_2", amount_unit=2000, status="ACCEPTED", sender_name="User2", insert_date="2026-09-30T10:05:00Z")

        # Mock della chiamata API
        service.get_payments_history = AsyncMock(return_value=[p2, p1])

        # 1. Primo ciclo: DB vuoto -> sincronizzazione iniziale silenziosa (restituisce [])
        first_run_new = await service.poll_new_payments()
        assert first_run_new == []
        assert test_db.has_payment("sat_1") is True
        assert test_db.has_payment("sat_2") is True

        # 2. Secondo ciclo: nessun nuovo pagamento -> restituisce []
        second_run_new = await service.poll_new_payments()
        assert second_run_new == []

        # 3. Terzo ciclo: arriva p3 -> rileva e restituisce [p3]
        p3 = SatispayPayment(id="sat_3", amount_unit=3000, status="ACCEPTED", sender_name="User3", insert_date="2026-09-30T10:10:00Z")
        service.get_payments_history = AsyncMock(return_value=[p3, p2, p1])

        third_run_new = await service.poll_new_payments()
        assert len(third_run_new) == 1
        assert third_run_new[0].id == "sat_3"
        assert test_db.has_payment("sat_3") is True



def test_generate_qr_code_image():
    service = SatispayService()
    buf = service.generate_qr_code_image("https://online.satispay.com/pay/test-uuid")
    assert buf is not None
    data = buf.getvalue()
    assert len(data) > 0
    # Verifica intestazione PNG standard
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

