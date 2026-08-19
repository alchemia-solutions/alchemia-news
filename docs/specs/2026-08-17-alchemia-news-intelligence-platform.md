# Spec: Alchemia News — plataforma de inteligência de notícias/artigos de CADD & AI Drug Discovery

**Setor:** alchemia-news (novo — décimo terceiro sub-agente da empresa, não é setor de negócio
tradicional, é infraestrutura de inteligência/monitoramento, mesma classe de `alchemia-brain`)
**Data:** 2026-08-17
**Status:** aprovado

## Propósito

A Alchemia Solutions (Alchemia LTDA) precisa de visibilidade contínua sobre o próprio nicho —
Computer-Aided Drug Design (CADD), AI Drug Discovery, engenharia de proteínas/anticorpos/vacinas —
para: (1) alimentar `alchemia-growth` com contexto real de mercado/concorrência, (2) alimentar
`alchemia-science`/`alchemia-athanor` com literatura nova relevante ao pipeline de curadoria, (3)
dar ao fundador um painel único, atualizado 3x/dia, do que está acontecendo no setor — sem
depender de checagem manual dispersa em múltiplas fontes. Hoje isso não existe em nenhum setor:
`alchemia-science` tem uma biblioteca Zotero curada manualmente (46 PDFs, ver
`alchemia-science/alchemia-library/`), mas nada monitora a web continuamente.

## Estado Atual

Setor inexistente até esta sessão — `alchemia-ai/alchemia-news/` foi criado vazio nesta mesma
conversa, a pedido explícito do fundador. Não há pipeline, não há dashboard, não há sub-agente.
Conectividade real testada nesta sessão (não presumida):

| Fonte | Acesso direto | Caminho real usado |
|---|---|---|
| PubMed (NCBI E-utils) | ✅ 200 | API E-utils direta (`esearch`/`efetch`) |
| bioRxiv | ✅ 200 | API pública `api.biorxiv.org/details/biorxiv/...` |
| arXiv | ✅ 200 | API `export.arxiv.org/api/query` (categoria q-bio) |
| ChemRxiv | ❌ 403 direto | **Proxy via Crossref** — DOIs ChemRxiv têm prefixo `10.26434` (Cambridge Open Engage), indexados no Crossref REST API, que responde 200 |
| SciELO | ❌ 403 direto (`search.scielo.org`) | **Proxy via Crossref** — DOIs SciELO Brasil têm prefixo `10.1590`, mesma técnica |
| Google News | ✅ 200 (RSS) | `news.google.com/rss/search?q=...` por termo de busca |
| Blogs de empresa (Anthropic/OpenAI/NVIDIA/DeepMind) | parcial — ver tabela de fontes no `companies.yaml` | RSS quando existe; fallback é o próprio agente ler a página e o fundador confirmar achados relevantes manualmente quando não há feed |
| Redes sociais (LinkedIn/X/Instagram das empresas) | Bloqueado nesta sessão (login automatizado exige permissão de depuração remota do Chrome, nunca concedida) | **Fora de escopo desta entrega, por decisão explícita do fundador nesta conversa** — revisitar depois. O fundador tem acesso às contas oficiais da Alchemia e pode fornecer credenciais numa rodada futura dedicada a isso. |

## Estado Alvo

Um pipeline Python determinístico (sem LLM na coleta — só filtragem por fonte/keyword, para nunca
fabricar relevância) que roda 3x/dia (manhã/tarde/noite) via cron, escreve dados normalizados em
`data/*.json`, e um dashboard Next.js real (App Router, TypeScript, Tailwind, na identidade visual
da Alchemia) com páginas separadas — Notícias, Artigos/Papers, Empresas, Bancos & Ferramentas,
Sobre — lendo esses JSONs em tempo de requisição (server components, `fs.readFileSync`), então
qualquer execução nova do pipeline aparece no dashboard sem rebuild. Camada de agente (Claude
Code) para curadoria/investigação mais profunda sob demanda, separada da coleta automática.

## Critérios de Sucesso

- `python pipeline/collectors/run_all.py` roda de ponta a ponta contra APIs reais (não mock) e
  produz `data/news.json`/`data/articles.json` com itens reais, datados, com URL/fonte/data de
  publicação — verificável abrindo o JSON e conferindo que as URLs resolvem.
- Deduplicação real: rodar o pipeline duas vezes seguidas não duplica itens (chave por URL/DOI
  normalizado), verificável comparando contagem antes/depois da segunda execução.
- `npm run build` do dashboard completa sem erro; `npm run dev` (ou `next start` após build) serve
  as 6 páginas (Home, Notícias, Artigos, Empresas, Bancos & Ferramentas, Sobre) e cada uma renderiza
  dados reais do `data/*.json` gerado pelo pipeline, não dados mockados no componente.
- Cron job criado e executado pelo menos uma vez com sucesso real (não só criado — disparado e
  confirmado com output real).
- Sub-agente `alchemia-news` + skill `news-intelligence-pipeline` seguem exatamente o formato dos
  12 sub-agentes/19 skills já existentes; `check_runtime_integrity.py` atualizado e passando com as
  contagens novas (13 agentes/20 skills).
- Filtro de relevância documentado e auditável: toda entrada carrega o termo/fonte que a trouxe,
  nunca uma classificação opaca.

## Arquitetura / Stack

- **Coleta:** Python 3.11 (mesmo runtime já usado no restante da empresa), `requests` (fallback
  `urllib` puro se `pip` não estiver disponível no ambiente-alvo — ver "Riscos" abaixo),
  `feedparser` para RSS quando disponível, senão parser XML manual via `xml.etree`. Sem
  dependência de banco de dados — armazenamento é arquivo JSON versionável, consistente com o
  princípio já usado em `alchemia-ai/alchemia-database` ("dado grande fora do controle de versão,
  referenciado por manifest").
- **Dashboard:** Next.js (App Router) + TypeScript + Tailwind CSS — mesmas versões majoritárias já
  validadas em `alchemia-ai/alchemia-database/website/frontend` (Next 16.x, React 19.x, Tailwind
  3.4.x), reaproveitando decisão já testada em vez de reabrir escolha de stack.
- **Orquestração:** `mcp__cronjob` (nível Hermes, fora do repositório) dispara o pipeline 3x/dia
  via `terminal`/script, modo `no_agent=True` (determinístico, sem custo de LLM, sem risco de
  alucinação numa tarefa que é ETL puro) — ver seção "Riscos" para o porquê desta escolha
  específica em vez de um agente LLM na coleta.

## Dependências

- **De outros setores:** nenhuma dependência de escrita. Leitura de referência: identidade visual
  de `alchemia-growth/branding/logos/` (read-only), convenções de `.claude/skills/realtime-dashboard/SKILL.md`
  e `.claude/skills/alchemia-spec-template/SKILL.md`. Nenhuma dependência do schema de
  `alchemia-database`/`alchemia-athanor` — este setor não toca dado molecular, só metadado de
  notícia/artigo.
- **De serviços externos:** PubMed E-utils, bioRxiv API, arXiv API, Crossref REST API (ChemRxiv +
  SciELO via prefixo DOI), Google News RSS, feeds RSS de empresas/institutos quando existirem. Sem
  chave de API obrigatória para nenhuma dessas (todas são endpoints públicos sem autenticação nesta
  configuração) — NCBI recomenda mas não exige `api_key`/`email` de contato educado (User-Agent
  identificável, rate limit respeitado).
- **De licenciamento:** este setor **não redistribui texto completo de artigo nenhum** — armazena
  só metadado público (título, autores, data, fonte, URL, resumo/snippet quando a própria API
  fornece um resumo curto como parte do metadado público, ex. abstract do PubMed). Nunca faz
  scraping de PDF pago ou paywall. Google News RSS entrega só título+snippet+link, nunca o
  conteúdo completo do artigo de terceiro — o dashboard sempre linka para a fonte original, nunca
  reproduz o artigo.

## Riscos e Efeitos de Segunda Ordem

1. **Licenciamento e proveniência:** metadado agregado de fontes públicas (PubMed/bioRxiv/arXiv são
   explicitamente abertos a esse uso; Crossref é um índice de metadado, não o texto do artigo).
   Risco real e monitorado: Google News RSS é uso não-oficial (Google não documenta um SLA público
   para esse endpoint) — tratado como "melhor esforço", com fallback silencioso (se cair, os
   outros coletores continuam) em vez de bloquear o pipeline inteiro.
2. **Governança de dados / LGPD:** nenhum dado pessoal é coletado — só metadado institucional de
   publicação científica/notícia corporativa. Nenhum formulário, nenhum e-mail de usuário. Se uma
   fase futura adicionar coleta de rede social (fora de escopo aqui, por decisão explícita do
   fundador nesta conversa), isso precisará de nova análise LGPD antes de implementar — sinalizado
   explicitamente, não presumido resolvido.
3. **Teto de hardware local:** irrelevante — nenhum estágio deste pipeline usa GPU; carga de CPU é
   trivial (requests HTTP + parsing de texto).
4. **Acoplamento entre setores:** nenhum hoje — setor novo, sem consumidor downstream ainda. Se
   `alchemia-growth` ou `alchemia-science` decidirem consumir `data/*.json` programaticamente no
   futuro, isso deve ser tratado como uma dependência nova, formalizada em spec própria daquele
   setor (mesma regra de "provedor confirma estabilidade do contrato antes do consumidor
   implementar" já em vigor para website/database).
5. **Falsa sensação de completude:** um agregador de notícias nunca é exaustivo — o dashboard deve
   deixar isso explícito (rodapé/Sobre: fontes cobertas, data da última coleta, limitações
   conhecidas), nunca alegar "todas as notícias" literalmente, ecoando a mesma disciplina
   anti-overclaiming já aplicada a `alchemia-growth`/`alchemia-database`.
6. **Ambiente de execução sem `pip`:** verificado nesta sessão que o Python pré-instalado no
   ambiente de automação (`hermes-agent/venv`) não tem `pip` funcional; um venv novo criado a
   partir dele tem `pip` normal. O script de setup deste setor deve criar seu próprio venv
   (`alchemia-ai/alchemia-news/pipeline/.venv`) em vez de presumir um ambiente compartilhado.

## Roadmap

1. **Fase 1 (esta entrega):** estrutura de diretório, spec, configs de fonte
   (`sources.yaml`/`companies.yaml`/`keywords.yaml`), coletores Python para PubMed/bioRxiv/arXiv/
   ChemRxiv-via-Crossref/SciELO-via-Crossref/Google News/feeds de empresa, dedupe, dashboard
   Next.js com as 5 páginas + Home, sub-agente + skill no harness, cron 3x/dia.
2. **Fase 2 (backlog):** camada de resumo/tradução assistida por IA (sob demanda, não na coleta
   automática) para artigos em inglês quando o fundador quiser um resumo em português; refinamento
   de relevância (hoje é keyword+fonte determinístico, pode evoluir para score ponderado).
3. **Fase 3 (backlog, explicitamente fora de escopo aqui por decisão do fundador nesta conversa):**
   redes sociais (LinkedIn/X/Instagram) das empresas de referência, usando as contas oficiais da
   Alchemia que o fundador disponibilizou — requer decisão de arquitetura própria (API oficial vs.
   automação de navegador) e nova análise de risco antes de implementar.

## Agente Responsável (Owner Agent)

`alchemia-news` (sub-agente novo, criado nesta mesma entrega — `.claude/agents/alchemia-news.md`).

## Portão de Revisão

`[x]` Revisado e aprovado pelo fundador em 2026-08-17 — pedido explícito e detalhado nesta
conversa (escopo completo de fontes, cadência 3x/dia, dashboard Next.js por página, harness a
seguir, decisão explícita de excluir redes sociais desta rodada tomada via pergunta direta antes
da implementação).
