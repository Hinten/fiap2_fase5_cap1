"""Flask application factory and public HTTP contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flask import Flask, jsonify, request, send_from_directory

from .watson_gateway import (
    WatsonConfigurationError,
    WatsonGateway,
    WatsonGatewayProtocol,
    WatsonServiceError,
)


MAX_MESSAGE_LENGTH = 500
MAX_CONVERSATION_ID_LENGTH = 256


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    gateway: WatsonGatewayProtocol | None = None,
) -> Flask:
    """Create the application; ``gateway`` is injectable for isolated tests."""

    frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    # Static files are served by the explicit routes below. Disabling Flask's
    # implicit catch-all keeps SPA fallback and JSON /api errors deterministic.
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(JSON_SORT_KEYS=False)
    if config:
        app.config.from_mapping(config)

    watson = gateway or WatsonGateway()
    app.extensions["watson_gateway"] = watson

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
                }
            ),
            200,
        )

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


def _error(code: str, message: str, status: int) -> tuple[Any, int]:
    return jsonify({"error": {"code": code, "message": message}}), status
