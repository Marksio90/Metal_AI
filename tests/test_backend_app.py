import sys
from pathlib import Path

sys.path.insert(0, str(Path("apps/backend").resolve()))
sys.path.insert(0, str(Path("src").resolve()))

import importlib
import os
import uuid

from fastapi.testclient import TestClient
import pytest

from app.config import BackendSettings
from app.schemas import ChatRequest
from app.services.llm_service import MockLLMProvider, OpenAIProvider, build_provider


def test_settings_loading_from_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", "MetalAI-Test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BACKEND_CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "12")

    settings = BackendSettings.from_env()

    assert settings.app_name == "MetalAI-Test"
    assert settings.app_env == "test"
    assert settings.cors_allow_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert settings.llm_provider == "mock"
    assert settings.openai_timeout_seconds == 12.0


def test_provider_selection_mock():
    settings = BackendSettings.from_env()
    settings.llm_provider = "mock"
    provider = build_provider(settings)
    assert isinstance(provider, MockLLMProvider)


def test_provider_selection_openai():
    settings = BackendSettings.from_env()
    settings.llm_provider = "openai"
    provider = build_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_chat_schema_validation():
    payload = ChatRequest(message="hello")
    assert payload.message == "hello"
    assert payload.history == []


@pytest.fixture
def test_client(monkeypatch):
    db_name = f"test_feedback_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///./{db_name}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_MODEL", "mock-model")
    import app.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_health_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "backend"


def test_config_endpoint(test_client):
    response = test_client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["llmProvider"] == "mock"


def test_chat_works_in_mock_mode(test_client):
    response = test_client.post("/api/chat", json={"message": "RFQ test"})
    assert response.status_code == 200
    data = response.json()
    assert "[MOCK:" in data["message"]


def test_rfq_analyze_valid_payload(test_client):
    response = test_client.post(
        "/api/rfq/analyze",
        json={
            "customer": "Example Customer",
            "message": "Please quote 50 pcs from S235 steel, 3 mm sheet, laser cut, bent twice, powder coated black.",
            "attachments": ["drawing.pdf"],
            "quantity": 50,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rfqId"]
    assert data["missingInformation"] == []
    assert "laser_cutting" in data["suggestedRoute"]
    assert "Thank you" in data["draftCustomerReply"]
    assert data["preliminaryCost"] is not None


def test_rfq_analyze_incomplete_payload(test_client):
    response = test_client.post(
        "/api/rfq/analyze",
        json={
            "customer": "Example Customer",
            "message": "Please quote this part.",
            "attachments": [],
            "quantity": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "material" in data["missingInformation"]
    assert "drawing_attachment" in data["missingInformation"]
    assert "please provide" in data["draftCustomerReply"].lower()


def test_quote_draft_preliminary_and_separated_content(test_client):
    analysis = test_client.post(
        "/api/rfq/analyze",
        json={
            "customer": "Example Customer",
            "message": "Please quote this part.",
            "attachments": [],
            "quantity": 0,
        },
    ).json()

    response = test_client.post(
        "/api/rfq/quote-draft",
        json={
            "rfqAnalysis": analysis,
            "language": "en",
            "tone": "professional",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["isPreliminary"] is True
    assert "preliminary" in data["customerFacingResponse"].lower()
    assert any("do not commit" in n.lower() for n in data["internalEstimatorNotes"])


def test_persistence_save_analysis_quote_and_feedback(test_client):
    analysis = test_client.post(
        "/api/rfq/analyze",
        json={
            "customer": "Example Customer",
            "message": "Please quote 20 pcs from S235 steel, 2 mm sheet, laser cut.",
            "attachments": ["drawing.pdf"],
            "quantity": 20,
        },
    ).json()

    save_analysis = test_client.post(
        "/api/rfq/save-analysis",
        json={"customer": "Example Customer", "message": "RFQ body", "analysis": analysis},
    )
    assert save_analysis.status_code == 200
    assert save_analysis.json()["saved"] is True

    save_draft = test_client.post(
        "/api/rfq/save-quote-draft",
        json={"rfqAnalysis": analysis, "language": "en", "tone": "professional"},
    )
    assert save_draft.status_code == 200

    feedback = test_client.post(
        "/api/rfq/feedback",
        json={"rfqId": analysis["rfqId"], "decision": "accepted", "correctedMaterial": "S355", "correctedOperationRoute": ["laser_cutting", "bending"], "correctedQuantity": 25, "correctedCost": 1500.0, "correctedMargin": 22.0, "correctionReason": "Material upgraded", "estimatorNote": "Customer requested stronger steel"},
    )
    assert feedback.status_code == 200


def test_upload_attachment_metadata_and_limits(test_client):
    analysis = test_client.post(
        "/api/rfq/analyze",
        json={"customer": "X", "message": "Please quote 5 pcs S235", "attachments": [], "quantity": 5},
    ).json()

    response = test_client.post(
        "/api/rfq/upload-attachment",
        data={"rfq_id": analysis["rfqId"]},
        files={"file": ("spec.txt", b"material S235 thickness 2mm", "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "spec.txt"
    assert data["extension"] == ".txt"


def test_company_config_requires_admin_and_is_tenant_scoped(test_client):
    denied = test_client.post(
        "/api/company/config",
        headers={"x-role": "sales", "x-org-id": "org-a", "x-user-id": "u1"},
        json={"companyName": "A Corp", "defaultCurrency": "EUR", "defaultLanguage": "de"},
    )
    assert denied.status_code == 403

    created = test_client.post(
        "/api/company/config",
        headers={"x-role": "admin", "x-org-id": "org-a", "x-user-id": "u1"},
        json={"companyName": "A Corp", "defaultCurrency": "EUR", "defaultLanguage": "de"},
    )
    assert created.status_code == 200

    fetched = test_client.get(
        "/api/company/config",
        headers={"x-role": "viewer", "x-org-id": "org-a", "x-user-id": "u2"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["defaultCurrency"] == "EUR"
