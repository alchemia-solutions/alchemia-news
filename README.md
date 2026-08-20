# Alchemia News

Plataforma interna de inteligência de notícias, literatura científica e captação de recursos do
nicho da **Alchemia Solutions** — Computer-Aided Drug Design (CADD), AI Drug Discovery, engenharia
de proteínas/anticorpos/vacinas. Pipeline de coleta 100% determinístico (zero LLM) + dashboard
privado (Next.js), com editais de fomento e programas corporativos curados para o perfil da
empresa, e uma newsletter diária publicada no Discord.

**Repositório privado.** Uso interno da Alchemia LTDA — acesso ao app publicado é restrito à
diretoria (ver "Deploy e acesso" abaixo).

---

## O que este repositório contém

| Diretório | O que é |
|---|---|
| `pipeline/` | Coleta determinística em Python (9 execuções de coletor, 8 arquivos), configuração viva em YAML, sincronização com Supabase e integração com `alchemia-science`. |
| `dashboard/` | App Next.js (App Router) que serve o painel — notícias, artigos, empresas, editais de fomento, programas corporativos, newsletter e bancos/ferramentas de referência. |
| `supabase/migrations/` | Schema SQL do banco Supabase, aplicado automaticamente via integração GitHub↔Supabase a cada `git push` para `main`. |
| `docs/specs/` | Specs aprovadas do setor (formato spec-driven da empresa — Propósito → Estado Atual → Estado Alvo → Critérios de Sucesso → Riscos → Roadmap). |
| `docs/qc/` | Relatórios de revisão de qualidade de código. |
| `AGENTS.md` | Documento canônico de contexto deste setor — histórico completo, decisões de arquitetura e addenda datados. Leia antes de mexer em qualquer coisa. |

---

## Pipeline de coleta

Nove execuções de coletor (8 arquivos — `feed_collector.py` roda duas vezes, para feeds temáticos
e para newsletters do nicho), todas sem LLM: relevância é **keyword + fonte, determinística**, e
todo item carrega o termo que o trouxe (`keywords_matched`) — nunca uma classificação opaca.

| Coletor | Fonte |
|---|---|
| `pubmed` | PubMed (NCBI E-utils) |
| `biorxiv` | bioRxiv/medRxiv |
| `arxiv` | arXiv (categorias q-bio) |
| `chemrxiv` | ChemRxiv, via proxy Crossref (acesso direto responde 403) |
| `scielo` | SciELO Brasil, via proxy Crossref (acesso direto responde 403) |
| `nature` | Feeds Nature (Reviews Drug Discovery e correlatos) |
| `newsletters` | Newsletters curadas do nicho (Drug Hunter, Longevity.Technology, etc.) |
| `googlenews` | Google News RSS (não-oficial, melhor esforço) |
| `companies` | ~20 empresas de referência monitoradas (RSS oficial ou fallback Google News) |

Roda 3x/dia via Windows Task Scheduler (`alchemia-ai/alchemia-bots/scripts/run_alchemia_news.cmd`),
em três etapas:

1. **Coleta** (`python -m pipeline.run_all`) — grava `pipeline/data/{articles,news,companies_activity}.json` + `meta.json`.
2. **Radar do dia** (`python -m pipeline.research_export`) — gera o resumo diário em `alchemia-science/research/` e, quando a abertura é confirmada por arXiv/bioRxiv/Unpaywall/Europe PMC na própria execução, baixa o PDF em texto completo para `alchemia-science/alchemia-library/`.
3. **Sincronização com Supabase** (`python -m pipeline.sync_supabase`) — espelha `articles.json`/`news.json` na tabela `items` (ver "Banco de dados" abaixo). Opcional: sem credencial configurada, esta etapa é pulada sem quebrar a cadeia.

Estado real mais recente (não estimado — `pipeline/data/meta.json`): **312 artigos, 1.972
notícias, 1.095 menções de empresa**, catálogo de referência em `pipeline/config/resources.yaml`
(9 entradas) e `pipeline/config/companies.yaml` (20 empresas).

### Rodar localmente

```bash
cd pipeline
python -m pip install -r requirements.txt
python -m pipeline.run_all                    # coleta completa
python -m pipeline.run_all --skip companies,scielo   # pular coletores específicos
python -m pipeline.run_all --biorxiv-days 180 # backfill mais profundo (caro, sob demanda)
```

---

## Editais de fomento e programas corporativos

Dois catálogos estáticos, curados manualmente a partir de dois guias de referência do fundador —
**não são coletados**, não usam LLM. Cada entrada cita a fonte (`source_guide`) e a data da última
revisão (`last_reviewed`).

- `pipeline/config/funding_channels.yaml` — 28 canais de fomento público (federal, estadual SP,
  saúde, universidades/ICTs, fundações privadas, internacional): CNPq, FINEP, FAPESP, CAPES,
  EMBRAPII, BNDES, Ministério da Saúde, PROADI-SUS, Horizon Europe, NIH, entre outros.
- `pipeline/config/corporate_programs.yaml` — 24 programas corporativos para startups (créditos de
  nuvem, aceleradoras, parques/habitats nacionais, hubs corporativos): Google for Startups, AWS
  Activate, Microsoft Founders Hub, NVIDIA Inception, CNPEM, SUPERA, Eretz.bio, Cubo Itaú,
  InovAtiva Brasil, entre outros.

Cada entrada tem `priority_alchemia` (`alta`/`media`/`complementar`), herdada diretamente da
priorização que os próprios guias já fazem para o perfil de biotech/CADD/oncologia molecular da
empresa — nunca uma prioridade inventada pelo pipeline. Servidos no dashboard em `/fomento` e
`/programas`, com filtro, checklist de documentos e tracker de status (persistidos no navegador).

**Limitação conhecida:** os dois catálogos são um retrato do momento da curadoria — não há hoje
monitoramento automático de "chamada aberta agora". Confirmar sempre no portal oficial antes de
qualquer decisão de submissão.

---

## Newsletter

A partir de 2026-08-19, o anúncio no Discord (bot **Axel**, mascote axolote) deixou de ser só
título+fonte+link e virou uma newsletter completa: resumo estruturado de cada achado do dia
(baseado só no dado coletado, nunca inventado) mais uma leitura interpretativa separada e rotulada
("💡 Insight Alchemia" — possibilidades de atuação da Alchemia, sempre condicional, nunca
apresentada como fato). Publicada 3x/dia:

- **Documento completo** — `pipeline/data/newsletter/AAAA-MM-DD.md`, servido pelo dashboard em `/newsletter`.
- **Mensagem condensada no Discord** — 3-5 destaques + link para a newsletter completa, dentro do limite de 2.000 caracteres.

Prompt versionado (guardrails completas: nunca inventar fato/número, nunca citar bastidor interno,
nunca prometer data, anti-overclaiming): `alchemia-ai/alchemia-bots/cron/axel-newsletter-prompt.md`
— é cópia byte-a-byte do que roda na Tarefa Agendada real.

---

## Dashboard

Next.js **16** (App Router) + React **19** + Tailwind + TypeScript, lendo a maior parte do dado em
tempo de requisição (server components) — qualquer coleta nova aparece sem rebuild.

| Rota | Conteúdo |
|---|---|
| `/` | Painel — estatísticas, mix recente, status por coletor |
| `/noticias` | Notícias, filtro por fonte |
| `/artigos` | Artigos e preprints, filtro por fonte |
| `/empresas` + `/empresas/[slug]` | Atividade por empresa monitorada |
| `/fomento` | Editais de fomento público |
| `/programas` | Programas corporativos para startups |
| `/newsletter` | Newsletter mais recente (somente leitura) |
| `/bancos-ferramentas` | Bancos de moléculas e ferramentas de referência |
| `/sobre` | Escopo, fontes cobertas, limitações conhecidas |

### Rodar localmente

```bash
cd dashboard
npm install
cp .env.local.example .env.local   # preencha com os valores reais do Supabase
npm run dev                         # http://localhost:3000, sem gate de acesso
npm run build && npm run start      # simula produção (gate de acesso ativo, ver abaixo)
```

---

## Banco de dados (Supabase)

Desde 2026-08-20, **artigos e notícias** passaram a ser lidos direto de um Postgres gerenciado
(Supabase) — não mais só do arquivo local. Isso elimina a espera de redeploy para o site refletir
uma coleta nova: o pipeline sincroniza logo após coletar, e o dashboard lê em tempo de requisição.

- **Escrita:** `pipeline/sync_supabase.py`, via API REST do Supabase (upsert em lote, chave
  `dedupe_key`) — não adiciona nenhum driver de banco novo ao pipeline.
- **Leitura:** `dashboard/lib/supabase.ts`, via `@supabase/supabase-js`, chave `anon`/`publishable`
  (pública por design, acesso restrito a leitura por Row Level Security).
- **Escopo atual:** só a tabela `items` (`kind: 'article'|'news'`). Empresas, editais, programas e
  newsletter continuam em arquivo — os JSONs locais nunca deixaram de ser gerados, o Supabase é
  espelho, não substituição.
- **Schema:** `supabase/migrations/` — aplicado automaticamente pela integração GitHub↔Supabase a
  cada `git push` para `main`. Nunca editado direto pelo painel do Supabase.

### Variáveis de ambiente necessárias

Nenhum valor real vive neste repositório — só os nomes, aqui e em `.env.local.example`:

| Variável | Onde | Segredo? |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `dashboard/.env.local` (local) e Vercel (produção) | Não — URL pública do projeto |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | idem | Não — só permite `SELECT`, protegida por RLS |
| `SUPABASE_SERVICE_ROLE_KEY` | Variável de ambiente de **usuário do Windows** na máquina que roda o pipeline | **Sim** — nunca em arquivo, nunca commitada, nunca em nenhuma tarefa agendada em texto claro |

---

## Deploy e acesso

Deploy privado na Vercel, restrito à diretoria da Alchemia. Dois mecanismos independentes:

1. **Repositório privado no GitHub** (`alchemia-solutions/alchemia-news`) — controla quem vê o
   código-fonte e o dado já coletado.
2. **Gate de acesso no próprio app** (`dashboard/proxy.ts`) — Basic Auth (usuário/senha definidos
   como `SITE_AUTH_USER`/`SITE_AUTH_PASSWORD` no painel da Vercel), ativo sempre que
   `NODE_ENV=production` (ou seja, em qualquer build de produção, não só na Vercel — e nunca em
   `npm run dev` local). **Falha fechada por design:** sem essas duas variáveis configuradas, o
   site fica bloqueado para todo mundo até serem definidas.

**Configuração do projeto na Vercel:**
- Root Directory: `dashboard`
- Framework Preset: Next.js (auto-detectado)
- Build/Install Command: default (já definidos em `dashboard/vercel.json`)
- Environment Variables: `SITE_AUTH_USER`, `SITE_AUTH_PASSWORD`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

Qualquer `git push` para `main` (código ou só dado) dispara redeploy automático — não é necessário
nenhum Deploy Hook adicional.

---

## Licenciamento e LGPD

- **Só metadado público é armazenado** — título, autores, data, fonte, URL, resumo curto quando a
  própria API o entrega. Nunca redistribui texto completo de artigo de terceiro fora do que
  arXiv/bioRxiv/Unpaywall/Europe PMC confirmam como open access.
- **Nenhum dado pessoal é coletado.** Sem formulário, sem e-mail de usuário — LGPD não é acionada
  na configuração atual.
- **Redes sociais estão fora de escopo** por decisão explícita do fundador — exigiria nova análise
  LGPD antes de qualquer implementação.

## Convenções deste setor

- **Spec-driven:** nenhuma mudança de arquitetura relevante começa sem uma spec aprovada em
  `docs/specs/`, seguindo o Portão de Revisão explícito do fundador.
- **`AGENTS.md` é append-only e é a fonte de verdade** — histórico completo de decisões, achados e
  correções, cada um datado. Leia antes de presumir qualquer coisa sobre o estado deste setor.
- **Nunca fabricar número.** Toda contagem citada em código, documentação ou no dashboard vem de
  leitura real do dado, nunca de estimativa.

---

*Alchemia Solutions — inteligência de mercado interna. Não redistribuir fora da empresa sem
autorização do fundador.*
