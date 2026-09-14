# CardioIA Acolhe — IR ALÉM 1

## IA Generativa e Extração de Informações Clínicas — Grupo 7

**FIAP — Fase 5, Capítulo 1**  
**Versão:** 1.0 — 14/09/2026  
**PDF gerado:** [`output/pdf/ir-alem-1-extracao-clinica.pdf`](../output/pdf/ir-alem-1-extracao-clinica.pdf) (`python scripts/generate_ir_alem1_report.py`)

### 1. Objetivo

O IR ALÉM 1 expande o assistente para **interpretar relatos clínicos não estruturados**: a pessoa escreve livremente o que sente e um modelo de linguagem devolve a mesma informação **organizada em JSON** — sintoma, intensidade de 0 a 10, duração, contexto, entidades nomeadas, nível de alerta e confiança. O módulo é um serviço Python independente (`src/backend/clinical_extractor.py`), exposto pela API Flask e integrado ao fluxo conversacional do Watson Assistant entregue na Parte 1.

**Limites clínicos.** O modelo apenas extrai e organiza o que foi relatado: não diagnostica, não prescreve e não recomenda medicamentos. A orientação de emergência (SAMU 192) é decidida pelo backend a partir do nível de alerta, nunca pelo modelo. Todos os textos usados no projeto são fictícios.

### 2. Fluxo de extração

```text
TEXTO LIVRE → PROMPT (system + few-shot + CoT) → MODELO (JSON mode, T = 0,2) → VALIDAÇÃO → JSON
```

1. O texto é validado (não vazio, até 2.000 caracteres na API) e normalizado.
2. O backend monta duas mensagens: um *system prompt* com papel, regras e esquema de saída, e uma mensagem de usuário com os exemplos *few-shot*, os passos de raciocínio e o texto a analisar.
3. A API Chat Completions (protocolo da OpenAI, aceito também por Google Gemini, Groq e outros) é chamada com `response_format={"type": "json_object"}`, temperatura 0,2 e limite de 4.000 tokens — folga necessária porque modelos com "raciocínio" interno (Gemini 3.x) consomem parte desse orçamento antes de escrever o JSON.
4. A resposta é convertida e validada: inteiros limitados a 0–10, confianças a 0,0–1,0, severidade mapeada para um *enum* e valores ausentes com padrões seguros.
5. O objeto `ClinicalExtraction` é serializado e devolvido pela API.

### 3. Técnicas de prompting aplicadas

| Técnica | Como foi aplicada | Onde está |
|---|---|---|
| System prompt com papel e regras | Papel de assistente de PLN clínica, dez regras explícitas (não diagnosticar, escalas numéricas, critérios de severidade, valores ausentes) e o esquema JSON esperado. | `SYSTEM_PROMPT` |
| Few-shot learning | Quatro exemplos completos — `critical`, `high`, `moderate` e `info` — com entidades, normalização e justificativa. | `FEW_SHOT_EXAMPLES` |
| Chain-of-thought | Seis passos ordenados que o modelo segue antes de responder; a justificativa fica no campo `reasoning`. | `COT_STEPS` |
| Saída estruturada (JSON mode) | Temperatura baixa, limite de tokens e `json_object` garantem JSON sintaticamente válido. | `ClinicalExtractor.extract` |
| Validação pós-modelo | Normaliza tipos, faixas, enum de severidade e tipos de entidade; nunca confia cegamente no texto gerado. | `parse_extraction` |

Passos de chain-of-thought enviados ao modelo:

1. Identifique o sintoma principal (ou registre que não há sintoma).
2. Estime a intensidade de 0 a 10 a partir das palavras usadas.
3. Localize a duração e o contexto (quando, onde, o que estava fazendo).
4. Procure sinais de alerta: dor no peito, suor frio, falta de ar em repouso, desmaio.
5. Classifique a severidade conforme as regras.
6. Liste entidades nomeadas e atribua a confiança geral.

### 4. Estrutura da saída

| Campo | Tipo | Descrição |
|---|---|---|
| `symptom` | string | Sintoma principal relatado ou "nenhum sintoma relatado". |
| `intensity` | inteiro 0–10 | Intensidade estimada; 0 quando não há sintoma. |
| `duration` | string | Duração ou frequência; "não informado" quando ausente. |
| `context` | string | Circunstâncias: momento, atividade, sinais associados. |
| `alert_severity` | enum | `critical`, `high`, `moderate`, `low` ou `info` — decide a ação do backend. |
| `confidence` | número 0,0–1,0 | Confiança geral do modelo na extração. |
| `entities` | lista | `value`, `type` (`symptom`, `medication`, `condition`, `duration`, `context`, `other`), `confidence`, `normalized`. |
| `reasoning` | string | Justificativa curta produzida pelo passo de chain-of-thought. |

Saída real do modelo `gemini-3.5-flash` (provedor Google) em 14/09/2026 para a entrada fictícia *"Acordei ontem à noite com uma dor forte no peito, tipo um aperto. Suei muito frio. Durou uns 30 minutos e achei que ia morrer."*, gravada por `python scripts/demo_clinical_extractor.py --real --save document/ir-alem-1-evidencia-llm.json`:

```json
{
  "symptom": "dor forte no peito em aperto e suor frio",
  "intensity": 9,
  "duration": "aproximadamente 30 minutos",
  "context": "ao acordar ontem à noite, com sensação de morte iminente",
  "alert_severity": "critical",
  "confidence": 0.98,
  "entities": [
    {"value": "dor forte no peito", "type": "symptom", "confidence": 0.98, "normalized": "dor torácica"},
    {"value": "aperto", "type": "symptom", "confidence": 0.95, "normalized": "dor em aperto"},
    {"value": "Suei muito frio", "type": "symptom", "confidence": 0.97, "normalized": "sudorese fria"},
    {"value": "30 minutos", "type": "duration", "confidence": 0.95, "normalized": null},
    {"value": "achei que ia morrer", "type": "symptom", "confidence": 0.92, "normalized": "sensação de morte iminente"},
    {"value": "ontem à noite", "type": "context", "confidence": 0.9, "normalized": null}
  ],
  "reasoning": "O relato descreve dor torácica de forte intensidade em aperto, associada a sudorese fria e sensação de morte iminente, o que configura um quadro de alta suspeita para emergência cardiovascular (infarto agudo do miocárdio)."
}
```

Os outros três cenários (falta de ar ao esforço → `high`, palpitações com losartana → `moderate` com entidade `medication`, pergunta educativa → `info`) estão no mesmo arquivo de evidência. Sem chave, `python scripts/demo_clinical_extractor.py` reproduz o mesmo esquema no modo de simulação.

### 5. Integração com o assistente conversacional

| Método | Rota | Contrato essencial |
|---|---|---|
| `POST` | `/api/extract` | `text` → `extraction` (JSON acima), `model` e `mode`. `400` para entrada inválida; `502` se o modelo falhar. |
| `POST` | `/api/chat/clinical` | `message` + `conversationId` → mesmo contrato de `/api/chat` (`reply`, `intent`, `entities`, `urgent`) mais `clinical` e `source`. |
| `GET` | `/api/health` | Inclui `clinical.mode` (`mock` ou `llm`), `clinical.provider` e `clinical.model`, sem expor segredos. |

| Nível de alerta | Critério | Comportamento de `/api/chat/clinical` |
|---|---|---|
| `critical` | Dor torácica com sinais de alerta, falta de ar em repouso, desmaio. | Responde imediatamente com orientação de emergência (`urgent: true`) sem consultar o Watson. |
| `high`, `moderate`, `low`, `info` | Demais relatos, perguntas e saudações. | O Watson responde e a extração é anexada em `clinical`; se o Watson não estiver configurado ou falhar, o backend devolve uma resposta educativa local construída a partir da extração. |

### 6. Tratamento de erros e privacidade

| Situação | Comportamento |
|---|---|
| Texto vazio ou acima do limite | `ValueError` no módulo; `400` na API, antes de qualquer chamada ao modelo. |
| Falha de rede, chave inválida ou cota esgotada | Erro do SDK encapsulado em `ClinicalExtractionError` com mensagem neutra; `502` em `/api/extract`; `/api/chat/clinical` segue com o Watson. |
| Resposta não JSON, vazia ou com estrutura errada | Mesmo tratamento seguro; o conteúdo bruto nunca é devolvido ao cliente. |
| Campos ausentes ou fora da faixa | Padrões seguros (intensidade 0, confiança 0,5, severidade `moderate`) e limites aplicados. |
| Privacidade | Nenhum texto clínico, resposta do modelo ou credencial é registrado em log; `raw_model_output` não sai da API; a chave fica apenas no `.env`, ignorado pelo Git. |

### 7. Modos de execução e reprodução

| Modo | Quando é usado | Características |
|---|---|---|
| `mock` | Sem `LLM_API_KEY` (padrão em testes e CI). | Simulação determinística por palavras-chave com o mesmo esquema e as mesmas regras de severidade; sem rede e sem custo. |
| `llm` | Com `LLM_API_KEY` no `.env`. | Chat Completions no provedor de `LLM_BASE_URL` e no modelo de `LLM_MODEL` (padrão `gpt-4o-mini`), JSON mode, temperatura 0,2, timeout de 20 s. |

O código usa o protocolo Chat Completions por meio do SDK `openai`; qualquer provedor compatível funciona sem alterar código. O **Google Gemini foi usado apenas nos testes e nas evidências** deste repositório, por oferecer free tier — OpenAI, Groq ou um Ollama local servem igualmente, trocando `LLM_BASE_URL` e `LLM_MODEL` (tabela de provedores no README).

```powershell
python scripts/demo_clinical_extractor.py            # 4 cenários no modo mock
python scripts/demo_clinical_extractor.py --real     # usa o provedor do .env
python scripts/demo_clinical_extractor.py --real --save document/ir-alem-1-evidencia-llm.json
python -m src.backend                                # API em http://127.0.0.1:5000
```

### 8. Testes automatizados

| Arquivo | Testes | Cobertura |
|---|---|---|
| `tests/backend/test_clinical_extractor.py` | 51 | Conteúdo do prompt, exemplos few-shot, parsing e limites, extrator real com cliente falso, provedores, mock e fábricas. |
| `tests/backend/test_clinical_api.py` | 23 | `/api/extract` e `/api/chat/clinical`: validação, severidade crítica, anexo ao Watson, degradação sem Watson, erros 502/503 sem vazamento. |
| Suíte original (API, gateway e export) | 42 | Inalterada; o health passou a informar o modo do extrator. |
| **Total** | **116** | **116/116 aprovados em 14/09/2026 com Python 3.11.9** |

### 9. Limites e próximos passos

O extrator trabalha apenas com texto; imagens simuladas não fazem parte desta entrega. A qualidade do modo com modelo real depende do provedor e do modelo escolhidos e não foi medida com um conjunto anotado — o critério de aceitação foi o esquema válido e a coerência com as regras de severidade nos exemplos. Evoluções naturais: avaliar precisão em um conjunto rotulado de relatos fictícios, ligar a interface React ao endpoint `/api/chat/clinical` e persistir extrações para o IR ALÉM 2.

### Referências

- OpenAI — [Text generation](https://platform.openai.com/docs/guides/text-generation) e [Structured outputs / JSON mode](https://platform.openai.com/docs/guides/structured-outputs).
- Google — [Gemini API: OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).
- Brown, T. B. et al. (2020). *Language Models are Few-Shot Learners*. arXiv:2005.14165.
- Wei, J. et al. (2022). *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. arXiv:2201.11903.
- Ministério da Saúde — [SAMU 192](https://www.gov.br/saude/pt-br/composicao/saes/samu-192).
