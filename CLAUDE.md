@AGENTS.md

## Nota Claude-específica

O import acima carrega o [`AGENTS.md`](AGENTS.md) deste diretório, o índice do Alchemia Radar, lido
por qualquer ferramenta que siga o padrão aberto AGENTS.md. Este arquivo guarda só o que é do
Claude Code:

- **Nó dono:** `alchemia-radar` (Kepler; até 2026-09-28, `alchemia-news`). É uma pasta no harness
  canônico, `alchemia-ai/ai-engineering/.claude/agents/alchemia-radar/` (`alchemia-radar.md` +
  `SOUL.md` + `NODE.md`), com espelho na raiz da empresa. **Nunca neste diretório.**
- **Skill:** `news-intelligence-pipeline`, canônica em `alchemia-ai/ai-engineering/.claude/skills/`.
- **`.claude/settings.json`** daqui é cópia do bloco `permissions` da empresa: o arquivo não herda de
  diretório ancestral.
- **`.mcp.json`** define o MCP do Supabase do Radar; **`.claude/settings.local.json`** o habilita,
  junto com `obsidian-alchemia-brain` e `hermes`. O `hermes` é resto do runtime dos bots, aposentado:
  removê-lo é decisão do fundador.
- **Abra a sessão na raiz da empresa**, não aqui: `memory: project` grava relativo ao diretório de
  trabalho, e uma sessão aberta aqui criaria `.claude/agent-memory/` fora da raiz.
- Contagem de nós e skills: rode `python alchemia-ai/ai-engineering/harness/check_runtime_integrity.py`;
  nunca a cite de memória.

**Correção/adição futura:** nada de conteúdo entra aqui. Registro datado vai para `docs/HISTORY.md`
(append-only); estado vivo, para o `README.md` e o hub no `alchemia-brain`; ponteiro novo, para o
`AGENTS.md`. O texto anterior deste arquivo está, verbatim, no addendum de 2026-09-28 do
`docs/HISTORY.md`.
