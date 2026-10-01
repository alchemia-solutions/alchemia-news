# Alchemia Radar

O web scraping e o pipeline automatizado de inteligência do nicho da **Alchemia Solutions**
(Computer-Aided Drug Design, AI Drug Discovery, engenharia de proteínas, anticorpos e vacinas).
Coleta determinística, sem LLM, que grava JSON versionado e serve de **back-end** para a página
Radar do **Alchemia System** (`/science/radar`). Até 2026-09-28 se chamava `alchemia-news`.

**Repositório público** no GitHub, `github.com/alchemia-solutions/alchemia-radar` (decisions-log (r), item 5,
2026-09-28; nome e visibilidade conferidos na API pública em 2026-09-30, e o nome antigo responde 301).
Com o nome antigo ficam o repositório no `alchemia-gitstore` e a URL do `origin` local. Índice para
agentes: [`AGENTS.md`](AGENTS.md). Histórico datado: [`docs/HISTORY.md`](docs/HISTORY.md).

---

## Estado (conferido em 2026-09-30)

| Frente | Estado |
|---|---|
| Coleta (Etapa 1a) e Supabase (Etapa 3) | `coleta.yml` no GitHub Actions, três vezes ao dia; único escritor de `pipeline/data/` |
| Radar datado para Science (Etapa 1b) | `research-export.yml`, disparado ao fim de cada coleta; se desliga sozinho sem o segredo `ALCHEMIA_SCIENCE_TOKEN` (se o segredo existe, não foi medido); sempre `--no-pdf` |
| Visualização | Alchemia System, `/science/radar`, lendo `pipeline/data/` e `pipeline/config/` pelo disco ou, sem o checkout, pelo GitHub público |
| `dashboard/` (Next.js) | congelado, sem deploy desde 2026-09-28; o código fica no disco |
| Bots (Axel, Baker, Discord) e newsletter | encerrados; o arquivo da newsletter vai até 2026-09-04 |
| Camada estocástica ("JEV" e Claude) | futura, por spec própria; hoje tudo é determinístico |

---

## O que este repositório contém

| Caminho | O que é |
|---|---|
| `pipeline/collectors/` | os coletores determinísticos, um arquivo por fonte (`feed_collector.py` atende `nature` e `newsletters`) |
| `pipeline/config/` | configuração viva em YAML: empresas, termos, fontes, recursos, fomento, programas |
| `pipeline/data/` | saída do Actions: `articles.json`, `news.json`, `companies_activity.json`, `meta.json`, `runs/` |
| `pipeline/run_all.py` | o orquestrador da coleta |
| `pipeline/research_export.py` | o radar do dia para `alchemia-science` |
| `pipeline/sync_supabase.py` | o espelho no Supabase (Etapa 3) |
| `pipeline/tests/` | testes sem rede e sem escrita em `pipeline/data/` |
| `pipeline/digest.py` | resto dos bots (digest para o Discord); sem chamador |
| `dashboard/` | o antigo painel Next.js, congelado ([`dashboard/README.md`](dashboard/README.md)) |
| `supabase/migrations/` | o schema do Supabase, registro já aplicado |
| `.github/workflows/` | a cadência real |
| `docs/specs/`, `docs/qc/`, `docs/HISTORY.md` | specs, revisões de código e histórico, append-only |

---

## Como a coleta roda

Três vezes ao dia (horários no `cron` de `coleta.yml`, em UTC, com o equivalente local no
comentário), o GitHub Actions:

1. **Etapa 1a:** `python -m pipeline.run_all` roda os coletores, funde com o estado já coletado
   (dedupe por DOI e URL normalizada), grava `pipeline/data/` e um snapshot em `pipeline/data/runs/`.
2. **Etapa 3:** `python -m pipeline.sync_supabase` espelha o dado no Supabase; sem credencial, é
   pulada com aviso e sai 0.
3. Commita `pipeline/data/` de volta, com `[skip ci]`.

Quando a coleta termina bem, `research-export.yml` (Etapa 1b) monta a árvore da empresa no runner
com checkout duplo (este repositório e `alchemia-science`) e roda
`python -m pipeline.research_export --no-pdf`. O script acha `alchemia-science/` subindo a árvore a
partir do repositório (`achar_raiz_da_empresa`), e por isso funciona igual na estação e no runner.

Quantos coletores e quais: conte `pipeline/collectors/` e leia `pipeline/config/sources.yaml`.
Quanto foi coletado: `pipeline/data/meta.json` **do remoto** (o checkout local atrasa).

### Rodar localmente (depuração)

Faça `git pull` antes: o bot do Actions é o dono de `pipeline/data/`.

```bash
cd alchemia-ai/softwares/internos/alchemia-radar
pipeline/.venv/Scripts/python.exe -m pipeline.collectors.arxiv_collector            # um coletor isolado; não grava nada
pipeline/.venv/Scripts/python.exe -m pipeline.research_export --no-pdf --dry-run    # mostra o destino; não grava
pipeline/.venv/Scripts/python.exe -m unittest pipeline.tests.test_raiz_da_empresa -v
pipeline/.venv/Scripts/python.exe -m pipeline.run_all --skip companies,scielo       # GRAVA pipeline/data/: só com motivo
```

---

## Contrato com o Alchemia System

O System só lê, pelos conectores `radar.ts` e `radar-remoto.ts` do repositório dele
(`alchemia-system/packages/core/src/connectors/`; mapa em `alchemia-system/docs/architecture/fontes-de-dado.md`):

- `pipeline/data/meta.json`, `news.json`, `articles.json` e `companies_activity.json`;
- `pipeline/data/newsletter/AAAA-MM-DD.md`, o arquivo histórico da newsletter (parou em 2026-09-04);
- `pipeline/config/funding_channels.yaml`, `corporate_programs.yaml`, `companies.yaml` e `resources.yaml`.

O pipeline não grava o coletor dentro do item; o System o infere pelo formato do item. Mudar
formato, campo ou caminho desses arquivos quebra o `/science/radar`: é mudança entre setores e
passa pelo nó `alchemia-system`.

**Onde há checkout, o System lê o checkout; o dado novo chega no remoto.** O `radar.ts` escolhe o
modo `local` quando `pipeline/data/meta.json` existe no disco, e o `remoto` (JSON do GitHub público,
cache de 15 min) sem o checkout ou com `RADAR_FONTE=remoto`. Na estação, sem `git pull` deste
repositório, o `/science/radar` mostra o último dado puxado. Medido em 2026-09-30: o `meta.json`
local terminou em 2026-09-22T14:15Z; o do remoto, em 2026-09-30T20:18Z.

---

## Radar datado e biblioteca (para Science)

`research_export.py` escreve o radar do dia em `alchemia-science/research/`. O nome do arquivo mantém o
nome antigo de propósito (`AAAA-MM-DD-alchemia-news-radar.md`): é contrato com Science, e trocá-lo
faria a regeneração de um dia antigo criar um segundo arquivo. Com rota aberta confirmada na própria
execução (arXiv, bioRxiv/medRxiv, Unpaywall `is_oa`, Europe PMC), baixa o PDF para
`alchemia-science/alchemia-library/`. No Actions roda sempre com `--no-pdf`, porque o repositório de
destino não versiona PDF: a biblioteca não cresce sozinha até haver destino para os arquivos.

---

## Editais de fomento e programas corporativos

Dois catálogos estáticos, curados à mão a partir de dois guias do fundador, sem coleta e sem LLM:
`pipeline/config/funding_channels.yaml` e `pipeline/config/corporate_programs.yaml`. Cada entrada
cita a fonte (`source_guide`), a data da última revisão (`last_reviewed`) e a prioridade dada pelo
próprio guia (`priority_alchemia`). São retrato da curadoria, não monitoramento de chamada aberta:
confirme sempre no portal oficial. Spec: `docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md`
(o monitoramento de chamada aberta é a Fase 2 dela, em backlog e dependente do fundador).

---

## Supabase

`pipeline/sync_supabase.py` espelha artigos, notícias, empresas, recursos, fomento, programas e
`meta` no projeto Supabase do Radar a cada coleta (Etapa 3), com `SUPABASE_SERVICE_ROLE_KEY` como
segredo do Actions. O leitor era o dashboard (`dashboard/lib/supabase.ts`); o System lê o disco.
Manter, desligar ou apontar o System para lá é decisão do fundador. O schema está em
`supabase/migrations/`, registro já aplicado e nunca editado. Nenhum valor de credencial vive neste
repositório.

---

## Dashboard (congelado)

O painel Next.js em `dashboard/` não tem deploy desde 2026-09-28; a visualização é do System. O
código fica no disco, sem manutenção, como referência. Desligar o projeto na Vercel é ação do
fundador. Detalhe e último estado registrado do deploy: [`dashboard/README.md`](dashboard/README.md).

---

## Limites e LGPD

- **Só metadado público:** título, autores, data, fonte, URL e resumo curto quando a própria API o
  entrega. Nenhum texto completo de terceiro fora das rotas abertas acima.
- **Nenhum dado pessoal coletado.** Redes sociais ficam fora de escopo até nova análise de LGPD
  aprovada pelo fundador.
- **Nunca "todas as notícias".** Quem apresenta o dado declara fontes cobertas, data da última
  coleta e limitações conhecidas.
- **Nunca fabricar número.** Toda contagem vem de `meta.json` ou dos JSON lidos na hora.

---

## Em aberto (conferido em 2026-09-30)

| Item | Decide |
|---|---|
| Projeto do dashboard na Vercel. Último registro (2026-08-26, `docs/HISTORY.md`): produção no ar, congelada numa versão anterior e lendo o Supabase ao vivo, com build novo recusado ("private GitHub organization repository on the Hobby plan"). O estado de hoje não foi medido; enquanto o projeto existir, pode haver um painel do Radar publicado fora do System. | fundador |
| Supabase: seu único leitor conhecido é o dashboard, inclusive essa produção congelada. | fundador |
| System com dado atrasado: depende de `git pull` deste checkout (atraso medido acima). | fundador e `alchemia-system` |
| Segredo `ALCHEMIA_SCIENCE_TOKEN` e o remoto de `alchemia-science` (o repositório local tem um único commit, de 2026-09-09, e nenhum remoto configurado). | fundador |
| O que é "JEV", e a spec da camada estocástica com Claude. | fundador |
| Portão não marcado de `docs/specs/2026-08-18-research-library-integration.md` (implementada). | fundador |
| Restos dos bots, listados no addendum de 2026-09-28 do `docs/HISTORY.md`. Remoção só pela Lixeira. | fundador |
| arXiv: zero sem erro de 2026-09-23 a 2026-09-27, zero legítimo pela regra do coletor (em 2026-09-28: 3 de 3 feeds responderam, 11 anunciados, 0 relevantes); o `meta.json` do remoto de 2026-09-30T20:18Z traz 1 item. A cobertura caiu com a migração para RSS (lote diário de três categorias pequenas, no lugar da busca por janela). | fundador (decisão de cobertura) |
| O GitHub já é `alchemia-radar` (medido em 2026-09-30). Falta trocar o nome antigo no repositório do `alchemia-gitstore`, no ponteiro `.git` e na URL do `origin` local; o padrão `RADAR_REMOTO_REPO` do System ainda usa o nome antigo e depende do redirecionamento (nó `alchemia-system`). | fundador |
| A coleta vai para a VM da Oracle, com cadência própria, e o System lê o dado local da VM (decisions-log (cr), 2026-09-30). Implementação depois do fechamento da v6, por spec; até lá o Actions segue escritor único. | fundador e `alchemia-tech` |

---

*Alchemia Solutions, inteligência de mercado interna. Não redistribuir fora da empresa sem
autorização do fundador.*
