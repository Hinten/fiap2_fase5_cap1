"""Unit tests for the IR ALÉM 1 clinical extractor (prompt, parsing, mock, API path)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.backend.clinical_extractor import (
    DEFAULT_MODEL,
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    AlertSeverity,
    ClinicalEntity,
    ClinicalExtraction,
    ClinicalExtractionError,
    ClinicalExtractor,
    MockClinicalExtractor,
    build_extraction_prompt,
    build_messages,
    create_extractor,
    create_extractor_from_env,
    parse_extraction,
    provider_from_base_url,
)


# --------------------------------------------------------------------------
# Prompt engineering
# --------------------------------------------------------------------------


def test_system_prompt_sets_role_boundaries_and_output_schema():
    assert "NÃO diagnostica" in SYSTEM_PROMPT
    assert '"alert_severity": "critical|high|moderate|low|info"' in SYSTEM_PROMPT
    assert "SAMU" not in SYSTEM_PROMPT  # guidance is the backend's job, not the model's


def test_prompt_contains_few_shot_examples_cot_steps_and_the_text():
    prompt = build_extraction_prompt("Sinto palpitação à noite")

    for example in FEW_SHOT_EXAMPLES:
        assert example["input"] in prompt
        assert example["output"]["alert_severity"] in prompt
    assert "PASSOS DE RACIOCÍNIO" in prompt
    assert '"Sinto palpitação à noite"' in prompt
    assert prompt.count("Exemplo ") == len(FEW_SHOT_EXAMPLES)


def test_few_shot_examples_cover_every_severity_used_by_the_flow():
    severities = {example["output"]["alert_severity"] for example in FEW_SHOT_EXAMPLES}
    assert {"critical", "high", "moderate", "info"} <= severities
    for example in FEW_SHOT_EXAMPLES:
        parsed = parse_extraction(example["output"])
        assert parsed.alert_severity.value == example["output"]["alert_severity"]


def test_messages_send_the_system_prompt_only_once():
    messages = build_messages("texto")

    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert SYSTEM_PROMPT not in messages[1]["content"]


# --------------------------------------------------------------------------
# Output validation
# --------------------------------------------------------------------------


def test_parse_extraction_normalises_a_complete_payload():
    extraction = parse_extraction(
        {
            "symptom": "  dor no peito ",
            "intensity": "8",
            "duration": "30 minutos",
            "context": "repouso",
            "alert_severity": "CRITICAL",
            "confidence": 0.951234,
            "entities": [
                {"value": "dor no peito", "type": "symptom", "confidence": 0.9, "normalized": "dor torácica"},
                {"value": "", "type": "symptom", "confidence": 0.9},
                {"value": "losartana", "type": "remedio", "confidence": "0.8"},
                "not-a-mapping",
            ],
            "reasoning": "sinal de alerta",
        },
        raw_output="{}",
    )

    assert extraction.symptom == "dor no peito"
    assert extraction.intensity == 8
    assert extraction.alert_severity is AlertSeverity.CRITICAL
    assert extraction.confidence == 0.951
    assert [entity.value for entity in extraction.extracted_entities] == ["dor no peito", "losartana"]
    assert extraction.extracted_entities[1].entity_type == "other"
    assert extraction.extracted_entities[0].normalized == "dor torácica"
    assert extraction.raw_model_output == "{}"


@pytest.mark.parametrize(
    ("payload", "intensity", "confidence", "severity"),
    [
        ({}, 0, 0.5, AlertSeverity.MODERATE),
        ({"intensity": 42, "confidence": 7}, 10, 1.0, AlertSeverity.MODERATE),
        ({"intensity": -3, "confidence": -1}, 0, 0.0, AlertSeverity.MODERATE),
        ({"intensity": "sete", "confidence": "alta", "alert_severity": "urgente"}, 0, 0.5, AlertSeverity.MODERATE),
        ({"intensity": 6.6, "confidence": True, "alert_severity": " High "}, 7, 0.5, AlertSeverity.HIGH),
        ({"symptom": None, "duration": 12, "alert_severity": "info"}, 0, 0.5, AlertSeverity.INFO),
    ],
)
def test_parse_extraction_uses_safe_defaults_and_bounds(payload, intensity, confidence, severity):
    extraction = parse_extraction(payload)

    assert extraction.intensity == intensity
    assert extraction.confidence == confidence
    assert extraction.alert_severity is severity
    assert extraction.symptom  # never empty
    assert isinstance(extraction.duration, str)


def test_parse_extraction_rejects_non_mapping_payload():
    with pytest.raises(ClinicalExtractionError):
        parse_extraction(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_to_dict_is_json_serialisable_and_hides_raw_output():
    extraction = ClinicalExtraction(
        symptom="dor no peito",
        intensity=8,
        duration="30 minutos",
        context="repouso",
        alert_severity=AlertSeverity.CRITICAL,
        confidence=0.92,
        extracted_entities=[ClinicalEntity("dor", "symptom", 0.95, "dor torácica")],
        reasoning="alerta",
        raw_model_output="segredo do provedor",
    )

    payload = extraction.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)

    assert set(payload) == {
        "symptom",
        "intensity",
        "duration",
        "context",
        "alert_severity",
        "confidence",
        "entities",
        "reasoning",
    }
    assert payload["alert_severity"] == "critical"
    assert payload["entities"] == [
        {"value": "dor", "type": "symptom", "confidence": 0.95, "normalized": "dor torácica"}
    ]
    assert "segredo" not in encoded


def test_entities_are_immutable():
    entity = ClinicalEntity("test", "symptom", 0.9)
    with pytest.raises(AttributeError):
        entity.value = "changed"  # type: ignore[misc]


# --------------------------------------------------------------------------
# API-backed extractor with a fake client (no network)
# --------------------------------------------------------------------------


class FakeChatClient:
    def __init__(self, content: Any = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    finish_reason = "stop"

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


def _model_json(**overrides: Any) -> str:
    payload = dict(FEW_SHOT_EXAMPLES[1]["output"])
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_extractor_uses_json_mode_and_parses_the_model_output():
    client = FakeChatClient(content=_model_json())
    extractor = ClinicalExtractor(model="modelo-teste", client=client)

    extraction = extractor.extract("  Falta de ar ao subir escadas  ")

    assert extractor.mode == "llm"
    assert extraction.alert_severity is AlertSeverity.HIGH
    assert extraction.symptom == "falta de ar ao esforço"
    assert [entity.entity_type for entity in extraction.extracted_entities] == ["symptom", "context", "duration"]
    assert extractor.get_stats()["total_extractions"] == 1

    call = client.calls[0]
    assert call["model"] == "modelo-teste"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["role"] == "system"
    assert "Falta de ar ao subir escadas" in call["messages"][1]["content"]


def test_extractor_reports_truncated_output_instead_of_a_json_error():
    client = FakeChatClient(content='{\n  "symptom": "dor no peito em aperto",\n  "intensity": 9,\n  "duration')
    client.finish_reason = "length"
    extractor = ClinicalExtractor(client=client)

    with pytest.raises(ClinicalExtractionError, match="limite de tokens"):
        extractor.extract("Dor no peito")


def test_extractor_rejects_empty_text_before_calling_the_model():
    client = FakeChatClient(content=_model_json())
    extractor = ClinicalExtractor(client=client)

    with pytest.raises(ValueError, match="empty"):
        extractor.extract("   ")
    assert client.calls == []


def test_extractor_truncates_very_long_text():
    client = FakeChatClient(content=_model_json())
    extractor = ClinicalExtractor(client=client)

    extractor.extract("x" * 6_000)

    assert "x" * 5_000 in client.calls[0]["messages"][1]["content"]
    assert "x" * 5_001 not in client.calls[0]["messages"][1]["content"]


@pytest.mark.parametrize(
    "client",
    [
        FakeChatClient(error=RuntimeError("apikey=segredo")),
        FakeChatClient(content="isto não é json"),
        FakeChatClient(content=""),
        FakeChatClient(content="[1, 2, 3]"),
    ],
)
def test_extractor_wraps_provider_failures_in_a_safe_error(client):
    extractor = ClinicalExtractor(client=client)

    with pytest.raises(ClinicalExtractionError) as info:
        extractor.extract("Dor no peito")

    assert "segredo" not in str(info.value)
    assert "Dor no peito" not in str(info.value)


class FakeStatusError(Exception):
    """Shape of openai.APIStatusError without importing the SDK."""

    def __init__(self, status_code: int, code: str | None = None, error_type: str | None = None) -> None:
        super().__init__(f"Error code: {status_code} - apikey=segredo; texto do paciente")
        self.status_code = status_code
        self.code = code
        self.body = {"error": {"code": code, "type": error_type, "message": "segredo"}}


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (FakeStatusError(401, "invalid_api_key"), "LLM_API_KEY inválida"),
        (FakeStatusError(429, "credit_balance_exhausted", "insufficient_quota"), "sem créditos"),
        (FakeStatusError(429, "insufficient_quota"), "sem créditos"),
        (FakeStatusError(429, "rate_limit_exceeded"), "Limite de requisições"),
        (FakeStatusError(404, "model_not_found"), "LLM_MODEL"),
        (FakeStatusError(500), "HTTP 500"),
        (ConnectionError("dns failure apikey=segredo"), "conectar"),
    ],
)
def test_extractor_reports_a_safe_operator_reason(error, fragment):
    extractor = ClinicalExtractor(client=FakeChatClient(error=error))

    with pytest.raises(ClinicalExtractionError) as info:
        extractor.extract("Dor no peito")

    message = str(info.value)
    assert fragment in message
    assert "segredo" not in message
    assert "paciente" not in message
    assert info.value.__cause__ is error


# --------------------------------------------------------------------------
# Mock extractor
# --------------------------------------------------------------------------


@pytest.fixture
def mock() -> MockClinicalExtractor:
    return MockClinicalExtractor()


@pytest.mark.parametrize(
    ("text", "severity", "symptom_fragment"),
    [
        ("Senti uma dor forte no peito ontem à noite, durou 30 minutos.", AlertSeverity.CRITICAL, "peito"),
        ("Acordei com dor no peito e suor frio", AlertSeverity.CRITICAL, "peito"),
        ("Quase desmaiei no ônibus hoje", AlertSeverity.CRITICAL, "desmaio"),
        ("Tenho falta de ar ao subir as escadas, uns 10 minutos.", AlertSeverity.HIGH, "falta de ar"),
        ("Sinto palpitações à noite, duram 2-3 minutos.", AlertSeverity.MODERATE, "palpita"),
        ("Tenho um incômodo geral no corpo.", AlertSeverity.LOW, "inespecífico"),
    ],
)
def test_mock_classifies_common_reports(mock, text, severity, symptom_fragment):
    extraction = mock.extract(text)

    assert extraction.alert_severity is severity
    assert symptom_fragment in extraction.symptom
    assert 0 <= extraction.intensity <= 10
    assert 0.0 <= extraction.confidence <= 1.0
    assert extraction.reasoning
    for entity in extraction.extracted_entities:
        assert entity.value
        assert entity.entity_type in {"symptom", "medication", "condition", "duration", "context", "other"}


def test_mock_echoes_the_duration_found_in_the_text(mock):
    assert mock.extract("Dor no peito por uns 30 minutos").duration == "30 minutos"
    assert mock.extract("Palpitações de 2-3 minutos").duration == "2-3 minutos"
    assert mock.extract("Palpitações à noite").duration == "não informado"


def test_mock_is_deterministic_counts_calls_and_rejects_empty_text(mock):
    first = mock.extract("Dor no peito com intensidade alta.")
    second = mock.extract("Dor no peito com intensidade alta.")

    assert first.to_dict() == second.to_dict()
    assert mock.get_stats() == {
        "mode": "mock",
        "provider": "mock",
        "model": "mock",
        "temperature": 0.0,
        "total_extractions": 2,
    }
    with pytest.raises(ValueError, match="empty"):
        mock.extract("")


def test_mock_suor_frio_adds_an_entity(mock):
    extraction = mock.extract("Dor no peito e muito suor frio")

    assert [entity.value for entity in extraction.extracted_entities] == ["dor no peito", "suor frio"]
    assert "suor frio" in extraction.context


# --------------------------------------------------------------------------
# Factories
# --------------------------------------------------------------------------


def test_create_extractor_returns_mock_on_request():
    extractor = create_extractor(use_mock=True)
    assert isinstance(extractor, MockClinicalExtractor)


def test_create_extractor_from_env_falls_back_to_mock_without_key():
    extractor = create_extractor_from_env({"LLM_API_KEY": "   "})
    assert isinstance(extractor, MockClinicalExtractor)


def test_extractor_without_arguments_reads_the_neutral_llm_variables(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.setenv("LLM_API_KEY", "chave-teste")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    extractor = ClinicalExtractor()

    assert extractor.provider == "groq"
    assert "api.groq.com" in str(extractor.client.base_url)


def test_create_extractor_from_env_builds_api_extractor_with_model(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    extractor = create_extractor_from_env({"LLM_API_KEY": "sk-test", "LLM_MODEL": " gpt-teste "})

    assert type(extractor) is ClinicalExtractor
    assert extractor.model == "gpt-teste"
    assert extractor.mode == "llm"
    assert extractor.provider == "openai"


def test_create_extractor_from_env_uses_default_model(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    extractor = create_extractor_from_env({"LLM_API_KEY": "sk-test"})
    assert extractor.model == DEFAULT_MODEL


def test_create_extractor_from_env_points_the_sdk_at_a_compatible_provider():
    pytest.importorskip("openai")
    extractor = create_extractor_from_env(
        {
            "LLM_API_KEY": "AIza-test",
            "LLM_MODEL": "gemini-3.5-flash",
            "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }
    )

    assert extractor.provider == "google"
    assert extractor.model == "gemini-3.5-flash"
    assert "generativelanguage.googleapis.com" in str(extractor.client.base_url)


@pytest.mark.parametrize(
    ("base_url", "provider"),
    [
        (None, "openai"),
        ("", "openai"),
        ("https://api.openai.com/v1", "openai"),
        ("https://generativelanguage.googleapis.com/v1beta/openai/", "google"),
        ("https://api.groq.com/openai/v1", "groq"),
        ("http://localhost:11434/v1", "local"),
        ("https://llm.example.edu/v1", "llm.example.edu"),
    ],
)
def test_provider_label_is_derived_from_the_base_url(base_url, provider):
    assert provider_from_base_url(base_url) == provider
