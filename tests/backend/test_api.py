from __future__ import annotations

from typing import Any

import pytest

from src.backend import create_app
from src.backend.watson_gateway import WatsonServiceError


class FakeGateway:
    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.chat_result: dict[str, Any] = {
            "reply": "Resposta educativa.",
            "conversationId": "session-2",
            "intent": "relatar_sintoma",
            "confidence": 0.91,
            "entities": [
                {"entity": "sintoma", "value": "palpitacao", "confidence": 0.96}
            ],
            "urgent": False,
        }
        self.chat_error: Exception | None = None
        self.reset_error: Exception | None = None
        self.chat_calls: list[tuple[str, str | None]] = []
        self.reset_calls: list[str | None] = []

    def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        self.chat_calls.append((message, conversation_id))
        if self.chat_error:
            raise self.chat_error
        return self.chat_result

    def reset(self, conversation_id: str | None) -> None:
        self.reset_calls.append(conversation_id)
        if self.reset_error:
            raise self.reset_error


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def client(gateway: FakeGateway):
    app = create_app({"TESTING": True}, gateway=gateway)
    return app.test_client()


def test_health_reports_configuration_without_exposing_credentials(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "cardioia-api",
        "watson": {"configured": True},
    }
    assert "key" not in response.get_data(as_text=True).lower()


def test_health_remains_available_when_watson_is_not_configured():
    app = create_app({"TESTING": True}, gateway=FakeGateway(configured=False))
    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["watson"]["configured"] is False


def test_unknown_api_get_returns_a_json_404(client):
    response = client.get("/api/desconhecida")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        (None, "JSON"),
        ({}, "message"),
        ({"message": None}, "texto"),
        ({"message": "   "}, "mensagem"),
        ({"message": "x" * 501}, "500"),
        ({"message": "oi", "conversationId": 123}, "conversationId"),
        ({"message": "oi", "conversationId": "id com espaço"}, "identificador"),
    ],
)
def test_chat_rejects_invalid_input(client, payload, expected_fragment):
    if payload is None:
        response = client.post("/api/chat", data="not-json", content_type="text/plain")
    else:
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 400
    assert expected_fragment.lower() in response.get_json()["error"]["message"].lower()


def test_chat_accepts_exactly_500_characters(client, gateway: FakeGateway):
    response = client.post("/api/chat", json={"message": "x" * 500})

    assert response.status_code == 200
    assert gateway.chat_calls == [("x" * 500, None)]


def test_chat_returns_stable_frontend_contract(client, gateway: FakeGateway):
    response = client.post(
        "/api/chat",
        json={"message": "  sinto palpitações  ", "conversationId": "session-1"},
    )

    assert response.status_code == 200
    assert response.get_json() == gateway.chat_result
    assert gateway.chat_calls == [("sinto palpitações", "session-1")]


def test_chat_returns_503_when_configuration_is_missing():
    gateway = FakeGateway(configured=False)
    app = create_app({"TESTING": True}, gateway=gateway)
    response = app.test_client().post("/api/chat", json={"message": "Olá"})

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "watson_not_configured"
    assert gateway.chat_calls == []


def test_chat_maps_watson_failure_to_safe_502(client, gateway: FakeGateway):
    gateway.chat_error = WatsonServiceError("apikey=segredo; texto do paciente")

    response = client.post("/api/chat", json={"message": "conteúdo clínico"})

    assert response.status_code == 502
    body = response.get_data(as_text=True)
    assert "watson_unavailable" in body
    assert "segredo" not in body
    assert "conteúdo clínico" not in body


def test_reset_deletes_remote_session_and_clears_client_identifier(client, gateway: FakeGateway):
    response = client.post("/api/reset", json={"conversationId": "session-1"})

    assert response.status_code == 200
    assert response.get_json() == {"reset": True, "conversationId": None}
    assert gateway.reset_calls == ["session-1"]


def test_reset_without_session_is_idempotent_even_without_configuration():
    gateway = FakeGateway(configured=False)
    app = create_app({"TESTING": True}, gateway=gateway)
    response = app.test_client().post("/api/reset", json={})

    assert response.status_code == 200
    assert response.get_json()["reset"] is True
    assert gateway.reset_calls == [None]


def test_reset_maps_remote_failure_to_502(client, gateway: FakeGateway):
    gateway.reset_error = WatsonServiceError("private SDK details")

    response = client.post("/api/reset", json={"conversationId": "session-1"})

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "watson_unavailable"
    assert "private SDK details" not in response.get_data(as_text=True)
