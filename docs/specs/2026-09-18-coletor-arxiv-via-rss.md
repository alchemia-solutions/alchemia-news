# Spec — coletor arXiv migra da API Atom para o RSS por categoria

**Data:** 2026-09-18
**Setor:** `alchemia-ai/alchemia-news`
**Status:** Portão de Revisão **APROVADO** pelo fundador nesta conversa
**Risco que fecha:** `alchemia-brain/01-Company/registros/risk-log.md` item **43**

---

## 1. Pedido

> "corrija o coletor arxiv usando o RSS"

## 2. O defeito, medido

O coletor arXiv retornou **0 itens nas últimas 6 execuções seguidas** e em **10 de 15**. O pipeline
**não quebrava**: `ColetaParcial` é exceção declarada, o erro ia para `meta.json` e a execução
seguia — os commits do bot continuavam entrando 3×/dia e tudo *parecia* saudável.

**Causa raiz, isolada por teste ao vivo contra a API:**

| `search_query` | Resposta |
|---|---|
| `all:electron` | **200** |
| `cat:cs.AI` | **200** |
| `cat:q-bio.BM` | **406 Not Acceptable** |
| `all:q-bio` | **406 Not Acceptable** |

**Qualquer `search_query` contendo hífen recebe 406** — e as três categorias monitoradas
(`q-bio.BM`, `q-bio.QM`, `q-bio.MN`) têm hífen todas.

Descartado **por medição**, não por suposição: não é header (406 com e sem `User-Agent`, com
`Accept: */*` e `application/atom+xml`, e com UA de navegador); não é limite de taxa (persiste após
45 s de pausa com requisição única); não é escape (`%2D`, `cat:"q-bio.BM"` e `"cat:q-bio.BM"` dão
406 igualmente); não é host (`arxiv.org` e `export.arxiv.org` respondem 200 a query sem hífen). O
padrão aponta para **filtro de borda na frente da API**, não para o parser de query do arXiv.

## 3. Decisão — RSS por categoria

`https://rss.arxiv.org/rss/<categoria>` responde **200** e carrega tudo o que o coletor precisa.
Verificado nesta data:

| Categoria | Itens hoje |
|---|---|
| `q-bio.QM` | 9 |
| `q-bio.BM` | 0 |
| `q-bio.MN` | 0 |
| `cs.LG` (controle) | 304 |

Campos do item: `title`, `link`, `description` (com o *abstract* embutido), `guid`
(`oai:arXiv.org:<id>`), `category` (múltiplas), `pubDate`, `announce_type`, `dc:creator`.

### 3.1 A diferença de comportamento, declarada e não escondida

| | API Atom (antes) | RSS (agora) |
|---|---|---|
| Alcance | janela de `window_days` (200) | **o lote de anúncio do dia** |
| Filtro de termo | servidor (`abs:"termo"`) | **cliente**, sobre título + abstract |
| Requisições | 1 | **3** (uma por categoria), com pausa entre elas |
| Backfill | possível | **impossível** |

Para monitoramento contínuo isto **não é perda**: o pipeline roda 3×/dia e deduplica, então nenhum
anúncio escapa. O que se perde é a capacidade de **recuperar histórico** — e ela estava quebrada de
qualquer modo, já que a API não responde.

### 3.2 `0` deixa de ser ambíguo

Categoria pequena sem anúncio no dia devolve **0 legitimamente** (`q-bio.BM` e `q-bio.MN` hoje). O
coletor passa a distinguir, no próprio `meta.json`:

- **feed buscado com sucesso e vazio** → conta 0, `error: null`, e o log diz quantos feeds
  responderam.
- **feed que falhou na requisição** → `ColetaParcial`, nomeando a categoria.

Sem isso, o dia quieto e o coletor morto ficam com a mesma assinatura — que é exatamente como este
defeito sobreviveu seis execuções.

### 3.3 Invariantes do setor, preservados

- **Nenhum LLM.** O filtro continua sendo keyword determinística.
- **Toda entrada carrega o termo que a trouxe.** Como o filtro saiu do servidor para o cliente,
  `keywords_matched` passa a registrar **os termos de `arxiv_query_terms` que casaram** mais os
  `topics` — mais honesto que antes, quando o termo que trouxe ficava implícito na URL da query.
- **Formato de saída inalterado** — `common.Item(...).to_dict()`, mesma forma que o pipeline e o
  dashboard já consomem.
- **Deduplicação entre categorias**: um preprint aparece em várias (`cross`), e é emitido uma vez.

## 4. Fora de escopo

- **`biorxiv`** (falha de paginação em `cursor=750`, consome 367 s de 409 s) e **`newsletters`**
  (1 de 5 feeds devolve HTML) — achados reais da mesma leitura, mas ambos **entregam itens** e
  merecem correção própria.
- **`nature` em 0** é desativação deliberada, já documentada. Não é falha.

## 5. Critérios de sucesso

1. O coletor roda contra o arXiv real e devolve itens, com os feeds das 3 categorias buscados.
2. A forma de saída é idêntica à anterior — verificada campo a campo contra `articles.json`.
3. Dia quieto devolve `0` **sem** erro; falha de rede devolve `ColetaParcial` nomeando a categoria.
4. Nenhuma duplicata entre categorias.
5. `python -m pipeline.run_all` (ou o coletor isolado) executa sem exceção.

---

## Portão de Revisão

- [x] **Aprovado pelo fundador** — 2026-09-18, por instrução direta citada no §1.
