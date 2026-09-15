# CardioIA Acolhe — IR ALÉM 2

## Automação Inteligente com RPA, IA e Dados Híbridos — Grupo 7

**FIAP — Fase 5, Capítulo 1**  
**Data:** 15/09/2026

### 1. Objetivo

O IR ALÉM 2 expande o Assistente Cardiológico com um **fluxo de automação robótica de processos (RPA)** que monitora dados clínicos simulados, aplica **IA para detectar anomalias** e registra alertas de forma rastreável. A solução combina um **banco relacional (PostgreSQL)**, para os dados clínicos estruturados e a auditoria, com um **banco não relacional (MongoDB)**, para as mensagens e os metadados enviados pelo IBM Watson Assistant.

Todos os pacientes, medições e mensagens são fictícios. O fluxo não diagnostica nem prescreve: ele simula a organização operacional de uma unidade de atendimento.

### 2. Componentes

| Componente | Arquivo | Papel no fluxo |
|---|---|---|
| Simulador de entradas | [`src/backend/simulador.py`](../src/backend/simulador.py) | Gera triagens e checkups de leito com pressão arterial, frequência cardíaca e adesão ao tratamento. |
| Motor analítico (robô RPA + IA) | [`src/backend/rpa_ia.py`](../src/backend/rpa_ia.py) | Lê periodicamente as medições pendentes, aplica `IsolationForest`, atualiza o estado do paciente e registra alertas. |
| Webhook do Watson | [`src/backend/api_watson.py`](../src/backend/api_watson.py) | Recebe o payload enviado por um nó do Watson Assistant e o grava no MongoDB. |
| Esquema relacional | [`config/SQL/setup_banco.sql`](../config/SQL/setup_banco.sql) | Cria as tabelas `pacientes`, `medicoes` e `logs_auditoria` e a base inicial de normalidade. |

### 3. Arquitetura

```mermaid
flowchart LR
    S[Simulador de entradas] -->|triagens e checkups| P[(PostgreSQL<br/>banco_clinico)]
    P -->|medições pendentes| R[Robô RPA + IsolationForest]
    R -->|anomalia, status e auditoria| P
    W[IBM Watson Assistant] -->|webhook de nó| H[API Flask /webhook]
    H -->|payload + data e hora| M[(MongoDB<br/>doctor_in.logs_watson)]
```

Os processos são independentes e se comunicam pelo banco de dados: o simulador só escreve medições, o robô só avalia o que ainda não foi avaliado e o webhook só registra o que o Watson envia. Esse desacoplamento reproduz o cenário típico de RPA, em que o robô observa uma fonte de dados compartilhada e age sobre ela.

### 4. Fluxo automatizado

O paciente simulado percorre três estados:

```text
triado ──(anomalia detectada pela IA)──> admitido ──(3 checkups normais)──> alta
```

| Etapa | Periodicidade | O que acontece |
|---|---|---|
| **Triagem** | a cada 5 s (representa 5 min) | Cria um paciente `triado` e uma medição. Em 80% dos casos os sinais são normais (PAS 110–129, PAD 70–84, FC 60–85, adesão 0,80–1,00); em 20%, de risco (PAS 160–190, PAD 100–120, FC 110–130, adesão 0,10–0,40). Registra o evento `Triagem`. |
| **Análise pela IA** | a cada 3 s | O robô busca as medições com `anomalia_detectada IS NULL`, executa a detecção e grava `TRUE` ou `FALSE` em cada uma. Se a leitura anômala é de um paciente `triado`, o status passa para `admitido` e é registrado o evento `Admissão Hospitalar` com nível `ALERTA`. |
| **Checkup de leito** | a cada 30 s (representa 30 min) | Para cada paciente `admitido`, gera uma nova medição que simula o efeito da medicação, reduzindo gradualmente os sinais em direção a 120×80 mmHg e 75 bpm, com adesão 1,0. Cada checkup avaliado como normal incrementa `checkups_normais`. Registra o evento `Checkup`. |
| **Alta** | no checkup | Com três checkups normais, o paciente recebe `alta` e é registrado o evento `Expurgo` com nível `ALTA`. |

### 5. Banco relacional — PostgreSQL

Banco `banco_clinico`, criado por `config/SQL/setup_banco.sql`.

```mermaid
erDiagram
    pacientes ||--o{ medicoes : possui
    pacientes {
        SERIAL id PK
        VARCHAR status "triado | admitido | alta"
        INT checkups_normais
    }
    medicoes {
        SERIAL id PK
        INT paciente_id FK
        INT pressao_sistolica
        INT pressao_diastolica
        INT frequencia_cardiaca
        DECIMAL adesao_tratamento
        BOOLEAN anomalia_detectada "NULL = pendente"
        TIMESTAMP data_registro
    }
    logs_auditoria {
        SERIAL id PK
        VARCHAR nivel_log
        VARCHAR evento
        TEXT detalhes
        TIMESTAMP data_hora
    }
```

| Tabela | Responsabilidade |
|---|---|
| `pacientes` | Identificador técnico, estado no fluxo clínico e contador de checkups normais. |
| `medicoes` | Sinais vitais e adesão de cada coleta, ligados ao paciente. A coluna `anomalia_detectada` funciona também como fila: `NULL` indica medição ainda não avaliada pelo robô. |
| `logs_auditoria` | Trilha de auditoria com nível, evento, detalhes e data e hora de cada ação do simulador e do robô. |

O script insere três pacientes e três medições normais, que dão à IA um parâmetro inicial de normalidade.

### 6. Banco não relacional — MongoDB

Banco `doctor_in`, coleção `logs_watson`. Cada chamada do webhook grava **um documento** com o JSON recebido do Watson Assistant, acrescido do campo `data_hora_recebimento` (UTC), gerado pelo servidor para rastreabilidade.

O conteúdo do payload é definido na configuração do webhook no nó do Watson e pode variar entre nós sem alteração de esquema — motivo da escolha de um banco orientado a documentos. Exemplo ilustrativo, com dados fictícios:

```json
{
  "_id": "ObjectId gerado pelo MongoDB",
  "conversation_id": "id-da-conversa",
  "evento": "triagem_concluida",
  "sintoma": "palpitacao",
  "intensidade": 4,
  "duracao": "20 minutos",
  "urgente": false,
  "data_hora_recebimento": "2026-09-14T20:30:00Z"
}
```

### 7. Técnica de IA — Isolation Forest

| Aspecto | Decisão |
|---|---|
| Algoritmo | `sklearn.ensemble.IsolationForest`, detecção de anomalias **não supervisionada**: não exige medições rotuladas. |
| Atributos | `pressao_sistolica`, `pressao_diastolica`, `frequencia_cardiaca` e `adesao_tratamento`. |
| Dados de ajuste | Até 50 medições históricas já classificadas como normais, somadas às medições pendentes do ciclo. |
| Parâmetros | `contamination=0.15` (proporção esperada de anomalias) e `random_state=42` (resultados reproduzíveis). |
| Saída | `predict` devolve `-1` para anomalia e `1` para leitura normal; o valor é convertido em `TRUE`/`FALSE` na coluna `anomalia_detectada`. |

O Isolation Forest isola pontos com poucas partições aleatórias: leituras muito distantes do padrão histórico — pressão elevada, taquicardia e baixa adesão ao mesmo tempo — são separadas rapidamente e recebem o rótulo de anomalia. O histórico normal funciona como referência do que é esperado.

### 8. Alertas e rastreabilidade

| Nível | Evento | Origem | Exemplo de detalhe |
|---|---|---|---|
| `INFO` | `Triagem` | Simulador | nova coleta de dados realizada. Paciente ID 12 com status triado (PA: 172x108, FC: 118) |
| `ALERTA` | `Admissão Hospitalar` | Robô RPA | ALERTA CRÍTICO: Paciente ID 12 com status admitido na auditoria após triagem alterada (Leitura ID: 15) |
| `INFO` | `Checkup` | Simulador | nova coleta de dados realizada. Checkup do Paciente ID 12 com status admitido (PA: 160x100, FC: 108). |
| `ALTA` | `Expurgo` | Simulador | nova coleta de dados realizada (Saída). Paciente ID 12 com status ALTA após estabilidade clínica. |

Cada registro traz data e hora, o identificador do paciente e, no alerta, o identificador da medição que o originou. Assim é possível reconstruir a história completa de um paciente simulado: consultar suas medições em `medicoes`, a decisão da IA em `anomalia_detectada` e cada ação correspondente em `logs_auditoria`. O robô também imprime os alertas no console durante a execução.

```sql
-- Trilha de um paciente: medições avaliadas e eventos de auditoria
SELECT id, pressao_sistolica, pressao_diastolica, frequencia_cardiaca,
       adesao_tratamento, anomalia_detectada, data_registro
FROM medicoes WHERE paciente_id = 12 ORDER BY data_registro;

SELECT nivel_log, evento, detalhes, data_hora
FROM logs_auditoria WHERE detalhes LIKE '%Paciente ID 12 %' ORDER BY data_hora;
```

### 9. Decisões de projeto

| Decisão | Justificativa |
|---|---|
| PostgreSQL para dados clínicos | Medições têm estrutura fixa e relacionamento explícito com o paciente; chaves estrangeiras e SQL facilitam consultas e auditoria. |
| MongoDB para mensagens do Watson | Os payloads dos nós do assistente são semiestruturados e podem mudar sem migração de esquema. |
| Coluna `anomalia_detectada` como fila | Dispensa uma fila externa: o robô processa somente o que ainda está `NULL` e cada medição é avaliada uma única vez. |
| Isolation Forest | Técnica simples vista em aula, adequada a dados sem rótulo e com poucos atributos numéricos. |
| Histórico normal como contexto | Garante uma referência de normalidade mesmo quando o ciclo tem poucas medições novas. |
| Processos separados com `schedule` | Simulador, robô e webhook evoluem e executam de forma independente, integrados apenas pelos bancos. |
| Regra de alta com três checkups normais | Critério objetivo e auditável para encerrar o ciclo do paciente simulado. |

### 10. Integração entre RPA, IA e dados

1. O **simulador** grava a medição no PostgreSQL com `anomalia_detectada` vazia e registra a triagem.
2. O **robô** percebe a medição pendente no ciclo seguinte, sem intervenção humana.
3. A **IA** compara a medição com o histórico normal e decide se é anômala.
4. O **robô** grava a decisão, altera o status do paciente quando necessário e registra o alerta.
5. O **simulador** passa a gerar checkups para o paciente admitido; cada checkup volta ao passo 2 até a alta.
6. Em paralelo, o **Watson Assistant** envia pelo webhook as mensagens e os metadados da conversa, preservados no **MongoDB**.

### 11. Como executar

Pré-requisitos: Python 3.11+, PostgreSQL e MongoDB locais. O código se conecta a `postgresql://postgres:123@localhost/banco_clinico` e a `mongodb://localhost:27017/`.

```powershell
python -m pip install pandas sqlalchemy psycopg2-binary scikit-learn schedule pymongo flask

# Cria o banco e o esquema relacional
psql -U postgres -c "CREATE DATABASE banco_clinico;"
psql -U postgres -d banco_clinico -f config/SQL/setup_banco.sql

# Em terminais separados, na raiz do projeto
python src/backend/simulador.py     # gera triagens e checkups
python src/backend/rpa_ia.py        # robô RPA com detecção de anomalias
python src/backend/api_watson.py    # webhook em http://127.0.0.1:5000/webhook
```

O webhook usa a porta 5000, a mesma da API principal do assistente; execute-os em momentos diferentes. Para receber chamadas do Watson Assistant, configure no nó desejado um webhook `POST` apontando para a URL pública do endpoint `/webhook` (por exemplo, por meio de um túnel HTTPS).

### Referências

- scikit-learn — [IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).
- Liu, F. T.; Ting, K. M.; Zhou, Z.-H. (2008). *Isolation Forest*. IEEE International Conference on Data Mining.
- PostgreSQL — [Documentation](https://www.postgresql.org/docs/).
- MongoDB — [PyMongo Documentation](https://pymongo.readthedocs.io/).
- IBM — [Making a programmatic call from dialog](https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-dialog-webhooks).
