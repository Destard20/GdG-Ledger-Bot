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
