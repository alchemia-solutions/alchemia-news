# Spec: O Radar na VM, gravando no Postgres do System (sai o Supabase, sai o GitHub Actions)

**Setor:** alchemia-ai/softwares/internos/alchemia-radar (lado do Radar; a migração do banco e o conector são do `alchemia-system`, e a VM é do `alchemia-tech`)
**Data:** 2026-10-02
**Status:** aprovado

## Propósito

O fundador declarou em 2026-10-02 (`alchemia-brain/01-Enterprise/registros/decisions-log.md`, entrada (eb)):

> *"o alchemia-radar agora vai rodar na VM e atualizar o system de forma sincronizada, nao vamos usar mais o supabase o
> banco do alchemia-radar vai para uma tabela do alchemia-system."*

A mesma entrada fixa que "agora só `system-prod`" está em uso, com banco físico `system_prod` (nome lógico com hífen nos
documentos, físico com underscore). Ela concretiza a (cr), de 2026-09-30 (*"vamos colocar o alchemia-radar na VM junto
com o alchemia-system"*), que previa o System lendo "o dado local da VM". Pela (eb), esse dado local é uma tabela do
banco do System, e não arquivo.

Esta spec cobre o lado do Radar: onde e como a coleta roda na VM, o que ela grava, com qual papel do Postgres, como o
acervo atual chega ao banco sem perda, o que o System passa a ler e o que sai (Supabase, GitHub Actions, a leitura pelo
GitHub, o clone parado na VM). O `AGENTS.md` do Radar já anunciava esta spec (§ 6): "a mudança da coleta para a VM, com
cadência própria, vem depois do fechamento da v6, por spec".

A coleta continua determinística: nenhum LLM entra no pipeline por esta spec (2026-09-28; o "JEV" segue sem definição e
fora daqui).

## Estado Atual

Tudo medido nesta sessão (2026-10-02), por leitura. Nenhum acesso ao Supabase, ao GitHub Actions pela API ou à VM foi
feito; o que vem da VM é do roteiro `alchemia-system/docs/architecture/deploy-na-vm.md`, medido por SSH em 2026-10-02
noutra sessão, e está marcado como tal.

### O que roda, e onde

| Peça | Onde roda hoje | Fonte |
|---|---|---|
| Coleta (Etapa 1a: `python -m pipeline.run_all`) | GitHub Actions, `coleta.yml`, `cron` 09:40, 15:40 e 21:40 UTC (06:40, 12:40, 18:40 em Brasília), `ubuntu-latest`, Python 3.12, `timeout-minutes: 20` | `.github/workflows/coleta.yml` |
| Espelho no Supabase (Etapa 3: `python -m pipeline.sync_supabase`) | o mesmo job, logo depois da coleta; sem `SUPABASE_SERVICE_ROLE_KEY`, pula e sai 0 | `coleta.yml`, `pipeline/sync_supabase.py:166-174` |
| Persistência | o job commita `pipeline/data/` de volta no repositório público, com `[skip ci]` | `coleta.yml`, passo final |
| Radar datado para Science (Etapa 1b) | `research-export.yml`, disparado ao fim de cada coleta; dormente sem o segredo `ALCHEMIA_SCIENCE_TOKEN` (se o segredo existe, não foi medido) | `.github/workflows/research-export.yml` |
| Tarefas Agendadas do Windows | desabilitadas desde 2026-09-07; o `.cmd` saiu com o `alchemia-bots` | `AGENTS.md` do Radar, § 3 |
| Na VM | um clone parado do repositório com o nome antigo, em `~/alchemia-news` (nome antigo; medido por SSH em 2026-10-02 noutra sessão, `deploy-na-vm.md` § 11, item 7) | roteiro da VM |

**Cadência real** (`git log origin/main --since=2026-09-25 --format='%cI %s' | grep "coleta automática"`): 110 commits
de coleta automática no ramo desde o primeiro, de 2026-08-26T21:36Z. Nos últimos dias, três por dia UTC, com horários que
não batem com o `cron` (por exemplo 00:46Z, 16:05Z e 20:18Z em 2026-09-30; 01:08Z e 15:59Z em 2026-10-02). Qual commit
corresponde a qual `cron` e quanto o Actions atrasou cada disparo não foi medido (exigiria a API do Actions).

**Duração e erros** (os 168 snapshots de `pipeline/data/runs/` no `origin/main`, de 2026-08-17T17:14Z a
2026-10-02T15:59Z; script de leitura no scratchpad desta sessão): duração mínima 8,5 s, mediana 143,75 s, máxima
1.123,9 s. Execuções com `error` não nulo, por coletor: `newsletters` 48, `biorxiv` 25, `arxiv` 22, `nature` 11,
`chemrxiv` 1, `scielo` 1. Execuções com `count` 0: `nature` 144 (desativado em 2026-08-26, `sources.yaml`), `arxiv` 44,
`biorxiv` 25, `newsletters` 9, `googlenews` 3, `pubmed` 2, `chemrxiv` 1, `scielo` 1.

### O dado

Último estado do remoto (`git show origin/main:pipeline/data/meta.json`, commit `ca5cff0`, 2026-10-02T15:59:43Z): a
execução começou 15:57:31Z e terminou 15:59:35Z (123,8 s). O checkout local está um commit atrás (`git status -sb`:
`behind 1`; `meta.json` local termina em 2026-10-02T01:08:22Z).

| Arquivo (`origin/main`) | Itens | Bytes | Observação medida |
|---|---|---|---|
| `articles.json` | 2.073 | 5.133.001 | `kind` sempre `article`; chave `doi:` em 1.997, `url:` em 76; 1.449 sem `published_date` (todos do PubMed) |
| `news.json` | 3.313 | 4.206.789 | `kind` sempre `news`; chave `url:` em todos; 1.030 fontes distintas; 2 com data 1970-01-01 |
| `companies_activity.json` | 1.829 | 2.298.164 | todo item tem `company_slug`; todas as chaves também estão em `news.json` |
| `pipeline/data/` inteiro | 215 arquivos | 14.906.043 | `git ls-tree -r -l origin/main pipeline/data`; inclui 168 snapshots, 13 edições da newsletter (2026-08-19 a 2026-09-04) e restos dos bots (`.axel_seen.json`, 1.836.263 bytes; `discord/`) |

- **Unicidade.** Em cada arquivo, `dedupe_key` é única e nunca vazia. `articles` e `news` não compartilham chave. A
  união das três é de **5.386** chaves.
- **Divergência entre `companies_activity` e `news`.** 113 itens têm a mesma chave nos dois arquivos com conteúdo
  diferente: em `news.json` eles estão sem `company_slug` (e com `source_type`, `collected_at`, `keywords_matched` e
  `extra` de outro coletor). Causa, pelo código: `run_all.py` funde `news_items + company_items` em `news.json`, e
  `merge_items` mantém o primeiro registro e só preenche `summary`, `authors`, `published_date` e `doi` vazios
  (`common.py:316-339`). O `company_slug` de quem chegou depois nunca entra.
- **Itens sem termo.** 41 artigos e 44 notícias têm `keywords_matched` vazio, embora a regra do Radar diga que toda
  entrada carrega o termo que a trouxe. Fica registrado; corrigir é outra entrega.
- **Comprimentos.** `dedupe_key` vai até 1.030 caracteres (URL do Google News, até 1.026); `summary` até 5.409; até 106
  autores num item. Isso pesa na escolha da chave primária (Arquitetura).

### O acervo perdido em 2026-09-07, recuperável pelo git

O `collected_at` mais antigo nos três arquivos é 2026-09-07T23:43Z, mas existem snapshots de execução desde 2026-08-17.
Pelo histórico (`git log origin/main -- pipeline/data/articles.json` e `git show <commit>:pipeline/data/articles.json`):

| Commit | Quando | `articles.json` |
|---|---|---|
| `6800a38` | 2026-09-07T19:37Z, coleta automática | 1.655 itens, parseia |
| `d5eb59a` | 2026-09-07, merge à mão ("Updating 07-09-26") | **não parseia** (`JSONDecodeError`, linha 9) |
| `912106f` | 2026-09-07T23:46Z, coleta seguinte | 168 itens |

É o defeito registrado na regra 4 do nó: `load_json()` devolve a lista vazia quando o arquivo está corrompido, e a
coleta seguinte grava por cima. Comparando `6800a38` com o `origin/main` de hoje, **3.464 chaves** únicas (das 5.594 de
`6800a38`) não existem mais nos JSON: 1.498 de `articles`, 1.812 de `news`, 1.164 de `companies_activity`. Elas
continuam no histórico do git. Se também estão no Supabase não foi medido. O `sync_supabase.py` só faz upsert e nunca
apaga, então é plausível, mas isso depende de a Etapa 3 ter rodado com credencial antes de 2026-09-07.

### O código que fala com o Supabase

`pipeline/sync_supabase.py` faz upsert em lote, de 500, pela API REST (`requests`, sem driver Postgres), com
`SUPABASE_SERVICE_ROLE_KEY` do ambiente. O endereço do projeto é um padrão fixo no código, sobrescrito por
`SUPABASE_URL`. As tabelas, pelas migrações em `supabase/migrations/` (registro já aplicado):

| Tabela | Chave | Espelha | Escrita por |
|---|---|---|---|
| `items` | `dedupe_key` (único; `id` uuid) | `articles.json` + `news.json` | `sync_supabase.py` |
| `companies`, `resources`, `funding_channels`, `corporate_programs` | `slug` | os quatro YAML de `pipeline/config/` | `sync_supabase.py` |
| `pipeline_meta` | `id = 'singleton'` | `meta.json` | `sync_supabase.py` |
| `newsletters` | `date` | a newsletter do Axel | um script do `alchemia-bots`, aposentado |

As sete têm RLS ligada com a política `"Public read access" ... using (true)`: qualquer portador da chave pública lê
tudo. Só a `service_role` escreve. O leitor era o `dashboard/` (congelado desde 2026-09-28). O `risk-log` registra o
resto: item 15 (credenciais de administrador do Supabase em `dashboard/.env.local`, dentro do Drive; o arquivo continua
lá, conferido por `ls`, conteúdo não lido) e item 63 (o projeto da Vercel republicava a cada coleta). Fora do pipeline,
o `.mcp.json` do repositório declara um servidor MCP `supabase` (só os nomes das chaves foram lidos), que o
`.claude/settings.local.json` habilita, segundo o `CLAUDE.md` do Radar.

### O que o System lê hoje

Pelo `packages/core/src/connectors/radar.ts` (368 linhas) e pelo `radar-remoto.ts` (165 linhas) do System:

- **modo** (`modoRadar()`): `RADAR_FONTE=local|remoto`; sem a variável, `remoto` em `SOURCE_MODE=snapshot` e `local`
  quando `pipeline/data/meta.json` existe sob a raiz da empresa;
- **local**: lê os três JSON e o `meta.json` do disco, com cache por `mtime`; os quatro YAML de `pipeline/config/`; as
  edições `pipeline/data/newsletter/AAAA-MM-DD.md`;
- **remoto**: busca `meta.json`, `news.json`, `articles.json` e `companies_activity.json` em `raw.githubusercontent.com`
  e a data do último commit em `api.github.com` (60 chamadas/hora sem token), com cache de processo de 15 minutos
  (`RADAR_REMOTO_TTL_MS`). Os YAML e a newsletter não têm modo remoto;
- **consumidores no System** (`grep`): `modules/science/{radar,catalog,summary}.ts`, `modules/analytics/{dashboard,kpis}.ts`,
  as tools `radar_search` e `radar_weekly` (`tools/science.ts`), a página `app/(app)/science/radar/page.tsx` e mais seis
  arquivos de `apps/web`. Oito arquivos de teste do core citam o Radar, entre eles `radar-remoto.test.ts`;
- `radarFeed()` carrega todos os itens de um tipo e filtra em memória (`modules/science/radar.ts:26-56`).

**Na VM** (`compose.yaml` do System, lido nesta sessão): o serviço `app` roda com `SOURCE_MODE: local`,
`ALCHEMIA_ROOT: /vault` e sem `RADAR_FONTE`. Pela regra do conector, ele lê o Radar da cópia sincronizada do vault
quando `/vault/alchemia-ai/softwares/internos/alchemia-radar/pipeline/data/meta.json` existe, e do GitHub quando não
existe. Qual dos dois acontece em produção **não foi medido nesta sessão**. O `fontes-de-dado.md` do System (linha 157)
registra "o `pipeline/` da cópia sincronizada do vault, ou o repositório remoto". Duas consequências, ainda hipóteses:

1. a cópia do vault vem do checkout do fundador pelo Drive, que só anda com `git pull`, e por isso atrasa (hoje está um
   commit atrás);
2. o rclone da VM corta arquivos acima de 5 MB (`deploy-na-vm.md` § 10.1). `articles.json` tem 5.133.001 bytes, o que
   deixa 109.879 bytes de folga até 5 MiB. A última execução acrescentou 99.109 bytes (de 5.033.892 em `01:08Z` para
   5.133.001 em `15:59Z`). Se o corte for `--max-size 5M` sem `--delete-excluded`, a cópia de `articles.json` na VM
   deixa de ser atualizada sem erro visível. Para conferir na VM: `grep -n "max-size\|delete-excluded" ~/sync-vault.sh`.

### A VM

Pelo `deploy-na-vm.md` (medido por SSH em 2026-10-02, noutra sessão): Oracle, Ubuntu 24.04.5, **aarch64**, 4 núcleos,
11 GiB, disco de 145 GB com 12 % usados; Docker Compose com `app` e `db` (`postgres:18`); banco hoje chamado
`alchemia_system` (`PG_BANCO`); papéis `alchemia_owner`, `alchemia_app` e `alchemia_bridge`, gerados por
`packages/core/src/db/papeis.ts`, com 37 tabelas e 23 migrações (`grep -c "pgTable(" schema.ts`;
`ls packages/core/drizzle/*.sql | wc -l`). **Sem backup do banco agendado e sem rotação de log do Docker.**

## Estado Alvo

1. **O Radar é um serviço na VM**, o contêiner `radar` no Compose do System. Ele coleta nos mesmos três horários de
   hoje e grava no `system-prod` (banco físico `system_prod`) pelo papel `alchemia_radar`, que só alcança o esquema
   `radar`.
2. **O banco é a fonte única do dado do Radar.** Cada execução grava itens, a linha da execução e os catálogos numa só
   transação. Não há mais JSON acumulado em disco, commit de dado no git nem espelho no Supabase.
3. **O acervo inteiro está no banco**: os 5.386 itens de hoje, as 3.464 chaves perdidas em 2026-09-07 recuperadas do
   histórico do git, os 168 snapshots de execução, as 13 edições da newsletter e, se o fundador exportar, o que o
   Supabase tiver a mais. A carga é idempotente e conferida por contagem.
4. **O System lê as tabelas ao vivo** (definição abaixo). `radar-remoto.ts`, a leitura do disco e a dependência de
   `raw.githubusercontent.com` e `api.github.com` saem do System.
5. **Saem**: o `coleta.yml` e o `research-export.yml` do GitHub Actions, o `sync_supabase.py`, o projeto Supabase
   (exportado antes, desligado pelo fundador) e o clone `~/alchemia-news` da VM (nome antigo).

### O que "atualizar o System de forma sincronizada" significa

Proposta de definição, para o fundador confirmar (D1):

- **O System lê a tabela ao vivo, no pedido.** Não há cópia, arquivo intermediário, ponte nem TTL de 15 minutos. Quando
  a transação da execução faz commit, o pedido seguinte ao `/science/radar` (ou à tool `radar_search`) já vê os itens
  novos e a nova data de coleta.
- **Cache só com invalidação por fato do banco.** Se o System quiser cache de processo, a chave é o `id` da última
  execução terminada (`select max(id) from radar.execucao where terminada_em is not null`). Execução nova invalida
  sozinha. A linha entra no `docs/architecture/cache-registry.md` do System (skill `performance-baseline`).
- **"Sincronizado" não é "em tempo real durante a coleta".** O dado de uma execução aparece inteiro ou não aparece. A
  tela nunca mostra meia coleta.
- **Opcional, fase posterior:** `NOTIFY radar_execucao` ao fim da transação, para uma tela aberta atualizar sem
  recarregar (o System já usa SSE). Fica fora do critério de pronto desta spec.

## Critérios de Sucesso

Cada item se confere por comando ou contagem. Os limiares marcados "proposto" são do fundador.

1. **Carga completa.** O `--dry-run` do migrador (`python -m pipeline.migrar_para_postgres --dry-run`) imprime, por
   origem (JSON atual, histórico do git, export do Supabase se houver), quantas chaves há e quantas são novas na união.
   Depois da carga, `select count(*) from radar.item` é igual ao total único que o `--dry-run` informou, sem tolerância.
2. **As 3.464 chaves de 2026-09-07 voltam.** Um teste lista as chaves de `6800a38` ausentes no `origin/main` e confirma
   que todas existem em `radar.item` depois da carga.
3. **Idempotência.** Rodar o migrador duas vezes deixa a segunda com 0 inserções e 0 atualizações, com a contagem
   inalterada. Rodar a coleta duas vezes contra a mesma resposta das fontes (fixture, sem rede) dá `novos = 0` na segunda.
4. **A divergência dos 113 some.** Depois da carga, toda chave de `companies_activity.json` tem `company_slug` não nulo
   em `radar.item`.
5. **Mínimo privilégio, testado nos dois sentidos** com o papel `alchemia_radar` num Postgres descartável: `select` e
   `insert` em `radar.item` passam; `select` em `public.user` falha com `permission denied`; `create table` falha;
   `delete` em `radar.item` falha. Com `alchemia_app`, `select` em `radar.item` passa e `insert` falha.
6. **Uma execução por vez.** Duas execuções disparadas juntas: a segunda sai sem gravar e registra
   `radar.execucao.ocupado` (trava consultiva do Postgres). Teste automatizado.
7. **Zero e falha continuam distinguíveis.** Fonte fora do ar (simulada) gera `estado = 'parcial'` e `error` no coletor,
   preservando os itens dos outros. Banco fora do ar gera uma linha de log `radar.execucao.falhou` e saída 1, sem
   arquivo escrito.
8. **Sombra de 7 dias (proposto).** VM e Actions coletam em paralelo. Os critérios (propostos): nenhum coletor fica com
   `count = 0` e `error` nulo na VM em três execuções seguidas em que o Actions trouxe mais de 0 do mesmo coletor no
   mesmo dia UTC; e a VM cobre pelo menos 90 % das chaves que o Actions coletou no período.
9. **O System lê só o banco.** `grep -rn "raw.githubusercontent.com\|api.github.com/repos" packages apps` no System
   devolve 0 linhas, e `grep -rn '"alchemia-radar", "pipeline"' packages` também.
10. **Leitura sincronizada.** Num teste do System com banco: depois de inserir uma execução terminada, o primeiro
    `radarMeta()` devolve aquele `last_run_finished`, sem esperar TTL.
11. **Sem segredo em repositório.** `security_baseline.py segredos` sobre o repositório do Radar e o `npm run
    check:secrets` do System saem 0. `PG_SENHA_RADAR` existe só em `deploy/producao.env`, que está no `.gitignore`.
12. **Os testes passam.** `pipeline/.venv/Scripts/python.exe -m unittest discover pipeline/tests` no Radar e
    `npm run verify` no System.
13. **Velocidade.** `/science/radar` responde morno em até 1,0 s (F6 da `frontend-quality-gate`), medido antes e depois
    da troca do conector.
14. **Saída comprovada.** Nenhum commit `coleta automática` no `origin/main` depois da data da virada (`git log`). O
    fundador confirma o Supabase desligado depois de registrar a contagem de linhas exportadas por tabela.
15. **Backup antes da virada.** Existe `pg_dump` agendado do `system_prod` e uma restauração testada (dependência da
    Tech) antes de o Actions parar. Hoje o git é o único histórico do dado do Radar; sem isso, a virada troca um
    histórico versionado por um volume sem cópia.

## Arquitetura / Stack

### O serviço

- **Contêiner `radar` no `compose.yaml` do System** (D2), na rede `interna`, sem `ports`, `read_only: true`,
  `tmpfs: /tmp`, `cap_drop: [ALL]`, `no-new-privileges` e usuário não root, o mesmo endurecimento da `ponte`.
  `depends_on: papeis-final: service_completed_successfully` garante que o esquema e as concessões existem antes da
  primeira coleta.
- **Imagem `alchemia-radar:<sha>`**, construída na VM (aarch64) a partir de um `Dockerfile` novo no repositório do Radar
  (`python:3.12-slim`), pelo `compose-build.yaml` do System com contexto `${RADAR_DIR}`. A etiqueta é o sha do commit
  do Radar, com o mesmo padrão de release e rollback do app (`deploy-na-vm.md` § 3 e § 9).
- **Agendamento dentro do contêiner**, sem cron do host e sem dependência nova: `python -m pipeline.agendador` dorme até
  o próximo horário de `RADAR_HORARIOS_UTC` (padrão `09:40,15:40,21:40`, os mesmos três de hoje), roda a coleta e volta
  a dormir. Os horários ficam em UTC para não depender de `tzdata` na imagem slim (o Brasil não tem horário de verão
  desde 2019). Disparo à mão:
  `docker compose --env-file deploy/producao.env run --rm radar python -m pipeline.run_all`.
- **O código do Radar na VM** é um clone do repositório público (`github.com/alchemia-solutions/alchemia-radar`) em
  `/home/ubuntu/alchemia-radar`, atualizado só por `git pull` (leitura). A configuração viva (`pipeline/config/*.yaml`)
  vem desse clone, e mudar um YAML passa a ser commit do fundador mais um `pull` e um novo release.

### O esquema `radar` no `system_prod` (dono: o System)

Esquema próprio dentro do banco do System, criado por migração Drizzle numerada e aditiva do System (`pgSchema("radar")`).
É "uma tabela do alchemia-system" no sentido da (eb): o banco é o do System, e o esquema separado só torna as concessões
exatas. As colunas de item mantêm os nomes do JSON para o `normalize()` do conector continuar valendo.

```sql
create schema radar;  -- dono: alchemia_owner

create table radar.execucao (
  id            bigint generated always as identity primary key,
  origem        text not null check (origem in ('agendada', 'manual', 'importada')),
  versao        text,                           -- sha da imagem do Radar
  iniciada_em   timestamptz not null,
  terminada_em  timestamptz,
  estado        text not null check (estado in ('rodando', 'ok', 'parcial', 'falhou')),
  duracao_s     numeric,
  coletores     jsonb not null default '{}',    -- o mesmo formato de meta.json "collectors"
  totais        jsonb not null default '{}'     -- o mesmo formato de meta.json "totals"
);

create table radar.item (
  dedupe_key        text primary key check (octet_length(dedupe_key) <= 2000),  -- doi: > url: > hash:, common.dedupe_key()
  kind              text not null check (kind in ('article', 'news')),
  title             text not null,
  url               text not null,
  source            text not null,
  source_type       text not null,
  published_date    date,                       -- 1970-01-01 do feed vira null na carga e na coleta
  collected_at      timestamptz not null,       -- a PRIMEIRA vez que foi visto
  authors           text[] not null default '{}',
  summary           text not null default '',
  doi               text,
  company_slug      text,
  keywords_matched  text[] not null default '{}',
  coletores         text[] not null default '{}', -- novo: quem achou o item; vazio no acervo importado
  extra             jsonb not null default '{}',
  primeira_execucao bigint references radar.execucao(id),
  vista_em          timestamptz not null,       -- a ÚLTIMA execução que o viu
  atualizado_em     timestamptz not null default now()
);
create index on radar.item (kind, published_date desc nulls last, collected_at desc);
create index on radar.item (company_slug) where company_slug is not null;

create table radar.catalogo (                   -- os quatro YAML que o System lê, sem remodelar
  tipo     text not null check (tipo in ('companies', 'resources', 'funding_channels', 'corporate_programs')),
  slug     text not null,
  posicao  int  not null,                       -- a ordem do YAML
  dados    jsonb not null,                      -- a entrada do YAML, como está
  atualizado_em timestamptz not null default now(),
  primary key (tipo, slug)
);

create table radar.newsletter (                 -- arquivo histórico, congelado em 2026-09-04
  data      date primary key,
  markdown  text not null
);

create view radar.meta as                       -- o contrato de meta.json, para radarMetaDoJson() valer sem mudança
  select iniciada_em as last_run_started, terminada_em as last_run_finished,
         duracao_s as duration_seconds, coletores as collectors, totais as totals
  from radar.execucao where terminada_em is not null order by id desc limit 1;
```

Notas de desenho:

- **Chave natural, não uuid.** A identidade do item já é `dedupe_key`. O `check` de 2.000 bytes protege o limite da
  B-tree (cerca de 2,7 kB por entrada). O teste usa a chave real mais longa medida (1.030 caracteres) e uma chave
  aleatória de 3.000 bytes **não compressível**, porque com texto repetitivo o Postgres comprime antes de conferir o
  limite e o teste passa mentindo (regra 8 da `code-quality-gate`).
- **Um item, uma linha.** O `companies_activity.json` vira `kind = 'news' and company_slug is not null`. O `news.json`
  vira `kind = 'news'`, e o `articles.json`, `kind = 'article'`. Some a duplicação que produzia os 113 divergentes.
- **Os catálogos entram como `jsonb`** porque o System já sabe normalizar cada YAML (`fundingChannels()` e os outros
  três): trocar a origem não reescreve a regra. A coleta faz upsert dos quatro a cada execução e apaga, na mesma
  transação, o `slug` que saiu do YAML. É a única tabela em que o papel do Radar tem `DELETE`.
- **A coluna `coletores`** resolve com dado explícito o que o conector hoje infere pelo formato (`inferCollector`). No
  acervo importado ela fica vazia e a inferência continua como recurso. Mudança de contrato, combinada com o
  `alchemia-system` (D9).

### Escrita idempotente (o lado do Radar)

`pipeline/armazenamento_pg.py`, novo, com `psycopg` 3 (D8), substitui o `load_json`/`merge_items`/`save_json` da
coleta. Os coletores não mudam. Uma execução:

1. `pg_try_advisory_lock(<constante do Radar>)`; sem a trava, registra `radar.execucao.ocupado` e sai 0.
2. Confere o contrato: as colunas de `radar.*` em `information_schema.columns` são as que o código espera; se não forem,
   sai 1 com a diferença no log (o esquema é do System, então é aqui que a deriva aparece).
3. Insere `radar.execucao` com `estado = 'rodando'` e faz commit. A tela pode mostrar "coleta em curso".
4. Roda os coletores (inalterados).
5. Numa transação: upsert dos itens com
   `insert ... on conflict (dedupe_key) do update set` preenchendo **só campo vazio**, como o `merge_items` de hoje:
   `summary`, `authors`, `published_date`, `doi` e `company_slug`, com `keywords_matched` e `coletores` em união.
   `vista_em` sempre recebe o valor novo. Novos e atualizados saem de `returning (xmax = 0)`. Depois, o upsert dos
   catálogos e o fechamento da execução (`estado`, `terminada_em`, `coletores`, `totais`).
6. Libera a trava.

Não há mais leitura-modificação-escrita do acervo inteiro, e com isso some a classe de defeito de 2026-09-07 (JSON
corrompido lido como vazio e gravado por cima). Duas mudanças pequenas no código existente: `common.py` cria
`pipeline/data/` e mais três pastas na importação (linhas 44-45), o que falha num sistema de arquivos só-leitura e deixa
de acontecer no modo Postgres; e o `run_all.py` ganha `--destino postgres|json`, com `json` só durante a sombra.

### A migração do dado atual

`pipeline/migrar_para_postgres.py`, novo, roda uma vez em `system_dev` (local) e depois em `system_prod`, com o papel
`alchemia_radar`:

| Origem | O que entra | Regra |
|---|---|---|
| JSON do `origin/main` no commit da virada | os três arquivos | a base; o registro de hoje vence |
| Histórico do git (`git log -- pipeline/data/{articles,news,companies_activity}.json`, toda versão que parseia) | chaves que sumiram, como as 3.464 de 2026-09-07 | entram como estão; versão que não parseia é contada e relatada, nunca silenciada |
| Export do Supabase (`items`, `newsletters`), se o fundador o fizer (D4) | o que não estiver nas duas acima | só preenche ausente; nunca sobrescreve |
| `pipeline/data/runs/*.json` (168) | `radar.execucao` com `origem = 'importada'` | um snapshot, uma linha; o `id` segue a ordem do carimbo |
| `pipeline/data/newsletter/AAAA-MM-DD.md` (13) | `radar.newsletter` | uma edição, uma linha |
| `pipeline/config/*.yaml` (os quatro) | `radar.catalogo` | igual à coleta |

Regras de fusão para a mesma chave vinda de mais de uma origem: `collected_at` é o mais antigo visto; `company_slug`
não nulo vence; `keywords_matched` é a união; os demais campos são os do registro mais recente que os tem preenchidos.
`.axel_seen.json` e `discord/` (restos dos bots) não migram.

### O que o System passa a ler (contrato com `connectors/radar.ts`)

Proposta ao `alchemia-system`, que é dono do conector e da migração:

| Hoje | Depois |
|---|---|
| `radarItems(kind)` lê `{news,articles,companies_activity}.json` ou o GitHub | `select` em `radar.item` pelo `kind` (e `company_slug is not null` para `companies`), com filtro e paginação no SQL |
| `radarMeta()` lê `meta.json` | `select * from radar.meta`; o `radarMetaDoJson()` atual serve sem mudança |
| `fundingChannels()`, `corporatePrograms()`, `monitoredCompanies()`, `radarResources()` leem YAML | `select dados from radar.catalogo where tipo = $1 order by posicao`; a normalização atual serve |
| `newsletterEditions()`, `newsletterEdition(data)` leem `.md` | `radar.newsletter` |
| `Sourced.source` aponta para arquivo ou URL do GitHub | `postgres:system-prod/radar.<tabela>`, com `sourceUpdatedAt` igual à `terminada_em` da última execução |
| `modoRadar()`, `RADAR_FONTE`, `RADAR_REMOTO_*`, `radar-remoto.ts`, `prepararRadar()`, `prepararUltimaColeta()` | saem; em dev, o System lê o `system_dev` local, onde o Radar roda à mão |

O System é o dono da migração Drizzle porque o banco é dele, e também do gerador de papéis: o `papeis.ts` ganha
`alchemia_radar` (abaixo) e deixa o `alchemia_app` só com `SELECT` em `radar.*`. Hoje o app recebe
`SELECT, INSERT, UPDATE, DELETE` em toda tabela do esquema (`papeis.ts:4`).

### O papel `alchemia_radar`

`LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION`, como os outros três. As concessões:
`CONNECT` no banco; `USAGE` no esquema `radar`; `SELECT, INSERT, UPDATE` em `radar.item`, `radar.execucao` e
`radar.newsletter`; `SELECT, INSERT, UPDATE, DELETE` em `radar.catalogo`; `SELECT` em `radar.meta`; `USAGE` na
sequência de `radar.execucao`. Nada em `public`, nada em `drizzle`, nenhuma DDL. A senha entra como as outras: o
serviço `papeis` do Compose roda `ALTER ROLE alchemia_radar PASSWORD :'s_radar'` com `PG_SENHA_RADAR` do
`deploy/producao.env`, e o serviço `radar` recebe
`DATABASE_URL_RADAR=postgres://alchemia_radar:${PG_SENHA_RADAR:?...}@db:5432/${PG_BANCO}`.

### Segredos, logs, falha e limites de taxa

- **Segredos.** Só um: `PG_SENHA_RADAR`, em `deploy/producao.env` (fora do git, `chmod 600`, só os caracteres que a URL
  aceita, como as outras senhas, `deploy-na-vm.md` § 2). As fontes são públicas e sem chave (o PubMed roda sem
  `api_key`). O segredo `SUPABASE_SERVICE_ROLE_KEY` do Actions e as credenciais do `dashboard/.env.local` (risk-log, item
  15) perdem o uso: revogar e remover é do fundador (D4). Nenhum agente lê, imprime ou testa credencial.
- **Logs.** Uma linha JSON por evento no stdout, no padrão da ponte (`{"evento":"radar.coletor","id":"pubmed","count":60,
  "segundos":3.3}`), com `radar.execucao.inicio`, `.fim`, `.parcial`, `.falhou` e `.ocupado`. Traceback continua
  passando por `sanitize_local_path`, e a URL do banco nunca entra no log. A rotação depende do
  `/etc/docker/daemon.json`, hoje ausente na VM (dependência da Tech). O histórico auditável deixa de ser o
  `pipeline/data/runs/` no git e passa a ser `radar.execucao`.
- **Falha de coleta.** Fonte que falha não derruba a execução: o coletor registra `error` e devolve o que tiver colhido
  (`ColetaParcial`, como hoje), e a execução fecha com `estado = 'parcial'`. Banco indisponível encerra com saída 1 e
  log; o agendador espera o próximo horário, e o `restart: unless-stopped` cobre a queda do processo. **Alarme**: hoje
  não existe nenhum. Proposta (D7): o System mostra no cartão da coleta um aviso quando a última execução terminada tem
  mais de 13 horas (o maior intervalo da cadência é de 12 horas, de 21:40 a 09:40 UTC), e o `/api/ready` não muda,
  porque coleta atrasada não pode tirar o app do ar. Um vigia externo (e-mail ou outro canal) continua decisão do
  fundador.
- **Limites de taxa.** O que o código já respeita: PubMed com 0,4 s entre pedidos (`pubmed_collector.py:148`; o NCBI
  aceita até cerca de 3 pedidos/s sem chave, pelo comentário do coletor); arXiv com 3 s entre feeds
  (`rss_delay_seconds`); newsletters com 1,5 s e uma segunda tentativa após 5 s; `nature` desativado por anti-bot
  (`sources.yaml`); retentativa exponencial de 1,5 s × tentativa em `http_get`. O Google News (15 consultas gerais e as
  empresas pelo método `google_news`; 15 das 21 linhas `method:` de `companies.yaml`) e o Crossref rodam sem pausa
  explícita. O que muda: a origem dos pedidos passa de IPs do GitHub para o IP fixo da VM na Oracle. Se Google News,
  bioRxiv ou Crossref tratam esse IP de outro jeito **não foi medido**, e é para isso que serve a sombra (critério 8). Na
  sombra, as fontes recebem o dobro de pedidos; o agendador da VM fica deslocado 20 minutos dos horários do Actions
  para não somar as rajadas. O `User-Agent` mantém `AlchemiaNewsBot/1.0`, que é identificador e não nome (regra de
  renomeação do Radar).

## Dependências

- **Do `alchemia-system`** (nó `alchemia-system`; spec `alchemia-ai/softwares/internos/alchemia-system/docs/specs/2026-10-02-alchemia-system-v7.md`,
  em redação nesta data): a migração Drizzle do esquema `radar`; o papel `alchemia_radar` e o `SELECT`-só do app em
  `papeis.ts` e `papeis.sql`; o serviço `radar` no `compose.yaml` e no `compose-build.yaml`; a reescrita de
  `connectors/radar.ts`, a remoção de `radar-remoto.ts` e dos testes dele; o cartão de atraso; as linhas novas do
  `cache-registry.md` e do `fontes-de-dado.md`.
- **Do `alchemia-tech`** (Gabriel Furniel; spec `alchemia-tech/docs/specs/2026-10-02-bancos-radar-e-vault-na-vm.md`, em
  redação nesta data): o banco físico `system_prod` (hoje `alchemia_system`); o backup agendado do banco com restauração
  testada (critério 15); a rotação de log do Docker; o clone `/home/ubuntu/alchemia-radar`; a remoção do clone
  `~/alchemia-news` (nome antigo) e a conferência do recorte do rclone (a cópia do Radar no vault deixa de ser lida).
- **Do harness** (`alchemia-harness`): `harness/measure_day.py:326` lê `pipeline/data/meta.json` do checkout local, que
  vai congelar. Ele passa a declarar "fonte na VM, não medido daqui" até haver uma leitura autorizada.
- **De Science**: a Etapa 1b (`research_export.py`) lê os JSON. Proposta (D6): ela fica suspensa, como já está de fato
  (sem o segredo), até uma spec própria a apontar para o banco.
- **De serviços externos**: as mesmas fontes de hoje (NCBI E-utilities, API do bioRxiv, RSS do arXiv, Crossref, Google
  News RSS, feeds das newsletters e das empresas). O Supabase e o GitHub Actions saem. O GitHub fica só como
  hospedagem do código.
- **De licenciamento**: `psycopg` 3, sob LGPL-3.0 (a conferir pela `software-license-audit`; usado como biblioteca,
  não redistribuído); imagem `python:3.12-slim`. Os metadados e resumos coletados: ver lente 1.

## Riscos e Efeitos de Segunda Ordem

1. **Licenciamento e proveniência.** O Radar guarda metadado público e o resumo que a própria API entrega (até 1.200
   caracteres no Crossref, `common.py:396`). O regime de direito dos resumos por editora **não foi verificado** nesta
   sessão. Hoje esse conteúdo é redistribuído publicamente duas vezes: no repositório público (`pipeline/data/`) e no
   Supabase com política de leitura pública. Depois da virada, ele fica atrás do login do System, o que reduz a
   exposição. Mas os JSON já publicados continuam no repositório e no histórico dele: o que fazer com eles é a D5. A
   proveniência por item fica explícita na coluna `coletores`.
2. **LGPD.** O acervo tem nomes de autores de artigos (até 106 num item), que são dado pessoal tornado público pelo
   titular. Nenhum dado de cliente, colaborador ou usuário entra nas tabelas `radar.*`, e o desenho não registra quem
   leu o quê. O papel `alchemia_radar` não alcança `public` (onde mora o dado de colaborador), e o critério 5 prova isso.
   O export do Supabase (D4) leva os mesmos nomes: guardar fora do Drive e fora do vault (`alchemia-workdata`) e
   apagar depois da conferência. Rede social continua fora de escopo.
3. **Hardware local.** Nada roda na RTX desta estação. Na VM (aarch64, 4 núcleos, 11 GiB, medido em 2026-10-02 noutra
   sessão), a coleta divide máquina com o app e o Postgres. A duração mediana medida no Actions é de 143,75 s e a
   máxima de 1.123,9 s; memória e CPU na VM **não foram medidas** e entram na sombra (`docker stats` por execução). O
   banco cresce pouco: os três JSON somam 11.637.954 bytes com duplicação; o tamanho das tabelas não foi medido e se
   mede depois da carga em `system_dev` (`pg_total_relation_size`). `psycopg` tem wheel aarch64, a confirmar no build.
4. **Acoplamento entre setores.** O maior risco da spec. O esquema `radar` é do System e é escrito pelo Radar: uma
   migração do System que renomeie coluna quebra a coleta em silêncio. A conferência de contrato no início de cada
   execução (passo 2) transforma isso em falha alta e nomeada, e a regra fica nos dois `AGENTS.md`: mudar `radar.*`
   exige combinar com o `alchemia-radar`. Outros efeitos:
   - o System perde a leitura dos JSON, e com ela os testes `radar-remoto.test.ts` e parte de `f4-f5-connectors` e
     `v6-4-conectores`;
   - o `measure_day.py` e a Etapa 1b perdem a fonte (Dependências);
   - em dev, o System passa a precisar do `system_dev` com o esquema `radar` carregado: o migrador roda localmente
     também;
   - o "escritor único" muda de dono: deixa de ser o Actions e passa a ser o contêiner `radar`, o que muda o `AGENTS.md`
     do Radar, a skill `news-intelligence-pipeline` e a definição do nó;
   - a tool `radar_search` muda o campo `source` das respostas;
   - **o histórico versionado acaba**: até hoje o git era o backup do Radar, e foi ele que guardou as 3.464 chaves de
     2026-09-07. Sem backup do banco (critério 15), a virada piora a recuperação. Por isso o Actions só para depois do
     backup.

## Roadmap

| Fase | Entrega | Destrava |
|---|---|---|
| **R0. Preparo** (sem tocar produção) | o fundador exporta o Supabase (D4) e guarda fora do Drive; a Tech agenda o `pg_dump` e testa uma restauração; a Tech confere na VM qual modo o Radar está usando (`RADAR_FONTE` ausente, cópia do vault ou GitHub) | R1 em produção sem risco de perda |
| **R1. Esquema** (System) | migração Drizzle do esquema `radar` e da view `radar.meta`; `alchemia_radar` e o `SELECT`-só do app no gerador de papéis; testes de concessão nos dois sentidos (critério 5) em Postgres descartável | R2 e R3 |
| **R2. Escritor Postgres** (Radar) | `armazenamento_pg.py`, `--destino`, a trava, a conferência de contrato, `agendador.py`, `Dockerfile`; `common.py` sem `mkdir` na importação; testes sem rede (critérios 3, 6 e 7) | R3 e R4 |
| **R3. Carga** (Radar) | `migrar_para_postgres.py` com `--dry-run`; carga em `system_dev` e conferência (critérios 1, 2 e 4); depois em `system_prod` | R4 com acervo completo |
| **R4. Sombra** (Radar e Tech) | serviço `radar` no ar na VM gravando no `system_prod`; o Actions segue gravando o git; sete dias de comparação (critério 8) | a decisão de virar |
| **R5. Leitura** (System) | `connectors/radar.ts` sobre o banco, `radar-remoto.ts` fora, cartão de atraso, `cache-registry.md` (critérios 9, 10 e 13) | R6 |
| **R6. Desligamento** (fundador, Tech e Radar) | o fundador desliga o `coleta.yml` e o `research-export.yml` (push dele) e o projeto Supabase; `sync_supabase.py`, `supabase/` e o MCP `supabase` do `.mcp.json` vão para a Lixeira ou ficam como registro (D5); remoção de `~/alchemia-news` (nome antigo) na VM; atualização de `AGENTS.md`, `README.md`, `docs/HISTORY.md`, da skill, do nó e do hub no vault (critério 14) | — |

## Decisões do fundador

| # | Decisão | Proposta desta spec |
|---|---|---|
| D1 | O que "sincronizado" quer dizer | o System lê a tabela ao vivo; uma execução aparece inteira no pedido seguinte; sem cópia e sem TTL |
| D2 | Onde o serviço mora | contêiner `radar` no Compose do System, com imagem própria e etiqueta por sha (a alternativa, um Compose separado ligado à rede `interna`, acopla duas pilhas pela rede) |
| D3 | Recuperar as 3.464 chaves perdidas em 2026-09-07 pelo histórico do git | sim; a carga é uma união medida, nunca uma escolha de um lado |
| D4 | Supabase: o que exportar e quem desliga | o fundador exporta `items` e `newsletters` (e, por completude, as outras cinco tabelas) antes; desliga o projeto; revoga a `service_role` e remove o segredo do Actions e o `dashboard/.env.local` (risk-log 15); o projeto da Vercel (risk-log 63) sai junto |
| D5 | `pipeline/data/` no repositório público depois da virada | congelar com um `README` datado ("parou em AAAA-MM-DD; o dado vive no `system-prod`") e parar de versionar dado novo; retirar o diretório do repositório (e do histórico) é git de escrita do fundador e pesa contra a lente 1 |
| D6 | A Etapa 1b e o radar datado de Science | suspensos (o `research-export.yml` sai com o `coleta.yml`) até uma spec de Science apontar para o banco |
| D7 | Alarme | aviso na tela com mais de 13 h sem coleta terminada; vigia externo continua a decidir |
| D8 | Dependência nova | `psycopg` 3 (LGPL-3.0), pela `software-license-audit` |
| D9 | A coluna `coletores` (contrato novo com o System) | entra, preenchida a partir da virada |
| D10 | Cadência e sombra | mantém os três horários de hoje; sombra de 7 dias com 90 % de cobertura como limiar |
| D11 | Retenção | nenhum item apagado por enquanto; revisitar com um ano de acervo ou quando a tabela passar de um tamanho que o fundador fixar |

## Agente Responsável

- **`alchemia-radar` (Kepler)**, dono desta spec e do repositório do Radar: o escritor Postgres, o agendador, o
  `Dockerfile`, o migrador de dados, a sombra e o desligamento do lado do repositório.
- **`alchemia-system` (Hipátia)**: a migração Drizzle do esquema `radar`, o gerador de papéis, o serviço no Compose, o
  conector e a tela. O banco é do System, então a migração é dele.
- **`alchemia-tech` (Arquimedes), com Gabriel Furniel**: a VM, o banco físico `system_prod`, backup, rotação de log,
  clones na VM e a aplicação dos papéis em produção.
- **Gates**: `alchemia-quality-gate` (Ada) revisa o código dos dois repositórios, com a `security-baseline` (segredos e
  papéis); `alchemia-frontend-gate` (Hopper) mede o `/science/radar` antes e depois (critério 13).
- Nenhum nó novo é necessário.

## Portão de Revisão

`[x] Revisado e aprovado pelo fundador em 2026-10-02 — *"Aprovada"*, resposta à pergunta "Você aprova as sete [specs da v7] com as recomendações dos agentes como padrão nas decisões abertas?" (decisions-log (ee)). As decisões que exigem o fundador seguem bloqueando só a etapa delas`. Nenhuma implementação começa antes desta caixa ser marcada.

## Addendum — 2026-10-02 (noite): R2 e R3 entregues do lado do Radar, até o ponto em que só falta a VM

Frente D da implementação paralela da v7 (decisão do fundador: *"vamos fazer todas as fases da v7 nessa sessão e só
depois vamos atualizar o deploy na VM"*). Nada rodou na VM, nada foi desligado, nenhum git de escrita. O Actions segue
escritor único de `pipeline/data/` até a R6. O esquema, os papéis e o serviço no Compose são da frente C (System), e os
testes abaixo usam a migração `0024_radar` e o `papeis.sql` reais dela.

### O que entrou

| Peça | Arquivo |
|---|---|
| O escritor (D8, `psycopg` 3): trava consultiva, contrato de colunas nos dois sentidos, execução órfã, upsert só-preenche-vazio, catálogos, fechamento numa transação | `pipeline/armazenamento_pg.py` |
| `--destino json` ou `postgres` (padrão `RADAR_DESTINO`, senão `json`, para o Actions seguir igual) e `--origem` | `pipeline/run_all.py` |
| `common.py` sem `mkdir` na importação; `RADAR_LOG_JSON=1` põe o log dos coletores em JSON | `pipeline/collectors/common.py` |
| O agendador, em UTC, com a coleta num processo filho | `pipeline/agendador.py` |
| A carga (D3), em duas metades: montar na estação (git) e carregar onde há banco, por um pacote `.json.gz` | `pipeline/migrar_para_postgres.py` |
| O export do Supabase (D4), pronto para o fundador rodar; nenhum agente o rodou | `pipeline/exportar_supabase.py` |
| A imagem e o contexto de build | `Dockerfile`, `.dockerignore`, `pipeline/requirements-pg.txt` (separado: o Actions instala só o `requirements.txt`) |
| O roteiro para o Gabriel (R0 a R6) | `deploy/README.md` |
| Os testes | `pipeline/tests/test_armazenamento_pg.py`, `test_migrar_para_postgres.py`, `test_agendador.py`, `test_exportar_supabase.py`, `pg_descartavel.py` |

### Critérios, com a evidência desta sessão

Comando: `PG_DESCARTAVEL_URL=<cluster descartável do System, porta 55431> pipeline/.venv/Scripts/python.exe -m unittest discover -s pipeline/tests`
dá `Ran 56 tests ... OK`, com `[concessões: papeis.sql do System]`; sem a variável, `OK (skipped=20)`.

| # | Estado | Evidência |
|---|---|---|
| 1 | feito na estação | `--dry-run` sobre `origin/main` (`ca5cff0`): JSON do ref, 5.386 chaves; histórico do git, 8.879 (131 commits, 347 versões de arquivo, 3 que não parseiam, todas do merge `d5eb59a`); união, 8.879. Depois da carga, `count(*)` de `radar.item` = 8.879 (`test_1`) |
| 2 | feito, com a contagem corrigida | ver "As 3.464 chaves" abaixo; `test_2` confere as 3.464 no banco e as 1.164 de empresa com `company_slug` |
| 3 | feito | segunda carga, pelo pacote: 0 inserções, 0 atualizações, 0 execuções, 0 newsletters (`test_3`); a coleta duas vezes com dublês sem rede: 0 novos e 0 atualizados na segunda (`test_coleta_duas_vezes_sem_rede`) |
| 4 | feito | toda chave do `companies_activity.json` de hoje tem `company_slug` no banco (`test_4`); na coleta, o item achado pelo Google News e pela página da empresa ganha a empresa no mesmo lote |
| 5 | feito | `PapelMinimo`: `alchemia_radar` lê e grava `radar.*` e lê `radar.meta`; recebe `InsufficientPrivilege` em `public."user"`, `create table` em `radar` e em `public`, `delete` e `drop` em `radar.item` e leitura em `drizzle`; `alchemia_app` lê e não grava |
| 6 | feito | `test_trava_ocupada_sai_sem_gravar`: saída 0, `radar.execucao.ocupado`, nenhuma linha |
| 7 | feito | fonte fora do ar: `parcial`, o erro no coletor, os itens dos outros e do `ColetaParcial` preservados, `pubmed` com 0 e `error` nulo; banco fora do ar: saída 1, `radar.execucao.falhou`, nenhum arquivo gravado, a senha fora da saída |
| 8 | não começou | a sombra é na VM (R4) |
| 9, 10, 13 | do System | frente C |
| 11 | feito no Radar | `security_baseline.py segredos` sai 0 com `--permitir docs/qc/segredos-permitidos.txt` (uma exceção justificada: a linha desta spec que cita a interpolação da senha do Compose); sem a exceção, sai 1 só por ela |
| 12 | feito no Radar | os 56 testes acima (um deles prova que o `--destino json` do Actions segue gravando os mesmos arquivos) |
| 14, 15 | do fundador e da Tech | — |

Coleta real de ponta a ponta, na estação, contra um banco descartável já com a carga: `python -m pipeline.run_all
--destino postgres` com `RADAR_LOG_JSON=1` saiu 0; execução 169 `parcial` (o `newsletters` falhou, como já falha no
Actions), 169,3 s, 30 itens novos e 1.774 atualizados (o acervo importado tem `coletores` vazio e a primeira coleta o
preenche), 0 recusados; toda linha da saída em JSON; `pipeline/data/` intocado (o número de arquivos de `runs/` e o
`mtime` do `meta.json` não mudaram). Com a carga, `radar.item` mede 16.064.512 bytes (`pg_total_relation_size`).

### As 3.464 chaves: a contagem era por arquivo

Medido nesta sessão contra `6800a38` e `origin/main`: das 5.594 chaves únicas de `6800a38`, **3.310 itens** não existem
em nenhum dos três JSON de hoje. As 3.464 da seção "O acervo perdido" são a união das ausências **por arquivo** (1.498 de
`articles`, 1.812 de `news`, 1.164 de `companies_activity`; a soma, 4.474, conta duas vezes o que estava em `news` e em
`companies_activity`): 154 delas continuam em `news.json` e só perderam a empresa. A carga devolve as duas coisas, o
item e a empresa.

O histórico ainda trouxe **183 itens** que nem `6800a38` nem o `origin/main` têm: todos estão em `9bdfbd8`
("Updating 07-09-26"), a coleta local do mesmo dia, o outro lado do merge `d5eb59a` que não parseia, coletados entre
2026-09-02 e 2026-09-07. São a mesma perda. Itens recuperados pelo histórico: **3.493** (3.310 + 183). Nenhuma chave
gravada difere do recálculo pela `dedupe_key()` de hoje (0 em 8.879), então a união não cria duplicata por mudança de
normalização.

### Escolhas de implementação

1. **`atualizados` conta mudança real.** O `where` do `on conflict` repete as condições do `set`, e `vista_em` anda num
   `update` à parte. Sem isso, toda coleta "atualizaria" tudo o que viu, e a idempotência não se mediria.
2. **Contrato estrito nos dois sentidos.** Coluna a mais em `radar.*` também reprova, com o nome dela no log. Uma
   migração aditiva do System no esquema `radar` exige atualizar `CONTRATO` em `armazenamento_pg.py` no mesmo ato.
3. **Catálogo YAML vazio, sem `slug` ou com `slug` repetido é recusado** antes de qualquer escrita, e nada é apagado: a
   classe de defeito de 2026-09-07 (vazio lido como "apague tudo") fica fechada também nos catálogos.
4. **`falhou` não tem `terminada_em`.** Todos os coletores com erro, contrato divergente ou exceção: a linha fica sem
   `terminada_em`, a view `radar.meta` continua mostrando a última coleta que terminou, e o aviso de 13 h da D7 dispara
   se nada termina.
5. **Execução `rodando` que sobrou vira `falhou`** na coleta seguinte: com a trava na mão, nenhuma outra está viva.
6. **Snapshot do Actions não entra depois da primeira coleta da VM.** A view escolhe pelo maior `id`; um snapshot
   importado na carga final da R6 ganharia `id` maior e tomaria o lugar da última coleta real, mesmo sendo mais antigo
   (achado por teste nesta sessão). O migrador pula todos e os conta (`execucoes_puladas_por_haver_coleta_da_vm`).
7. **Importada é `ok` ou `parcial`**, nunca `falhou`: aquela execução terminou e gravou o JSON.
8. **A carga é um pacote.** O histórico mora na estação; o banco de produção, só na rede interna da VM. `--salvar-pacote`
   na estação, `--pacote` no contêiner; o pacote leva a lista das chaves de 2026-09-07, e a conferência roda nos dois lados.

### Para a frente C (System), não aplicado aqui

- O `compose-build.yaml` não tem o serviço `radar`, e o comentário do `compose.yaml` manda construir por ele. Sugestão:
  um serviço `radar` com `image: alchemia-radar:${RADAR_RELEASE:?...}` e `build` de contexto
  `${RADAR_DIR:-/home/ubuntu/alchemia-radar}`, `dockerfile: Dockerfile` e o argumento `RADAR_VERSAO: ${RADAR_RELEASE}`.
  Até lá, o `deploy/README.md` constrói por `docker build`.
- No serviço `radar`: `init: true`, `stop_grace_period: 30s` e `logging` `json-file` com `max-size: "10m"` e
  `max-file: "5"` (rotação sem depender do `daemon.json`, ausente na VM). O agendador já trata `SIGTERM` sem o `init`.
- A view `radar.meta` ordenada por `terminada_em desc`, em vez de `id desc`, seria robusta a qualquer ordem de inserção.
  O Radar já se protege (escolha 6): é melhoria, não bloqueio.
- Com `PG_SENHA_RADAR` vazia, o contêiner sobe com senha vazia e a coleta sai 1 com `radar.execucao.falhou`, visível no
  log; a guarda `:?` falharia antes, no `up`.

### Para o fundador

- Proposta para a skill `security-baseline`: a regra `url-com-senha` ignorar `${...}`, como a regra `atribuicao` já faz.
  Hoje a citação da interpolação nesta spec exige uma exceção.
- O que sai na R6 está preparado e listado no `deploy/README.md`; desligar é dele.
