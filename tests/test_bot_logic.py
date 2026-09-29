import pytest
from httpx import AsyncClient, ASGITransport
from config import settings
from core.security import is_chat_allowed
from bot.handlers import extract_satispay_id_from_text
from main import api_app


def test_is_chat_allowed():
    settings.TELEGRAM_ALLOWED_CHAT_ID = 12345
    assert is_chat_allowed(12345) is True
    assert is_chat_allowed(99999) is False
    assert is_chat_allowed(-100123) is False


def test_extract_satispay_id_from_text():
    sample_text = (
        "🔔 *Notifica Pagamento Satispay*\n\n"
        "📥 *Ricevuto pagamento da:* Mario Rossi\n"
        "💰 *Importo:* `+15.00 €`\n"
        "🆔 *ID Satispay:* `e8f52f8d-69f2-4e89-9a74-954f9a0c71bd`\n"
    )
    extracted = extract_satispay_id_from_text(sample_text)
    assert extracted == "e8f52f8d-69f2-4e89-9a74-954f9a0c71bd"

    sample_simple = "ID Satispay: sat_custom_123"
    extracted_simple = extract_satispay_id_from_text(sample_simple)
    assert extracted_simple == "sat_custom_123"

    sample_no_id = "Questo è un messaggio normale senza identificativo"
    assert extract_satispay_id_from_text(sample_no_id) is None


@pytest.mark.asyncio
async def test_api_health_endpoint():
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "GdG-Ledger-Bot"}


@pytest.mark.asyncio
async def test_api_satispay_test_endpoint():
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhook/satispay/test?amount=12.5&sender=Luigi")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "simulated"
        assert data["payment"]["amount_unit"] == 1250
        assert data["payment"]["sender_name"] == "Luigi"
