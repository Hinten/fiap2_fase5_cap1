"""Demonstração do IR ALÉM 1: texto livre → JSON clínico estruturado.

Por padrão usa o extrator de simulação (sem chave, sem rede). Com ``--real``
carrega o ``.env`` e usa o provedor/modelo definidos em ``LLM_BASE_URL`` e
``LLM_MODEL`` (OpenAI, Google Gemini, Groq ou qualquer API compatível).
``--save`` grava as saídas em JSON (evidência usada pelo PDF do IR ALÉM 1);
``--list-models`` lista os modelos que a chave enxerga no provedor.
Os relatos abaixo são fictícios.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backend.clinical_extractor import (  # noqa: E402 - after sys.path setup
    ClinicalExtractionError,
    MockClinicalExtractor,
    create_extractor_from_env,
)


SCENARIOS = (
    (
        "Emergência (dor torácica)",
        "Acordei ontem à noite com uma dor forte no peito, tipo um aperto. "
        "Suei muito frio. Durou uns 30 minutos e achei que ia morrer.",
    ),
    (
        "Alerta alto (falta de ar ao esforço)",
        "Quando subo escadas ou corro fico muito ofegante. Demora uns 10 minutos "
        "pra respiração voltar ao normal. Nunca tive isso antes.",
    ),
    (
        "Moderado (palpitações recorrentes)",
        "Sinto palpitações de vez em quando, principalmente à noite. Duram uns 2-3 minutos "
        "e passam sozinhas. Tem umas 2 semanas. Tomo losartana todo dia.",
    ),
    (
        "Sem sintoma (pergunta educativa)",
        "Oi! Quais alimentos ajudam a cuidar do coração?",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real",
        action="store_true",
        help="usa o provedor configurado no .env (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="com --real, apenas lista os modelos disponíveis no provedor e sai",
    )
    parser.add_argument("--text", help="analisa apenas este texto em vez dos cenários padrão")
    parser.add_argument(
        "--pause",
        type=float,
        default=8.0,
        help="segundos de espera entre cenários no modo --real (free tiers limitam requisições/min)",
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="grava modo, modelo, data e as saídas em um arquivo JSON (evidência)",
    )
    return parser.parse_args()


def build_extractor(real: bool):
    if not real:
        return MockClinicalExtractor()
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    extractor = create_extractor_from_env()
    if extractor.mode != "llm":
        raise SystemExit("LLM_API_KEY não encontrada no .env; rode sem --real para usar o mock.")
    return extractor


def list_models(extractor) -> int:
    try:
        models = sorted(model.id for model in extractor.client.models.list())
    except Exception as error:  # noqa: BLE001 - diagnostic output for the operator
        print(f"Não foi possível listar modelos em {extractor.provider}: {type(error).__name__}")
        return 1
    print(f"{len(models)} modelos disponíveis em {extractor.provider}:")
    for model_id in models:
        print(f"  {model_id}")
    return 0


def extract_with_retry(extractor, text: str, *, real: bool, attempts: int = 3, wait: float = 20.0):
    """Free tiers answer 429 under load; wait and try again a few times."""

    for attempt in range(1, attempts + 1):
        try:
            return extractor.extract(text)
        except ClinicalExtractionError as error:
            transient = "Limite de requisições" in str(error) or "indisponível" in str(error)
            if not real or not transient or attempt == attempts:
                raise
            print(f"  ({error} Nova tentativa {attempt + 1}/{attempts} em {wait:.0f}s.)")
            time.sleep(wait)
    raise AssertionError("unreachable")


def main() -> int:
    arguments = parse_args()
    extractor = build_extractor(arguments.real)
    print(
        f"CardioIA Acolhe - IR ALÉM 1 | modo={extractor.mode} "
        f"provedor={extractor.provider} modelo={extractor.model}\n"
    )
    if arguments.list_models:
        return list_models(extractor)

    scenarios = [("Texto informado", arguments.text)] if arguments.text else list(SCENARIOS)
    results = []
    for index, (title, text) in enumerate(scenarios):
        if arguments.real and index and arguments.pause > 0:
            time.sleep(arguments.pause)
        print("=" * 78)
        print(title)
        print("-" * 78)
        print(f"Entrada: {text}\n")
        try:
            extraction = extract_with_retry(extractor, text, real=arguments.real)
        except ClinicalExtractionError as error:
            print(f"Falha na extração: {error}\n")
            continue
        payload = extraction.to_dict()
        results.append({"title": title, "input": text, "output": payload})
        print("Saída JSON:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if extraction.alert_severity.value == "critical":
            print("\n>> Sinal de alerta crítico: orientar emergência / SAMU 192.")
        print()

    print("=" * 78)
    print(json.dumps(extractor.get_stats(), ensure_ascii=False))

    if arguments.save:
        evidence = {
            "mode": extractor.mode,
            "provider": extractor.provider,
            "model": extractor.model,
            "date": date.today().isoformat(),
            "scenarios": results,
        }
        arguments.save.parent.mkdir(parents=True, exist_ok=True)
        arguments.save.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Evidência gravada em {arguments.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
