from __future__ import annotations

from collections import deque
from typing import Any

import pytest

from src.backend.watson_gateway import (
    LEARNING_OPT_OUT_HEADERS,
    V1_CONTEXT_MAX_ENTRIES,
    V1_CONTEXT_TTL_SECONDS,
    WatsonConfigurationError,
    WatsonGateway,
    WatsonServiceError,
    WatsonSettings,
    normalize_watson_response,
)


class SDKResult:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def get_result(self) -> dict[str, Any]:
        return self.result


class SDKError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"SDK failure {code}")
        self.code = code


class FakeWatsonService:
    def __init__(self, message_results: list[Any] | None = None) -> None:
        self.message_results = deque(message_results or [])
        self.created = 0
        self.create_kwargs: list[dict[str, Any]] = []
        self.message_kwargs: list[dict[str, Any]] = []
        self.delete_kwargs: list[dict[str, Any]] = []

    def create_session(self, **kwargs):
        self.created += 1
        self.create_kwargs.append(kwargs)
        return SDKResult({"session_id": f"new-session-{self.created}"})

    def message(self, **kwargs):
        self.message_kwargs.append(kwargs)
        result = self.message_results.popleft()
        if isinstance(result, Exception):
            raise result
        return SDKResult(result)

    def delete_session(self, **kwargs):
        self.delete_kwargs.append(kwargs)
        return SDKResult({})


def settings(**overrides) -> WatsonSettings:
    values = {
        "api_key": "test-key",
        "service_url": "https://example.invalid",
        "assistant_id": "assistant-id",
        "environment_id": "environment-id",
        "workspace_id": None,
        "api_mode": "auto",
        "version": "2024-08-25",
    }
    values.update(overrides)
    return WatsonSettings(**values)


def v1_settings(**overrides) -> WatsonSettings:
    values = {
        "assistant_id": None,
        "environment_id": None,
        "workspace_id": "workspace-id",
        "api_mode": "v1",
    }
    values.update(overrides)
    return settings(**values)


def response_payload(text: str = "Olá") -> dict[str, Any]:
    return {
        "output": {
            "generic": [{"response_type": "text", "text": text}],
            "intents": [{"intent": "saudacao", "confidence": 0.8}],
            "entities": [],
        }
    }


def test_settings_require_all_current_v2_runtime_values():
    assert settings().configured is True
    assert settings(api_key=None).configured is False
    assert settings(environment_id=None).configured is False


def test_settings_select_v1_or_v2_without_ambiguous_partial_configuration():
    assert settings().resolved_mode == "v2"
    assert v1_settings().configured is True
    assert v1_settings().resolved_mode == "v1"
    assert settings(workspace_id="workspace-id").resolved_mode == "v2"
    assert settings(api_mode="v1", workspace_id="workspace-id").resolved_mode == "v1"
    assert settings(api_mode="invalid").configured is False


def test_settings_from_environment_supports_explicit_v1_selection():
    parsed = WatsonSettings.from_env(
        {
            "WATSON_API_KEY": " key ",
            "WATSON_URL": " https://example.invalid ",
            "WATSON_WORKSPACE_ID": " workspace ",
            "WATSON_API_MODE": " V1 ",
        }
    )

    assert parsed.configured is True
    assert parsed.resolved_mode == "v1"
    assert parsed.workspace_id == "workspace"


def test_unconfigured_gateway_never_constructs_sdk_client():
    called = False

    def factory(_settings):
        nonlocal called
        called = True

    gateway = WatsonGateway(settings(api_key=None), service_factory=factory)

    with pytest.raises(WatsonConfigurationError):
        gateway.chat("Olá")
    assert called is False


def test_new_conversation_creates_stateful_session_and_requests_context():
    service = FakeWatsonService([response_payload("Tudo bem")])
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    result = gateway.chat("Olá")

    assert result["conversationId"] == "new-session-1"
    assert result["reply"] == "Tudo bem"
    assert service.create_kwargs == [
        {
            "assistant_id": "assistant-id",
            "environment_id": "environment-id",
            "headers": LEARNING_OPT_OUT_HEADERS,
        }
    ]
    request = service.message_kwargs[0]
    assert request["session_id"] == "new-session-1"
    assert request["input"] == {
        "message_type": "text",
        "text": "Olá",
        "options": {"return_context": True},
    }
    assert request["headers"] == LEARNING_OPT_OUT_HEADERS


def test_environment_id_is_forwarded_for_current_api_variants():
    service = FakeWatsonService([response_payload()])
    gateway = WatsonGateway(
        settings(environment_id="environment-id"), service_factory=lambda _: service
    )

    gateway.chat("Olá")

    assert service.create_kwargs[0] == {
        "assistant_id": "assistant-id",
        "environment_id": "environment-id",
        "headers": LEARNING_OPT_OUT_HEADERS,
    }
    assert service.message_kwargs[0]["environment_id"] == "environment-id"


def test_existing_session_is_reused_without_creation():
    service = FakeWatsonService([response_payload()])
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    result = gateway.chat("Oi", "existing-session")

    assert result["conversationId"] == "existing-session"
    assert service.created == 0


@pytest.mark.parametrize("expired_code", [404, 410])
def test_expired_session_is_recreated_and_original_message_retried_once(expired_code):
    service = FakeWatsonService([SDKError(expired_code), response_payload("Sessão renovada")])
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    result = gateway.chat("Minha mensagem", "expired-session")

    assert result["conversationId"] == "new-session-1"
    assert result["reply"] == "Sessão renovada"
    assert len(service.message_kwargs) == 2
    assert [call["input"]["text"] for call in service.message_kwargs] == [
        "Minha mensagem",
        "Minha mensagem",
    ]


def test_non_expiry_failure_does_not_create_or_retry_session():
    service = FakeWatsonService([SDKError(500)])
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    with pytest.raises(WatsonServiceError):
        gateway.chat("Olá", "session")

    assert service.created == 0
    assert len(service.message_kwargs) == 1


def test_retry_failure_is_sanitized_and_not_repeated_again():
    service = FakeWatsonService([SDKError(404), SDKError(500)])
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    with pytest.raises(WatsonServiceError) as captured:
        gateway.chat("segredo clínico", "expired")

    assert "segredo clínico" not in str(captured.value)
    assert len(service.message_kwargs) == 2
    assert service.created == 1


def test_reset_deletes_session_and_treats_expired_session_as_success():
    service = FakeWatsonService()
    gateway = WatsonGateway(settings(), service_factory=lambda _: service)

    gateway.reset("session")

    assert service.delete_kwargs == [
        {
            "assistant_id": "assistant-id",
            "environment_id": "environment-id",
            "session_id": "session",
            "headers": LEARNING_OPT_OUT_HEADERS,
        }
    ]


def test_v1_uses_workspace_context_and_normalizes_top_level_nlp_fields():
    service = FakeWatsonService(
        [
            {
                "output": {"text": ["Qual é a intensidade?"]},
                "intents": [{"intent": "relatar_sintoma", "confidence": 0.92}],
                "entities": [
                    {"entity": "sintoma", "value": "palpitacao", "confidence": 0.95}
                ],
                "context": {"sintoma": "palpitacao", "etapa": "intensidade"},
            },
            {
                "output": {"text": ["Há quanto tempo começou?"]},
                "intents": [],
                "entities": [{"entity": "sys-number", "value": 5}],
                "context": {
                    "sintoma": "palpitacao",
                    "intensidade": 5,
                    "etapa": "duracao",
                },
            },
        ]
    )
    ids = iter(["local-conversation"])
    gateway = WatsonGateway(
        v1_settings(),
        service_factory=lambda _: service,
        conversation_id_factory=lambda: next(ids),
    )

    first = gateway.chat("Estou com palpitações")
    second = gateway.chat("5", first["conversationId"])

    assert first == {
        "reply": "Qual é a intensidade?",
        "conversationId": "local-conversation",
        "intent": "relatar_sintoma",
        "confidence": 0.92,
        "entities": [
            {"entity": "sintoma", "value": "palpitacao", "confidence": 0.95}
        ],
        "urgent": False,
    }
    assert second["conversationId"] == "local-conversation"
    assert second["entities"] == [
        {"entity": "sys-number", "value": "5", "confidence": 1.0}
    ]
    assert service.message_kwargs[0] == {
        "workspace_id": "workspace-id",
        "input": {"text": "Estou com palpitações"},
        "context": {},
        "headers": LEARNING_OPT_OUT_HEADERS,
    }
    assert service.message_kwargs[1]["context"] == {
        "sintoma": "palpitacao",
        "etapa": "intensidade",
    }


def test_v1_context_expires_after_ttl_and_gets_a_new_local_identifier():
    now = [10.0]
    service = FakeWatsonService(
        [
            {"output": {"text": ["um"]}, "context": {"etapa": "dois"}},
            {"output": {"text": ["novo"]}, "context": {}},
        ]
    )
    ids = iter(["local-1", "local-2"])
    gateway = WatsonGateway(
        v1_settings(),
        service_factory=lambda _: service,
        clock=lambda: now[0],
        conversation_id_factory=lambda: next(ids),
        v1_context_ttl_seconds=30,
    )

    first = gateway.chat("primeiro")
    now[0] += 30
    second = gateway.chat("segundo", first["conversationId"])

    assert second["conversationId"] == "local-2"
    assert service.message_kwargs[1]["context"] == {}


def test_v1_context_cache_has_a_bounded_lru_capacity():
    service = FakeWatsonService(
        [
            {"output": {"text": ["ok"]}, "context": {"n": number}}
            for number in range(4)
        ]
    )
    ids = iter(["local-a", "local-b", "local-c", "local-d"])
    gateway = WatsonGateway(
        v1_settings(),
        service_factory=lambda _: service,
        conversation_id_factory=lambda: next(ids),
        v1_context_max_entries=2,
    )

    first = gateway.chat("a")
    gateway.chat("b")
    gateway.chat("c")
    after_eviction = gateway.chat("a outra vez", first["conversationId"])

    assert after_eviction["conversationId"] == "local-d"
    assert service.message_kwargs[-1]["context"] == {}
    assert len(gateway._v1_contexts) == 2


def test_v1_reset_discards_only_local_context_without_remote_delete():
    service = FakeWatsonService(
        [
            {"output": {"text": ["ok"]}, "context": {"sintoma": "tontura"}},
            {"output": {"text": ["reiniciada"]}, "context": {}},
        ]
    )
    ids = iter(["local-1", "local-2"])
    gateway = WatsonGateway(
        v1_settings(),
        service_factory=lambda _: service,
        conversation_id_factory=lambda: next(ids),
    )

    first = gateway.chat("tontura")
    gateway.reset(first["conversationId"])
    restarted = gateway.chat("oi", first["conversationId"])

    assert restarted["conversationId"] == "local-2"
    assert service.delete_kwargs == []
    assert service.message_kwargs[-1]["context"] == {}


def test_v1_context_defaults_are_bounded():
    assert V1_CONTEXT_TTL_SECONDS == 1_800
    assert V1_CONTEXT_MAX_ENTRIES == 500


def test_normalizer_joins_multiple_texts_and_selects_highest_confidence_intent():
    payload = {
        "output": {
            "generic": [
                {"response_type": "text", "text": "Primeira linha"},
                {"response_type": "image", "source": "ignored"},
                {"response_type": "text", "text": "Segunda linha\u0000"},
            ],
            "intents": [
                {"intent": "agradecimento", "confidence": 0.51},
                {"intent": "sinal_alerta", "confidence": 0.98},
            ],
            "entities": [
                {"entity": "sintoma", "value": "dor_no_peito", "confidence": 0.93},
                {"malformed": True},
            ],
        },
        "context": {
            "skills": {"main skill": {"user_defined": {"urgent": True}}}
        },
    }

    result = normalize_watson_response(payload, "session")

    assert result == {
        "reply": "Primeira linha\nSegunda linha",
        "conversationId": "session",
        "intent": "sinal_alerta",
        "confidence": 0.98,
        "entities": [
            {"entity": "sintoma", "value": "dor_no_peito", "confidence": 0.93}
        ],
        "urgent": True,
    }


def test_normalizer_returns_safe_fallback_when_watson_has_no_text():
    result = normalize_watson_response({"output": {}}, "session")

    assert result["conversationId"] == "session"
    assert "192" in result["reply"]
    assert result["intent"] is None
    assert result["urgent"] is False
