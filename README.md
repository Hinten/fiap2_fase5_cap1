# FIAP — Faculdade de Informática e Administração Paulista

<p align="center">
  <a href="https://www.fiap.com.br/">
    <img src="https://raw.githubusercontent.com/lfusca/templateFiap/50e1e2720637b222357a7ebd1919c38a44af7cd2/assets/logo-fiap.png" alt="FIAP — Faculdade de Informática e Administração Paulista" width="320">
  </a>
</p>

<br>

<div align="center">
  <img src="assets/cardioia-mark.svg" alt="Símbolo do CardioIA Acolhe" width="96">
  <h1>CardioIA Acolhe</h1>
  <p><strong>Acolhimento educativo para organizar relatos de sintomas cardiológicos com segurança e clareza.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/FIAP-Fase%205%20%C2%B7%20Cap%C3%ADtulo%201-ed145b" alt="FIAP — Fase 5, Capítulo 1">
    <img src="https://img.shields.io/badge/vers%C3%A3o-0.1.0-0b706f" alt="Versão 0.1.0">
  </p>
</div>

> [!IMPORTANT]
> O CardioIA Acolhe não realiza diagnóstico, não prescreve tratamento e não substitui profissionais ou serviços de saúde. Em caso de emergência, procure atendimento imediatamente ou ligue para o **SAMU 192**. Este projeto é acadêmico: não insira dados reais de pacientes.

## Grupo 7

## 👨‍🎓 Integrantes

| Integrante | RM |
|---|---:|
| Alice Caroline Marinho de Assis | 566233 |
| Leonardo Sampaio Souza | 563928 |
| Lucas Bassetto Francelino | 561409 |
| Pedro Lucas Tostes Silva | 561644 |
| Vitor Albuquerque Bezerra da Silva | 563001 |

## 👩‍🏫 Professores

### Tutor(a)

- Caique Nonato da Silva Bezerra

### Coordenador(a)

- André Godoi Chiovato

## Sumário

- [Descrição](#descricao)
- [Demonstração da interface](#interface)
- [Aderência ao enunciado](#aderencia)
- [Como funciona](#como-funciona)
- [Arquitetura](#arquitetura)
- [API da aplicação](#api)
- [Estrutura de pastas](#estrutura)
- [Configuração do Watson Assistant](#configuracao)
- [IR ALÉM 1 — extração clínica com IA generativa](#ir-alem-1)
- [IR ALÉM 2 — automação inteligente com RPA, IA e dados híbridos](#ir-alem-2)
- [Como executar o código](#execucao)
- [Testes e qualidade](#qualidade)
- [Histórico de lançamentos](#historico)
- [Licença](#licenca)

<a id="descricao"></a>

## 📜 Descrição

O **CardioIA Acolhe** é um assistente conversacional educativo que ajuda uma pessoa a organizar informações sobre sintomas cardiológicos antes de procurar atendimento profissional. Em uma conversa curta e determinística, a aplicação identifica o sintoma relatado, pergunta intensidade e duração, preserva as respostas no contexto e devolve um resumo estruturado. Também ajuda o usuário a preparar perguntas e informações para uma consulta.

O processamento de linguagem natural do fluxo principal utiliza uma **Dialog Skill do IBM Watson Assistant**, sem IA generativa. A skill em português brasileiro reúne intents, entidades, sinônimos, variáveis de contexto, um nó de emergência prioritário e fallback final. O backend Flask protege as credenciais e normaliza as respostas; a interface web baseada em HTML, React e Vite oferece histórico, sugestões, estados de carregamento e erro, reinício da conversa, alerta de urgência e detalhes de NLP.

Como desafio opcional, o [IR ALÉM 1](#ir-alem-1) adiciona um módulo de **IA generativa** que transforma relatos clínicos em texto livre em JSON estruturado (sintoma, intensidade, duração, contexto, entidades, nível de alerta e confiança), usando system prompt, few-shot, chain-of-thought e JSON mode, com validação e modo de simulação sem chave.

O [IR ALÉM 2](#ir-alem-2) acrescenta um **fluxo de automação robótica de processos (RPA)**: um simulador gera dados clínicos fictícios em **PostgreSQL**, um robô Python os lê periodicamente e aplica **Isolation Forest** para detectar anomalias, alertas e eventos ficam registrados em trilha de auditoria e as mensagens enviadas pelo Watson Assistant são preservadas em **MongoDB**.

<a id="interface"></a>

## 🖼️ Demonstração da interface

<p align="center">
  <img src="assets/screenshots/cardioia-desktop.png" alt="Tela inicial desktop do CardioIA Acolhe conectado, com sugestões e painel de detalhes NLP" width="100%">
  <br>
  <sub>Interface desktop conectada — 1440 × 900 px</sub>
</p>

<p align="center">
  <img src="assets/screenshots/cardioia-mobile.png" alt="Tela inicial responsiva e conectada do CardioIA Acolhe em um dispositivo móvel" width="390">
  <br>
  <sub>Interface responsiva conectada — 390 × 844 px</sub>
</p>

<a id="aderencia"></a>

## 🎯 Aderência ao enunciado

| Critério ou entregável | Evidência | Situação atual |
|---|---|---|
| Fluxo conversacional com NLP — 3 pontos | 7 intents, 4 entidades, 14 nós, contexto, fallback e alerta prioritário | **Implementado e verificado** |
| Integração entre backend e assistente — 2 pontos | Flask integrado ao IBM Watson Assistant Classic/Lite pela API V1 | **Verificada em 13/09/2026** |
| Interface funcional — 2 pontos | Aplicação web React/Vite baseada em HTML, integrada à API e registrada nas capturas acima | **Implementada e verificada** |
| Organização e clareza do código — 2 pontos | Estrutura por frontend, backend, configuração, scripts e testes | **Disponível** |
| Documentação — 1 ponto | README, relatório técnico de duas páginas e instruções de reprodução | **Disponível** |
| Backend Python | [`src/backend`](src/backend) | **Disponível** |
| Export do assistente | [`cardioia-dialog.json`](config/watson/cardioia-dialog.json) | **Disponível** |
| Relatório curto | [PDF](output/pdf/relatorio-cardioia.pdf) · [fonte em Markdown](document/relatorio-cardioia.md) | **Disponível — 2 páginas** |
| Repositório GitHub público | Repositório do projeto | **Exceção consciente:** mantido privado; avaliador previamente convidado |
| Vídeo de até 3 minutos | [Demonstração no YouTube](https://www.youtube.com/watch?v=ynFGrxRVwWA) | **Publicado** |
| Grupo de 4 a 5 integrantes — 1 ponto extra | Grupo 7 com cinco integrantes identificados acima | **Atende à formação recomendada** |
| IR ALÉM 1 — código Python | [`clinical_extractor.py`](src/backend/clinical_extractor.py), rotas `/api/extract` e `/api/chat/clinical`, [demo](scripts/demo_clinical_extractor.py), 74 testes e [evidência real com Gemini](document/ir-alem-1-evidencia-llm.json) | **Implementado; execução real verificada em 14/09/2026** |
| IR ALÉM 1 — documento PDF | [PDF](output/pdf/ir-alem-1-extracao-clinica.pdf) · [fonte em Markdown](document/ir-alem-1-extracao-clinica.md) | **Disponível — 4 páginas** |
| IR ALÉM 2 — código da automação (Python) | [`simulador.py`](src/backend/simulador.py), [`rpa_ia.py`](src/backend/rpa_ia.py) e [`api_watson.py`](src/backend/api_watson.py) | **Implementado** |
| IR ALÉM 2 — estrutura dos bancos | PostgreSQL em [`setup_banco.sql`](config/SQL/setup_banco.sql); MongoDB `doctor_in.logs_watson` descrito no relatório | **Disponível** |
| IR ALÉM 2 — relatório técnico | [`ir-alem-2-automacao-rpa.md`](document/ir-alem-2-automacao-rpa.md) | **Disponível** |

<a id="como-funciona"></a>

## 💬 Como funciona

| Etapa | O que acontece |
|---:|---|
| **1. Relato** | O usuário descreve um sintoma em linguagem natural. |
| **2. Coleta** | O diálogo solicita intensidade e duração e mantém essas informações no contexto. |
| **3. Orientação** | O assistente apresenta um resumo educativo e ajuda a preparar a consulta. |

Sinais explícitos de alerta têm prioridade sobre o fluxo comum. Dor torácica intensa, falta de ar importante, suor frio ou desmaio acionam uma orientação clara para busca imediata de emergência ou contato com o SAMU 192 — sem inferir causa ou diagnóstico.

A ordem do diálogo é:

1. sinais explícitos de alerta;
2. coleta de sintoma, intensidade e duração;
3. resumo educativo e preparação para consulta;
4. limites, agradecimento e despedida;
5. fallback, sempre ao final.

<a id="arquitetura"></a>

## 🏗️ Arquitetura

```mermaid
flowchart LR
    U[Usuário] -->|mensagem| R[React + Vite]
    R -->|POST /api/chat| F[API Flask]
    F -->|API V1 · Classic/Lite| W[IBM Watson Assistant]
    W -->|texto + NLP| F
    F -->|resposta normalizada| R

    classDef user fill:#f3f4f6,stroke:#6b7280,color:#111827
    classDef app fill:#dff5f2,stroke:#0b706f,color:#064e4d
    classDef external fill:#e8efff,stroke:#2563eb,color:#1e3a8a
    class U user
    class R,F app
    class W external
```

O frontend nunca acessa o Watson diretamente. O backend atua como fronteira de segurança, lê credenciais somente de variáveis de ambiente e oferece compatibilidade com a API V1 da Dialog Skill em instâncias Classic/Lite e com a API V2 quando um ambiente compatível estiver disponível.

Na V1, o contexto é efêmero e mantido apenas na memória do processo por até 30 minutos, com limite de 500 conversas. Não há banco de dados nem persistência de conversas. As requisições ao Watson incluem opt-out de aprendizagem; ainda assim, a demonstração deve usar somente frases fictícias, sem nomes, documentos, prontuários ou outros dados pessoais.

O módulo do IR ALÉM 1 fica ao lado do gateway, em `src/backend/clinical_extractor.py`. A rota `POST /api/chat/clinical` estrutura a mensagem com o extrator antes de consultar o Watson: um nível `critical` recebe orientação de emergência imediata; nos demais casos o Watson responde e a extração é anexada em `clinical`. Sem `LLM_API_KEY`, o extrator roda em modo de simulação, então o fluxo principal nunca depende de um provedor de IA generativa.

<a id="api"></a>

## 🔌 API da aplicação

| Método | Rota | Finalidade |
|---|---|---|
| `GET` | `/api/health` | Informa a saúde da aplicação e a presença da configuração, sem expor segredos. |
| `POST` | `/api/chat` | Envia `message` e `conversationId`; devolve resposta, conversa, NLP e `urgent`. |
| `POST` | `/api/reset` | Encerra ou descarta a sessão e reinicia o contexto. |
| `POST` | `/api/extract` | IR ALÉM 1: recebe `text` (até 2.000 caracteres) e devolve `extraction` em JSON, `model` e `mode`. |
| `POST` | `/api/chat/clinical` | IR ALÉM 1: mesmo contrato de `/api/chat`, acrescido de `clinical` (extração) e `source` (`watson` ou `clinical`). |

Mensagens vazias ou maiores que 500 caracteres retornam `400`; configuração ausente retorna `503`; indisponibilidade do Watson retorna `502`. Uma sessão V2 expirada é recriada uma única vez. Em `/api/extract`, falha do modelo de linguagem retorna `502`; `/api/health` informa `clinical.mode` (`mock` ou `llm`), `clinical.provider` e `clinical.model`.

<details>
<summary><strong>Exemplo do contrato de chat</strong></summary>

Requisição:

```json
{
  "message": "Estou sentindo palpitação",
  "conversationId": null
}
```

Resposta normalizada:

```json
{
  "reply": "Qual é a intensidade de 0 a 10?",
  "conversationId": "identificador-da-conversa",
  "intent": "relatar_sintoma",
  "confidence": 0.92,
  "entities": [
    {
      "entity": "sintoma",
      "value": "palpitacao",
      "confidence": 0.95
    }
  ],
  "urgent": false
}
```

Os textos e níveis de confiança variam conforme a resposta do Watson; o exemplo apenas ilustra o formato da API.

</details>

<a id="estrutura"></a>

## 📁 Estrutura de pastas

Dentre os arquivos e pastas presentes na raiz do projeto, definem-se:

```text
.
├── .github/                  # arquivos de apoio à qualidade do repositório
├── assets/                   # marca e capturas de tela da documentação
├── config/
│   ├── SQL/                  # esquema PostgreSQL do fluxo RPA (IR ALÉM 2)
│   └── watson/               # export versionado da Dialog Skill
├── document/                 # relatório técnico e documentos do IR ALÉM 1 e do IR ALÉM 2
├── output/pdf/               # relatório técnico e documento do IR ALÉM 1 em PDF
├── scripts/                  # validação, preparação, demo do IR ALÉM 1 e geração de entregáveis
├── src/
│   ├── backend/              # API Flask, gateway do Watson, extrator clínico (IR ALÉM 1), simulador, robô RPA e webhook (IR ALÉM 2)
│   └── frontend/             # interface React/Vite
├── tests/backend/            # testes da API, gateway, export do Watson e extração clínica
├── .env.example              # modelo de configuração, sem credenciais
├── requirements.txt          # dependências Python
└── README.md                 # guia geral do projeto
```

<a id="configuracao"></a>

## ⚙️ Configuração do Watson Assistant

1. No IBM Cloud, use uma instância existente no plano Lite e crie um assistant chamado **CardioIA Acolhe**.
2. Crie uma **Dialog Skill** em português brasileiro.
3. Execute `python scripts/prepare_watson_upload.py` e importe o arquivo compacto gerado em `tmp/watson/cardioia-dialog-upload.json`.
4. Vincule a skill ao novo assistant sem alterar os assistentes já existentes.
5. Copie `.env.example` para `.env` e escolha o modo compatível com a instância:

| Modo | Variáveis obrigatórias |
|---|---|
| `v1` — Dialog Skill Classic/Lite | `WATSON_API_KEY`, `WATSON_URL`, `WATSON_WORKSPACE_ID` |
| `v2` — assistant + environment | `WATSON_API_KEY`, `WATSON_URL`, `WATSON_ASSISTANT_ID`, `WATSON_ENVIRONMENT_ID` |
| `auto` | Seleciona a configuração V2 completa; caso contrário, usa V1 se houver `WATSON_WORKSPACE_ID` |

6. Confirme no painel se as intents, entidades e a ordem dos nós foram importadas corretamente.

> [!CAUTION]
> Nunca compartilhe nem versione a API key. A configuração do IBM Cloud deve ser realizada com o responsável pelo projeto acompanhando. Não confirme upgrade, plano pago ou complemento faturável.

<a id="ir-alem-1"></a>

## 🧠 IR ALÉM 1 — extração clínica com IA generativa

O módulo [`src/backend/clinical_extractor.py`](src/backend/clinical_extractor.py) transforma um relato em texto livre em JSON estruturado usando uma API **Chat Completions** com **system prompt** (papel, regras e esquema), **few-shot** (quatro exemplos, um por nível de alerta), **chain-of-thought** (seis passos) e **JSON mode**, seguidos de validação de tipos e faixas. A explicação completa do fluxo está no [documento PDF](output/pdf/ir-alem-1-extracao-clinica.pdf) e na [fonte em Markdown](document/ir-alem-1-extracao-clinica.md).

| Modo | Como ativar | Uso |
|---|---|---|
| `mock` | Padrão, sem chave | Simulação determinística com o mesmo esquema; usada nos testes, no CI e na demo. |
| `llm` | `LLM_API_KEY` no `.env` (+ `LLM_BASE_URL` e `LLM_MODEL`) | Extração real com o modelo de linguagem do provedor configurado. |

O código fala o protocolo Chat Completions da OpenAI por meio do SDK `openai`, então **qualquer provedor compatível funciona sem alterar código** — basta trocar as variáveis do `.env`. O **Google Gemini foi usado apenas nos testes e nas evidências deste repositório**, por oferecer free tier sem cartão; não é um requisito do projeto. A execução real foi verificada em 14/09/2026 com `gemini-3.5-flash`: os quatro cenários da demo e as saídas JSON completas estão em [`document/ir-alem-1-evidencia-llm.json`](document/ir-alem-1-evidencia-llm.json) e no PDF.

| Provedor | `LLM_BASE_URL` | `LLM_MODEL` (exemplo) | Chave |
|---|---|---|---|
| Google Gemini (usado nos testes) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.5-flash` | [Google AI Studio](https://aistudio.google.com/apikey) — free tier (cerca de 20 requisições/dia por modelo; se esgotar, troque `LLM_MODEL`, por exemplo para `gemini-3.5-flash-lite`) |
| OpenAI | *(vazio)* | `gpt-4o-mini` | [platform.openai.com](https://platform.openai.com/api-keys) — pré-pago |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | [console.groq.com](https://console.groq.com/keys) — free tier |
| Ollama (local) | `http://localhost:11434/v1` | modelo baixado localmente | qualquer valor não vazio |

```powershell
python scripts/demo_clinical_extractor.py                    # quatro cenários fictícios no modo mock
python scripts/demo_clinical_extractor.py --real             # mesmo roteiro com o provedor do .env
python scripts/demo_clinical_extractor.py --real --list-models   # confere os nomes de modelo disponíveis
python scripts/demo_clinical_extractor.py --real --save document/ir-alem-1-evidencia-llm.json
python scripts/generate_ir_alem1_report.py                   # regenera o PDF (usa a evidência acima, se existir)
```

Exemplo de chamada com a API em execução:

```powershell
$body = @{ text = "Falta de ar ao subir escadas, uns 10 minutos" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/extract -ContentType "application/json" -Body $body
```

> [!NOTE]
> O extrator não diagnostica nem prescreve: apenas organiza o que foi relatado. A orientação de emergência (SAMU 192) é decidida pelo backend a partir do nível de alerta. Nenhum texto clínico, resposta do modelo ou credencial é registrado em log.

<a id="ir-alem-2"></a>

## 🤖 IR ALÉM 2 — automação inteligente com RPA, IA e dados híbridos

O IR ALÉM 2 simula um robô que **monitora dados clínicos estruturados**, **identifica anomalias com IA** e **registra alertas de forma rastreável**, combinando um banco relacional e um não relacional. O fluxo completo, as decisões de projeto e a estrutura dos bancos estão no [relatório técnico](document/ir-alem-2-automacao-rpa.md).

```mermaid
flowchart LR
    S[Simulador de entradas] -->|triagens e checkups| P[(PostgreSQL<br/>banco_clinico)]
    P -->|medições pendentes| R[Robô RPA + IsolationForest]
    R -->|anomalia, status e auditoria| P
    W[IBM Watson Assistant] -->|webhook de nó| H[API Flask /webhook]
    H -->|payload + data e hora| M[(MongoDB<br/>doctor_in.logs_watson)]

    classDef app fill:#dff5f2,stroke:#0b706f,color:#064e4d
    classDef data fill:#fff4e5,stroke:#b45309,color:#78350f
    classDef external fill:#e8efff,stroke:#2563eb,color:#1e3a8a
    class S,R,H app
    class P,M data
    class W external
```

| Componente | Arquivo | Papel |
|---|---|---|
| Simulador de entradas | [`src/backend/simulador.py`](src/backend/simulador.py) | A cada 5 s cria uma triagem (80% normal, 20% de risco) e a cada 30 s gera checkups dos pacientes admitidos, simulando a normalização dos sinais. |
| Robô RPA + IA | [`src/backend/rpa_ia.py`](src/backend/rpa_ia.py) | A cada 3 s lê as medições ainda não avaliadas, aplica `IsolationForest` e, diante de anomalia na triagem, admite o paciente e registra um alerta. |
| Webhook do Watson | [`src/backend/api_watson.py`](src/backend/api_watson.py) | Recebe o payload de um nó do Watson Assistant e grava o documento, com data e hora de recebimento, no MongoDB. |
| Esquema relacional | [`config/SQL/setup_banco.sql`](config/SQL/setup_banco.sql) | Tabelas `pacientes`, `medicoes` e `logs_auditoria`, com base inicial de normalidade. |

O paciente simulado percorre o ciclo **triado → admitido → alta**: a IA admite quem apresenta leitura anômala na triagem, e a alta ocorre após três checkups avaliados como normais.

| Requisito do enunciado | Como é atendido |
|---|---|
| Ler periodicamente dados clínicos em banco relacional | O robô consulta no PostgreSQL as medições com `anomalia_detectada` nula — pressão arterial, frequência cardíaca e adesão ao tratamento. |
| Banco não relacional para mensagens e metadados | O MongoDB (`doctor_in.logs_watson`) armazena os payloads enviados pelo Watson Assistant, sem esquema fixo. |
| Técnica de IA para identificar anomalias | `IsolationForest` (`contamination=0.15`, `random_state=42`) sobre os quatro sinais, usando o histórico normal como referência. |
| Alertas e eventos rastreáveis | `logs_auditoria` registra nível (`INFO`, `ALERTA`, `ALTA`), evento, paciente, medição de origem e data e hora de cada ação. |

<details>
<summary><strong>Como executar o IR ALÉM 2</strong></summary>

Pré-requisitos: Python 3.11+, PostgreSQL e MongoDB locais. O código se conecta a `postgresql://postgres:123@localhost/banco_clinico` e a `mongodb://localhost:27017/`.

```powershell
python -m pip install pandas sqlalchemy psycopg2-binary scikit-learn schedule pymongo flask

psql -U postgres -c "CREATE DATABASE banco_clinico;"
psql -U postgres -d banco_clinico -f config/SQL/setup_banco.sql

# Em terminais separados, na raiz do projeto
python src/backend/simulador.py     # triagens e checkups
python src/backend/rpa_ia.py        # robô RPA com detecção de anomalias
python src/backend/api_watson.py    # webhook em http://127.0.0.1:5000/webhook
```

O webhook usa a porta 5000, a mesma da API principal do assistente; execute-os em momentos diferentes. Para que o Watson Assistant o chame, configure no nó desejado um webhook `POST` para a URL pública do endpoint `/webhook`.
</details>

<a id="execucao"></a>

## 🔧 Como executar o código

### Pré-requisitos

- Git;
- Python 3.11 ou superior;
- Node.js 20.19+ ou 22.12+;
- pnpm 11.19 ou compatível;
- instância IBM Watson Assistant configurada para conversas reais.

Os comandos abaixo usam **PowerShell**.

### 1. Obtenha o projeto

```powershell
git clone https://github.com/Hinten/fiap2_fase5_cap1.git
Set-Location fiap2_fase5_cap1
```

### 2. Prepare o backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha o `.env` de acordo com o modo V1 ou V2 descrito acima (e, opcionalmente, o provedor de IA generativa da seção [IR ALÉM 1](#ir-alem-1)). Em seguida, inicie a API:

```powershell
python -m src.backend
```

O backend fica disponível em `http://127.0.0.1:5000`. Como alternativa, após criar a `.venv`, execute `./scripts/run-dev.ps1` para iniciar o Flask em modo de desenvolvimento.

### 3. Inicie o frontend

Em outro terminal, na raiz do projeto:

```powershell
pnpm --dir src/frontend install --frozen-lockfile
pnpm --dir src/frontend dev
```

A interface fica disponível em `http://127.0.0.1:5173` e encaminha as chamadas `/api` para o Flask.

### 4. Gere o build integrado

```powershell
pnpm --dir src/frontend build
python -m src.backend
```

Após o build, o Flask serve a interface e a API na mesma origem em `http://127.0.0.1:5000`.

<a id="qualidade"></a>

## ✅ Testes e qualidade

Na raiz do projeto, com o ambiente Python ativo e as dependências do frontend instaladas:

```powershell
python -m pytest
pnpm --dir src/frontend lint
pnpm --dir src/frontend build
```

Resultado local verificado em 13/09/2026: **42 testes aprovados com Python 3.14.0**, lint aprovado com ESLint 10.10.0 e build de produção aprovado com Vite 8.3.0. A suíte cobre o contrato da API, validações, contexto e sessões, normalização das respostas e estrutura da Dialog Skill. Em 14/09/2026, com o IR ALÉM 1, a suíte passou a **116 testes aprovados com Python 3.11.9**: 51 unitários do extrator (prompt, parsing, mock, provedores e caminho real com cliente falso) e 23 de integração das rotas `/api/extract` e `/api/chat/clinical`, todos sem rede e sem chave.

O smoke test real foi concluído em 13/09/2026 com uma instância IBM Watson Assistant Classic/Lite, Dialog Skill **CardioIA Acolhe** e API V1. A jornada React → Flask → Watson verificou explicitamente:

1. estado de carregamento (`loading`) durante a requisição;
2. envio da mensagem pelo botão;
3. envio da mensagem pela tecla Enter;
4. apresentação de erro seguro, sem HTML interpretado, credenciais, stack trace ou detalhes internos;
5. reset por **Nova conversa**, descartando o contexto anterior;
6. sinal de alerta com `urgent: true` e orientação de emergência;
7. exibição dos detalhes de NLP: intent, confiança e entidades;
8. fluxo normal em três turnos, preservando sintoma, intensidade (`@sys-number`) e duração até o resumo;
9. fallback para pergunta fora do escopo;
10. responsividade na viewport de 390 × 844 px.

Todos os cenários empregaram exclusivamente frases fictícias, sem dados pessoais.

<a id="historico"></a>

## 🗃 Histórico de lançamentos

- **0.3.0 — 15/09/2026**
  - IR ALÉM 2: simulador clínico, robô RPA com `IsolationForest`, PostgreSQL para dados clínicos e auditoria, webhook do Watson com MongoDB e relatório técnico.
  - Vídeo de demonstração publicado no [YouTube](https://www.youtube.com/watch?v=ynFGrxRVwWA).
- **0.2.0 — 14/09/2026**
  - IR ALÉM 1: extrator clínico com IA generativa (`clinical_extractor.py`), rotas `/api/extract` e `/api/chat/clinical`, modo de simulação sem chave, demo, 74 testes novos e documento PDF.
- **0.1.0 — 12/09/2026**
  - Primeira versão do assistente, da interface, dos testes automatizados e da documentação acadêmica.
  - Integração real com o IBM Watson Assistant V1 verificada em 13/09/2026.
  - Vídeo de demonstração mantido como pendência explícita.

<a id="licenca"></a>

## 📋 Licença

<p>
  <img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1" alt="Creative Commons" height="22">
  <img src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1" alt="Atribuição" height="22">
</p>

O **CardioIA Acolhe**, do Grupo 7 — FIAP, está licenciado sob a [Creative Commons Atribuição 4.0 Internacional](https://creativecommons.org/licenses/by/4.0/deed.pt-br) (**CC BY 4.0**).

---

<p align="center"><sub>Projeto acadêmico · FIAP · Fase 5, Capítulo 1</sub></p>
