"""Clinical information extraction with generative AI (IR ALÉM 1).

Turns a free-text symptom report into a validated, JSON-serialisable
structure using prompt-engineering techniques: a role/system prompt with
explicit clinical boundaries, few-shot examples, chain-of-thought steps and
JSON mode. The model is reached through the Chat Completions protocol of the
``openai`` SDK, so any compatible provider works (OpenAI, Google Gemini, Groq,
a local Ollama...) by changing ``LLM_BASE_URL``/``LLM_MODEL``. The SDK
is imported lazily so the mock extractor and the rest of the backend work
without it. No clinical content or credential is logged by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_CLINICAL_TEXT_LENGTH = 5_000
# The JSON answer needs ~400 tokens, but "thinking" models (Gemini 3.x, o-series)
# spend part of this budget on hidden reasoning; 800 was cut off mid-JSON.
MAX_OUTPUT_TOKENS = 4_000
ENTITY_TYPES = frozenset({"symptom", "medication", "condition", "duration", "context", "other"})


class ClinicalExtractionError(RuntimeError):
    """A safe failure: the message never contains clinical text or secrets."""


class AlertSeverity(Enum):
    """Alert level attached to an extraction, from most to least urgent."""

    CRITICAL = "critical"  # emergency: chest pain with red flags, syncope
    HIGH = "high"  # needs prompt medical evaluation
    MODERATE = "moderate"  # should be investigated by a professional
    LOW = "low"  # mild or unspecific complaint
    INFO = "info"  # no symptom reported (question, greeting, request)


SEVERITY_RANK = {
    AlertSeverity.INFO: 0,
    AlertSeverity.LOW: 1,
    AlertSeverity.MODERATE: 2,
    AlertSeverity.HIGH: 3,
    AlertSeverity.CRITICAL: 4,
}


@dataclass(frozen=True)
class ClinicalEntity:
    """A named entity found in the text (symptom, medication, condition...)."""

    value: str
    entity_type: str
    confidence: float
    normalized: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "type": self.entity_type,
            "confidence": self.confidence,
            "normalized": self.normalized,
        }


@dataclass(frozen=True)
class ClinicalExtraction:
    """Structured output of one extraction, already validated."""

    symptom: str
    intensity: int  # 0-10
    duration: str
    context: str
    alert_severity: AlertSeverity
    confidence: float  # 0.0-1.0
    extracted_entities: list[ClinicalEntity] = field(default_factory=list)
    reasoning: str = ""
    raw_model_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Public JSON contract; ``raw_model_output`` is intentionally omitted."""

        return {
            "symptom": self.symptom,
            "intensity": self.intensity,
            "duration": self.duration,
            "context": self.context,
            "alert_severity": self.alert_severity.value,
            "confidence": self.confidence,
            "entities": [entity.to_dict() for entity in self.extracted_entities],
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Prompt engineering: system prompt, few-shot examples and CoT instructions
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um assistente de processamento de linguagem natural clínica do CardioIA Acolhe.
Sua única tarefa é EXTRAIR e ORGANIZAR informações de relatos livres de sintomas cardiológicos.

REGRAS OBRIGATÓRIAS:
1. Você NÃO diagnostica, NÃO prescreve e NÃO recomenda medicamentos. Apenas extrai o que foi relatado.
2. "intensity" é um inteiro de 0 a 10 (0 = nenhum sintoma; 10 = o pior possível).
3. "alert_severity" deve ser exatamente um de: "critical", "high", "moderate", "low", "info".
4. "confidence" é um número de 0.0 a 1.0 que expressa a sua confiança na extração.
5. Sinais de alerta que tornam o caso "critical": dor ou aperto no peito com intensidade alta,
   dor no peito acompanhada de suor frio, falta de ar em repouso, desmaio ou síncope.
6. Falta de ar ao esforço, dor no peito leve ou palpitações com mal-estar: "high".
7. Palpitações isoladas, cansaço ou tontura sem outros sinais: "moderate" ou "low".
8. Perguntas, saudações ou mensagens sem sintoma: "info", com "intensity" 0.
9. Quando uma informação não aparecer no texto, escreva "não informado" no campo correspondente.
10. Extraia entidades nomeadas com "type" em: symptom, medication, condition, duration, context, other.

FORMATO DE SAÍDA (JSON válido, sem texto fora do JSON):
{
  "symptom": "string",
  "intensity": 0,
  "duration": "string",
  "context": "string",
  "alert_severity": "critical|high|moderate|low|info",
  "confidence": 0.0,
  "entities": [
    {"value": "string", "type": "symptom|medication|condition|duration|context|other",
     "confidence": 0.0, "normalized": "string ou null"}
  ],
  "reasoning": "explicação breve do raciocínio"
}"""

FEW_SHOT_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "input": "Acordei ontem com dor forte no peito, parecia um aperto, durou umas 3 horas. Tive muito suor frio também.",
        "output": {
            "symptom": "dor no peito em aperto",
            "intensity": 9,
            "duration": "3 horas",
            "context": "ao acordar, em repouso, com suor frio",
            "alert_severity": "critical",
            "confidence": 0.95,
            "entities": [
                {"value": "dor forte no peito", "type": "symptom", "confidence": 0.97, "normalized": "dor torácica"},
                {"value": "suor frio", "type": "symptom", "confidence": 0.93, "normalized": "sudorese fria"},
                {"value": "3 horas", "type": "duration", "confidence": 0.9, "normalized": None},
            ],
            "reasoning": "Dor torácica intensa em aperto associada a suor frio é sinal de alerta para emergência.",
        },
    },
    {
        "input": "Falta de ar ao subir as escadas. Normal cansaço ou algo preocupante? Aconteceu por uns 10 minutos.",
        "output": {
            "symptom": "falta de ar ao esforço",
            "intensity": 6,
            "duration": "10 minutos",
            "context": "durante atividade física (subir escadas)",
            "alert_severity": "high",
            "confidence": 0.88,
            "entities": [
                {"value": "falta de ar", "type": "symptom", "confidence": 0.95, "normalized": "dispneia"},
                {"value": "subir as escadas", "type": "context", "confidence": 0.9, "normalized": "esforço físico"},
                {"value": "10 minutos", "type": "duration", "confidence": 0.9, "normalized": None},
            ],
            "reasoning": "Dispneia ao esforço sem suor frio ou desmaio: requer avaliação, mas não é emergência imediata.",
        },
    },
    {
        "input": "Tenho palpitações de vez em quando, principalmente à noite. Duram uns 2-3 minutos, já faz uma semana. Tomo losartana.",
        "output": {
            "symptom": "palpitações",
            "intensity": 4,
            "duration": "2 a 3 minutos por episódio, há 1 semana",
            "context": "à noite, episódios recorrentes",
            "alert_severity": "moderate",
            "confidence": 0.85,
            "entities": [
                {"value": "palpitações", "type": "symptom", "confidence": 0.96, "normalized": "palpitação"},
                {"value": "losartana", "type": "medication", "confidence": 0.98, "normalized": "losartana"},
                {"value": "uma semana", "type": "duration", "confidence": 0.88, "normalized": "7 dias"},
            ],
            "reasoning": "Palpitações recorrentes sem sintomas associados graves: investigar com profissional, sem urgência.",
        },
    },
    {
        "input": "Oi! Quais alimentos ajudam a cuidar do coração?",
        "output": {
            "symptom": "nenhum sintoma relatado",
            "intensity": 0,
            "duration": "não informado",
            "context": "pergunta educativa sobre alimentação",
            "alert_severity": "info",
            "confidence": 0.9,
            "entities": [],
            "reasoning": "A mensagem é uma pergunta geral; não há sintoma para extrair.",
        },
    },
)

COT_STEPS = (
    "Identifique o sintoma principal (ou registre que não há sintoma).",
    "Estime a intensidade de 0 a 10 a partir das palavras usadas.",
    "Localize a duração e o contexto (quando, onde, o que estava fazendo).",
    "Procure sinais de alerta: dor no peito, suor frio, falta de ar em repouso, desmaio.",
    "Classifique a severidade conforme as regras.",
    "Liste entidades nomeadas e atribua a confiança geral.",
)


def build_extraction_prompt(clinical_text: str) -> str:
    """User message: few-shot examples, chain-of-thought steps and the text."""

    parts = ["EXEMPLOS DE EXTRAÇÃO:"]
    for index, example in enumerate(FEW_SHOT_EXAMPLES, start=1):
        parts.append(f'\nExemplo {index}\nTexto: "{example["input"]}"')
        parts.append("Saída JSON:")
        parts.append(json.dumps(example["output"], ensure_ascii=False, indent=2))

    parts.append("\nPASSOS DE RACIOCÍNIO (siga em ordem antes de responder):")
    parts.extend(f"{index}. {step}" for index, step in enumerate(COT_STEPS, start=1))

    parts.append(f'\nTEXTO CLÍNICO A ANALISAR:\n"{clinical_text}"')
    parts.append("\nResponda APENAS com o JSON no formato definido.")
    return "\n".join(parts)


def build_messages(clinical_text: str) -> list[dict[str, str]]:
    """Chat Completions payload: the system prompt is sent once, as a system message."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_extraction_prompt(clinical_text)},
    ]


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------


def parse_extraction(data: Mapping[str, Any], raw_output: str = "") -> ClinicalExtraction:
    """Normalise a model payload into ``ClinicalExtraction`` with safe defaults."""

    if not isinstance(data, Mapping):
        raise ClinicalExtractionError("O modelo retornou uma estrutura inválida.")

    entities: list[ClinicalEntity] = []
    raw_entities = data.get("entities")
    if isinstance(raw_entities, Sequence) and not isinstance(raw_entities, (str, bytes)):
        for item in raw_entities:
            if not isinstance(item, Mapping):
                continue
            value = _text(item.get("value"), default="")
            if not value:
                continue
            entity_type = _text(item.get("type"), default="other").lower()
            normalized = _text(item.get("normalized"), default="")
            entities.append(
                ClinicalEntity(
                    value=value,
                    entity_type=entity_type if entity_type in ENTITY_TYPES else "other",
                    confidence=_ratio(item.get("confidence"), default=0.7),
                    normalized=normalized or None,
                )
            )

    return ClinicalExtraction(
        symptom=_text(data.get("symptom"), default="não informado"),
        intensity=_bounded_int(data.get("intensity"), default=0, low=0, high=10),
        duration=_text(data.get("duration"), default="não informado"),
        context=_text(data.get("context"), default="não informado"),
        alert_severity=_severity(data.get("alert_severity")),
        confidence=_ratio(data.get("confidence"), default=0.5),
        extracted_entities=entities,
        reasoning=_text(data.get("reasoning"), default=""),
        raw_model_output=raw_output,
    )


def _text(value: Any, *, default: str, limit: int = 500) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return default
    cleaned = "".join(char for char in value if char == "\n" or ord(char) >= 32).strip()
    return cleaned[:limit] or default


def _bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _ratio(value: Any, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.0, min(1.0, number)), 3)


def _severity(value: Any) -> AlertSeverity:
    if isinstance(value, str):
        try:
            return AlertSeverity(value.strip().lower())
        except ValueError:
            logger.warning("Severidade desconhecida retornada pelo modelo; usando 'moderate'.")
    return AlertSeverity.MODERATE


def _safe_reason(error: Exception) -> str:
    """Map an SDK failure to a short reason without secrets or clinical text."""

    status = getattr(error, "status_code", None)
    code = str(getattr(error, "code", "") or "")
    error_type = ""
    body = getattr(error, "body", None)
    if isinstance(body, Mapping):
        inner = body.get("error") if isinstance(body.get("error"), Mapping) else body
        code = code or str(inner.get("code") or "")
        error_type = str(inner.get("type") or "")

    if status in (401, 403):
        return "O provedor recusou a chave de API (LLM_API_KEY inválida ou sem permissão)."
    if status == 429 and ("quota" in code or "credit" in code or "quota" in error_type):
        return "A conta do provedor está sem créditos ou sem cota (insufficient_quota)."
    if status == 429:
        return "Limite de requisições do provedor atingido; tente novamente em instantes."
    if status == 404:
        return "O modelo configurado em LLM_MODEL não foi encontrado no provedor."
    if status is None:
        return "Não foi possível conectar à API do modelo de linguagem (verifique LLM_BASE_URL)."
    return f"O modelo de linguagem está indisponível (HTTP {status})."


def provider_from_base_url(base_url: str | None) -> str:
    """Short provider label for health checks and reports; never includes secrets."""

    if not base_url:
        return "openai"
    host = (urlparse(base_url).hostname or "").lower()
    if host.endswith("googleapis.com"):
        return "google"
    if host.endswith("openai.com"):
        return "openai"
    if host.endswith("groq.com"):
        return "groq"
    if host in {"localhost", "127.0.0.1"}:
        return "local"
    return host or "custom"


def _prepare_text(clinical_text: Any) -> str:
    if not isinstance(clinical_text, str) or not clinical_text.strip():
        raise ValueError("Clinical text cannot be empty")
    text = clinical_text.strip()
    if len(text) > MAX_CLINICAL_TEXT_LENGTH:
        logger.warning("Texto clínico truncado para %d caracteres.", MAX_CLINICAL_TEXT_LENGTH)
        text = text[:MAX_CLINICAL_TEXT_LENGTH]
    return text


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


class ClinicalExtractor:
    """Extracts structured clinical data through a Chat Completions compatible API."""

    mode = "llm"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        *,
        base_url: str | None = None,
        client: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:  # pragma: no cover - depends on the environment
                raise ImportError("OpenAI client not installed. Install it with: pip install openai") from error
            # Explicit arguments win; otherwise the provider-neutral LLM_* variables
            # are used. Secrets go only to the SDK and are never logged.
            api_key = api_key or (os.environ.get("LLM_API_KEY") or "").strip() or None
            base_url = base_url or (os.environ.get("LLM_BASE_URL") or "").strip() or None
            # Free tiers answer 429/503 under load; the SDK retries those with backoff.
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=4)
        self.client = client
        self.model = model
        self.temperature = temperature
        self.provider = provider_from_base_url(base_url)
        self._extraction_count = 0
        logger.info("ClinicalExtractor pronto: provedor=%s modelo=%s.", self.provider, model)

    def extract(self, clinical_text: str) -> ClinicalExtraction:
        """Return a validated extraction or raise ``ClinicalExtractionError``."""

        text = _prepare_text(clinical_text)
        self._extraction_count += 1

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=build_messages(text),
                temperature=self.temperature,
                max_tokens=MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            # SDK errors are wrapped so callers never expose provider details;
            # only a content-free reason survives to help operators.
            raise ClinicalExtractionError(_safe_reason(error)) from error

        raw_output = self._message_content(response)
        try:
            parsed = json.loads(raw_output)
        except (TypeError, ValueError) as error:
            raise ClinicalExtractionError("O modelo retornou uma resposta que não é JSON válido.") from error

        extraction = parse_extraction(parsed, raw_output=raw_output)
        logger.info(
            "Extração #%d concluída: severidade=%s confiança=%.2f",
            self._extraction_count,
            extraction.alert_severity.value,
            extraction.confidence,
        )
        return extraction

    @staticmethod
    def _message_content(response: Any) -> str:
        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise ClinicalExtractionError("O modelo retornou uma resposta vazia.") from error
        if getattr(choice, "finish_reason", None) == "length":
            raise ClinicalExtractionError(
                "O modelo interrompeu a resposta por limite de tokens (aumente MAX_OUTPUT_TOKENS)."
            )
        if not isinstance(content, str) or not content.strip():
            raise ClinicalExtractionError("O modelo retornou uma resposta vazia.")
        return content

    def get_stats(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "total_extractions": self._extraction_count,
        }


class MockClinicalExtractor(ClinicalExtractor):
    """Deterministic, keyword-based simulation for tests and offline demos.

    It mirrors the schema and the severity rules of the generative extractor
    without any network call or API key.
    """

    mode = "mock"

    def __init__(self) -> None:  # noqa: D107 - intentionally skips the SDK setup
        self.client = None
        self.model = "mock"
        self.provider = "mock"
        self.temperature = 0.0
        self._extraction_count = 0
        logger.info("MockClinicalExtractor pronto (modo de simulação).")

    def extract(self, clinical_text: str) -> ClinicalExtraction:
        text = _prepare_text(clinical_text)
        self._extraction_count += 1
        lowered = text.lower()
        raw = '{"mock": true}'

        if any(word in lowered for word in ("desmai", "síncope", "sincope", "apaguei")):
            return ClinicalExtraction(
                symptom="desmaio",
                intensity=9,
                duration=_find_duration(lowered),
                context="perda de consciência relatada",
                alert_severity=AlertSeverity.CRITICAL,
                confidence=0.93,
                extracted_entities=[ClinicalEntity("desmaio", "symptom", 0.95, "síncope")],
                reasoning="Desmaio ou síncope é sempre sinal de alerta crítico.",
                raw_model_output=raw,
            )

        if "dor" in lowered and ("peito" in lowered or "torácica" in lowered or "toracica" in lowered):
            entities = [ClinicalEntity("dor no peito", "symptom", 0.95, "dor torácica")]
            context = "repouso"
            if any(word in lowered for word in ("suor", "suei", "suando", "sudorese")):
                entities.append(ClinicalEntity("suor frio", "symptom", 0.9, "sudorese fria"))
                context = "repouso, com suor frio"
            return ClinicalExtraction(
                symptom="dor no peito",
                intensity=8,
                duration=_find_duration(lowered),
                context=context,
                alert_severity=AlertSeverity.CRITICAL,
                confidence=0.95,
                extracted_entities=entities,
                reasoning="Dor torácica intensa é sinal de alerta crítico.",
                raw_model_output=raw,
            )

        if any(word in lowered for word in ("falta de ar", "ofegante", "dispneia", "sem ar")):
            return ClinicalExtraction(
                symptom="falta de ar ao esforço",
                intensity=6,
                duration=_find_duration(lowered),
                context="durante esforço físico",
                alert_severity=AlertSeverity.HIGH,
                confidence=0.85,
                extracted_entities=[
                    ClinicalEntity("falta de ar", "symptom", 0.9, "dispneia"),
                    ClinicalEntity("esforço", "context", 0.85, None),
                ],
                reasoning="Dispneia ao esforço exige avaliação, mas não é emergência imediata.",
                raw_model_output=raw,
            )

        if "palpita" in lowered or "coração acelerado" in lowered or "coracao acelerado" in lowered:
            return ClinicalExtraction(
                symptom="palpitações",
                intensity=4,
                duration=_find_duration(lowered),
                context="episódios recorrentes",
                alert_severity=AlertSeverity.MODERATE,
                confidence=0.8,
                extracted_entities=[ClinicalEntity("palpitações", "symptom", 0.88, "palpitação")],
                reasoning="Palpitações isoladas: investigar com profissional, sem urgência.",
                raw_model_output=raw,
            )

        return ClinicalExtraction(
            symptom="relato inespecífico",
            intensity=2,
            duration=_find_duration(lowered),
            context="não informado",
            alert_severity=AlertSeverity.LOW,
            confidence=0.5,
            extracted_entities=[],
            reasoning="Nenhum sinal de alerta identificado no relato.",
            raw_model_output=raw,
        )


def _find_duration(lowered_text: str) -> str:
    """Tiny heuristic so mock outputs echo the duration mentioned in the text."""

    match = re.search(r"(\d+(?:\s*[-a]\s*\d+)?)\s*(minutos?|horas?|dias?|semanas?|meses?)", lowered_text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return "não informado"


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def create_extractor(
    use_mock: bool = False,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> ClinicalExtractor:
    """Return the mock or the API-backed extractor."""

    if use_mock:
        return MockClinicalExtractor()
    return ClinicalExtractor(api_key=api_key, model=model or DEFAULT_MODEL, base_url=base_url)


def create_extractor_from_env(environ: Mapping[str, str] | None = None) -> ClinicalExtractor:
    """Use the configured provider when ``LLM_API_KEY`` is set; otherwise the mock.

    ``LLM_BASE_URL`` selects the provider (empty = OpenAI; Google Gemini, Groq
    and others expose Chat Completions compatible endpoints).
    """

    source = environ if environ is not None else os.environ
    api_key = (source.get("LLM_API_KEY") or "").strip()
    model = (source.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL
    base_url = (source.get("LLM_BASE_URL") or "").strip() or None
    if not api_key:
        logger.info("LLM_API_KEY ausente; a extração clínica usará o modo de simulação.")
        return MockClinicalExtractor()
    try:
        return ClinicalExtractor(api_key=api_key, model=model, base_url=base_url)
    except ImportError:
        logger.warning("Pacote openai não instalado; a extração clínica usará o modo de simulação.")
        return MockClinicalExtractor()
