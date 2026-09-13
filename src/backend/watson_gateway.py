"""Small, testable gateway for Watson Assistant V1 and V2.

No credential or conversation content is logged here.  The SDK is imported
lazily so the Flask app can still expose a useful health endpoint before the
optional Watson dependency has been installed.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import os
from threading import RLock
from time import monotonic
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4


DEFAULT_WATSON_VERSION = "2021-11-27"
EXPIRED_SESSION_STATUS_CODES = frozenset({404, 410})
VALID_API_MODES = frozenset({"auto", "v1", "v2"})
LEARNING_OPT_OUT_HEADERS = {"X-Watson-Learning-Opt-Out": "true"}
V1_CONTEXT_TTL_SECONDS = 30 * 60
V1_CONTEXT_MAX_ENTRIES = 500


class WatsonError(RuntimeError):
    """A safe, public-neutral Watson integration failure."""


class WatsonConfigurationError(WatsonError):
    """Raised when required Watson configuration is missing."""


class WatsonServiceError(WatsonError):
    """Raised when Watson cannot complete an operation."""


class WatsonGatewayProtocol(Protocol):
    """Dependency-injection boundary used by the Flask application."""

    @property
    def configured(self) -> bool: ...

    def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]: ...

    def reset(self, conversation_id: str | None) -> None: ...


@dataclass(frozen=True)
class WatsonSettings:
    """Non-secret and secret runtime settings read from environment variables."""

    api_key: str | None
    service_url: str | None
    assistant_id: str | None
    environment_id: str | None = None
    workspace_id: str | None = None
    api_mode: str = "auto"
    version: str = DEFAULT_WATSON_VERSION

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "WatsonSettings":
        source = environ if environ is not None else os.environ
        return cls(
            api_key=_clean_setting(source.get("WATSON_API_KEY")),
            service_url=_clean_setting(source.get("WATSON_URL")),
            assistant_id=_clean_setting(source.get("WATSON_ASSISTANT_ID")),
            environment_id=_clean_setting(source.get("WATSON_ENVIRONMENT_ID")),
            workspace_id=_clean_setting(source.get("WATSON_WORKSPACE_ID")),
            api_mode=(_clean_setting(source.get("WATSON_API_MODE")) or "auto").lower(),
            version=_clean_setting(source.get("WATSON_VERSION")) or DEFAULT_WATSON_VERSION,
        )

    @property
    def configured(self) -> bool:
        if not self.api_key or not self.service_url or self.api_mode not in VALID_API_MODES:
            return False
        if self.api_mode == "v1":
            return bool(self.workspace_id)
        if self.api_mode == "v2":
            return bool(self.assistant_id and self.environment_id)
        return bool(
            (self.assistant_id and self.environment_id) or self.workspace_id
        )

    @property
    def resolved_mode(self) -> str:
        """Select V2 first in auto mode, then the Lite-compatible V1 API."""

        if self.api_mode not in VALID_API_MODES:
            raise WatsonConfigurationError("WATSON_API_MODE deve ser auto, v1 ou v2.")
        if self.api_mode != "auto":
            return self.api_mode
        if self.assistant_id and self.environment_id:
            return "v2"
        if self.workspace_id:
            return "v1"
        raise WatsonConfigurationError("Watson Assistant não está configurado.")


@dataclass
class _V1ContextEntry:
    context: dict[str, Any]
    last_seen: float


def _clean_setting(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _status_code(error: Exception) -> int | None:
    """Extract an HTTP status without depending on one SDK exception version."""

    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


class WatsonGateway:
    """V2 sessions plus bounded, process-local context for V1 Dialog Skills."""

    def __init__(
        self,
        settings: WatsonSettings | None = None,
        *,
        service_factory: Callable[[WatsonSettings], Any] | None = None,
        clock: Callable[[], float] = monotonic,
        conversation_id_factory: Callable[[], str] | None = None,
        v1_context_ttl_seconds: float = V1_CONTEXT_TTL_SECONDS,
        v1_context_max_entries: int = V1_CONTEXT_MAX_ENTRIES,
    ) -> None:
        if v1_context_ttl_seconds <= 0:
            raise ValueError("v1_context_ttl_seconds must be positive")
        if v1_context_max_entries <= 0:
            raise ValueError("v1_context_max_entries must be positive")
        self.settings = settings or WatsonSettings.from_env()
        self._service_factory = service_factory or self._build_service
        self._service: Any | None = None
        self._clock = clock
        self._conversation_id_factory = conversation_id_factory or (
            lambda: str(uuid4())
        )
        self._v1_context_ttl_seconds = v1_context_ttl_seconds
        self._v1_context_max_entries = v1_context_max_entries
        self._v1_contexts: OrderedDict[str, _V1ContextEntry] = OrderedDict()
        self._v1_context_lock = RLock()

    @property
    def configured(self) -> bool:
        return self.settings.configured

    @property
    def api_mode(self) -> str | None:
        try:
            return self.settings.resolved_mode if self.configured else None
        except WatsonConfigurationError:
            return None

    def _require_service(self) -> Any:
        if not self.configured:
            raise WatsonConfigurationError("Watson Assistant não está configurado.")
        if self._service is None:
            try:
                self._service = self._service_factory(self.settings)
            except WatsonError:
                raise
            except Exception as error:
                raise WatsonServiceError("Não foi possível inicializar o Watson Assistant.") from error
        return self._service

    @staticmethod
    def _build_service(settings: WatsonSettings) -> Any:
        # Lazy imports keep configuration checks and unit tests independent of
        # the third-party SDK. Credentials are passed only to the IAM client.
        from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
        from ibm_watson import AssistantV1, AssistantV2

        authenticator = IAMAuthenticator(settings.api_key)
        service_class = AssistantV1 if settings.resolved_mode == "v1" else AssistantV2
        service = service_class(version=settings.version, authenticator=authenticator)
        service.set_service_url(settings.service_url)
        service.set_http_config({"timeout": 15})
        service.set_default_headers(dict(LEARNING_OPT_OUT_HEADERS))
        return service

    def _v2_runtime_kwargs(self) -> dict[str, str]:
        return {
            "assistant_id": str(self.settings.assistant_id),
            "environment_id": str(self.settings.environment_id),
        }

    def _create_session(self, service: Any) -> str:
        try:
            result = service.create_session(
                **self._v2_runtime_kwargs(),
                headers=dict(LEARNING_OPT_OUT_HEADERS),
            ).get_result()
            session_id = result.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise WatsonServiceError("O Watson retornou uma sessão inválida.")
            return session_id
        except WatsonError:
            raise
        except Exception as error:
            raise WatsonServiceError("Não foi possível iniciar a conversa no Watson.") from error

    def _send_v2(self, service: Any, session_id: str, message: str) -> dict[str, Any]:
        request = self._v2_runtime_kwargs()
        request.update(
            {
                "session_id": session_id,
                "input": {
                    "message_type": "text",
                    "text": message,
                    "options": {"return_context": True},
                },
                "headers": dict(LEARNING_OPT_OUT_HEADERS),
            }
        )
        return service.message(**request).get_result()

    def chat(self, message: str, conversation_id: str | None = None) -> dict[str, Any]:
        service = self._require_service()
        if self.settings.resolved_mode == "v1":
            return self._chat_v1(service, message, conversation_id)
        return self._chat_v2(service, message, conversation_id)

    def _chat_v2(
        self, service: Any, message: str, conversation_id: str | None
    ) -> dict[str, Any]:
        session_id = conversation_id or self._create_session(service)

        try:
            response = self._send_v2(service, session_id, message)
        except Exception as error:
            if conversation_id and _status_code(error) in EXPIRED_SESSION_STATUS_CODES:
                # Retry once with a new server-side context. Any error from the
                # second attempt is deliberately converted to the same safe 502.
                session_id = self._create_session(service)
                try:
                    response = self._send_v2(service, session_id, message)
                except Exception as retry_error:
                    raise WatsonServiceError("O Watson Assistant está indisponível.") from retry_error
            else:
                raise WatsonServiceError("O Watson Assistant está indisponível.") from error

        return normalize_watson_response(response, session_id)

    def _chat_v1(
        self, service: Any, message: str, conversation_id: str | None
    ) -> dict[str, Any]:
        local_id, context = self._load_v1_context(conversation_id)
        try:
            response = service.message(
                workspace_id=str(self.settings.workspace_id),
                input={"text": message},
                context=context,
                headers=dict(LEARNING_OPT_OUT_HEADERS),
            ).get_result()
        except Exception as error:
            raise WatsonServiceError("O Watson Assistant está indisponível.") from error

        if not isinstance(response, Mapping):
            raise WatsonServiceError("O Watson retornou uma resposta inválida.")
        returned_context = response.get("context")
        if isinstance(returned_context, Mapping):
            context = deepcopy(dict(returned_context))
        self._store_v1_context(local_id, context)
        return normalize_watson_response(response, local_id)

    def _load_v1_context(
        self, conversation_id: str | None
    ) -> tuple[str, dict[str, Any]]:
        now = self._clock()
        with self._v1_context_lock:
            self._prune_v1_contexts(now)
            if conversation_id:
                entry = self._v1_contexts.get(conversation_id)
                if entry is not None:
                    entry.last_seen = now
                    self._v1_contexts.move_to_end(conversation_id)
                    return conversation_id, deepcopy(entry.context)
            return self._new_v1_conversation_id(), {}

    def _new_v1_conversation_id(self) -> str:
        # A custom factory makes collision handling deterministic in tests.
        for _ in range(10):
            candidate = self._conversation_id_factory()
            if (
                isinstance(candidate, str)
                and candidate
                and candidate not in self._v1_contexts
            ):
                return candidate
        raise WatsonServiceError("Não foi possível iniciar uma conversa local.")

    def _store_v1_context(self, conversation_id: str, context: dict[str, Any]) -> None:
        now = self._clock()
        with self._v1_context_lock:
            self._prune_v1_contexts(now)
            self._v1_contexts[conversation_id] = _V1ContextEntry(
                context=deepcopy(context), last_seen=now
            )
            self._v1_contexts.move_to_end(conversation_id)
            while len(self._v1_contexts) > self._v1_context_max_entries:
                self._v1_contexts.popitem(last=False)

    def _prune_v1_contexts(self, now: float) -> None:
        expired = [
            conversation_id
            for conversation_id, entry in self._v1_contexts.items()
            if now - entry.last_seen >= self._v1_context_ttl_seconds
        ]
        for conversation_id in expired:
            self._v1_contexts.pop(conversation_id, None)

    def reset(self, conversation_id: str | None) -> None:
        if not conversation_id:
            return
        service = self._require_service()
        if self.settings.resolved_mode == "v1":
            with self._v1_context_lock:
                self._v1_contexts.pop(conversation_id, None)
            return
        request = self._v2_runtime_kwargs()
        request["session_id"] = conversation_id
        request["headers"] = dict(LEARNING_OPT_OUT_HEADERS)
        try:
            service.delete_session(**request).get_result()
        except Exception as error:
            # An already-expired/deleted session is equivalent to a successful reset.
            if _status_code(error) not in EXPIRED_SESSION_STATUS_CODES:
                raise WatsonServiceError("Não foi possível encerrar a conversa no Watson.") from error


def normalize_watson_response(response: Mapping[str, Any], session_id: str) -> dict[str, Any]:
    """Convert the SDK payload to the stable, minimal API contract used by React."""

    safe_response = response if isinstance(response, Mapping) else {}
    output = safe_response.get("output")
    output = output if isinstance(output, Mapping) else {}

    texts: list[str] = []
    generic = output.get("generic")
    if isinstance(generic, list):
        for item in generic:
            if not isinstance(item, Mapping) or item.get("response_type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(_safe_text(text))

    if not texts:
        legacy_text = output.get("text")
        if isinstance(legacy_text, list):
            texts.extend(_safe_text(text) for text in legacy_text if isinstance(text, str) and text.strip())
        elif isinstance(legacy_text, str) and legacy_text.strip():
            texts.append(_safe_text(legacy_text))

    reply = "\n".join(texts) or (
        "Não consegui formular uma orientação agora. Tente explicar o sintoma novamente. "
        "Em caso de sinais graves, procure atendimento de emergência ou ligue 192."
    )

    # V2 returns NLP details inside output; V1 returns them at the top level.
    raw_intents = output.get("intents")
    if not isinstance(raw_intents, list):
        raw_intents = safe_response.get("intents")
    raw_intents = raw_intents if isinstance(raw_intents, list) else []
    intents = [item for item in raw_intents if isinstance(item, Mapping)]
    primary = max(intents, key=lambda item: _number(item.get("confidence")), default={})
    intent_name = primary.get("intent") if isinstance(primary.get("intent"), str) else None
    confidence = _number(primary.get("confidence")) if intent_name else 0.0

    entities: list[dict[str, Any]] = []
    raw_entities = output.get("entities")
    if not isinstance(raw_entities, list):
        raw_entities = safe_response.get("entities")
    raw_entities = raw_entities if isinstance(raw_entities, list) else []
    for item in raw_entities:
        if not isinstance(item, Mapping):
            continue
        name = item.get("entity")
        value = item.get("value")
        if not isinstance(name, str) or not isinstance(value, (str, int, float)):
            continue
        entities.append(
            {
                "entity": _safe_text(name),
                "value": _safe_text(str(value)),
                "confidence": _number(item.get("confidence"), default=1.0),
            }
        )

    urgent_from_context = _urgent_context(safe_response.get("context"))
    return {
        "reply": reply,
        "conversationId": session_id,
        "intent": intent_name,
        "confidence": confidence,
        "entities": entities,
        "urgent": intent_name == "sinal_alerta" or urgent_from_context,
    }


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: str, limit: int = 4_000) -> str:
    # Preserve ordinary line breaks while removing protocol control characters.
    cleaned = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
    return cleaned.strip()[:limit]


def _urgent_context(context: Any) -> bool:
    if not isinstance(context, Mapping):
        return False
    # V1 Dialog Skills expose user context variables directly.
    if context.get("urgent") is True:
        return True
    # V2 wraps the same variables by skill.
    skills = context.get("skills")
    if not isinstance(skills, Mapping):
        return False
    for skill in skills.values():
        if not isinstance(skill, Mapping):
            continue
        user_defined = skill.get("user_defined")
        if isinstance(user_defined, Mapping) and user_defined.get("urgent") is True:
            return True
    return False
