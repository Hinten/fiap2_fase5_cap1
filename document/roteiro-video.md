# Roteiro de vídeo — CardioIA Acolhe

**Duração-alvo:** 2min35s (faixa aceita: 2min20s a 2min50s)  
**Link do vídeo:** **PENDENTE — inserir pelo usuário após a gravação.**

> Use apenas dados fictícios durante a demonstração. Deixe o navegador com zoom legível, feche notificações e confirme que nenhuma credencial ou arquivo `.env` está visível.

## 0:00–0:18 — Abertura e problema

**Tela:** título da aplicação e aviso educacional.

**Fala:**

“Olá! Somos o Grupo 7 da FIAP e este é o CardioIA Acolhe. Criamos um assistente educativo para organizar relatos de sintomas cardiológicos antes de uma conversa com um profissional. Ele não diagnostica, não prescreve e não substitui atendimento médico.”

## 0:18–0:37 — Arquitetura

**Tela:** diagrama do README e, rapidamente, a estrutura do repositório.

**Fala:**

“A interface responsiva foi feita com React e Vite. O backend Flask valida as entradas, protege as credenciais e gerencia a sessão. O entendimento da linguagem e o fluxo determinístico ficam em uma Dialog Skill do IBM Watson Assistant. O repositório também inclui o export da skill, testes e documentação.”

## 0:37–1:13 — Fluxo normal em três turnos

**Tela:** interface do chat.

**Ações:**

1. Envie: `Estou sentindo palpitação.`
2. Responda à intensidade: `4`.
3. Responda à duração: `Há cerca de 20 minutos.`
4. Mostre o resumo retornado.

**Fala:**

“Em um fluxo comum, o Watson reconhece o relato e o sistema coleta apenas três informações: sintoma, intensidade de zero a dez e duração. Essas respostas permanecem no contexto da conversa. Ao final, recebemos um resumo estruturado e uma orientação educativa para preparar a consulta.”

## 1:13–1:35 — Alerta prioritário

**Tela:** clique em “Nova conversa” e envie a frase abaixo.

**Ação:** envie `Estou com dor forte no peito, falta de ar e suor frio.`

**Fala:**

“Os sinais explícitos de alerta têm prioridade sobre os demais nós. Nesse exemplo, o assistente não sugere uma causa: orienta a busca imediata por emergência ou o contato com o SAMU 192, e a interface destaca a resposta como urgente.”

## 1:35–1:52 — Fallback e limites

**Tela:** nova conversa e pergunta fora do escopo.

**Ação:** envie `Qual é a previsão do tempo?`

**Fala:**

“Quando a pergunta foge do escopo, o fallback é acionado por último. Em vez de inventar uma resposta, ele explica como o CardioIA pode ajudar e oferece caminhos para retomar o atendimento.”

## 1:52–2:12 — Detalhes de NLP e interface

**Tela:** abra “Detalhes NLP”, mostre intent, confiança e entidades; depois reduza a largura do navegador.

**Fala:**

“Para tornar o funcionamento verificável, este painel exibe a intent, a confiança e as entidades devolvidas pelo Watson. A interface também possui histórico, sugestões, carregamento, tratamento de erros, reinício de sessão, navegação por teclado e adaptação para telas menores.”

## 2:12–2:32 — Testes e encerramento

**Tela:** terminal com os testes concluídos; README aberto na seção de estrutura.

**Fala:**

“Validamos a estrutura do Watson, a prioridade do alerta, o fallback e os contratos da API, incluindo entradas inválidas, falhas externas, expiração e reset. Também executamos lint e build do React e um smoke test real de ponta a ponta. O código, o relatório e as instruções de reprodução estão no repositório. Obrigado!”

## Checklist antes de publicar

- [ ] O vídeo tem entre 2min20s e 2min50s.
- [ ] Nenhuma chave, `.env`, e-mail, notificação ou dado pessoal aparece na gravação.
- [ ] Os três cenários usam exatamente dados fictícios.
- [ ] A fala sobre testes corresponde aos resultados efetivamente mostrados.
- [ ] O link permite acesso ao avaliador sem solicitar permissão adicional.
- [ ] O link foi inserido neste arquivo e no `README.md`.
