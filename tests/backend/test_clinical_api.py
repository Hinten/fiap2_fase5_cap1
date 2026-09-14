"""Integration tests for the IR ALÉM 1 endpoints: /api/extract and /api/chat/clinical."""

from __future__ import annotations

from typing import Any

import pytest

from src.backend import create_app
from src.backend.clinical_extractor import (
    AlertSeverity,
    ClinicalEntity,
    ClinicalExtraction,
    ClinicalExtractionError,
    MockClinicalExtractor,
)
from src.backend.watson_gateway import WatsonServiceError


class FakeGateway:
    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured
        self.chat_result: dict[str, Any] = {
            "reply": "Qual é a intensidade de 0 a 10?",
            "conversationId": "session-2",
            "intent": "relatar_sintoma",
            "confidence": 0.91,
            "entities": [{"entity": "sintoma", "value": "palpitacao", "confidence": 0.96}],
            "urgent": False,
        }
        self.chat_error: Exception | None = None
        self.chat_calls: list[tuple[str, str | None]] = []

    def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        self.chat_calls.append((message, conversation_id))
        if self.chat_error:
            raise self.chat_error
        return dict(self.chat_result)

    def reset(self, conversation_id: str | None) -> None:
        return None


def _extraction(severity: AlertSeverity, **overrides: Any) -> ClinicalExtraction:
    values: dict[str, Any] = {
        "symptom": "palpitações",
        "intensity": 4,
        "duration": "2 minutos",
        "context": "à noite",
        "alert_severity": severity,
        "confidence": 0.8,
        "extracted_entities": [ClinicalEntity("palpitações", "symptom", 0.88, "palpitação")],
        "reasoning": "teste",
        "raw_model_output": "detalhe interno do provedor",
    }
    values.update(overrides)
    return ClinicalExtraction(**values)


class FakeExtractor:
    """Scripted extractor so severity and failures are chosen per test."""

    mode = "fake"
    provider = "fake-provider"
    model = "fake-model"

    def __init__(
        self,
        result: ClinicalExtraction | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or _extraction(AlertSeverity.MODERATE)
        self.error = error
        self.calls: list[str] = []

    def extract(self, clinical_text: str) -> ClinicalExtraction:
        self.calls.append(clinical_text)
        if self.error:
            raise self.error
        return self.result


def make_client(gateway: FakeGateway | None = None, extractor: Any = None):
    app = create_app(
        {"TESTING": True},
        gateway=gateway or FakeGateway(),
        extractor=extractor or FakeExtractor(),
    )
    return app.test_client()


# --------------------------------------------------------------------------
# /api/health
# --------------------------------------------------------------------------


def test_health_reports_the_clinical_extractor_mode_without_secrets():
    response = make_client(extractor=MockClinicalExtractor()).get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["clinical"] == {"mode": "mock", "provider": "mock", "model": "mock"}
    assert "key" not in response.get_data(as_text=True).lower()


# --------------------------------------------------------------------------
# /api/extract
# --------------------------------------------------------------------------


def test_extract_returns_the_structured_json_and_the_model_used():
    extractor = FakeExtractor(_extraction(AlertSeverity.CRITICAL, symptom="dor no peito", intensity=8))
    response = make_client(extractor=extractor).post(
        "/api/extract", json={"text": "  Acordei com dor forte no peito  "}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "fake"
    assert body["provider"] == "fake-provider"
    assert body["model"] == "fake-model"
    assert body["extraction"]["symptom"] == "dor no peito"
    assert body["extraction"]["alert_severity"] == "critical"
    assert body["extraction"]["entities"][0]["type"] == "symptom"
    assert "detalhe interno" not in response.get_data(as_text=True)
    assert extractor.calls == ["Acordei com dor forte no peito"]


def test_extract_with_the_mock_is_reproducible_end_to_end():
    client = make_client(extractor=MockClinicalExtractor())

    response = client.post("/api/extract", json={"text": "Dor no peito e suor frio há 20 minutos"})

    assert response.status_code == 200
    extraction = response.get_json()["extraction"]
    assert extraction["alert_severity"] == "critical"
    assert extraction["duration"] == "20 minutos"
    assert [entity["value"] for entity in extraction["entities"]] == ["dor no peito", "suor frio"]


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        (None, "JSON"),
        ({}, "text"),
        ({"text": 42}, "texto"),
        ({"text": "   "}, "texto clínico"),
        ({"text": "x" * 2001}, "2000"),
    ],
)
def test_extract_rejects_invalid_input(payload, expected_fragment):
    extractor = FakeExtractor()
    client = make_client(extractor=extractor)
    if payload is None:
        response = client.post("/api/extract", data="not-json", content_type="text/plain")
    else:
        response = client.post("/api/extract", json=payload)

    assert response.status_code == 400
    assert expected_fragment.lower() in response.get_json()["error"]["message"].lower()
    assert extractor.calls == []


def test_extract_accepts_exactly_2000_characters():
    extractor = FakeExtractor()
    response = make_client(extractor=extractor).post("/api/extract", json={"text": "x" * 2000})

    assert response.status_code == 200
    assert extractor.calls == ["x" * 2000]


@pytest.mark.parametrize(
    "error",
    [ClinicalExtractionError("modelo indisponível"), RuntimeError("apikey=segredo; texto do paciente")],
)
def test_extract_maps_model_failures_to_a_safe_502(error):
    response = make_client(extractor=FakeExtractor(error=error)).post(
        "/api/extract", json={"text": "conteúdo clínico"}
    )

    assert response.status_code == 502
    body = response.get_data(as_text=True)
    assert "extraction_unavailable" in body
    assert "segredo" not in body
    assert "conteúdo clínico" not in body


# --------------------------------------------------------------------------
# /api/chat/clinical
# --------------------------------------------------------------------------


def test_clinical_chat_reuses_the_chat_validation_rules():
    gateway = FakeGateway()
    extractor = FakeExtractor()
    client = make_client(gateway, extractor)

    assert client.post("/api/chat/clinical", json={"message": "   "}).status_code == 400
    assert client.post("/api/chat/clinical", json={"message": "x" * 501}).status_code == 400
    assert client.post("/api/chat/clinical", json={"message": "oi", "conversationId": 1}).status_code == 400
    assert gateway.chat_calls == []
    assert extractor.calls == []


def test_critical_report_answers_with_emergency_guidance_without_calling_watson():
    gateway = FakeGateway()
    extractor = FakeExtractor(_extraction(AlertSeverity.CRITICAL, symptom="dor no peito", intensity=9))
    response = make_client(gateway, extractor).post(
        "/api/chat/clinical", json={"message": "Dor forte no peito e suor frio", "conversationId": "s-1"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["urgent"] is True
    assert body["source"] == "clinical"
    assert body["conversationId"] == "s-1"
    assert body["intent"] is None
    assert "192" in body["reply"]
    assert body["clinical"]["alert_severity"] == "critical"
    assert body["entities"] == [{"entity": "symptom", "value": "palpitações", "confidence": 0.88}]
    assert gateway.chat_calls == []


def test_non_critical_report_goes_to_watson_with_the_extraction_attached():
    gateway = FakeGateway()
    extractor = FakeExtractor(_extraction(AlertSeverity.MODERATE))
    response = make_client(gateway, extractor).post(
        "/api/chat/clinical", json={"message": "  Sinto palpitações à noite  ", "conversationId": "s-1"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["reply"] == gateway.chat_result["reply"]
    assert body["intent"] == "relatar_sintoma"
    assert body["urgent"] is False
    assert body["source"] == "watson"
    assert body["clinical"]["symptom"] == "palpitações"
    assert body["clinical"]["alert_severity"] == "moderate"
    assert gateway.chat_calls == [("Sinto palpitações à noite", "s-1")]
    assert extractor.calls == ["Sinto palpitações à noite"]


@pytest.mark.parametrize(
    ("severity", "fragment"),
    [
        (AlertSeverity.HIGH, "ainda hoje"),
        (AlertSeverity.LOW, "consulta"),
        (AlertSeverity.INFO, "Não identifiquei um sintoma"),
    ],
)
def test_local_reply_when_watson_is_not_configured(severity, fragment):
    gateway = FakeGateway(configured=False)
    response = make_client(gateway, FakeExtractor(_extraction(severity))).post(
        "/api/chat/clinical", json={"message": "relato"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "clinical"
    assert body["urgent"] is False
    assert fragment in body["reply"]
    assert "não substitui" in body["reply"]
    assert body["clinical"]["alert_severity"] == severity.value
    assert gateway.chat_calls == []


def test_watson_failure_degrades_to_the_local_reply_when_extraction_exists():
    gateway = FakeGateway()
    gateway.chat_error = WatsonServiceError("apikey=segredo")
    response = make_client(gateway, FakeExtractor(_extraction(AlertSeverity.LOW))).post(
        "/api/chat/clinical", json={"message": "cansaço leve"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "clinical"
    assert "segredo" not in response.get_data(as_text=True)


def test_extraction_failure_falls_back_to_plain_watson():
    gateway = FakeGateway()
    extractor = FakeExtractor(error=ClinicalExtractionError("indisponível"))
    response = make_client(gateway, extractor).post("/api/chat/clinical", json={"message": "oi"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["reply"] == gateway.chat_result["reply"]
    assert body["source"] == "watson"
    assert body["clinical"] is None
    assert gateway.chat_calls == [("oi", None)]


def test_unexpected_extraction_error_never_leaks_and_still_uses_watson():
    gateway = FakeGateway()
    extractor = FakeExtractor(error=RuntimeError("apikey=segredo"))
    response = make_client(gateway, extractor).post("/api/chat/clinical", json={"message": "oi"})

    assert response.status_code == 200
    assert "segredo" not in response.get_data(as_text=True)
    assert response.get_json()["source"] == "watson"


def test_extraction_failure_without_watson_returns_503():
    gateway = FakeGateway(configured=False)
    extractor = FakeExtractor(error=ClinicalExtractionError("indisponível"))
    response = make_client(gateway, extractor).post("/api/chat/clinical", json={"message": "oi"})

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "watson_not_configured"


def test_extraction_failure_with_watson_failure_returns_502():
    gateway = FakeGateway()
    gateway.chat_error = WatsonServiceError("indisponível")
    extractor = FakeExtractor(error=ClinicalExtractionError("indisponível"))
    response = make_client(gateway, extractor).post("/api/chat/clinical", json={"message": "oi"})

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "watson_unavailable"


def test_original_chat_endpoint_is_untouched_by_the_extractor():
    gateway = FakeGateway()
    extractor = FakeExtractor()
    response = make_client(gateway, extractor).post("/api/chat", json={"message": "oi"})

    assert response.status_code == 200
    assert response.get_json() == gateway.chat_result
    assert extractor.calls == []
