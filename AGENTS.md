# AGENTS.md — alchemia-radar

> **Índice, não manual.** Diz **onde** procurar; nunca duplica a fonte nem carrega número que
> envelhece. O teto de linhas e bytes vive em `alchemia-ai/ai-engineering/harness/harness_contract.py`
> (`INDEX_MAX_LINES`, `INDEX_MAX_BYTES`) e é imposto por `check_runtime_integrity.py`.
> **Histórico completo** (addenda datados, verbatim): [`docs/HISTORY.md`](docs/HISTORY.md)
> — append-only, consultado por `grep` de data, nunca inteiro.

## 1. O que é

**Alchemia Radar** (até 2026-09-28, `alchemia-news`): todo o web scraping e o pipeline automatizado
de inteligência do nicho da empresa (CADD, AI drug discovery, engenharia de proteínas, anticorpos e
vacinas). Coleta **metadado público** de fontes acadêmicas e de imprensa em cadência fixa e grava
JSON versionado. É o **back-end** da visualização do Radar no **Alchemia System** (`/science/radar`);
quem mostra é o System, e o Radar não publica front-end.

Declaração do fundador (2026-09-28): *"o alchemia-news agora vai ser o radar alchemia e vai funcionar
como o back-end para a visualização no front-end do alchemia-system, não vamos ter mais deploy na
vercel para o alchemia-news, somente o alchemia radar que agora vai ser toda a parte de
web-scrapping e o pipeline automatizado, depois vamos implementar o JEV e a parte estocástica com
Claude mas agora vai continuar sendo determinístico por enquanto"*.

- **Determinístico.** Nenhum LLM participa da coleta: relevância é palavra-chave + fonte, e toda
  entrada carrega o termo que a trouxe (`keywords_matched`). O "JEV" e a camada estocástica com
  Claude virão depois, por spec própria. "JEV" não está definido em nenhum documento; fica literal.
- **Sem deploy na Vercel.** O `dashboard/` Next.js fica no disco, congelado: [`dashboard/README.md`](dashboard/README.md).
- **Sem bots.** Axel, Baker e o Discord saíram da empresa em 2026-09-28; nada aqui publica mensagem.
- **Não toca dado molecular**, nem o schema do AURORA, nem o pipeline ATHANOR.

A pasta se chama `alchemia-radar`, e o GitHub também: `github.com/alchemia-solutions/alchemia-radar`, público (API
pública, 2026-09-30; o nome antigo responde 301). Com o nome antigo ficam, até o fundador trocá-los, o
repositório no `alchemia-gitstore` e a URL do `origin` local.

## 2. Dono no harness

| | |
|---|---|
| Nó | `alchemia-radar` (**Kepler**), dono de `alchemia-ai/softwares/internos/alchemia-radar/**` |
| Setor | Alchemia AI (dono humano Aryel Bezerra); "Radar" também é escopo declarado de Alchemia Science (Andrei Felix): `harness/company-tree.json` |
| Skills | `news-intelligence-pipeline`, `obsidian-sync`, `agent-self-improvement` |
| Consumidores | **Alchemia System** (nó `alchemia-system`): lê `pipeline/data/` e `pipeline/config/` pelo disco ou, sem o checkout, pelo GitHub público (`RADAR_FONTE`) · **`alchemia-science`**: o radar datado em `research/` e a `alchemia-library` |
| Portões | `alchemia-quality-gate` (código) · `alchemia-frontend-gate` (interface) |
| Hub no vault | `alchemia-brain/03-Softwares/internos/radar/` |

## 3. Onde está a verdade

| Pergunta | Fonte | Natureza |
|---|---|---|
| O que roda hoje, o que parou, o que está em aberto | [`README.md`](README.md) | live |
| A decisão de 2026-09-28 e o escopo declarado | `alchemia-ai/ai-engineering/docs/specs/2026-09-28-nova-arvore-da-empresa.md` + `alchemia-ai/ai-engineering/harness/company-tree.json` | aprovada + live |
| Spec do produto | `docs/specs/2026-08-17-alchemia-news-intelligence-platform.md` (as demais em `docs/specs/`) | append-only |
| Como rodar, depurar e estender | skill `news-intelligence-pipeline` | live |
| Quais coletores existem | `pipeline/collectors/` + `pipeline/config/sources.yaml`: **conte, não cite** | medido |
| Empresas, termos, fontes, fomento, programas | `pipeline/config/*.yaml` | live |
| Quanto foi coletado | `pipeline/data/meta.json` e `pipeline/data/runs/` **do remoto**: o checkout local atrasa | derivado |
| Cadência real | `.github/workflows/coleta.yml` e `.github/workflows/research-export.yml` | live |
| O que o System lê (o contrato) | `alchemia-ai/softwares/internos/alchemia-system/packages/core/src/connectors/radar.ts` e `radar-remoto.ts` · `alchemia-system/docs/architecture/fontes-de-dado.md` | live |
| Estado operacional no vault | `alchemia-brain/03-Softwares/internos/radar/alchemia-radar-state.md` | live |

⚠️ **Escritor único.** Desde 2026-09-07 o **GitHub Actions** é o único escritor de `pipeline/data/`.
As duas Tarefas Agendadas do Windows, que mantêm o nome antigo ("Alchemia News - Coleta" e "- Pos-Coleta"),
estão desabilitadas (`schtasks`, 2026-09-30), e o `.cmd` que chamavam saiu com o `alchemia-bots`, aposentado.
**Não reative uma cadência local sem desligar a outra.**

## 4. Invariantes deste diretório

1. **Nenhum LLM na coleta** enquanto a spec da camada estocástica não for aprovada. Relevância
   determinística, e toda entrada carrega o termo que a trouxe.
2. **O que o System e Science leem é contrato entre setores.** Formato e caminho de `pipeline/data/`
   e `pipeline/config/`, e o nome do radar, que mantém o nome antigo de propósito
   (`AAAA-MM-DD-alchemia-news-radar.md`, tag `fonte/alchemia-news`): mudar qualquer
   um quebra o `/science/radar` ou duplica o radar do dia.
3. **Nunca baixar conteúdo de paywall.** Texto completo só com rota aberta confirmada na própria
   execução (arXiv, bioRxiv/medRxiv, Unpaywall `is_oa`, Europe PMC).
4. **Deduplicação é obrigatória.** `common.normalize_url()` alimenta `dedupe_key()`: mexer numa sem
   a outra reintroduz duplicata em silêncio.
5. **Não editar `pipeline/data/` à mão**: é saída do Actions, e um commit local colide com o do bot.
6. **Caminho fora do repositório se acha por marcador, nunca por profundidade**
   (`research_export.achar_raiz_da_empresa`, testado em `pipeline/tests/`).
7. **Nunca `git commit`/`push`.** Remoção só pela Lixeira (`alchemia-ai/ai-engineering/harness/lixeira.py`).

## 5. Antes de implementar

Spec em `docs/specs/AAAA-MM-DD-titulo.md` (skill `alchemia-spec-template`), Portão de Revisão do
fundador, depois implementação. Coletor novo mede o delta real antes de entrar na cadência. Começam
por spec própria: a camada estocástica ("JEV" e Claude), fonte nova, e qualquer mudança no que o
System lê. Mudança em `.github/workflows/` só vale no CI depois que o fundador der `push`.

## 6. Em aberto

O registro vivo é `alchemia-brain/01-Enterprise/registros/risk-log.md`; a lista do Radar, com data e
medição, está no [`README.md`](README.md), seção "Em aberto". Escalam ao fundador: desligar o
projeto na Vercel, o destino do Supabase sem o dashboard, o segredo `ALCHEMIA_SCIENCE_TOKEN`, o que
é "JEV", e o Portão ainda não marcado de `docs/specs/2026-08-18-research-library-integration.md`. A mudança
da coleta para a VM, com cadência própria (decisions-log (cr), 2026-09-30), vem depois do fechamento da v6, por spec.
