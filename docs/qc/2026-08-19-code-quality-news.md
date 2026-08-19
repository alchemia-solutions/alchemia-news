# Code Quality Gate — alchemia-news — 2026-08-19

**Escopo revisado:** primeira passada real deste setor (nunca auditado antes — ver
`alchemia-ai/REVIEW.md`, linha "nunca auditado" até hoje).

- `pipeline/collectors/common.py` (365 linhas) — utilidades compartilhadas (HTTP, dedupe,
  normalização de URL, merge de estado).
- `pipeline/run_all.py` (148) — orquestrador dos 9 coletores.
- `pipeline/digest.py` (157) — digest para o cron `--no-agent` do Hermes.
- `pipeline/research_export.py` (980) — exportação para `alchemia-science`/`alchemia-library`
  (radar + colheita de PDF open access), incluindo o mecanismo de lock (`trava_colheita`).
- Os 8 coletores individuais: `pubmed_collector.py`, `biorxiv_collector.py`, `arxiv_collector.py`,
  `chemrxiv_collector.py`, `scielo_collector.py`, `feed_collector.py` (Nature + newsletters),
  `googlenews_collector.py`, `companies_collector.py`.
- `pipeline/requirements.txt`.
- `dashboard/lib/data.ts`, `dashboard/lib/types.ts`, `dashboard/scripts/copy-pipeline-data.js`,
  `dashboard/app/page.tsx`, `dashboard/app/empresas/page.tsx`, `dashboard/package.json`
  (`overrides`).
- `.gitignore` + `git status`/`git ls-files` (o repositório é real, `.git` confirmado, privado por
  decisão do fundador registrada em `AGENTS.md`).
- `AGENTS.md`/`CLAUDE.md` do setor, lidos primeiro para entender a arquitetura real antes de
  revisar código, conforme pedido.

**Não coberto nesta passada** (declarado, não é cobertura silenciosa):

- Os demais componentes/páginas do dashboard não lidos individualmente:
  `dashboard/app/{artigos,noticias,bancos-ferramentas,sobre,not-found,layout}.tsx`,
  `dashboard/app/empresas/[slug]/page.tsx`, `dashboard/components/*.tsx`
  (`ItemCard`, `StatCard`, `PageHeader`, `LiveClock`, `AutoRefresh`). `AGENTS.md` do setor
  documenta correções recentes e verificadas ao vivo (curl 200 em todas as rotas) para vários
  desses arquivos — não reverificado independentemente aqui.
- Conteúdo completo dos 4 YAMLs de config (`sources.yaml`, `companies.yaml`, `keywords.yaml`,
  `resources.yaml`) — só contagem de linhas e leitura indireta via os coletores que os consomem.
  São dado de configuração, não lógica.
- `pipeline/.venv/`, `dashboard/node_modules/`, `dashboard/.next/` — binários/dependências, fora
  do escopo de código-fonte revisável.
- `pipeline/data/*` (JSON de estado, snapshots, `runs/`) — dado de saída, não código; citado só
  como evidência de um achado abaixo.
- `funding_channels.yaml`/`corporate_programs.yaml` (Fase 2, spec em revisão, ainda não
  implementada) — fora do escopo desta passada.

## Achados

### 🔴 Bloqueante

- **`pipeline/collectors/feed_collector.py:174-242`** (`_collect_section`) — falha parcial de UM
  feed descarta os itens de TODOS os feeds da seção que funcionaram na mesma execução, ao
  contrário do que a própria docstring da função (linhas 174-176) e o addendum de 2026-08-18 do
  `AGENTS.md` deste setor afirmam ("os feeds que funcionaram na rodada não são perdidos").
  Evidência: o laço acumula itens de cada feed com sucesso em `items` (linha 189 em diante), mas
  quando `falhas` não está vazio o código executa `raise RuntimeError(...)` na linha 241 **antes**
  de `return items` na linha 242 — a função nunca retorna a lista parcial, ela sempre levanta
  exceção primeiro. `run_all.py::_run_collector` (linhas 46-57) captura qualquer exceção do
  coletor e trata como `items = []`, então o `run_all.py` registra a seção inteira como 0 itens
  coletados nesta execução, mesmo que 4 dos 5 feeds tenham retornado dado válido.
  Cenário de falha concreto: `newsletter_feeds` mistura Drug Hunter/Longevity.Technology
  (funcionando hoje) com Fierce Biotech/BioPharma Dive/Labiotech — se qualquer um desses cinco
  falhar num timeout de rede pontual, os itens novos de Drug Hunter/Longevity daquela execução são
  descartados silenciosamente em vez de entrarem em `news.json`. O mesmo vale para `nature_feeds`.
  Direção: separar "itens coletados" de "erro a reportar" — retornar `(items, falhas)` (ou anexar
  o erro a `collector_results` sem descartar `items`) para que `run_all.py` sempre funda o que foi
  coletado com sucesso, independentemente de outro feed da mesma seção ter falhado.

### 🟡 Importante

- **Nenhum teste automatizado em todo o setor** (`Grep` por `*test*` em
  `alchemia-ai/alchemia-news` retorna zero arquivos, tanto no pipeline Python quanto no
  dashboard). A lógica de maior risco real — `dedupe_key`/`normalize_url`/`merge_items` em
  `pipeline/collectors/common.py` e `resolver_oa`/`dia_do_item` em `pipeline/research_export.py`
  — já teve pelo menos três bugs reais encontrados e corrigidos só por execução manual e leitura
  de log (URL normalization com `utm_`, paginação do bioRxiv, item duplicado entre seções), cada
  um documentado em addendum do `AGENTS.md` deste setor. Nenhum desses casos tem um teste de
  regressão hoje — a próxima alteração pode reintroduzir qualquer um deles sem que nada acuse.
  Direção: cobrir ao menos as funções puras de `common.py` (`normalize_url`, `dedupe_key`,
  `merge_items`, `parse_date_safe`) e `resolver_oa`/`dia_do_item` de `research_export.py` com
  `pytest`, usando os três casos reais já documentados como casos de teste.

### 🟢 Sugestão

- **`pipeline/requirements.txt:1`** declara `requests>=2.31,<3`, mas nenhum arquivo do pipeline
  importa `requests` — todo HTTP é feito via `urllib.request` (`pipeline/collectors/common.py`,
  `pipeline/research_export.py`, ambos com sua própria implementação de retry/backoff quase
  idêntica). Confirmado por busca (`import requests`/`requests\.` — zero ocorrências em
  `pipeline/`). Dependência morta: reduz superfície de instalação/CVE sem custo removê-la, ou
  migrar as duas implementações de `http_get` duplicadas para usar `requests` de fato, já que ele
  está declarado.
- **`pipeline/collectors/common.py:363-365`** (`write_run_snapshot`) grava um JSON novo por
  execução em `pipeline/data/runs/`, sem nenhuma política de retenção/poda — e esses arquivos são
  rastreados no `.git` do repositório (`git ls-files pipeline/data/runs` confirma 21 dos 32
  arquivos de `pipeline/data` rastreados são snapshots de execução). Hoje são 104 KB/23 arquivos
  em ~2 dias de operação a até 6 execuções/dia; a cadência real é 3x/dia (ver `AGENTS.md`), então o
  crescimento é lento, mas ilimitado. É exatamente a classe de crescimento de disco não vigiado que
  já custou caro à empresa em 2026-08-09 (`C:` chegou a 10 MB livres) — lição que o próprio
  `research_export.py` cita e mitiga com `--min-free-gb`, mas que este arquivo mais antigo não
  aplica. Direção: podar snapshots com mais de N dias, ou parar de rastrear `pipeline/data/runs/`
  no git (mover para `.gitignore`, mantendo só localmente).
- **Staleness de contagem em `AGENTS.md`:** o addendum de 2026-08-18 ("O que passou a existir")
  descreve `pipeline/research_export.py` como "~560 linhas". O arquivo real hoje tem **980
  linhas** — cresceu no mesmo dia com o mecanismo de lock/commit-imediato acrescentado depois
  daquele addendum ter sido escrito (o próprio corpo do `AGENTS.md` documenta essas adições em
  addenda posteriores, só a contagem inicial nunca foi atualizada). Não é um bug funcional, só uma
  contagem para corrigir no próximo addendum datado, seguindo a própria disciplina "nunca fabricar
  número" do setor.

## Não verificado

- Não executei o pipeline nem o dashboard nesta passada (gate é só-leitura de código-fonte) — os
  bugs 🔴/🟡 acima são identificados por leitura de código, não por reprodução ao vivo.
- Não confirmei se o achado 🔴 já se manifestou de fato em produção (i.e., se alguma execução real
  já perdeu itens de `newsletter_feeds`/`nature_feeds` por essa causa) — os logs de execução
  (`pipeline/data/runs/*.json`) não foram varridos item a item em busca de uma seção com `error`
  não nulo e itens de feeds-irmãos perdidos.
- Componentes/páginas do dashboard não lidos individualmente (ver "Não coberto" acima) podem
  conter achados não capturados nesta passada.
- Não avaliei correção química/dado (fora de escopo deste gate) — este setor não toca dado
  molecular, conforme o próprio `AGENTS.md` já declara.
