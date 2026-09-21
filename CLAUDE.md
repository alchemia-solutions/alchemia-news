@AGENTS.md

## Nota Claude-específica

O import acima carrega `AGENTS.md` deste diretório — documento canônico e completo do setor
`alchemia-news`, lido por qualquer ferramenta que suporte o padrão aberto AGENTS.md (Claude Code,
Codex, Cursor, Cowork e 20+ outras). Este arquivo existe só para o que for genuinamente
Claude-específico.

**Sub-agente e skill deste setor (criados em 2026-08-17):**

- `.claude/agents/alchemia-news/alchemia-news.md` — sub-agente dono do setor. Desde 2026-08-20
  cada nó é uma **pasta** (`<nome>.md` + `SOUL.md` + `NODE.md`), não um `.md` plano — o caminho
  antigo `.claude/agents/alchemia-news.md` não existe mais.
- `.claude/skills/news-intelligence-pipeline/SKILL.md` — como rodar, depurar e estender o
  pipeline: disparar coleta, investigar coletor com 0 itens ou erro, adicionar empresa/termo/fonte
  nova, e reconciliar o dashboard com o cron 3x/dia.

Ambos vivem no harness canônico `alchemia-ai/alchemia-agents/.claude/`, com espelho byte-idêntico
em `.claude/` na raiz da empresa — **nunca neste diretório**. Em 2026-08-17, quando este parágrafo
foi escrito, as contagens do harness eram 13 sub-agentes / 20 skills.

**Nota histórica:** até a manhã de 2026-08-17 este arquivo registrava que o setor **não tinha**
sub-agente nem skill, apesar de a spec exigir os dois como Critério de Sucesso — as contagens reais
eram 12/19. Isso foi corrigido no mesmo dia.

**Cuidado com contagem — o próprio "13/20" acima já ficou velho.** Verificado ao vivo em
2026-08-31 (auditoria deste setor): o harness real é **15 sub-agentes / 24 skills** hoje (cresceu
com `alchemia-bots` em 2026-08-19, a reestruturação em pastas de 2026-08-20, `alchemia-frontend-gate`
em 2026-08-21 e `brand-system` em 2026-08-22/31). Não cite nenhum desses números de memória em
outro documento, nem o novo — os números do harness mudam quando um setor novo aparece. Confira
sempre com `ls .claude/agents/` ou rode `harness/check_runtime_integrity.py`.

**Correção/adição futura (regra alterada em 2026-09-18):** `AGENTS.md` passou a ser um **índice** com teto de 150 linhas / 12 KB — fato novo **não** entra nele. Registro datado vai para `docs/HISTORY.md` (append-only); estado vivo, para o `README.md` deste diretório e para o hub no `alchemia-brain`. O índice só muda quando um **ponteiro** muda. Nunca neste `CLAUDE.md`. Contrato: `alchemia-ai/alchemia-agents/docs/specs/2026-09-18-agents-md-index-contract.md`.