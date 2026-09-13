# CardioIA Acolhe

## Relatório técnico — Grupo 7

**FIAP — Fase 5, Capítulo 1**  
**Versão:** 0.1.0 — 13/09/2026

### 1. Objetivo

O CardioIA Acolhe é um protótipo acadêmico de assistente conversacional para acolhimento inicial e organização de relatos sobre sintomas cardiológicos. Seu objetivo é conduzir uma conversa curta, registrar no contexto o sintoma, a intensidade e a duração informados e devolver um resumo educativo que ajude o usuário a se preparar para conversar com um profissional de saúde. A solução não formula diagnósticos, não prescreve medicamentos, não estima prognósticos e não substitui atendimento médico.

O projeto também demonstra a integração entre uma interface web acessível, uma API própria e o processamento de linguagem natural do IBM Watson Assistant, sem uso de IA generativa. Por se tratar de uma demonstração, os testes devem empregar apenas frases fictícias, sem nomes, documentos, prontuários ou outros dados pessoais e sensíveis.

### 2. Arquitetura

A interface foi implementada em React com Vite. Ela apresenta o histórico da conversa, sugestões iniciais, envio por botão ou tecla Enter, estado de carregamento, mensagens de erro, botão de nova conversa, destaque visual para urgência e um painel de detalhes de NLP. A região de mensagens usa atualização anunciada por tecnologia assistiva e a navegação pode ser feita por teclado. A renderização padrão do React evita interpretar a resposta do chatbot como HTML.

O backend Flask atua como fronteira de segurança e adaptação. A integração real foi configurada em 13/09/2026 no IBM Watson Assistant Classic/Lite pela API V1. A rota `POST /api/chat` valida mensagens de 1 a 500 caracteres, conversa com a Dialog Skill e normaliza a resposta em `reply`, `conversationId`, `intent`, `confidence`, `entities` e `urgent`; o backend também preserva compatibilidade com a API V2 quando houver ambiente correspondente. Na V1, o contexto existe somente em memória por até 30 minutos, limitado a 500 conversas; não há persistência em banco. `POST /api/reset` descarta esse contexto ou encerra a sessão V2; `GET /api/health` expõe somente o estado, o modo e a presença da configuração. Credenciais ficam exclusivamente no `.env`, ignorado pelo Git, e textos clínicos não aparecem nos logs. Entradas inválidas retornam HTTP 400, configuração ausente retorna 503 e falha externa retorna 502.

```text
Usuário → React/Vite → Flask (/api) → IBM Watson Assistant
Usuário ← interface segura ← resposta normalizada ← Dialog Skill
```

### 3. Modelagem de linguagem e fluxo

A Dialog Skill **CardioIA Acolhe**, em português brasileiro, contém 14 nós de diálogo, sete intents (`saudacao`, `relatar_sintoma`, `sinal_alerta`, `preparar_consulta`, `limites_assistente`, `agradecimento` e `despedida`) e quatro entidades: `sintoma`, `intensidade`, `confirmacao` e a entidade de sistema `@sys-number`. Cada intent é treinada com no mínimo cinco exemplos variados. As variáveis `$sintoma`, `$intensidade` e `$duracao` preservam as informações necessárias entre os turnos.

A ordenação dos 14 nós é parte do requisito de segurança. O nó de alerta aparece antes do fluxo comum e considera tanto o sintoma do turno quanto o já preservado; dor no peito ou falta de ar com intensidade numérica a partir de 7/10 é tratada operacionalmente como intensa. Em seguida vêm coleta de sintoma, intensidade de 0 a 10, duração e resumo. Os nós de preparação para consulta, limites, agradecimento e despedida completam os caminhos auxiliares. O fallback é o último nó e oferece opções para retomar a conversa, em vez de inventar uma resposta.

Quando o usuário relata dor torácica intensa, falta de ar importante, suor frio ou desmaio, o assistente não tenta inferir a causa. Ele orienta a busca imediata por um serviço de emergência ou o contato com o SAMU 192. O indicador `urgent` permite que a interface apresente o aviso com maior destaque, sem alterar o conteúdo clínico determinado pelo diálogo.

### 4. Limites éticos e privacidade

O sistema adota o princípio de comunicação mínima: coleta apenas as informações fictícias necessárias ao fluxo e não possui banco de dados. Nenhuma conversa é apresentada como prontuário. As requisições enviam o cabeçalho de opt-out de aprendizagem da IBM; ainda assim, como políticas de retenção podem variar por plano, a demonstração deve usar exclusivamente frases fictícias e nunca informações identificáveis.

O atendimento de emergência segue referências públicas oficiais: o Ministério da Saúde lista dor ou desconforto no peito, falta de ar, suor frio e desmaio entre sinais que podem exigir atendimento imediato; o SAMU 192 é um serviço gratuito acionado pelo número 192. A aplicação apresenta orientação de acesso ao serviço, e não diagnóstico.

Embora o enunciado solicite um repositório público, o grupo adotou conscientemente a exceção de mantê-lo privado. O avaliador foi previamente convidado para acessar a entrega; não há compromisso de tornar o repositório público.

### 5. Testes e resultados

A qualidade foi verificada em quatro camadas. Testes estruturais examinaram o JSON exportado do Watson, o mínimo de exemplos por intent e a posição do alerta e do fallback. Testes Flask cobriram saúde, validação, múltiplos blocos de texto, normalização de NLP, configuração ausente, falha externa, expiração de sessão e reset. O frontend passou por lint e build. Por fim, em 13/09/2026, os smoke tests reais foram concluídos com aprovação das integrações Flask → Watson e React → Flask → Watson, usando IBM Watson Assistant Classic/Lite pela API V1.

| Evidência | Critério de aceitação | Registro final |
|---|---|---|
| Testes Python | Suíte concluída sem falhas | 42 testes aprovados em Python 3.14 |
| Lint e build React | Ambos com código de saída 0 | ESLint e build Vite 8.3 aprovados |
| IBM Watson | Serviço Classic/Lite e Dialog Skill disponíveis | API V1 configurada em 13/09/2026; 7 intents, 4 entidades e 14 nós |
| Smoke Flask → Watson | Chamada real processada pela Dialog Skill | Aprovado |
| Smoke React → Flask → Watson | Jornada completa funciona de ponta a ponta | Aprovado em 13/09/2026 |
| Vídeo | Roteiro com duração-alvo de 2min32s | PENDENTES a gravação e o link pelo usuário |

No smoke real da interface, foram verificadas explicitamente as seguintes evidências:

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

A integração real com o Watson está confirmada. A gravação e o link do vídeo permanecem pendentes como etapa separada da validação técnica.

### Referências

- IBM. [Watson Assistant: adding a dialog skill](https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-skill-dialog-add).
- IBM. [Watson Assistant APIs overview](https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-api-overview).
- IBM. [Security and privacy](https://cloud.ibm.com/docs/watson-assistant?topic=watson-assistant-admin-securing).
- Ministério da Saúde. [Infarto](https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/i/infarto).
- Ministério da Saúde. [SAMU 192](https://www.gov.br/saude/pt-br/composicao/saes/samu-192).
