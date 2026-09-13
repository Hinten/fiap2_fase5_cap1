# Registro de problemas e pendências

Este documento registra bloqueios, decisões e evidências que exigem acompanhamento humano antes da entrega do CardioIA Acolhe. Não inclua credenciais, mensagens clínicas reais ou dados pessoais.

## Estado atual

| Item | Estado | Ação necessária | Responsável |
|---|---|---|---|
| Configuração do IBM Watson Assistant | Concluído | Assistant **CardioIA Acolhe** e Dialog Skill configurados no IBM Watson Assistant Classic/Lite; integração pela API V1 validada em 13/09/2026. | Equipe |
| Credenciais locais | Concluído | Credenciais usadas somente no ambiente local de validação, sem envio pelo chat ou versionamento. | Usuário |
| PDF do relatório | Concluído | PDF A4 de 2 páginas gerado e ambas as páginas verificadas visualmente. | Equipe |
| Vídeo | Pendente | Gravar, publicar e inserir o link no README e no roteiro. | Usuário |
| Testes locais | Concluído | 42 testes Python, lint e build aprovados em 13/09/2026. | Equipe |
| Smoke test final | Concluído | Jornada real React → Flask → Watson aprovada em 13/09/2026: `loading`, envio por botão e Enter, erro seguro, reset, alerta com `urgent`, detalhes de NLP, fluxo normal em 3 turnos, fallback e viewport 390 × 844. | Equipe |
| Avaliação independente | Em andamento | Avaliação 1 concluída e achados documentais incorporados nesta revisão; repetir a avaliação até 10/10 ou três ciclos. | Equipe |

## Restrições confirmadas

- Usar somente o plano IBM Lite e não confirmar upgrades ou complementos pagos.
- Não alterar os dois assistants existentes na conta.
- Não armazenar dados reais nem registrar o texto das conversas.
- Não apresentar o protótipo como ferramenta de diagnóstico ou prescrição.
- Manter o repositório privado como exceção consciente ao enunciado; o avaliador foi previamente convidado e não há compromisso de tornar o repositório público.

## Modelo de ocorrência

Copie este bloco para cada problema identificado:

```markdown
### [AAAA-MM-DD] Título curto

- Etapa:
- Sintoma observado:
- Resultado esperado:
- Evidência sem dados sensíveis:
- Causa identificada:
- Decisão/correção:
- Validação posterior:
- Estado: aberto | resolvido | aceito
```

## Critério para encerrar as pendências

Todos os itens da tabela devem estar concluídos, os links devem estar acessíveis ao avaliador e nenhuma evidência pode expor segredos ou dados pessoais. O push final só deve ocorrer depois de testes aprovados e nota 10/10 na avaliação independente.
