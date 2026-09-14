"""Flask application factory and public HTTP contract."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from flask import Flask, jsonify, request, send_from_directory

from .clinical_extractor import (
    AlertSeverity,
    ClinicalExtraction,
    ClinicalExtractionError,
    ClinicalExtractor,
    create_extractor_from_env,
)
from .watson_gateway import (
    WatsonConfigurationError,
    WatsonGateway,
    WatsonGatewayProtocol,
    WatsonServiceError,
)


logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 500
MAX_CONVERSATION_ID_LENGTH = 256
MAX_CLINICAL_TEXT_LENGTH = 2_000


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    gateway: WatsonGatewayProtocol | None = None,
    extractor: ClinicalExtractor | None = None,
) -> Flask:
    """Create the application; ``gateway`` and ``extractor`` are injectable for tests."""

    frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    # Static files are served by the explicit routes below. Disabling Flask's
    # implicit catch-all keeps SPA fallback and JSON /api errors deterministic.
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(JSON_SORT_KEYS=False)
    if config:
        app.config.from_mapping(config)

    watson = gateway or WatsonGateway()
    app.extensions["watson_gateway"] = watson
    # IR ALÉM 1: one extractor per process (mock without LLM_API_KEY).
    clinical = extractor or create_extractor_from_env()
    app.extensions["clinical_extractor"] = clinical

    @app.get("/api/health")
    def health() -> tuple[Any, int]:
        watson_status: dict[str, Any] = {"configured": bool(watson.configured)}
        api_mode = getattr(watson, "api_mode", None)
        if api_mode in {"v1", "v2"}:
            watson_status["mode"] = api_mode
        return (
            jsonify(
                {
                    "status": "ok",
                    "service": "cardioia-api",
                    "watson": watson_status,
                    "clinical": {
                        "mode": clinical.mode,
                        "provider": clinical.provider,
                        "model": clinical.model,
                    },
                }
            ),
            200,
        )

    @app.post("/api/extract")
    def extract() -> tuple[Any, int]:
        """IR ALÉM 1: free text in, validated clinical JSON out."""

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("invalid_request", "Envie um corpo JSON válido.", 400)

        validation_error = _validate_clinical_text(payload.get("text"))
        if validation_error:
            return _error("invalid_text", validation_error, 400)

        try:
            extraction = clinical.extract(payload["text"].strip())
        except ValueError as error:
            return _error("invalid_text", str(error), 400)
        except ClinicalExtractionError:
            return _error(
                "extraction_unavailable",
                "Não foi possível interpretar o texto clínico agora. Tente novamente.",
                502,
            )
        except Exception:
            # Do not expose SDK details, credentials, or user content.
            logger.exception("Falha inesperada na extração clínica.")
            return _error(
                "extraction_unavailable",
                "Não foi possível interpretar o texto clínico agora. Tente novamente.",
                502,
            )

        return (
            jsonify(
                {
                    "extraction": extraction.to_dict(),
                    "mode": clinical.mode,
                    "provider": clinical.provider,
                    "model": clinical.model,
                }
            ),
            200,
        )

    @app.post("/api/chat/clinical")
    def chat_clinical() -> tuple[Any, int]:
        """Chat enriched by the clinical extraction (IR ALÉM 1).

        1. The message is structured by the extractor (severity, entities...).
        2. A ``critical`` severity answers immediately with emergency guidance.
        3. Otherwise the Watson dialog answers and the extraction is attached.
        4. Without Watson (not configured or unavailable) an educational local
           reply is built from the extraction, so the endpoint still degrades
           gracefully.
        """

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("invalid_request", "Envie um corpo JSON válido.", 400)

        validation_error = _validate_message(payload.get("message"))
        if validation_error:
            return _error("invalid_message", validation_error, 400)

        conversation_id, conversation_error = _optional_conversation_id(
            payload.get("conversationId")
        )
        if conversation_error:
            return _error("invalid_conversation", conversation_error, 400)

        message = payload["message"].strip()
        extraction = _safe_extract(clinical, message)

        if extraction is not None and extraction.alert_severity is AlertSeverity.CRITICAL:
            return jsonify(_local_chat_response(extraction, conversation_id)), 200

        if watson.configured:
            try:
                result = watson.chat(message, conversation_id)
            except Exception:
                # Watson failures are already sanitised by the gateway; with an
                # extraction in hand the user still gets a useful answer.
                if extraction is None:
                    return _error(
                        "watson_unavailable",
                        "Não foi possível consultar o Watson Assistant. Tente novamente.",
                        502,
                    )
                return jsonify(_local_chat_response(extraction, conversation_id)), 200
            return jsonify(_merge_clinical(result, extraction)), 200

        if extraction is None:
            return _error(
                "watson_not_configured",
                "Watson Assistant não está configurado no servidor.",
                503,
            )
        return jsonify(_local_chat_response(extraction, conversation_id)), 200

    @app.post("/api/chat")
    def chat() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("invalid_request", "Envie um corpo JSON válido.", 400)

        validation_error = _validate_message(payload.get("message"))
        if validation_error:
            return _error("invalid_message", validation_error, 400)

        conversation_id, conversation_error = _optional_conversation_id(
            payload.get("conversationId")
        )
        if conversation_error:
            return _error("invalid_conversation", conversation_error, 400)

        if not watson.configured:
            return _error(
                "watson_not_configured",
                "Watson Assistant não está configurado no servidor.",
                503,
            )

        try:
            result = watson.chat(payload["message"].strip(), conversation_id)
        except WatsonConfigurationError:
            return _error(
                "watson_not_configured",
                "Watson Assistant não está configurado no servidor.",
                503,
            )
        except WatsonServiceError:
            return _error(
                "watson_unavailable",
                "Não foi possível consultar o Watson Assistant. Tente novamente.",
                502,
            )
        except Exception:
            # Do not expose SDK details, credentials, or user content.
            return _error(
                "watson_unavailable",
                "Não foi possível consultar o Watson Assistant. Tente novamente.",
                502,
            )

        return jsonify(result), 200

    @app.post("/api/reset")
    def reset() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return _error("invalid_request", "Envie um corpo JSON válido.", 400)

        conversation_id, conversation_error = _optional_conversation_id(
            payload.get("conversationId")
        )
        if conversation_error:
            return _error("invalid_conversation", conversation_error, 400)

        if conversation_id and not watson.configured:
            return _error(
                "watson_not_configured",
                "Watson Assistant não está configurado no servidor.",
                503,
            )

        try:
            watson.reset(conversation_id)
        except WatsonConfigurationError:
            return _error(
                "watson_not_configured",
                "Watson Assistant não está configurado no servidor.",
                503,
            )
        except WatsonServiceError:
            return _error(
                "watson_unavailable",
                "Não foi possível encerrar a sessão no Watson Assistant.",
                502,
            )
        except Exception:
            return _error(
                "watson_unavailable",
                "Não foi possível encerrar a sessão no Watson Assistant.",
                502,
            )

        return jsonify({"reset": True, "conversationId": None}), 200

    @app.get("/")
    def frontend_index() -> Any:
        if frontend_dist.joinpath("index.html").is_file():
            return send_from_directory(frontend_dist, "index.html")
        return _error(
            "frontend_not_built",
            "Interface ainda não compilada. Execute o build do frontend.",
            404,
        )

    @app.get("/<path:asset_path>")
    def frontend_asset(asset_path: str) -> Any:
        if asset_path.startswith("api/"):
            return _error("not_found", "Endpoint não encontrado.", 404)
        target = frontend_dist.joinpath(asset_path)
        if target.is_file():
            return send_from_directory(frontend_dist, asset_path)
        if frontend_dist.joinpath("index.html").is_file():
            return send_from_directory(frontend_dist, "index.html")
        return _error("not_found", "Recurso não encontrado.", 404)

    return app


def _validate_message(value: Any) -> str | None:
    if not isinstance(value, str):
        return "O campo 'message' deve ser um texto."
    stripped = value.strip()
    if not stripped:
        return "Digite uma mensagem antes de enviar."
    if len(stripped) > MAX_MESSAGE_LENGTH:
        return f"A mensagem deve ter no máximo {MAX_MESSAGE_LENGTH} caracteres."
    return None


def _optional_conversation_id(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, "O campo 'conversationId' deve ser um texto."
    cleaned = value.strip()
    if not cleaned:
        return None, None
    if len(cleaned) > MAX_CONVERSATION_ID_LENGTH:
        return None, "O identificador de conversa é inválido."
    if any(ord(char) < 33 or ord(char) > 126 for char in cleaned):
        return None, "O identificador de conversa é inválido."
    return cleaned, None


def _validate_clinical_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return "O campo 'text' deve ser um texto."
    stripped = value.strip()
    if not stripped:
        return "Envie um texto clínico para análise."
    if len(stripped) > MAX_CLINICAL_TEXT_LENGTH:
        return f"O texto deve ter no máximo {MAX_CLINICAL_TEXT_LENGTH} caracteres."
    return None


def _safe_extract(extractor: ClinicalExtractor, message: str) -> ClinicalExtraction | None:
    """Never let the extraction break the chat; log a content-free reason."""

    try:
        return extractor.extract(message)
    except ClinicalExtractionError as error:
        logger.warning("Extração clínica indisponível: %s", error)
    except Exception:
        logger.exception("Falha inesperada na extração clínica.")
    return None


def _merge_clinical(
    result: Mapping[str, Any], extraction: ClinicalExtraction | None
) -> dict[str, Any]:
    merged = dict(result)
    merged["source"] = "watson"
    merged["clinical"] = extraction.to_dict() if extraction else None
    return merged


def _local_chat_response(
    extraction: ClinicalExtraction, conversation_id: str | None
) -> dict[str, Any]:
    """Same contract as ``/api/chat`` so the React client can reuse it."""

    return {
        "reply": _local_reply(extraction),
        "conversationId": conversation_id,
        "intent": None,
        "confidence": extraction.confidence,
        "entities": [
            {
                "entity": entity.entity_type,
                "value": entity.value,
                "confidence": entity.confidence,
            }
            for entity in extraction.extracted_entities
        ],
        "urgent": extraction.alert_severity is AlertSeverity.CRITICAL,
        "source": "clinical",
        "clinical": extraction.to_dict(),
    }


_DISCLAIMER = (
    "Este assistente é educativo: não diagnostica, não prescreve e não substitui "
    "a avaliação de um profissional de saúde."
)


def _local_reply(extraction: ClinicalExtraction) -> str:
    severity = extraction.alert_severity
    if severity is AlertSeverity.INFO:
        return (
            "Não identifiquei um sintoma na sua mensagem. Se quiser organizar um relato, "
            "descreva o que sente, há quanto tempo e a intensidade de 0 a 10. "
            + _DISCLAIMER
        )

    summary = (
        f"Entendi o seu relato: {extraction.symptom}, intensidade {extraction.intensity}/10, "
        f"duração {extraction.duration}, contexto: {extraction.context}."
    )
    if severity is AlertSeverity.CRITICAL:
        guidance = (
            "Esse relato contém sinais de alerta. Procure atendimento de emergência agora "
            "ou ligue para o SAMU 192. Não espere o sintoma passar."
        )
    elif severity is AlertSeverity.HIGH:
        guidance = (
            "Recomendo avaliação médica ainda hoje. Se surgir dor no peito, falta de ar em "
            "repouso, suor frio ou desmaio, ligue 192 imediatamente."
        )
    else:
        guidance = (
            "Anote quando o sintoma começou, o que melhora ou piora e leve essas informações "
            "a uma consulta. Se piorar ou surgirem sinais de alerta, ligue 192."
        )
    return f"{summary} {guidance} {_DISCLAIMER}"


def _error(code: str, message: str, status: int) -> tuple[Any, int]:
    return jsonify({"error": {"code": code, "message": message}}), status

