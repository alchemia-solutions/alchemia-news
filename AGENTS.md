# AGENTS.md — alchemia-news

Documento canônico deste setor, criado em **2026-08-17**. Padrão aberto `AGENTS.md` (lido
nativamente por Claude Code, Codex, Cursor e 20+ ferramentas — ver
`alchemia-ai/alchemia-agents/docs/specs/2026-08-12-harness-world-standard.md`). `CLAUDE.md` deste
diretório importa este arquivo via `@AGENTS.md` e nunca duplica conteúdo.

**Nota de origem:** este arquivo não existia até hoje, apesar de o setor já ter pipeline rodando e
dashboard construído — o próprio `.gitignore` deste repositório já referenciava "ver AGENTS.md
deste setor" numa linha de comentário, apontando para um arquivo inexistente. Corrigido agora.

---

## O que é

`alchemia-news` é a plataforma de **inteligência de notícias e literatura** do nicho da Alchemia
Solutions — CADD (Computer-Aided Drug Design), AI Drug Discovery, engenharia de proteínas/
anticorpos/vacinas. Coleta metadado público de fontes acadêmicas e de imprensa 3x/dia (alvo), e
serve tudo num dashboard Next.js.

**Não é um setor de negócio tradicional** — é infraestrutura de monitoramento, mesma classe de
`alchemia-brain`. Não toca dado molecular; não tem relação com o schema de `alchemia-database`
nem com o pipeline `alchemia-athanor`.

**Spec canônica (Portão de Revisão aprovado pelo fundador em 2026-08-17):**
`docs/specs/2026-08-17-alchemia-news-intelligence-platform.md`. Onde este arquivo divergir da
spec, **este arquivo descreve o que está em disco hoje** e a spec descreve o que foi aprovado —
as divergências reais estão listadas em "Estado real vs. spec" abaixo, não escondidas.

## Estrutura real em disco (verificada 2026-08-17)

```
alchemia-news/
├── AGENTS.md · CLAUDE.md          ← este arquivo + import Claude-específico
├── .gitignore                     ← ignora .venv, node_modules, .next, .env, logs
├── docs/specs/
│   └── 2026-08-17-alchemia-news-intelligence-platform.md   (aprovada)
├── pipeline/                      ← coleta determinística, sem LLM
│   ├── run_all.py                 (142 linhas — orquestrador)
│   ├── requirements.txt           (requests, PyYAML, feedparser)
│   ├── collectors/                (8 coletores + common.py, 1.094 linhas)
│   ├── config/                    (4 YAMLs — fontes, empresas, recursos, keywords)
│   └── data/                      ← saída JSON consumida pelo dashboard
└── dashboard/                     ← Next.js 16 App Router, TypeScript, Tailwind
    ├── app/                       (6 rotas)
    ├── components/                (5 componentes)
    └── lib/data.ts · lib/types.ts
```

Total de código Python: **1.236 linhas** em 10 arquivos.

## Pipeline — os oito coletores

Nenhum LLM participa da coleta. Filtro de relevância é **keyword + fonte, determinístico** — toda
entrada carrega o termo/fonte que a trouxe (`keywords_matched`), nunca uma classificação opaca.
Isso é requisito de spec, não detalhe de implementação: é o que impede o setor de fabricar
relevância.

| Coletor | Método real | Por que assim |
|---|---|---|
| `pubmed_collector` | NCBI E-utils (`esearch`/`efetch`) direto | 200 OK verificado |
| `biorxiv_collector` | API `api.biorxiv.org/details/biorxiv` | Não filtra por keyword no servidor — pagina por data, filtra no cliente |
| `arxiv_collector` | `export.arxiv.org/api/query` (q-bio) | 200 OK verificado |
| `chemrxiv_collector` | **Proxy via Crossref**, prefixo DOI `10.26434` | ChemRxiv direto responde **403** |
| `scielo_collector` | **Proxy via Crossref**, prefixo DOI `10.1590` | `search.scielo.org` direto responde **403** |
| `feed_collector` | RSS (Nature Reviews Drug Discovery, Nature/Drug Discovery) | Feeds temáticos — sem filtro de keyword |
| `googlenews_collector` | `news.google.com/rss/search?q=...` | Endpoint **não-oficial**, sem SLA público — tratado como melhor esforço, falha silenciosa não derruba o pipeline |
| `companies_collector` | RSS/página das 22 empresas de referência | Fallback manual quando não há feed |

**Configuração viva** (editável sem tocar em Python): 22 empresas monitoradas (Schrödinger,
Isomorphic Labs, Insilico Medicine, Adaptyv Bio, Rowan Scientific, Anthropic/Claude Science…),
9 bancos/ferramentas de referência (COCONUT, BrNPDB, ChEMBL 37, ZINC 20, Enamine, Molport…),
41 termos-tópico, além de queries dedicadas de PubMed/arXiv/Google News (pt e en).

### Execução real registrada (não estimada)

`pipeline/data/runs/20260817T171445Z-pipeline_run.json` e `pipeline/data/meta.json`:

| | Primeira execução (17:14Z) | Segunda execução (17:15Z) |
|---|---|---|
| Duração | 38,8 s | 20,5 s |
| Artigos | 128 (128 novos) | 128 (**0 novos**) |
| Notícias | 1.709 (1.709 novas) | 1.709 (**0 novas**) |
| Atividade de empresas | 938 (938 novas) | 938 (**0 novas**) |

**A segunda execução prova a deduplicação** (chave por DOI/URL normalizado) — critério de sucesso
da spec, verificado de fato, não presumido.

**Ressalva real:** `biorxiv` retornou **0 itens** na execução completa e foi `skipped` na segunda.
Não está confirmado se isso é comportamento correto (janela incremental de 3 dias, nada novo no
nicho) ou falha silenciosa. **Não investigado nesta rodada** — ver "Pendências".

### Como rodar

```bash
cd alchemia-ai/alchemia-news && python -m pipeline.run_all
```

Backfill mais profundo de bioRxiv (job separado, sob demanda, caro):

```bash
python -m pipeline.run_all --biorxiv-days 180
```

Pular coletores para depuração: `--skip companies,scielo`.

**Ambiente:** o venv deste setor é `pipeline/.venv`, criado próprio. O Python pré-instalado do
ambiente de automação (`hermes-agent/venv`) **não tem `pip` funcional** — verificado, não
presumido. Nunca presuma um ambiente compartilhado.

## Dashboard

Next.js **16.2.11** + React **19.2.8** + Tailwind **3.4.19** + TypeScript 5.9.3 (mesmas majors já
validadas no `website/` de `alchemia-database` — decisão reaproveitada, não reaberta). Node ≥ 20.9.

Seis rotas: `/` (Home), `/noticias`, `/artigos`, `/empresas` (+ `/empresas/[slug]`),
`/bancos-ferramentas`, `/sobre`.

`lib/data.ts` lê os JSONs **em tempo de requisição** via server components
(`fs.readFileSync` sobre `../pipeline/data`) — qualquer execução nova do pipeline aparece no
dashboard **sem rebuild**. É design deliberado; não troque por import estático.

## Licenciamento e LGPD — o que este setor pode e não pode fazer

- **Armazena só metadado público**: título, autores, data, fonte, URL, e o resumo curto quando a
  própria API o entrega como metadado público (ex. abstract do PubMed).
- **Nunca redistribui texto completo de artigo.** Nunca faz scraping de PDF pago ou paywall. O
  dashboard **sempre linka para a fonte original**, nunca reproduz o artigo de terceiro.
- **Nenhum dado pessoal é coletado** — só metadado institucional de publicação/notícia
  corporativa. Sem formulário, sem e-mail de usuário. LGPD não é acionada na configuração atual.
- **Redes sociais estão fora de escopo** por decisão explícita do fundador (2026-08-17). Se uma
  fase futura adicionar LinkedIn/X/Instagram, isso exige **nova análise LGPD antes de
  implementar** — não presuma resolvido.
- **Anti-overclaiming:** um agregador nunca é exaustivo. A página `/sobre` e o rodapé devem sempre
  declarar fontes cobertas, data da última coleta e limitações conhecidas. Nunca alegar "todas as
  notícias" — mesma disciplina já imposta a `alchemia-growth` e `alchemia-database`.

## Estado real vs. spec — divergências verificadas em 2026-08-17

A spec está marcada como aprovada e vários dos seus Critérios de Sucesso **ainda não foram
cumpridos**. Registrado aqui para que nenhuma sessão futura presuma que o setor está fechado:

1. 🔴 **Sub-agente e skill nunca foram criados.** A spec exige o sub-agente `alchemia-news` +
   skill `news-intelligence-pipeline`, com `check_runtime_integrity.py` passando em **13 agentes /
   20 skills**. Real em disco: **12 agentes / 19 skills**, e uma busca por `alchemia-news` em todo
   `alchemia-ai/alchemia-agents/` retorna **zero ocorrências**. O harness não conhece este setor.
2. 🔴 **Nenhum cron job existe.** A spec exige cron 3x/dia criado *e* disparado com sucesso real.
   O `cron/jobs.json` do Hermes contém **apenas os 2 jobs do pipeline F1** (08h e 18h); nenhum job
   de `alchemia-news` existe em nenhum dos quatro perfis. As duas execuções registradas foram
   manuais. **A cadência 3x/dia não está acontecendo.**
3. 🟡 **Caminho do runner divergente.** A spec cita `pipeline/collectors/run_all.py`; o arquivo
   real é `pipeline/run_all.py`. Um agente seguindo a spec ao pé da letra não encontra o script.
4. 🟡 **`dashboard/package.json` tem a chave `"overrides"` duplicada.** JSON não permite chaves
   repetidas — a última vence, então o override de `js-yaml` para `4.3.1` é **silenciosamente
   descartado** e só o de `postcss` tem efeito. `js-yaml` fica na `4.1.0` da dependência direta.
   Corrigir fundindo as duas chaves num único objeto.
5. 🟡 **Risco de deploy na Vercel.** `vercel.json` builda a partir de `dashboard/`, mas
   `lib/data.ts` lê `process.cwd()/../pipeline/data` — **fora da raiz do deploy**. Como
   `readJsonSafe` tem fallback silencioso para `[]`, o site publicado renderizaria **vazio, sem
   erro**. Precisa de decisão de arquitetura antes de publicar (copiar os JSONs no build, mover o
   `pipeline/data` para dentro de `dashboard/public`, ou servir por API).
6. 🟡 **`biorxiv` com 0 itens**, ver acima.

## Pendências (nenhuma resolvida nesta rodada)

- Criar sub-agente + skill e atualizar `check_runtime_integrity.py` (itens 1 acima).
- Criar o cron 3x/dia e **disparar uma vez de verdade**, confirmando output real (item 2).
- Corrigir `package.json` (item 4) e decidir a arquitetura de deploy (item 5).
- Confirmar se `biorxiv` 0-itens é correto ou falha silenciosa (item 6).
- Fase 2 (backlog): resumo/tradução PT assistida por IA **sob demanda**, nunca na coleta
  automática; score de relevância ponderado no lugar do keyword booleano.
- Fase 3 (backlog, fora de escopo por decisão do fundador): redes sociais.

## Addendum — 2026-08-17 (mais tarde): crons no ar, bug real do `run_all.py` corrigido — a seção "Estado real vs. spec" acima está parcialmente desatualizada

A lista "Estado real vs. spec" acima foi escrita de manhã. Correções datadas, item por item:

| Item de cima | Estado agora |
|---|---|
| 1. Sub-agente + skill no harness (12/19 vs. 13/20) | ✅ **resolvido** — ver abaixo |
| 2. "Nenhum cron job existe / a cadência 3x/dia não está acontecendo" | ✅ **resolvido** — ver abaixo |
| 3. Caminho do runner divergente | ✅ **resolvido, e era pior do que parecia** — ver abaixo |
| 4. `package.json` com `"overrides"` duplicado | ⏳ segue aberto |
| 5. Risco de deploy na Vercel (`../pipeline/data` fora da raiz) | ⏳ segue aberto |
| 6. `biorxiv` com 0 itens | ⏳ segue sem diagnóstico |

**Crons existem e disparam.** Três jobs `--no-agent --script` no perfil Hermes **`baker-bot`**,
às **07h/13h/19h** (`Brazil/East`), rodando `pipeline/digest.py` (novo). O gateway do `baker-bot`
está no ar, então a cadência é real — não só registrada. Arquitetura, justificativa do modo
`--no-agent` e IDs dos jobs: `alchemia-ai/alchemia-bots/AGENTS.md` e a spec daquele setor. A
entrega ainda é `local`; vira `discord:<channel_id>` quando o Axel subir.

**O item 3 não era só divergência de caminho — era um bug real, e foi corrigido.**
`pipeline/run_all.py` inseria `Path(__file__).parent.parent` no `sys.path`, então
`from collectors import …` só funcionava ao invocar o arquivo **por caminho**
(`python pipeline/run_all.py`). **O modo documentado no docstring do próprio arquivo,
`python -m pipeline.run_all`, quebrava com `ModuleNotFoundError`** — e é justamente o modo que o
cron usa. Corrigido para `.parent`, com comentário no código explicando; verificado de ponta a
ponta (39,0 s, +14 notícias, +9 itens de empresa).

**O harness passou a conhecer este setor.** `.claude/agents/alchemia-news.md` e
`.claude/skills/news-intelligence-pipeline/SKILL.md` foram criados (2026-08-17 17:10), levando as
contagens a **13 sub-agentes / 20 skills** — exatamente o que a spec exigia. Verificado por
listagem direta e por `harness/check_runtime_integrity.py`, que já foi atualizado para os números
novos e **passa** neles. Isso fecha o último Critério de Sucesso estrutural desta spec; o único
item que o checker ainda acusa é o bearer token do plugin Obsidian em texto puro, que é
escalonamento ao fundador (rotação), não deste setor.

**`pipeline/digest.py` é novo neste setor.** Resume o delta de cada execução em formato compacto
(contagem por coletor + destaques com fonte, link e o termo que trouxe cada item) e **imprime nada
quando não há novidade** — o Hermes trata stdout vazio como tick silencioso, então um canal não
recebe três mensagens diárias dizendo "nada mudou". Ele nunca despeja a base inteira.

## Rodando o dashboard localmente (sem deploy)

**Decisão do fundador (2026-08-17): por enquanto o dashboard roda só local — nada de deploy na
Vercel ainda.** O `vercel.json` e o hook `prebuild` (`scripts/copy-pipeline-data.js`) continuam no
repositório e funcionando, prontos para quando essa decisão mudar; só não há publicação.

Dois modos, ambos a partir de `alchemia-ai/alchemia-news/dashboard/`:

```bash
npm run dev      # desenvolvimento, hot reload — use ao mexer no front
npm run build && npm run start   # produção local, mais rápido para só consultar
```

Abre em `http://localhost:3000`. Há também `.claude/launch.json` na raiz da empresa com a
configuração `alchemia-news-dashboard`, para subir o servidor pelo próprio harness.

**Não é preciso rebuildar quando o pipeline roda.** `lib/data.ts` lê os JSONs **em tempo de
requisição** (server components), então uma coleta nova aparece ao recarregar a página — inclusive
no modo `start`. É design deliberado.

**Verificado ao vivo em 2026-08-17** (build de produção, `next start`): as **7 rotas** respondem
200 — `/`, `/noticias`, `/artigos`, `/empresas`, `/empresas/[slug]`, `/bancos-ferramentas`,
`/sobre` — e a home mostrou **163 artigos · 1.738 notícias · 954 menções de empresas**, com a
duração real da última coleta. Os 163 artigos (contra 128 pela manhã) são a confirmação prática de
que a correção de paginação do `biorxiv_collector` funcionou.

### Auto-refresh (novo, 2026-08-17, a pedido do fundador)

`components/AutoRefresh.tsx` — client component montado no `layout.tsx`, portanto **vale em todas
as rotas**. Chama `router.refresh()` a cada **60 s**.

Por que `router.refresh()` e não `<meta http-equiv="refresh">`: o primeiro **revalida os server
components** (que leem `pipeline/data/*.json` a cada requisição) e troca a árvore no lugar,
**preservando scroll e estado de cliente**; o segundo recarrega a página inteira e joga o usuário
de volta ao topo. Todas as rotas são `ƒ` (server-rendered on demand) no build, que é a condição
para isso funcionar.

Duas decisões que evitam trabalho inútil: **pausa quando a aba fica oculta**
(`visibilitychange`) e **revalida imediatamente ao voltar** para a aba, em vez de esperar o
próximo tick.

**Honestidade sobre o que isso é:** não é streaming nem websocket. O dado só muda quando o
pipeline roda (3x/dia). O intervalo curto existe para a mudança aparecer sozinha logo após a
coleta — mesma disciplina anti-overclaiming de `.claude/skills/realtime-dashboard/SKILL.md`, cuja
convenção ("nunca prometa polling que não existe") o `LiveClock.tsx` já citava. Como o polling
passou a existir, o comentário e o `title` daquele componente foram atualizados na mesma rodada,
para o que se anuncia continuar sendo exatamente o que acontece.

Para mudar o intervalo: `<AutoRefresh intervalMs={30_000} />` no `layout.tsx`.

## Regras invioláveis (herdadas da raiz da empresa)

- **Nunca fabricar números.** Toda contagem citada em qualquer documento vem de leitura real do
  JSON/config, nunca de estimativa ou memória.
- **Nunca sobrescrever silenciosamente** documento com valor de auditoria (specs, este arquivo,
  changelog do vault) — correção entra como **addendum datado**, corpo original preservado.
- **Nenhum comando git de escrita em remoto** (`commit`/`push`/`tag`/`init`) por nenhum agente —
  escalar ao fundador. `status`/`diff`/`log` são permitidos. Este diretório **não tem `.git`
  hoje**, consistente com a decisão de fase de desenvolvimento do fundador (backup = Google Drive).
- **Nenhuma operação destrutiva** sem confirmação explícita.
- Toda entrega/decisão deste setor recebe registro datado e linkado em `alchemia-brain`
  (`02-Harness/alchemia-news.md` + `99-Changelog/AAAA-MM-DD.md`).

## Addendum — 2026-08-17 (mais tarde, perfil Hermes `default`): retomada de operação — 4 itens da seção "Estado real vs. spec" resolvidos

A seção "Estado real vs. spec" acima documentava 6 divergências. Nesta rodada, 4 foram resolvidas
e verificadas por execução real (não presumidas):

1. ✅ **Sub-agente + skill criados.** `alchemia-ai/alchemia-agents/.claude/agents/alchemia-news.md`
   + `.claude/skills/news-intelligence-pipeline/SKILL.md`, com manifest, mirror `.claude/` (raiz) e
   mirror `.codex/` (TOML + `config.toml`). `harness/check_runtime_integrity.py` atualizado para
   **13 agentes/20 skills** e passa.
2. 🟡 **Cron parcialmente resolvido, mas com achado novo.** Um cron 3x/dia foi criado e disparado
   com sucesso real no perfil Hermes `default` (`05511d259e81`, `0 6,14,22 * * *`,
   `last_status: ok`). **Descoberto depois, ao ler `alchemia-brain/02-Harness/alchemia-news.md`:**
   o perfil `baker-bot` já tinha três jobs próprios para a mesma coleta (`0 7,13,19 * * *`,
   `--no-agent`), criados em sessão anterior no mesmo dia — perfis Hermes não compartilham
   `cronjob(action='list')` entre si, então esta sessão não tinha visibilidade disso até revisar o
   vault. **Resultado real: o pipeline roda 6x/dia, não 3x, em dois mecanismos diferentes.**
   Decisão de qual manter (ou consolidar) pendente do fundador — nenhum dos dois jobs foi
   removido/pausado unilateralmente.
3. ✅ **Caminho do runner já era `pipeline/run_all.py`** (item 3 antigo já estava correto, era só
   a spec que citava um caminho diferente — sem ação necessária).
4. ✅ **`package.json` duplicado corrigido.** `js-yaml` subiu para `4.3.1` como dependência direta;
   `overrides` ficou só com `postcss`. Verificado com `npm install` real sem erro `EOVERRIDE`.
5. ✅ **Risco de deploy Vercel mitigado.** Hook `prebuild`
   (`dashboard/scripts/copy-pipeline-data.js`) copia os JSONs/YAMLs para
   `dashboard/.pipeline-data/`; `lib/data.ts` prioriza o caminho ao vivo (`../pipeline/data`) e cai
   para o snapshot só quando ele não existir. Verificado com `npm run build && npm run start`
   reais.
6. ✅ **`biorxiv` 0-itens era falha silenciosa real, não comportamento correto.** A API pagina em
   blocos de **~30 itens**, não 100 como `biorxiv_collector.py` assumia — o cursor avançava rápido
   demais e o corte de "última página" (`len(collection) < 100`) interrompia o loop já na primeira
   página. Corrigido (`cursor += len(collection)`, corte por coleção vazia). Verificado: janela de
   30 dias foi de 0 para 36 itens relevantes de 498 preprints varridos; execução de produção
   seguinte trouxe **35 artigos novos** (contra 0 nas duas execuções anteriores a esta correção).

Também corrigido nesta rodada, fora da lista original: `dashboard/app/empresas/[slug]/page.tsx`
estava incompatível com Next.js 15+ (`params` como `Promise`, não objeto síncrono) — toda página de
empresa retornava 404 silencioso mesmo com a empresa existindo em `companies.yaml`. Verificado com
`curl` real em todas as 7 rotas do dashboard após a correção (200 em todas).

Ver `alchemia-brain/02-Harness/alchemia-news.md` e `alchemia-brain/99-Changelog/2026-08-17.md`
(continuação datada da mesma sessão) para o registro completo, incluindo o achado do cron
duplicado entre perfis.

## Addendum — 2026-08-18: o setor passa a alimentar `alchemia-science` — radar diário de pesquisa e colheita de PDF open access

Auditoria completa de `alchemia-ai` (news + bots) a pedido do fundador. Este addendum cobre o que
mudou **neste setor**; o do `alchemia-bots` cobre as rotinas, e
`docs/specs/2026-08-18-research-library-integration.md` tem a decisão completa.

### O que passou a existir

`pipeline/research_export.py` (novo, ~560 linhas) exporta **o dia inteiro** do `alchemia-news`
para `alchemia-science/research/AAAA-MM-DD-alchemia-news-radar.md` — todos os artigos, notícias e
atividade de empresas daquela data, mais a saúde real dos 8 coletores lida de `meta.json`. E, para
cada artigo, tenta resgatar o **texto completo**: se houver rota open access **confirmada naquela
execução** (arXiv · bioRxiv/medRxiv · Unpaywall `is_oa` · Europe PMC `isOpenAccess`), o PDF entra
em `alchemia-science/alchemia-library/` já registrado em `manifest.csv` e `alchemia-library.json`;
se não houver, o artigo entra **só como markdown, com o motivo literal**. Artigo de paywall nunca
é baixado — é a classe de decisão que a cultura da empresa manda escalar, não automatizar.

Verificado por execução real, não presumido: radares de **2026-08-17** (174 KB) e **2026-08-18**
gerados; as quatro rotas exercidas contra a rede (arXiv 200 `%PDF`; bioRxiv 6,3 MB; Unpaywall
`cc-by`; Europe PMC consultada, `isOpenAccess=N` no lote do dia); reexecução idempotente
(`ja_na_biblioteca=2, baixado=0`); `run_alchemia_news.cmd` rodando a cadeia completa e saindo 0.

**ChemRxiv, achado reverificado:** responde **403** também na `public-api`, não só no acesso
direto — e o prefixo `10.26434` não é indexado pelo Unpaywall. O texto completo do ChemRxiv só sai
manualmente pelo navegador. O radar reporta esse motivo específico em vez de um "não encontrado"
genérico.

### Dois bugs reais corrigidos no pipeline

**1. `common.normalize_url()` deformava URL e não removia o `utm_`.** A implementação antiga
fatiava a string à mão: com qualquer parâmetro **antes** do tracking (`?id=7&utm_source=rss`), ela
remontava como `?id=7?utm_source=rss` — dois `?`, e o `utm_source` **sobrevivia**. Como essa
função alimenta `dedupe_key()`, a mesma matéria chegando com `utm_source` diferente geraria duas
chaves e entraria **duas vezes** na base. Reescrita com `urllib.parse` (tracking removido de
verdade, parâmetros reordenados, fragmento descartado).

**Honestidade sobre o impacto:** medido antes de corrigir — **zero** das 3.044 entradas da base
muda de chave, porque nenhuma URL do corpus atual tem parâmetro antes de um `utm_` (links do
Google News são `?oc=5`, DOIs não têm query). O bug era real mas **ainda não tinha disparado**.
Nenhuma migração foi necessária e nenhuma duplicata precisou ser colapsada. O `oc=5` do Google
News é deliberadamente **mantido**: é constante naquela fonte, não distingue nada, e removê-lo só
quebraria a URL.

**2. Artigos de PubMed chegavam sem `keywords_matched`.** Eram os únicos — a `pubmed_query` já é
do nicho, então o coletor nunca aplicava `match_keywords`. Mas a spec deste setor exige que *toda
entrada carregue o termo que a trouxe*, e sem isso um artigo de PubMed no radar não podia ser
justificado a posteriori. Corrigido: os tópicos são casados contra título+resumo **sem descartar
nada** (nenhum item é filtrado por não casar) — é rastreabilidade, não filtro. Medido depois:
**56 de 60** itens passaram a carregar termo; os 4 restantes entraram pela query do PubMed sem
casar tópico do `keywords.yaml`, o que é justamente o sinal útil de termo candidato a ser
adicionado.

### Correção a duas afirmações que este próprio arquivo carregava

- **O addendum de 2026-08-17 ("retomada de operação", item 2) registra que o pipeline roda "6x/dia,
  não 3x, em dois mecanismos diferentes", com a decisão de consolidar pendente do fundador.
  Isso não é mais verdade.** Verificado nesta data lendo os `cron/jobs.json` de cada perfil: os 4
  jobs do Hermes estão **`enabled: false`**, e o job duplicado do perfil `default`
  (`05511d259e81`) **não existe mais** — o perfil foi reconstruído após o incidente do
  `hermes update --force`. O `default` hoje só tem os 3 jobs pessoais de F1. A cadência real é
  **3x/dia, num mecanismo só** (Windows Task Scheduler, `LastTaskResult=0`). A pendência está
  resolvida por consequência, não por decisão — mas está resolvida.
- Os itens 4 e 5 de "Estado real vs. spec" (`package.json` com `overrides` duplicado; `lib/data.ts`
  lendo fora da raiz de deploy) seguem corretamente marcados como resolvidos no addendum de
  2026-08-17 — **reconfirmados por leitura direta nesta data** (uma única chave `overrides`; o
  hook `prebuild` e o fallback para `.pipeline-data/` estão no lugar).

### Como rodar

```bash
cd alchemia-ai/alchemia-news
python -m pipeline.research_export                    # o dia de hoje, com colheita
python -m pipeline.research_export --date 2026-08-17  # refaz/backfill um dia anterior
python -m pipeline.research_export --no-pdf           # só o markdown
python -m pipeline.research_export --dry-run          # não escreve nada
```

Tetos, todos ajustáveis por flag: `--max-pdf 6` por execução · `--max-mb 60` por arquivo ·
`--max-total-mb 150` por execução · **`--min-free-gb 20`**, piso de espaço livre abaixo do qual a
colheita é pulada por inteiro e o radar registra o motivo (memória da crise de disco de
2026-08-09). O que passa do teto é **reportado como adiado**, nunca truncado em silêncio.

`pipeline/data/discord/` é novo: guarda a cópia verbatim do que o Axel publicou, para o radar
poder incluir a seção "Publicado no Discord" sem perdê-la quando o markdown é regenerado (o radar
é derivado, reescrito por inteiro a cada execução). Ver o `README.md` daquele diretório.

### Pendência real desta rodada

**~75 artigos de 2026-08-17 com rota aberta ficaram adiados pelo teto de `--max-pdf`.** Nada foi
descartado — eles reaparecem enquanto não estiverem na biblioteca, e o backfill acontece sozinho
ao longo dos próximos ciclos. Forçar de uma vez (`--date 2026-08-17 --max-pdf 20`) é decisão do
fundador: o custo é disco.

Ver `alchemia-brain/02-Harness/alchemia-news-state.md` e
`alchemia-brain/99-Changelog/2026-08-18.md`.

### Continuação 2026-08-18: dashboard atualizado, sem vulnerabilidade, rodando em `localhost:3000`

A pedido do fundador ("atualize todo o app e deixe ele ativo no meu localhost completamente
atualizado"), na mesma sessão da integração acima.

**2 vulnerabilidades ALTAS fechadas.** `npm audit` acusava `sharp <0.35.0` (CVE-2026-33327,
-33328, -35590, -35591, herdadas do libvips), puxado transitivamente pelo Next **16.2.11**.
Corrigido subindo para **Next 16.3.1**. Estado real após a atualização: **`found 0
vulnerabilities`**.

**O que subiu, e o que deliberadamente não subiu.** Atualizados dentro da mesma major, sem risco
de quebra: `next` 16.2.11→**16.3.1**, `postcss` 8.5.23→**8.5.26**, `autoprefixer`
10.4.21→**10.5.4**, `@types/react` 19.2.17→**19.2.18**, `@types/react-dom` 19.2.3→**19.2.4**.
**Não** atualizados, por serem major com quebra real e exigirem migração própria — não é
manutenção, é projeto: `tailwindcss` 3.4.19→4.3.3 (o v4 muda o modelo de configuração inteiro),
`typescript` 5.9.3→7.0.2, `@types/node` 24→26 (o Node desta máquina é **v22**; os tipos da 26
descreveriam uma runtime que não existe aqui), `js-yaml` 4.3.1→5.3.0 (pin deliberado deste setor
desde o incidente de `overrides` de 2026-08-17).

**Armadilha real encontrada no caminho, vale registrar:** subir o `postcss` falhou duas vezes com
`EOVERRIDE` — o bloco `overrides` do `package.json` pinava `8.5.23` enquanto a `devDependency`
tentava ir para `8.5.26`, e o npm compara os dois. É o **mesmo** `EOVERRIDE` que este setor já
enfrentou em 2026-08-17 com o `js-yaml`. Regra prática para a próxima vez: **ao mexer num pacote
que aparece em `overrides`, mude os dois lugares na mesma edição.** O npm também reintroduziu
`^` nas versões que instalou; revertido para pin exato, que é a convenção deste `package.json`.

**Bug real de exibição, corrigido:** `common.strip_html()` removia tags mas **não decodificava
entidades HTML** — todo resumo vindo do Google News aparecia na home com `&nbsp;&nbsp;` literal
antes do nome da fonte. Corrigido com `html.unescape()`, aplicado **antes** do filtro de tags (a
ordem importa: decodificar depois transformaria um `&lt;script&gt;` numa tag de verdade já fora do
alcance do filtro — verificado com esse caso exato no teste). Os itens já gravados foram
normalizados de uma vez: **2.826 campos** de `title`/`summary` nos três JSONs; entidades restantes
nos arquivos servidos: **0**.

**Verificação real, não presumida.** `npm run build` limpo no Next 16.3.1; as **7 rotas
respondendo 200** (`/`, `/noticias`, `/artigos`, `/empresas`, `/empresas/[slug]`,
`/bancos-ferramentas`, `/sobre`); **zero erro no console**; todas as rotas seguem `ƒ`
(server-rendered on demand), que é a condição para o dashboard refletir uma coleta nova **sem
rebuild**. Home mostrando o dado ao vivo: **212 artigos · 1.820 notícias · 1.017 menções de
empresas**, última coleta 87,9 s.

**Como o fundador sobe de novo depois de fechar:** `alchemia-news-dashboard` no
`.claude/launch.json` da raiz (porta 3000, `npm run start`), ou
`alchemia-news-dashboard-dev` (porta 3001, hot reload). Deploy na Vercel segue **adiado por
decisão do fundador** — nada mudou nisso.

### Continuação 2026-08-18: primeira execução agendada real do Baker expôs um defeito de concorrência — corrigido

O fundador rodou "Run now" na tarefa `alchemia-news-baker-curadoria`. **A rotina funcionou como
projetada** — leu `meta.json`, viu coleta de 11 min antes e não redisparou, checou 8/8 coletores
(notando corretamente que `nature` com 0 itens sem erro **não** é o padrão de regressão do
`biorxiv`), rodou o `research_export`, colheu +1 PDF do bioRxiv, `check_sync` OK, atualizou a nota
de estado do vault com números reais, e **não mexeu em nenhuma config** (conservador, como manda a
regra de 1–2 adições/dia só com padrão observado).

**Mas uma checagem manual feita em paralelo, às 11:08:03, acusou a biblioteca fora de sincronia:
56 PDFs em disco, 55 no manifest.** Reconferindo 59 segundos depois: **56/56/56, OK**. Não era
corrupção — era a biblioteca sendo lida **no meio de uma escrita**. O PDF foi gravado às 11:07:39 e
o manifest só às 11:08:11.

**A causa é um defeito real na primeira versão do `research_export`,** não um acaso:

1. **Escrita em lote.** O PDF ia para o disco dentro do laço, mas `gravar_biblioteca()` só era
   chamado **depois de todos os downloads**. Com o teto de 6 PDFs, isso é uma janela de **minutos**
   em que disco e manifest discordam — e um processo morto no meio deixaria órfão **permanente**.
2. **Nenhuma exclusão mútua.** A colheita faz read-modify-write de `manifest.csv` e
   `alchemia-library.json`. Duas execuções sobrepostas — cenário **normal**, não exótico: Task
   Scheduler às 12:40 fazendo backfill lento + Baker às 12:50 — leriam a mesma versão e a segunda
   reescreveria **sem** as entradas da primeira, deixando PDF órfão para sempre.
3. **Consequência operacional pior que as duas:** a rotina do Baker é instruída a **reportar ao
   fundador** um `check_sync` que falha. Sem distinguir "biblioteca quebrada" de "colheita
   rodando", ele geraria **alarme falso 3x/dia** — e alarme falso recorrente treina todo mundo a
   ignorar o alarme de verdade, que é exatamente o que este guarda-corpo existe para evitar.

**Três correções, todas testadas contra os casos reais:**

- **Commit imediato por download.** `gravar_biblioteca()` roda logo após cada PDF, não em lote no
  fim. A janela caiu de minutos para milissegundos, e uma queda perde no máximo o item em voo.
- **Lock exclusivo** (`alchemia-library/.harvest.lock`, criação atômica com `O_EXCL`, obsoleto
  após 45 min para uma queda não travar a colheita para sempre). Quem não pega o lock **não falha
  e não espera**: pula só a colheita, registra o motivo no radar do dia, e o markdown sai normal.
  Os PDFs não colhidos reaparecem na execução seguinte — mesma disciplina do teto de `--max-pdf`.
- **`check_sync` ciente do lock.** Com colheita em andamento, divergência vira `EM ANDAMENTO` e
  **exit 0** (estado transitório esperado); com o lock liberado ou obsoleto, segue sendo **exit 1**.

**Verificado por teste real, não por leitura:** órfão sem lock → exit **1**; mesmo órfão com lock
ativo → exit **0**; mesmo órfão com lock forjado a 46 min → exit **1** (obsoleto não mascara);
`research_export` com lock de outro processo → pula a colheita, gera o radar, registra o motivo,
exit **0**; sem lock → colhe normal e libera o lock no fim. Cadeia completa do wrapper: exit 0,
`check_sync --hashes` OK em **56/56/56**.

**Correção menor, mesmo caminho:** os avisos impressos no `stdout` levavam emoji e acento direto.
O Task Scheduler roda em console **cp1252** — um `⏭️` ali levanta `UnicodeEncodeError` e derruba a
execução inteira por causa de um caractere decorativo. Agora o stdout é transliterado (NFKD, acento
removido mas letra preservada: "execucao", não "execuo"), enquanto o markdown do radar segue com
emoji e acentuação completos.

## Addendum — 2026-08-18 (fontes): poda das improdutivas, newsletters do nicho, e um zero
## silencioso do `nature` que durava o dia inteiro

A pedido do fundador: remover fontes que rendem 0, incluir newsletters da área
(`longevity.technology`, `nature.com/nrd`, `drughunter.com` "e as mais relevantes"), e consolidar
tudo no app e nos markdowns para o Axel montar a mensagem do Discord.

### 🔴 O achado que mudou o plano: `nature` estava falhando em silêncio

Antes de mexer em qualquer fonte, o rendimento real foi medido. O coletor `nature` foi de
**38 → 8 → 0** ao longo de 2026-08-18, com `error: null` nas três medições. Não era "nada novo":
o nature.com aplica **desafio anti-bot** e devolve **HTTP 200 com uma página HTML**. O caminho do
código engolia isso perfeitamente — `http_get` não vê erro (é 200), `ET.fromstring` quebra, o
fallback do `feedparser` acha 0 entradas, e o coletor reporta `count: 0, error: null`.

Isso é pior que uma falha: a rotina do Baker é instruída a investigar `error`, e **nunca havia
erro para investigar**. O mesmo padrão do bug de paginação do bioRxiv, que passou dias despercebido.

**Três correções no `feed_collector`:**

1. **Detecção de página anti-bot** (`Client Challenge`, `Just a moment...`, Cloudflare etc.) →
   levanta `FeedIndisponivel`. Resposta HTML ou vazia onde se espera XML também levanta.
2. **Falha de feed sobe como erro da seção**, depois de todos serem tentados — os feeds que
   funcionaram na rodada não são perdidos, mas `meta.json` passa a registrar `error` de verdade.
3. **Espaçamento entre requisições do mesmo host** (`delay_seconds`, 4 s para nature.com) — a
   rajada era a causa provável do desafio.

**Efeito verificado na execução seguinte:** `nature` continua em 0, mas agora com
`error: "4/5 feed(s) de 'nature_feeds' falharam: ... resposta é uma página anti-bot"`. O bloqueio é
do lado da fonte; o que mudou é que ele **aparece**.

### Segundo bug do parser, encontrado ao adicionar o Fierce Biotech

O feed do Fierce tem **markup aninhado dentro do `<title>`**, então `child.text` vinha vazio e os
**25 itens eram descartados por "título vazio"** — outro zero sem erro. Corrigido com um helper
`_texto()` que usa `itertext()` (mesma técnica que o coletor do PubMed já usava). Também foram
acrescentados a `parse_date_safe` os formatos de data reais desses feeds (`"Aug 18, 2026 8:14am"`).

### Poda: 2 removidas, 2 mantidas com justificativa

Rendimento medido sobre os 1.017 itens acumulados. Quatro fontes em zero, mas **por dois motivos
diferentes** — e a distinção importa:

| Fonte | Itens | Decisão |
|---|---|---|
| `genix-ai` | 0 | **removida** — o Google News não acha notícia nenhuma sobre a empresa |
| `ai4pharma` | 0 | **removida** — idem |
| `nvidia` | 0 | **mantida** — o feed funciona (6 itens); é o `filter_relevance` cortando um blog generalista |
| `microsoft-research` | 0 | **mantida** — idem (3 itens) |

As duas mantidas são **vigias que ainda não dispararam**: quando a NVIDIA anunciar algo de
BioNeMo, ou a MSR algo de descoberta de fármacos, o filtro deixa passar. Custam 2 requisições por
execução. Removê-las é decisão do fundador — mas seria remover um alarme, não uma fonte morta.

De 22 empresas monitoradas para **20**.

### Newsletters: 5 adicionadas, 7 verificadas e rejeitadas

Seção nova `newsletter_feeds` no `sources.yaml`, coletor `newsletters` no `run_all`. **Toda URL foi
testada ao vivo** (HTTP 200 + contagem real de `<item>`/`<entry>`) antes de entrar — nenhuma foi
presumida a partir do domínio.

| Feed | URL | Filtro | Itens/30d |
|---|---|---|---|
| **Drug Hunter** | `drughunter.com/rss.xml` | sem filtro (curadoria do nicho) | **22** |
| **Longevity.Technology** | `longevity.technology/feed/` | com filtro | **6** |
| Fierce Biotech | `fiercebiotech.com/rss/xml` | com filtro | 0 hoje (25 entradas, nenhuma do nicho) |
| BioPharma Dive | `biopharmadive.com/feeds/news/` | com filtro | 0 hoje |
| Labiotech | `labiotech.eu/feed/` | com filtro | 0 hoje |

Mais três periódicos na seção `nature_feeds` (mesmo host, mesmo espaçamento): Nature
Biotechnology, Nature Machine Intelligence, Nature Chemical Biology — todos com filtro próprio.

**Rejeitados, com o motivo registrado no próprio YAML** para ninguém retentar o mesmo 403 daqui a
um mês: Endpoints News (403), In the Pipeline/Derek Lowe (403, duas rotas), Science Translational
Medicine (403), Drug Discovery Today (403), C&EN (404, três rotas), Chemistry World (202 sem
itens), J. Cheminformatics (anti-bot). São veículos relevantes — o bloqueio é do lado deles.

**`nature.com/nrd` já estava configurado** desde 2026-08-17; o pedido do fundador estava atendido
antes desta rodada, e o que faltava era ele **funcionar** (ver o zero silencioso acima).

### Duas decisões de calibração, ambas medidas

**Janela de data (`window_days: 30`) é obrigatória em feed de newsletter.** Drug Hunter devolveu
**284** entradas e Longevity.Technology **1.500** numa única chamada — o arquivo inteiro. Sem
janela, a primeira execução teria quase dobrado a base de notícias com conteúdo velho.

**`filter_relevance` por feed, não por seção.** Longevity.Technology sem filtro traz **159
itens/mês**; com filtro, **6**. O primeiro número inundaria o radar e o Discord, onde cabem ~5
itens por post. A fonte segue coberta, como o fundador pediu — só entra o que toca o nicho.

### Consolidação no app e nos markdowns

- **`source_type: newsletter`** é um tipo novo, com rótulo ("Newsletter") e cor próprios no
  dashboard. Newsletter curada tem sinal muito maior que resultado de Google News e precisa ser
  distinguível.
- **Radar diário** (`alchemia-science/research/`) ganhou a seção **"Newsletters do nicho"**,
  posicionada **antes** de "Notícias" — é a de maior sinal do dia.
- **Feed do Axel** ganhou a mesma seção, com a disputa de deduplicação ajustada para
  `companies → newsletters → articles → news` (a newsletter vence a notícia genérica quando o
  mesmo item aparece nos dois).
- **Prompt do Axel** passou a ter quatro seções e uma **regra de prioridade explícita**: se não
  couber tudo nos 2.000 caracteres, corta Notícias e Empresas antes de Newsletters e Artigos.

### Verificado por execução real

Pipeline completo: **9 coletores**, 127,1 s, `newsletters: 28`. As sete rotas do dashboard em 200,
com "Drug Hunter (22)" e "Fierce Biotech (33)" já aparecendo como filtro de fonte em `/noticias`.
Feed do Axel: quatro seções populadas, **zero link repetido** entre elas. E a coleta agendada das
12:40 do Task Scheduler rodou sozinha em cima das fontes novas, com `+0 novos` — o dedupe
funcionando sobre o que esta sessão já havia coletado.

## Addendum — 2026-08-18 (dashboard): o app não é um serviço; e o contador de empresas do painel
## estava chumbado em `22`

**Por que a porta 3000 não estava ativa.** O dashboard não roda como serviço nem tem autostart: a
Tarefa Agendada `Alchemia News - Coleta` (única tarefa do setor no Task Scheduler) executa **só o
pipeline Python** e escreve os JSONs — nada nela sobe o Next.js. O servidor é iniciado à mão por
sessão (`npm run start` na `dashboard/`, `.claude/launch.json` da raiz da empresa) e morre junto
com a árvore de processos daquela sessão. Verificado nesta rodada: nenhum listener em `:3000`, e
todos os processos `node` da máquina eram do Hermes. Não havia falha do app — só ninguém servindo.

Subido de novo nesta rodada e verificado: `Ready in 4.3s`, as 7 rotas em **200**
(`/`, `/artigos`, `/noticias`, `/empresas`, `/empresas/[slug]`, `/bancos-ferramentas`, `/sobre`),
e os números do painel batendo exatamente com `pipeline/data/meta.json` da coleta das 15:42Z
(214 artigos / 1.855 notícias / 1.021 menções / 127,1 s) — a leitura em tempo de requisição
(`export const dynamic = 'force-dynamic'`) funcionando como projetado, sem rebuild.

**🔴 Achado corrigido: número fabricado na home.** `app/page.tsx:43` trazia
`hint={`${topCompanies.length ? '22' : '0'} empresas monitoradas`}` — o **22 era literal no
código**, não uma contagem. A poda de fontes de hoje (addendum "fontes" acima) levou
`companies.yaml` de 22 para **20**, e o painel seguia exibindo 22. É exatamente a classe de erro
que a regra "nunca fabricar números" existe para impedir, dentro do app cujo propósito é reportar
números. Corrigido para `getCompanies().length` (a função já existia em `lib/data.ts` e lê o YAML
real); `typecheck` limpo, `build` limpo, home renderizando **20 empresas monitoradas**.

Vale a suspeita geral: qualquer outro literal numérico na camada de apresentação deste app deve
ser tratado como suspeito até provar que vem de contagem real.

### Correção ao addendum acima, mesma data: subir pelo preview do agente **não** deixa o app no ar

O parágrafo acima ("subido de novo nesta rodada e verificado") estava correto **no instante em que
foi escrito** e enganoso um minuto depois: o servidor iniciado pela ferramenta de preview do agente
é filho do job object da sessão e **morre quando o turno termina**. Confirmado logo em seguida —
porta 3000 sem listener de novo, lista de previews vazia.

**Forma que funciona de verdade** (usada nesta rodada, servidor de pé em `:3000`, PID do `node` do
`next start` = 3544, log em `logs/dashboard.log`): criar o processo pelo **serviço WMI**, cujo pai
é o `WmiPrvSE` e não a sessão do agente —

```
powershell -NoProfile -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd /c cd /d \"<...>\alchemia-news\dashboard\" && npm run start > \"<...>\alchemia-news\logs\dashboard.log\" 2>&1'}"
```

É o mesmo princípio já registrado para job longo no WSL (`setsid`+`nohup`): processo em segundo
plano simples morre em silêncio junto com a sessão que o criou. Sobrevive ao fim da sessão, **não**
sobrevive a reboot/logoff — para isso seria preciso uma Tarefa Agendada com gatilho "ao logon",
que **não** foi criada (decisão do fundador, muda o comportamento da máquina a cada logon).

## Addendum — 2026-08-19: Fase 2 especificada (editais de fomento + programas corporativos + reestruturação do app); repositório GitHub privado confirmado

A pedido do fundador, esta rodada abre a **Fase 2** do setor (já prevista como backlog na spec
fundacional): adicionar ao app editais de fomento à pesquisa e programas corporativos para
startups, usando dois guias de referência fornecidos pelo fundador
(`guia-captacao-programas-corporativos-startups.md`, `canais-editais-fomento-brasil.md`), mais
reestruturação das páginas/navegação com assets interativos, consolidando o `alchemia-news` como
ferramenta de uso da empresa inteira. Spec nova, **em revisão** (Portão de Revisão pendente):
`docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md`. Resumo da decisão de
arquitetura: dois catálogos estáticos novos (`funding_channels.yaml`, `corporate_programs.yaml`),
seguindo exatamente o padrão já validado de `resources.yaml` — **não** uma extensão de `common.Item`
(catálogo de referência tem forma diferente de evento datado que se acumula e deduplica). Deploy com
acesso privado via URL é explicitamente Fase 4, fora do escopo de implementação desta spec, por
pedido do fundador ("posteriormente").

**Achado da auditoria desta rodada, agora resolvido:** esta própria auditoria tinha encontrado
`alchemia-ai/alchemia-news/.git` real (branch `main`, um commit `ccc83d7 "first commit"`, remoto
`github.com/alchemia-solutions/alchemia-news.git`) sem nenhum documento do setor mencionar isso.
**Confirmado pelo fundador nesta conversa:** o repositório é **privado**, e o commit/push inicial
foi ação dele mesmo, fora de qualquer sessão de agente — consistente com a política de git de toda
a empresa (nenhum agente executa comando git de escrita em remoto). Este é o destino de hospedagem
planejado para o deploy da Fase 4 (ainda não executado).

**Spec companheira, setor irmão:** `alchemia-ai/alchemia-bots/docs/specs/
2026-08-19-axel-newsletter-upgrade.md` (também em revisão) — upgrade da mensagem do Axel de
"título+fonte+link" para newsletter completa com resumo estruturado e insights, consumindo o mesmo
dado deste setor (incluindo, quando implementada, a seção de oportunidades desta spec).
`alchemia-bots` ganhou sub-agente dedicado nesta mesma rodada (não tinha nenhum até hoje) — ver
`alchemia-ai/alchemia-agents/.claude/agents/alchemia-bots.md`.

Ver `alchemia-brain/02-Harness/alchemia-news.md` e `alchemia-brain/99-Changelog/2026-08-19.md`.

## Addendum — 2026-08-19 (mais tarde): gate de acesso da diretoria (`dashboard/proxy.ts`), pronto para o deploy privado na Vercel

A pedido do fundador, o deploy privado (Fase 4 da spec acima, antes "posteriormente") começou nesta
mesma data. Decisão: **gate de acesso no próprio app**, não a proteção nativa da Vercel — no plano
Hobby, "Vercel Authentication" só protege URLs de preview, o domínio de produção fica público;
proteger produção de verdade exigiria upgrade para Pro. Gate no app funciona em qualquer plano.

`dashboard/proxy.ts` — Basic Auth via `SITE_AUTH_USER`/`SITE_AUTH_PASSWORD` (variáveis de ambiente,
nunca no código). **Só entra em vigor quando `process.env.VERCEL` existe** (setado automaticamente
pela Vercel) — `npm run dev`/`npm run start` local continuam sem gate, como sempre. **Falha
fechada por design:** se as duas variáveis não estiverem configuradas no projeto Vercel, o site
fica bloqueado para todo mundo até serem definidas — nunca abre por esquecimento de configuração.

**Nota técnica real, específica desta versão do Next.js:** o arquivo se chama `proxy.ts`, não
`middleware.ts` — no Next.js 16, `middleware` foi **deprecado e renomeado para `proxy`** (mesma
API, export renomeado). Confirmado lendo `node_modules/next/dist/docs/.../proxy.md` antes de
escrever qualquer código — o próprio `dashboard/AGENTS.md` deste repositório já avisa para não
confiar em memória de treino sobre a API desta versão.

**Bug real encontrado e corrigido antes de aplicar:** a primeira versão usava travessão (—,
U+2014) dentro do valor do header `WWW-Authenticate` — headers HTTP só aceitam ByteString (Latin1),
e isso quebrava com `500 Internal Server Error` em vez do `401` esperado (`TypeError: Cannot
convert argument to a ByteString`). Trocado por hífen ASCII. **Verificado com servidor de produção
real** (`npm run build` + `npm run start`, `VERCEL=1` simulado), 5 cenários: sem credencial → 401;
credencial errada → 401; credencial certa → 200; `VERCEL=1` sem as variáveis configuradas → 401
(fail-closed); sem `VERCEL` (dev local) → 200 sem credencial nenhuma.

**Dado dinâmico e frescor do deploy:** confirmado que `pipeline/data/*.json`,
`pipeline/data/newsletter/*.md` e os dois catálogos YAML **não estão no `.gitignore`** — são
versionados de propósito. Consequência prática: qualquer `git push` (de código ou só de dado)
dispara um redeploy automático na Vercel (integração padrão GitHub↔Vercel) — não foi necessário
nenhum Deploy Hook novo para a Fase 4 funcionar no nível de "atualizar quando eu quiser".
Atualização automática 3x/dia (sem intervenção manual) não foi implementada nesta rodada — exigiria
automatizar `git push`, e nenhum agente tem permissão de escrever em remoto (regra fixa da
empresa); decisão de automatizar isso (ou não) fica com o fundador.

Ver `alchemia-brain/02-Harness/alchemia-news.md` (a atualizar) e a instrução completa de deploy
dada ao fundador nesta mesma conversa.

## Addendum — 2026-08-20 (performance): três causas reais de lentidão achadas e corrigidas com
## medição real, não suposição

A pedido do fundador ("está muito lento pra abrir as páginas"), medi (`curl -w %{time_total}`,
build de produção local) antes de mudar qualquer coisa. Números reais: `/noticias` **3,1s** por
requisição (repetido, sem melhora — nada cacheava), `/` **2,3s**, `/artigos` **0,85s** (tabela
menor, confirma que o tamanho da tabela era o fator).

**Três causas reais, todas no código introduzido pela integração Supabase (addendum anterior,
mesma data):**
1. `dashboard/lib/supabase.ts` buscava a tabela `items` **inteira** por `kind` em toda
   requisição — `/noticias` trazia as ~2.000 linhas de `news` só para renderizar uma lista, sem
   paginação nem limite.
2. A consulta ordena por `published_date`, mas a migração original só indexou `kind` e
   `collected_at` — todo request fazia sort completo sem índice.
3. Toda página usava `force-dynamic` — zero cache, mesmo pedido repetido em segundos recomeçava
   do zero.

**Corrigido:**
- `supabase/migrations/20260820143134_add_published_date_index.sql` — índice que faltava.
- `fetchItemsByKind()` ganhou limite padrão de 500 itens (antes: sem limite) — `DEFAULT_ITEM_LIMIT`
  em `lib/supabase.ts`. Rótulos de UI mudaram de "Todas (N)" para "Recentes (N)" em `/noticias` e
  `/artigos`, para não alegar completude que deixou de existir.
- `countItemsByKind()` (novo) — contagem exata via `count: 'exact', head: true` (não transfere
  linha nenhuma), usada nos `StatCard` da home para o total continuar real mesmo com a lista
  limitada.
- `getArticles()`/`getNews()`/`getArticlesCount()`/`getNewsCount()` agora passam por
  `unstable_cache` (`next/cache`, ainda suportado nesta versão — ver
  `node_modules/next/dist/docs/.../unstable_cache.md`; substituído por `use cache`/Cache
  Components, que exige flag experimental não habilitada neste projeto), revalidação de 5 min.
  **Achado real ao aplicar:** a primeira tentativa (sem o limite de 500) estourava o teto de 2MB
  por entrada do `unstable_cache` (payload de `news` media 2,39MB) — o cache falhava em silêncio
  e a página voltava a buscar tudo. O limite de 500 resolveu as duas coisas juntas: cabe no cache
  e reduz o tempo de resposta.
- `/` (sem `searchParams`) virou página estática com `revalidate`. `/noticias`/`/artigos` usam
  `searchParams` (filtro por fonte) — isso força renderização dinâmica no Next.js e ignora
  `revalidate` de página inteira, por isso o cache foi aplicado na função de busca em si, não na
  página.

**Medido de novo depois da correção, mesma máquina:** `/noticias` 3,1s → 0,35-0,39s (fria) →
0,11-0,12s (com cache). `/` 2,3s → 0,015-0,019s. `/artigos` 0,85s → ~0,09-0,10s. Confirmado depois
do `git push` do fundador e da migração aplicar de verdade no banco de produção (mesma faixa de
tempo se manteve).

**Achado adicional, corrigido no mesmo ciclo:** a rotina do Baker nunca verificava se a
sincronização com o Supabase estava de fato funcionando — ver addendum de hoje em
`alchemia-ai/alchemia-bots/AGENTS.md`.

**Limitação registrada, não resolvida:** `/noticias` e `/artigos` agora mostram só os 500 itens
mais recentes de cada tipo, não o histórico completo — não há paginação na interface hoje. Se o
fundador quiser acesso ao histórico completo, precisa de paginação real (client-side ou rotas
`?page=N`), não implementada nesta rodada.

## Addendum — 2026-08-20 (Fase 3 do Supabase): expansão completa — todo o dashboard lê do banco,
## nada além de código exige `git push` para atualizar

A pedido do fundador ("quero tudo... atualizado diariamente e depositado no Supabase... sem
precisar commitar nada depois"), a integração que cobria só `articles`/`news` (addendum anterior)
foi expandida para o resto do dashboard.

**`companies_activity` não ganhou tabela própria, de propósito.** Confirmado por leitura direta:
seus itens já são o mesmo formato de `items` (`kind='news'`, `company_slug` preenchido) e já
chegam à tabela via a sincronização existente de `news.json` (o pipeline deposita todo item de
empresa nos dois arquivos locais, de propósito, desde antes desta integração). Criar uma tabela
paralela duplicaria dado sem necessidade — `dashboard/lib/supabase.ts` ganhou
`fetchCompanyActivity()`, um filtro `company_slug IS NOT NULL` sobre a mesma tabela `items`
(índice novo `items_company_slug_idx`).

**Seis novos alvos de sincronização** (migração
`supabase/migrations/20260820145152_expand_remaining_tables.sql`):
- `companies` (espelha `companies.yaml`), `resources` (`resources.yaml`), `funding_channels`
  (`funding_channels.yaml`), `corporate_programs` (`corporate_programs.yaml`), `pipeline_meta`
  (linha única, espelha `meta.json`) — todos sincronizados por `pipeline/sync_supabase.py`
  (reescrito com uma função genérica `_upsert()`/`_sync_catalog()` reaproveitada pelos quatro
  catálogos, `--only <tabela>` para sincronizar um alvo isolado).
- `newsletters` (chave primária `date`) — **não** entra no `sync_supabase.py`: é conteúdo
  interpretativo gerado pela rotina do Axel mais tarde no dia (a etapa 3 do cron roda logo após a
  coleta, antes de a newsletter do dia existir). Sincronizado por um script novo e separado,
  `alchemia-ai/alchemia-bots/scripts/sync_newsletter.py` — ver addendum de hoje em
  `alchemia-ai/alchemia-bots/AGENTS.md`.

**`dashboard/lib/data.ts` — todos os getters que liam arquivo local viraram assíncronos**, lendo
primeiro do Supabase (cacheado 5min via `unstable_cache`, mesmo padrão de `getArticles`/`getNews`)
e **caindo para o arquivo local só se a tabela vier vazia** (rede de segurança: Supabase fora do
ar, ou migração aplicada mas sincronização ainda não rodou hoje). Sete páginas precisaram de
ajuste de `async`/`await` para acompanhar (`empresas`, `empresas/[slug]`, `fomento`, `programas`,
`newsletter`, `sobre`, `bancos-ferramentas`, e a home).

**Verificado, não presumido:** `npm run typecheck` e `npm run build` limpos; as 10 rotas
retornaram `200` num build de produção local, com as tabelas novas **ainda não existindo** no
Supabase real (confirmado pelo próprio erro no console: `Could not find the table
'public.pipeline_meta'`) — prova viva de que a rede de segurança funciona: conteúdo real
(Schrödinger, FINEP) renderizou via fallback para os arquivos locais, nenhuma página quebrou.
`pipeline/sync_supabase.py --dry-run` confirmou as contagens reais antes de qualquer escrita: 2.366
itens, 20 empresas, 9 recursos, 28 canais de fomento, 24 programas.

**Pendente, depende do fundador:** a migração `*_expand_remaining_tables.sql` só aplica de verdade
depois do próximo `git push` (integração GitHub↔Supabase, mesmo mecanismo já usado para o índice
de `published_date`). Até lá, todas as sete tabelas/consultas novas operam 100% via a rede de
segurança de arquivo local — comportamento correto, não um bug.

Ver `alchemia-ai/alchemia-bots/AGENTS.md` (addendum de hoje, script `sync_newsletter.py` e
atualização da rotina do Axel).

## Addendum — 2026-08-20 (mais tarde ainda): `/newsletter` virou lista navegável por data

A pedido do fundador ("organizar por data e horário... não ter o texto inteiro no começo, só
quando clicar"), `/newsletter` deixou de mostrar só a edição mais recente com o conteúdo inteiro
exposto.

- `/newsletter` — lista todas as edições (`getNewsletters()`, tabela `newsletters` inteira — poucas
  linhas, uma por dia, sem necessidade de paginação como `items`), cada uma como card com data,
  a linha `_Atualizado às HH:MM..._` já embutida no markdown como subtítulo, e uma prévia curta
  (`previewNewsletter()`, ~220 caracteres de texto corrido, markdown removido).
- `/newsletter/[date]` (rota nova) — conteúdo completo de uma edição específica, só carregado ao
  clicar. `notFound()` para data que não existe.
- Filtro por "horário" não foi implementado como campo estruturado — a tabela `newsletters` guarda
  uma linha por **dia** (o conteúdo acumula as três rodadas do dia num só documento, por decisão de
  spec anterior), não uma por execução. O horário de cada atualização já fica visível na linha
  `_Atualizado às..._` de cada edição, mas não é uma coluna consultável separadamente — se o
  fundador quiser filtrar por horário de verdade, precisa de uma decisão de schema nova (guardar
  granularidade por execução, não por dia), não implementada nesta rodada.

**Verificado com servidor de produção real:** `/newsletter` → 200 com link pra edição de hoje;
`/newsletter/2026-08-20` → 200 com "Insight Alchemia" renderizado; `/newsletter/1999-01-01` → 404.

## Addendum — 2026-08-20 (fechamento): migração aplicada de verdade, sincronização real rodou,
## bug real encontrado e corrigido — as sete tabelas estão populadas e o site lê tudo do banco

Depois do `git push` do fundador, a integração GitHub↔Supabase aplicou
`20260820145152_expand_remaining_tables.sql` de verdade. Rodei `pipeline.sync_supabase` sem
`--dry-run` pela primeira vez contra as tabelas novas.

**Bug real encontrado e corrigido no processo:** o upsert de `funding_channels` falhava —
`null value in column "requires" violates not-null constraint`. Causa: quando um canal não tem
`requires`/`programs` no YAML (ex.: `sebrae`), `entry.get(col)` devolve `None` em Python, que vira
`null` **explícito** no payload JSON — e um `null` explícito sobrescreve o `default '{}'` da
coluna (o default só vale quando a chave está ausente do payload, não quando vem `null`).
Corrigido em `pipeline/sync_supabase.py` (`_ARRAY_DEFAULT_COLUMNS`): `None` vira `[]` antes de
montar a linha, só para essas duas colunas array/jsonb.

**Verificado, não presumido — sincronização real completa, todos os sete alvos:**
`items` 2.366, `companies` 20, `resources` 9, `funding_channels` 28, `corporate_programs` 24,
`pipeline_meta` 1 (singleton), `newsletters` 1 (edição de hoje, sincronizada manualmente já que a
rotina do Axel ainda não tinha rodado com o passo novo). `npm run build` depois disso: **zero**
erro de "table not found" no console (antes reportava `companies`/`pipeline_meta` ausentes).

**Teste final, servidor de produção real, as 11 rotas do dashboard:** todas `200`, todos os tempos
abaixo de 0,3s (a maioria abaixo de 0,1s) — confirma que a expansão completa está no ar e
performática, não só "aplicada sem erro".

Nenhuma credencial foi exibida em nenhum momento — a `SUPABASE_SERVICE_ROLE_KEY` foi lida direto
da variável de ambiente de usuário do Windows via PowerShell (`[Environment]::GetEnvironmentVariable`)
para cada execução pontual, nunca impressa, nunca escrita em arquivo.

## Addendum — 2026-08-19 (implementação): Fase 1 da spec de fomento/programas entregue —
## dois catálogos novos, duas rotas novas, três assets interativos, newsletter (leitura), sidebar
## em 3 grupos

Continuação da mesma data — a spec `docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md`
(Portão de Revisão `[x]` aprovado pelo fundador) teve sua Fase 1 implementada nesta rodada. Números
abaixo vêm de leitura real (`yaml.safe_load` + contagem de entradas), `npm run typecheck`/
`npm run build` reais e `curl` real contra um servidor de produção subido só para verificação
(porta 3100, parado ao final — este setor segue sem serviço persistente, decisão de 2026-08-17
inalterada) — nada estimado.

**Dois catálogos novos, estáticos, curados a partir dos dois guias do fundador** (transcrição em
palavras próprias, nunca cópia extensa verbatim — risco 1 da spec):

- `pipeline/config/funding_channels.yaml` — **28 entradas** (`federal`: 13 · `internacional`: 5 ·
  `estadual_sp`: 3 · `saude`: 3 · `universidade_ict`: 2 · `fundacao_privada`: 2), cobrindo todo o
  mínimo exigido pelo Critério de Sucesso (CNPq, CAPES, FINEP, MCTI, EMBRAPII, BNDES, Sebrae/
  InovAtiva, 4 agências reguladoras, FAPESP com 12 modalidades listadas em `programs`, USP/AUSPIN,
  PROADI-SUS com os 7 hospitais, Serrapilheira, Horizon Europe, NIH/Fogarty) e mais. `priority_alchemia`:
  4 `alta` + 4 `media` + 20 `complementar` — herdado literalmente da seção 9 do guia
  (`canais-editais-fomento-brasil.md`); todo item sem classificação explícita naquela seção recebe
  `complementar` com nota dizendo isso, nunca uma prioridade inventada.
- `pipeline/config/corporate_programs.yaml` — **24 entradas** (`cloud_credits`: 6 ·
  `hub_corporativo`: 5 · `accelerator_equity`: 4 · `accelerator_no_equity`: 4 ·
  `habitat_nacional`: 3 · `saas_discount`: 2), cobrindo o mínimo exigido (Google for Startups
  Cloud, AWS Activate, Microsoft Founders Hub, NVIDIA Inception, CNPEM/LNBio, SUPERA, Eretz.bio,
  Cubo Itaú, InovAtiva Brasil) e mais. `priority_alchemia`: 4 `alta` + 3 `media` + 17
  `complementar` — mapeamento explícito dos 3 blocos da seção 10 do guia
  (`guia-captacao-programas-corporativos-startups.md`): "Prioridade máxima"→`alta`, "Prioridade
  alta"→`media`, "Complementares"→`complementar` (documentado no cabeçalho do próprio YAML, para
  não perder essa distinção); itens fora da seção 10 recebem `complementar` com nota própria.

**`dashboard/lib/types.ts`**: `FundingChannel`/`CorporateProgram` (+ tipos auxiliares
`FundingScope`/`CorporateProgramCategory`/`CorporateProgramRegion`/`PriorityAlchemia` e 4 mapas de
label) — interfaces próprias, deliberadamente **não** um union type de `ItemKind`, conforme a
decisão de arquitetura da spec.

**`dashboard/lib/data.ts`**: `getFundingChannels()`/`getCorporatePrograms()`, mesmo padrão
`readYamlSafe` de `getResources()`; `getLatestNewsletter()` novo (lê `pipeline/data/newsletter/
AAAA-MM-DD.md` mais recente por nome de arquivo, `null` se o diretório não existir/estiver vazio —
sem quebrar a rota).

**Rotas novas** (`dashboard/app/fomento/page.tsx`, `dashboard/app/programas/page.tsx`,
`dashboard/app/newsletter/page.tsx`), mesmo padrão de `bancos-ferramentas/page.tsx`
(`force-dynamic`, agrupamento, `PageHeader`) + seção "★ Recomendado para a Alchemia" (itens com
`priority_alchemia: alta`) em cada uma das duas primeiras.

**Três componentes interativos novos**, todos client components com estado em `localStorage`,
nenhum backend novo:

- `components/OpportunityFilterBar.tsx` — filtro por categoria/escopo + prioridade + busca
  textual. Decisão de design não prevista originalmente na spec, registrada aqui porque molda a
  arquitetura: Server Components não podem passar **funções** como prop para Client Components (a
  fronteira RSC só serializa dado + elementos React já renderizados), então este componente não
  recebe um "render prop" de cartão — cada página server-renderiza o cartão de cada item e passa
  metadado de filtragem (`category`/`priority`/`searchText`) junto com o nó já renderizado
  (`node: React.ReactNode`); o componente só decide, no cliente, quais nós mostrar/esconder.
- `components/DocumentChecklist.tsx` — os 12 itens da seção 11 do guia de programas corporativos
  ("Prepare uma vez, reutilize sempre"), uma chave só de `localStorage`
  (`alchemia-news:document-checklist`), deliberadamente compartilhada entre `/fomento` e
  `/programas` — é preparo único da empresa, não algo por página.
- `components/StatusTracker.tsx` — 5 estados (não aplicado/em preparação/submetido/aprovado/
  rejeitado) por `slug` de oportunidade, `localStorage` chaveado por slug
  (`alchemia-news:opportunity-status:<slug>`), embutido em cada cartão via
  `FundingChannelCard.tsx`/`CorporateProgramCard.tsx` (dois componentes server-safe novos, sem
  `'use client'`, no mesmo espírito de `ItemCard.tsx` já existente).

**`components/MarkdownLite.tsx`** (novo, não listado na spec original mas necessário para a rota
`/newsletter`): renderizador de Markdown mínimo, **sem dependência nova** (nenhum pacote npm
adicionado) — suficiente para títulos, listas, negrito/itálico, links, `código` e `---`; não é um
parser CommonMark completo. Decisão deliberada: a spec não especifica o formato exato que
`alchemia-bots` vai gravar em `pipeline/data/newsletter/*.md`, e este setor não tem acesso de
escrita a `alchemia-ai/alchemia-bots/` para coordenar antecipadamente — um parser mínimo e
sem-dependência é o que reduz risco de quebra por formato inesperado, sem acoplar a um pacote
externo para um caso de uso simples.

**`components/Sidebar.tsx`** reorganizado em 3 grupos com `<h3>` de seção — "Inteligência de
Mercado" (Notícias, Artigos & Papers, Empresas, Bancos & Ferramentas), "Captação de Recursos"
(Fomento, Programas), "Comunicação" (Newsletter) — mais "Painel" como item de topo (fora dos
grupos, antes deles) e "Sobre" como item de rodapé (fora dos grupos, depois deles), preservando a
posição visual que "Sobre" já tinha. **Nota de nomenclatura:** a spec original (seção "Estado
Alvo", ponto 5) previa só 2 grupos, sem "Comunicação"/Newsletter — o prompt de implementação desta
rodada pediu explicitamente 3 grupos incluindo Newsletter; tratado como extensão explícita da spec
pelo fundador nesta mesma conversa, não como divergência não resolvida.

**`app/sobre/page.tsx`**: nova seção "Fomento e programas corporativos" descrevendo os dois
catálogos como curadoria estática (não coletada), com o qualificador "direcional — confirmar
sempre na fonte/portal oficial"; parágrafo de abertura reescrito para descrever o app como
ferramenta da **empresa inteira**, não só do setor que o mantém; duas linhas novas em "O que este
painel NÃO faz (ainda)" cobrindo o escopo real do `localStorage` (checklist/tracker são por
navegador, não multiusuário) e da rota `/newsletter` (somente leitura, populada por outro setor).

**Verificação real, não presumida:**

- `npm run typecheck` — limpo, exit 0, zero erro.
- `npm run build` — `Compiled successfully in 15.1s`; as **10 rotas de página** do App Router
  (`/`, `/artigos`, `/bancos-ferramentas`, `/empresas`, `/empresas/[slug]`, `/fomento`,
  `/newsletter`, `/noticias`, `/programas`, `/sobre`) todas `ƒ` (server-rendered on demand) — a
  condição para refletir o pipeline/YAML sem rebuild, preservada.
- Servidor de produção subido só para este teste (`next start -p 3100`, parado ao final): as
  **9 rotas de página estática** (excluindo a dinâmica `/empresas/[slug]`, inalterada nesta rodada)
  responderam **200** via `curl` real.
- **Critério de Sucesso "dado lido do YAML, não hardcoded" verificado ao vivo**: editado
  temporariamente `name: "CNPq"` → `"CNPq-VERIFICACAO-TEMP"` em `funding_channels.yaml` com o
  servidor já no ar (sem restart) — a mudança apareceu em `/fomento` na requisição seguinte;
  revertido e reconfirmado (`grep` mostrando `CNPq-VERIFICACAO-TEMP` some, `CNPq` volta), YAML
  re-parseado depois (28 entradas, `cnpq.name == "CNPq"`) para confirmar que a edição/reversão não
  corrompeu o arquivo.
- Checklist/tracker testados por leitura de código + `localStorage`, não por clique manual em
  navegador real nesta sessão (harness sem acesso a browser interativo) — a lógica de
  leitura/escrita (`JSON.stringify`/`JSON.parse`, chave por slug, placeholder de mesma altura
  pré-hidratação) foi revisada linha a linha, mas o Critério de Sucesso "testado manualmente:
  clicar, marcar, recarregar" da spec **não foi exercitado por clique humano nesta rodada** — fica
  como verificação recomendada ao fundador antes de considerar este item 100% fechado.
- `alchemia-ai/alchemia-agents/harness/check_runtime_integrity.py` — **OK** (`14 agentes/20 skills`
  Claude e Codex, 6 `AGENTS.md` canônicos, mirror íntegro, configs sem token literal) — nenhum
  arquivo de harness foi tocado nesta rodada; o número de agentes subiu para 14 por trabalho
  paralelo de outra sessão (`alchemia-bots`, ver addendum acima), não por esta implementação.

**Não implementado nesta rodada, por escopo explícito da Fase 1** (nada disso é pendência
silenciosa — todos já listados como Fase 2/3/4 na spec): monitoramento ativo de "chamadas abertas"
com timestamp de verificação; persistência multiusuário do tracker de status; deploy privado com
URL. `pipeline/data/newsletter/` segue vazio nesta sessão (setor `alchemia-bots` popula em
paralelo) — a rota `/newsletter` foi verificada apenas no estado vazio ("Nenhuma newsletter
publicada ainda."), nunca com conteúdo real, porque nenhuma edição existia no momento do teste.

**Arquivos criados:** `pipeline/config/funding_channels.yaml`, `pipeline/config/corporate_programs.yaml`,
`dashboard/app/fomento/page.tsx`, `dashboard/app/programas/page.tsx`, `dashboard/app/newsletter/page.tsx`,
`dashboard/components/OpportunityFilterBar.tsx`, `dashboard/components/DocumentChecklist.tsx`,
`dashboard/components/StatusTracker.tsx`, `dashboard/components/FundingChannelCard.tsx`,
`dashboard/components/CorporateProgramCard.tsx`, `dashboard/components/MarkdownLite.tsx`.
**Arquivos editados:** `dashboard/lib/types.ts`, `dashboard/lib/data.ts`,
`dashboard/components/Sidebar.tsx`, `dashboard/app/sobre/page.tsx`, este arquivo (`AGENTS.md`).

## Addendum — 2026-08-20: integração Supabase para `articles`/`news` -- elimina a espera de
## redeploy, mas fica em três pontas reais até o fundador completar a parte dele

A pedido do fundador, o dashboard deixa de depender de `git push` + redeploy para refletir uma
coleta nova, para `articles`/`news` (escopo desta rodada -- empresas/editais/programas/newsletter
continuam em arquivo, decisão do fundador). Arquitetura: Supabase roda **em paralelo** aos JSONs
locais, não no lugar deles -- `pipeline/run_all.py` continua escrevendo `articles.json`/`news.json`
exatamente como antes (nada mudou lá), e uma etapa nova espelha o resultado já mesclado para uma
tabela `items` (Postgres gerenciado, projeto `texszxmvolbiduhrrdsq`); o dashboard passa a ler
`articles`/`news` de lá, não mais do arquivo.

**🔴 Achado real desta rodada: o MCP do Supabase, que o fundador configurou via
`claude mcp add --scope project` dentro deste diretório, nunca carregou nesta sessão.** MCP
projeto-scoped é lido do `.mcp.json` do diretório onde a sessão da Claude Code abre -- esta sessão
abriu na raiz da empresa (`Alchemia LTDA/`), não aqui, então o `alchemia-news/.mcp.json` nunca foi
lido. Confirmado por busca direta nas ferramentas MCP carregadas na sessão: zero ferramenta
`mcp__supabase__*` disponível. Consequência prática: **nenhuma tabela foi criada/verificada ao vivo
no Supabase nesta rodada**, e a chave publishable/anon real (pública por design, mas cujo valor
não foi fornecido nem pôde ser lido via MCP) não pôde ser preenchida em `.env.local`. Para uma
próxima rodada usar o MCP de verdade, a sessão precisa abrir com `alchemia-ai/alchemia-news/` como
diretório de projeto (ou o `.mcp.json` precisa ser replicado na raiz, mesmo padrão já usado para
`obsidian-alchemia-brain`/`hermes`).

**O que foi entregue, verificado sem o MCP:**

- `supabase/migrations/20260820033359_create_items_table.sql` -- tabela `items` (schema revisado
  do rascunho do fundador, mesmas colunas), RLS habilitado, policy de leitura pública, sem policy
  de escrita para `anon` (só `service_role`, que ignora RLS, escreve). **Não aplicada** -- a
  integração GitHub↔Supabase já configurada aplica migrações automaticamente ao `git push` para
  `main` (lendo esta mesma pasta `supabase/`); até lá, ou até uma sessão com o MCP real rodar a
  migração diretamente, a tabela não existe no projeto.
- `pipeline/sync_supabase.py` -- upsert em lote via REST (`requests`, sem driver novo),
  `on_conflict=dedupe_key`, `Prefer: resolution=merge-duplicates`. Lê `SUPABASE_SERVICE_ROLE_KEY`
  de `os.environ` (nunca hardcoded); sem ela, pula com aviso e sai 0 -- nunca derruba a cadeia.
  **Testado de verdade com `--dry-run` contra o dado real local:** 2.284 itens sincronizariam
  (312 artigos + 1.972 notícias). Sem a tabela existir e sem a `service_role` key, a escrita real
  no Supabase **não foi exercitada** nesta rodada.
- `alchemia-ai/alchemia-bots/scripts/run_alchemia_news.cmd` ganhou a **Etapa 3**, chamando o script
  acima com log próprio (`cron-supabase.log`, já coberto pelo `.gitignore` existente
  `pipeline/logs/*.log`). Mesma politica de falha das etapas 1/2: cada etapa roda mesmo se a
  anterior falhou, e só a Etapa 1 (coleta) manda no código de saída da cadeia.
- `dashboard/lib/supabase.ts` (novo) + `dashboard/lib/data.ts` (`getArticles()`/`getNews()`
  viraram `async`, leem `fetchItemsByKind()` em vez de `fs.readFileSync`) -- paginado em blocos de
  1000 linhas (limite padrão do PostgREST por resposta), porque `news` já tem 1.972 itens hoje e só
  cresce. `@supabase/supabase-js` instalado como dependência **pinada** (`2.112.3`, sem `^`, mesma
  convenção do resto do `package.json`) via `npm install --save-exact`.
- Os 4 call sites (`app/page.tsx`, `app/artigos/page.tsx`, `app/noticias/page.tsx`,
  `app/bancos-ferramentas/page.tsx`) viraram `async function` com `await`/`Promise.all`.

**Bug real, pré-existente, encontrado e corrigido no caminho (fora do escopo original, mas nos
mesmos arquivos que esta rodada já tornou `async`):** `/noticias` e `/artigos` acessavam
`searchParams.fonte` de forma síncrona -- no Next.js 16, `searchParams` é uma `Promise`, mesma
classe do bug já documentado neste arquivo (addendum 2026-08-17) para `/empresas/[slug]`. Gerava
warning real no dev server (`sync-dynamic-apis`), nunca corrigido porque ninguém tinha reaberto
esses dois arquivos desde a migração do Next. Corrigido (`searchParams: Promise<{ fonte?: string
}>`, `await searchParams`); verificado que o warning some no log do dev server ao vivo.

**Verificação real feita, e o que ficou de fora por depender do fundador:**

- `npm run typecheck` e `npm run build` limpos (as 10 rotas de página seguem `ƒ`, condição para
  refletir dado novo sem rebuild -- preservada).
- **Servidor de dev do próprio fundador, já rodando em `:3000` de uma sessão anterior, não foi
  derrubado** -- verificado que era de fato este dashboard antes de qualquer ação, e usado como
  alvo de verificação (hot reload captou as mudanças sozinho). As 4 rotas tocadas responderam
  `200`; o log do dev server confirmou o fallback gracioso (`"Supabase não configurado ...
  retornando lista vazia"`) em vez de qualquer erro 500 -- comportamento esperado, já que
  `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` ainda não existem em nenhum
  `.env.local` real.
- `dashboard/.env.local.example` criado (URL real do projeto, que não é segredo; placeholder para a
  publishable key). **Não escrevi `.env.local` real** -- não tenho o valor da chave.

**Três coisas que só o fundador pode fechar, nessa ordem:**

1. Aplicar a migração -- via `git push` (a integração já cuida do resto) ou rodando a sessão com o
   MCP do Supabase carregado (cwd em `alchemia-ai/alchemia-news/`) e aplicando direto.
2. Preencher `dashboard/.env.local` (copiar de `.env.local.example`) com a publishable key real, e
   configurar as mesmas duas variáveis (`NEXT_PUBLIC_SUPABASE_URL`/`..._PUBLISHABLE_KEY`) no
   projeto Vercel quando o deploy acontecer.
3. Configurar `SUPABASE_SERVICE_ROLE_KEY` como variável de ambiente de usuário do Windows (mesmo
   padrão já usado para `OBSIDIAN_MCP_TOKEN`) -- sem ela, a Etapa 3 do cron segue pulando
   silenciosamente, e a tabela nunca recebe dado novo mesmo depois de criada.

Até os três passos acima, o dashboard mostra `articles`/`news` vazios (fallback gracioso, não
erro) -- os JSONs locais continuam existindo e corretos, só não são mais a fonte que o dashboard lê.

## Addendum — 2026-08-20 (verificação visual real): dois bugs encontrados e corrigidos ao abrir o
## app renderizado com dado real do Supabase, nenhum deles pego pelo `typecheck`/`build`

A pedido do fundador ("Confere se abriu certinho no navegador"), depois de todas as correções de
performance/expansão Supabase já registradas nos addenda acima, o app foi de fato aberto num
navegador (não só compilado) contra o Supabase real, produção local (`npm run start`, porta 3300,
credenciais de teste). Dois bugs reais só visíveis olhando a tela renderizada, nenhum dos dois
pego por `npm run typecheck`/`npm run build` (ambos passam limpos nos dois casos, antes e depois):

1. **Data da newsletter aparecia um dia atrás.** `/newsletter` mostrava "19 de ago. de 2026" para a
   edição cuja linha no Supabase tem `date = '2026-08-20'` (confirmado por query direta -- só essa
   linha existe). Causa: `new Date("2026-08-20")` em JS interpreta string `YYYY-MM-DD` como
   meia-noite UTC; formatado no timezone do servidor (Brazil/East, UTC-3), rola um dia para trás.
   Corrigido em `formatDate()` (`dashboard/lib/data.ts`) com parsing manual de data-sem-hora usando
   o construtor `Date` em componentes locais (`new Date(ano, mes-1, dia)`), que não sofre conversão
   de timezone. Mesma função é usada em todo o app -- não é um fix isolado da newsletter.
2. **StatCard "Menções de Empresas" da home mostrava o teto de busca (500), não o total real.**
   `companiesActivity.length` (a lista, limitada por `DEFAULT_ITEM_LIMIT` em `lib/supabase.ts`) era
   usado como se fosse a contagem total -- mesma classe de erro que os addenda anteriores já tinham
   corrigido nos textos "Recentes (N)" de `/noticias` e `/artigos`, mas esta StatCard específica
   tinha ficado de fora daquela correção. Corrigido com `countCompanyActivity()`
   (`dashboard/lib/supabase.ts`, `count: 'exact', head: true`, sem transferir linha nenhuma) +
   `getCompaniesActivityCount()` (`dashboard/lib/data.ts`, cacheado 5 min via `unstable_cache`,
   mesmo padrão dos demais getters) + wiring em `app/page.tsx`. Verificado ao vivo: **988**, não
   500.

**O padrão que vale registrar:** os dois bugs só existiam porque a UI já filtra/soma corretamente
os dados retornados -- o problema estava em qual dado o Supabase devolvia (dado vs. contagem,
UTC vs. local), algo que `tsc`/`next build` não têm como pegar porque o código está tipado
corretamente e compila -- só o valor em runtime está errado. Reforça a mesma lição já registrada
neste diretório e em `alchemia-ai/alchemia-athanor/CLAUDE.md` (2026-08-09): verificação de
tipo/build prova ausência de um tipo de erro, nunca corretude visual -- só abrir a tela renderizada
pega esta classe.

**Pendência real, não fechada nesta rodada:** as duas correções estão só localmente, verificadas
contra um servidor de produção local (`npm run start`, não o dev server) -- ainda não passaram por
`git push`, então a Vercel de produção segue servindo a versão com os dois bugs até o fundador
commitar. Nenhum commit/push foi feito por este agente (convenção da empresa, `CLAUDE.md`/`AGENTS.md`
raiz -- o fundador sempre faz o push).

## Addendum — 2026-08-21: a casca do dashboard vira responsiva; faixa de estado do pipeline;
## contraste e teclado corrigidos — auditoria com medição real antes e depois

A pedido do fundador ("panorama geral... UX/UI do nosso aplicativo"), uma auditoria mediu o app
renderizado em vez de ler só o código. Quatro defeitos reais, nenhum deles pego por
`npm run typecheck` nem por `npm run build` — os dois passavam limpos antes e depois de todas as
correções abaixo.

**🔴 O app era inutilizável em celular.** O `<aside>` era `fixed w-60` e o `<main>` era `ml-60`,
**sem nenhuma variante responsiva** — as grades internas das páginas já eram responsivas desde
sempre (`sm:`/`md:`/`lg:`), só a casca nunca tinha sido adaptada. Medido num viewport de 375 px:
**71 px** de coluna de conteúdo (375 − 240 de sidebar − 64 de `px-8`), com a sidebar cobrindo 64 %
da tela e **sem forma de fechá-la**. O app esteve publicado nesse estado.

Corrigido: `components/Sidebar.tsx` virou gaveta abaixo de `md` (768 px) — barra de topo `sticky`
com botão, `-translate-x-full` → `translate-x-0`, fundo escuro clicável, `Esc` fecha e devolve o
foco ao botão, scroll do body travado enquanto aberta, e fechamento automático ao navegar (sem
isso, tocar num link no celular carregava a página nova com a gaveta por cima). `app/layout.tsx`
passou a `md:ml-60` com padding progressivo (`px-4 sm:px-6 md:px-8`).

**Medido depois, no app renderizado, em quatro larguras:**

| Viewport | Conteúdo antes | Conteúdo depois | Sidebar | Overflow horizontal |
|---|---|---|---|---|
| 375 px | **71 px** | **343 px** | gaveta | nenhum |
| 414 px | ~110 px | **382 px** | gaveta | nenhum |
| 768 px | 464 px | 464 px | fixa | nenhum |
| 1280 px | 976 px | 976 px | fixa | nenhum |

Estados da gaveta verificados por interação real (não por leitura): fechada `transform` −240 →
aberta `0`; `aria-expanded` alterna; `aria-label` alterna; fundo aparece/some; `body` trava e
destrava o scroll; `Esc` fecha **e** devolve o foco ao botão. **Nota de método:** a primeira
tentativa de medir isso por `<iframe>` deu resultado errado (reportava a gaveta parada em −240
mesmo aberta) — a medição válida foi feita no documento de topo. Instrumentação também erra;
quando o número contradiz o comportamento esperado, desconfie da medição antes do código.

**🟡 Contraste abaixo do mínimo em 17 elementos.** `text-slate-600` (`#475569`) media **2,57 : 1**
sobre o navy-950 — nos rótulos que organizam a navegação inteira ("Inteligência de Mercado",
"Captação de Recursos", "Comunicação"), a 10 px, ou seja **57 % do mínimo** de 4,5 : 1.
`text-slate-500` (`#64748b`) media **4,09 : 1** em mais 17 ocorrências (rótulos de `StatCard`,
listas de fonte). Todos os `text-slate-500`/`text-slate-600` de `app/` e `components/` subiram para
`text-slate-400`. Preservados de propósito: `border-slate-500`, `bg-slate-500` e
`decoration-slate-600`, que não são cor de texto. **Reauditado no app renderizado: zero
reprovações.**

**🟡 Navegação por teclado praticamente sem suporte.** Só `OpportunityFilterBar` e `StatusTracker`
definiam qualquer estilo de foco; os 17 links da sidebar dependiam do contorno padrão do navegador,
que sobre o navy quase não aparece. Adicionados em `app/globals.css`: regra global
`:focus-visible` (e não `:focus` — não desenha anel em clique de mouse) e `.skip-link` para pular a
navegação, agora o primeiro elemento focável de toda página. Os grupos da sidebar passaram de
`<h3>` para `role="group"` + `aria-labelledby`: são rótulos de agrupamento de navegação, não seções
do documento, e entrar no outline de headings competia com o `<h1>` de cada página sem nunca haver
um `<h2>` entre eles. O `<aside>` e o `<nav>` ganharam rótulo acessível; ícones decorativos ganharam
`aria-hidden`.

**🆕 `components/PipelineHealthBanner.tsx` — faixa de estado do pipeline** (metade "estado" do
alarme; a metade "evento" é a mensagem do Axel no Discord, ver `alchemia-ai/alchemia-bots/AGENTS.md`
addendum de hoje). Montada no layout raiz, vale em todas as rotas. **Silenciosa quando está tudo
bem** — não ocupa espaço permanente para dizer "ok". Três estados: coleta ≥ 8 h (âmbar), ≥ 14 h
(vermelho, dois ciclos perdidos), e coletor com `error` na última coleta (âmbar).

O limiar de 8 h é deliberado e corrige um buraco real: a coleta roda a cada 6 h, e a tolerância de
~7 h do passo 3b da rotina do Baker é **maior que o intervalo entre ciclos** — um ciclo inteiro
perdido passava dentro da janela sem alarme, que foi exatamente o que aconteceu em 21/08. O limiar
precisa ser maior que um intervalo (senão alarme falso entre ciclos normais) e menor que dois.

Os dois estados foram verificados **forçando o relógio de avaliação** (+9 h e +15 h) contra o app
real e conferindo o HTML servido: âmbar com "A coleta está atrasada", vermelho com "A coleta não
roda há mais de dois ciclos". Alteração de teste revertida em seguida (`assess(meta, Date.now())`).

**🟢 `AutoRefresh` de 60 s → 300 s.** O intervalo de 60 s era herdado de quando `lib/data.ts` lia
os JSONs do disco a cada requisição, quando um tick barato podia de fato trazer dado novo. Desde a
migração para o Supabase os getters passam por `unstable_cache` com `revalidate: 300` — quatro em
cada cinco ticks não tinham como encontrar nada, e na Vercel cada um é uma invocação de função
(~1.440/dia por aba aberta). A 300 s o comportamento visível é idêntico (o dado muda 3x/dia) com
~80 % menos invocações.

**Verificado ao final:** `npm run typecheck` limpo · `npm run build` limpo, com as 11 rotas
preservando `ƒ` (exceto `/` e `/_not-found`, estáticas com `revalidate` de 5 min) e o
`Proxy (Middleware)` do gate de acesso intacto · as 9 rotas de página respondendo 200.

**⏳ NÃO corrigido nesta rodada, por depender de decisão do fundador:** `/artigos` continua
entregando **3,36 MB** de HTML e `/noticias` **1,94 MB**, porque renderizam a lista inteira sem
paginação (491 e 500 cartões). O teto de 500 itens de 2026-08-20 resolveu o custo *da consulta* ao
Supabase, mas o custo de *renderizar e transmitir* continuou inteiro. A correção certa depende de
saber se essas rotas precisam do histórico completo (paginação real, `?page=N`) ou se 50 por página
com busca basta — pergunta aberta com o fundador, não decisão de agente.

**Nenhum `git push` foi executado.** As correções estão locais e verificadas; a Vercel de produção
segue servindo a versão anterior até o fundador commitar.

Ver `alchemia-ai/alchemia-bots/AGENTS.md` (addendum 2026-08-21) e
`alchemia-ai/alchemia-agents/docs/specs/2026-08-21-frontend-quality-gate.md` (spec nova, Portão de
Revisão **não** marcado).

### Continuação — 2026-08-21: paginação entregue; as 9 rotas passam nos limiares de peso e tempo

O addendum acima registrava `/artigos` e `/noticias` como **não corrigidos**, por dependerem de uma
decisão do fundador. Ele respondeu "corrija também todos esses problemas encontrados", então a
paginação foi implementada — com uma parte da decisão original deliberadamente **não** tomada
(abaixo).

`components/Pagination.tsx` (novo) — `?page=N`, **60 itens por página**, server component: nenhum
JavaScript de cliente para navegar, e funciona com JS desabilitado. Cada página tem URL própria e
compartilhável; o filtro `?fonte=` é preservado; a janela de links é curta (nunca imprime 40
números). `paginar()`/`lerPagina()` são funções puras, e `lerPagina` tolera `?page=` ausente, vazio,
não-numérico ou negativo — tudo vira 1.

**Medido depois, morno, mesma metodologia de antes:**

| Rota | Antes | Depois |
|---|---|---|
| `/artigos` | 3.359.639 B · 3,159 s | **391.149 B · 0,335 s** |
| `/noticias` | 1.938.436 B · 2,486 s | **269.392 B · 0,315 s** |

As 9 rotas ficam agora **entre 23 KB e 391 KB** e **entre 0,041 s e 0,335 s** — todas dentro dos
limiares F5 (≤ 500 KB) e F6 (≤ 1,0 s) do `frontend-quality-gate`. Verificado além do peso:
`aria-label="Paginação"` como landmark, links reais no HTML, `?fonte=PubMed&page=2` preservando o
filtro, e 120 ocorrências de `.alchemia-card` por página (60 itens × 2).

**O que a paginação deliberadamente NÃO resolveu.** `fetchItemsByKind` mantém
`DEFAULT_ITEM_LIMIT = 500`, então `/noticias` pagina sobre os **500 mais recentes**, não sobre os
2.103 do banco. Os rótulos seguem dizendo "Recentes (N)", nunca "Todos" — é honestidade, não
omissão. Subir o teto reintroduz o estouro do limite de 2 MB por entrada do `unstable_cache`
documentado no addendum de 2026-08-20 acima. **Qual dos dois (histórico completo com outra
estratégia de cache, ou 500 mais recentes com busca) é decisão de produto do fundador** — um agente
não a toma sozinha, mesmo com "corrija tudo".

**Estado do alvo, verificado pelo gate:** `docs/qc/2026-08-21-frontend-quality-dashboard.md`,
addendum de hoje — 🔴 0 · 🟡 0 · 🟢 0 · passa em F1–F10.
