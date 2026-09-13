# Registro de problemas e pendências

Este documento registra bloqueios, decisões e evidências que exigem acompanhamento humano antes da entrega do CardioIA Acolhe. Não inclua credenciais, mensagens clínicas reais ou dados pessoais.

## Estado atual

| Item | Estado | Ação necessária | Responsável |
|---|---|---|---|
| Configuração do IBM Watson Assistant | Pendente | Criar o terceiro assistant, importar a Dialog Skill e executar smoke test com o usuário acompanhando. | Equipe + usuário |
| Credenciais locais | Pendente | Preencher `.env` localmente; nunca enviar pelo chat ou versionar. | Usuário |
| PDF do relatório | Concluído | PDF A4 de 2 páginas gerado e ambas as páginas verificadas visualmente. | Equipe |
| Vídeo | Pendente | Gravar, publicar e inserir o link no README e no roteiro. | Usuário |
| Testes locais | Concluído | 42 testes Python, lint e build aprovados em 12/09/2026. | Equipe |
| Smoke test final | Pendente | Validar React → Flask → Watson após configurar a IBM. | Equipe + usuário |
| Avaliação independente | Pendente | Obter nota do subagente e aplicar feedback, até 10/10 ou três ciclos. | Equipe |

## Restrições confirmadas

- Usar somente o plano IBM Lite e não confirmar upgrades ou complementos pagos.
- Não alterar os dois assistants existentes na conta.
- Não armazenar dados reais nem registrar o texto das conversas.
- Não apresentar o protótipo como ferramenta de diagnóstico ou prescrição.
- Manter o repositório privado, conforme decisão do usuário, garantindo acesso prévio do avaliador.

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
