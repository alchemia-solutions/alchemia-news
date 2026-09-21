# AGENTS.md — alchemia-news

> **Índice, não manual.** Diz **onde** procurar; nunca duplica a fonte nem carrega número que
> envelhece. Teto **150 linhas / 12 KB**, imposto por
> `alchemia-ai/alchemia-agents/harness/check_runtime_integrity.py`.
> **Histórico completo** (addenda datados até 2026-09-18, verbatim): [`docs/HISTORY.md`](docs/HISTORY.md)
> — append-only, consultado por `grep` de data, nunca inteiro.

## 1. O que é

Plataforma de **inteligência de notícias e literatura** do nicho da empresa — CADD, AI drug
discovery, engenharia de proteínas/anticorpos/vacinas. Coleta metadado público de fontes acadêmicas
e de imprensa em cadência fixa, e serve tudo num dashboard Next.js.

**Não é setor de negócio** — é infraestrutura de monitoramento, mesma classe do `alchemia-brain`.
**Não toca dado molecular**: só metadado público de publicação, nenhuma relação com o schema do
AURORA nem com o pipeline ATHANOR.

**Nenhum LLM participa da coleta, por decisão de spec.** Relevância é keyword + fonte
determinística, e toda entrada carrega o termo que a trouxe — é o que impede o sistema de fabricar
relevância.

## 2. Dono no harness

| | |
|---|---|
| Nó | `alchemia-news` (dono de `alchemia-ai/alchemia-news/**`) |
| Skills | `news-intelligence-pipeline`, `obsidian-sync`, `agent-self-improvement` |
| Consumidor a jusante | nó `alchemia-bots` (feed do Axel, digest do Baker) e `alchemia-science` (radar + biblioteca) |
| Portão de interface | nó `alchemia-frontend-gate` |
| Hub no vault | `alchemia-brain/02-Harness/news/` |

## 3. Onde está a verdade

| Pergunta | Fonte | Natureza |
|---|---|---|
| Spec aprovada (Portão de Revisão) | `docs/specs/2026-08-17-alchemia-news-intelligence-platform.md` | append-only |
| O que o pipeline faz, e como depurar | skill `news-intelligence-pipeline` | live |
| Quantos coletores existem, e quais | `pipeline/` + `config/sources.yaml` — **conte, não cite** | medido |
| Empresas, termos e fontes monitoradas | `config/companies.yaml`, `keywords.yaml`, `sources.yaml`, `resources.yaml` | live |
| Dado coletado | `pipeline/data/*.json` — **escrito pelo GitHub Actions**, não por você | derivado |
| Cadência real | `.github/workflows/` — a fonte única desde 2026-09-07 | live |
| Estado do deploy | `vercel.json` + o hub no vault | live |

⚠️ **Escritor único.** Desde 2026-09-07 o **GitHub Actions** é o único escritor de `pipeline/data/`;
as duas Tarefas Agendadas do Windows foram **desabilitadas** (não apagadas). Duas cadências gravando
o mesmo diretório causaram conflito real de rebase em 2026-09-01. **Não reative uma sem desligar a
outra.** Duas capacidades pararam junto e o workflow não as cobre: a Etapa 1b (`research_export`,
que alimenta `alchemia-science`) e o alarme de falha.

## 4. Invariantes deste diretório

1. **Nenhum LLM na coleta.** Relevância é determinística e toda entrada carrega o termo que a
   trouxe.
2. **Nunca baixar conteúdo de paywall.** A colheita de texto completo só ocorre com rota aberta
   confirmada na própria execução (arXiv, bioRxiv/medRxiv, Unpaywall `is_oa`, Europe PMC).
3. **Deduplicação é obrigatória.** `common.normalize_url()` alimenta `dedupe_key()` — mexer numa
   sem a outra reintroduz entrada duplicada silenciosamente.
4. **Não editar `pipeline/data/` à mão** — é saída do Actions, e um commit local colide.
5. **Nenhuma mensagem publicada sem o verificador.** `verify_axel_message.py` é obrigatório entre o
   rascunho e a publicação: em 2026-08-21 o Axel publicou uma URL errada num canal público.
6. **Nunca `git commit`/`push`.**

## 5. Antes de implementar

Spec em `docs/specs/AAAA-MM-DD-titulo.md` (skill `alchemia-spec-template`), Portão de Revisão do
fundador, depois implementação. Coletor novo: siga a skill, e meça o delta real antes de ligar a
cadência.

## 6. Em aberto

`alchemia-brain/01-Company/registros/risk-log.md` e `docs/specs/` (Fase 2 — editais de fomento e
programas corporativos, Portão ainda não marcado).
