# Frontend Quality Gate — `alchemia-news/dashboard`

**Data:** 2026-08-21
**Nó:** `alchemia-frontend-gate` · **Skill:** `frontend-quality-gate`
**Alvo:** `alchemia-ai/alchemia-news/dashboard`, servido em `localhost:3001` (`npm run dev`)
**Spec de origem:** `alchemia-ai/alchemia-agents/docs/specs/2026-08-21-frontend-quality-gate.md` (Fase 2)

**Contexto que muda a leitura deste relatório:** este app foi auditado e **corrigido** mais cedo
nesta mesma data (ver `AGENTS.md` deste setor, addendum 2026-08-21). Esta passada é a verificação
independente daquelas correções, com o gate formal — e a primeira medição dos limiares que aquela
auditoria não cobriu.

## Resumo

| | |
|---|---|
| 🔴 Bloqueante | 1 |
| 🟡 Importante | 1 |
| 🟢 Sugestão | 0 |
| ✅ Passou | F1, F2, F3, F4, F7, F8, F9, F10 |

**Oito dos dez limiares passam.** Os dois que falham são a mesma causa raiz — ausência de paginação
— e estão explicitamente **bloqueados numa decisão do fundador** (pergunta P6 da auditoria de hoje:
histórico completo ou 50-por-página com busca), não por impedimento técnico.

---

## 🔴 N1 — `/artigos` entrega 3,36 MB de HTML (F5)

Medido morno, segunda passada, servidor já compilado e cache do Supabase quente:

| Rota | Tempo | HTML | Limiar F5 (≤ 500 KB) |
|---|---|---|---|
| `/artigos` | 3,159 s | **3.359.639 B (3,36 MB)** | 🔴 **6,7×** acima; acima do teto de 2 MB |
| `/noticias` | 2,486 s | **1.938.436 B (1,94 MB)** | 🟡 3,9× acima |
| `/fomento` | 0,175 s | 279.591 B | ✅ |
| `/programas` | 0,116 s | 187.938 B | ✅ |
| `/` | 0,097 s | 68.800 B | ✅ |
| `/empresas` | 0,086 s | 45.888 B | ✅ |
| `/bancos-ferramentas` | 0,081 s | 39.796 B | ✅ |
| `/sobre` | 0,052 s | 30.809 B | ✅ |
| `/newsletter` | 0,061 s | 23.116 B | ✅ |

**Causa:** as duas rotas renderizam a lista inteira no servidor, sem paginação — 491 e 500 cartões.
O teto de 500 itens introduzido em 2026-08-20 resolveu o custo *da consulta* ao Supabase; o custo de
*renderizar e transmitir* permaneceu integral.

**Cenário de falha:** em rede móvel de 4G a ~2 Mbps reais, 3,36 MB são mais de 13 segundos só de
transferência, além dos 3,2 s de servidor. As outras sete rotas provam que não é problema de
arquitetura — é dessas duas telas.

**Bloqueado, não esquecido.** A correção certa depende de P6.

---

## 🟡 N2 — `/artigos` e `/noticias` acima do teto de tempo (F6)

3,159 s e 2,486 s contra limiar de 1,0 s. Mesma causa raiz de N1 — listado à parte porque tempo e
peso são limiares independentes, e a correção de um pode não fechar o outro (virtualização
resolveria o tempo de render mas não o peso do HTML; paginação resolve os dois).

As demais sete rotas ficam entre **0,052 s e 0,175 s** — todas com folga de mais de 5×.

---

## O que passou

| Limiar | Medido | Veredito |
|---|---|---|
| F1 — conteúdo em 375 px (≥ 320) | **343 px** | ✅ |
| F2 — overflow horizontal | **0 px** | ✅ |
| F3/F4 — contraste | **0 reprovações** | ✅ |
| F7 — foco visível | regra global `:focus-visible` em `globals.css` | ✅ |
| F8 — skip-link | presente, primeiro elemento focável | ✅ |
| F9 — literal numérico na apresentação | só `404` em `not-found.tsx` (legítimo) | ✅ |
| F10 — landmarks e ARIA | `nav` 1 · `main` 1 · `h1` 1 · **18** atributos ARIA | ✅ |

**F1 e F2 verificados na casca corrigida hoje:** a 375 px a sidebar fica em `left: -240px`
(off-canvas), o botão de menu está presente, e o conteúdo ocupa 343 px. Antes das correções desta
data eram **71 px** — o gate confirma o ganho de forma independente.

**F3/F4 medidos com o script corrigido** (ver Nota de método): zero reprovações contra o fundo real
de cada elemento. Confirma a correção `slate-500/600 → slate-400` aplicada hoje, e mostra que ela
não deixou nenhum caso residual nos cartões, que têm fundo próprio.

**F9 é o limiar que este app já reprovou no passado** — `'22 empresas monitoradas'` hardcoded,
achado em 2026-08-18 quando a poda de fontes levou o YAML de 22 para 20. Hoje passa limpo.

---

## Nota de método — o script de contraste foi corrigido durante esta rodada

A primeira versão do auditor de contraste compunha toda cor de texto sobre o fundo do `<body>`,
ignorando que botão, cartão e pílula têm fundo próprio. Isso gerou um falso positivo no outro alvo
desta Fase 2 (ver `alchemia-database/website/docs/qc/2026-08-21-frontend-quality-website.md`,
seção "Nota de método").

**Os números de contraste deste relatório usam a versão corrigida** — cada medida é feita contra o
primeiro ancestral com `background-color` opaco. Isso importa especialmente aqui: o dashboard usa
`.alchemia-card` com gradiente semitransparente sobre o navy, e a versão antiga do script poderia
tanto perder um caso real quanto inventar um.

---

## Comparação com a auditoria manual de hoje

A auditoria manual de mais cedo encontrou quatro defeitos e corrigiu três. Este gate, rodando os dez
limiares de forma independente, **confirma as três correções** (F1/F2, F3/F4, F7/F8/F10) e
**reencontra o quarto** (F5/F6, peso e tempo) exatamente onde ela o deixou — bloqueado em P6.

Nenhum defeito novo apareceu. Para uma primeira passada formal sobre um app recém-corrigido, isso é
o resultado esperado; se tivesse aparecido um 🔴 novo, o mais provável seria defeito no gate, não no
app.

---

*Nenhum arquivo do alvo foi modificado por esta passada. Nenhum commit foi feito. O índice
`alchemia-ai/REVIEW.md` não foi editado — dono único é o `alchemia-quality-gate`, que deve indexar
este relatório.*

---

## Addendum — 2026-08-21 (mesma sessão): N1 e N2 corrigidos — os 10 limiares passam

A pedido do fundador ("corrija também todos esses problemas encontrados"), a paginação foi
implementada. **Os dois únicos achados deste relatório estão fechados; o alvo agora passa em
F1–F10.**

`components/Pagination.tsx` (novo) — `?page=N`, 60 itens por página, server component (nenhum JS de
cliente para navegar; funciona com JS desabilitado). Cada página tem URL própria, compartilhável;
o filtro `?fonte=` é preservado ao paginar. Janela curta de links (nunca imprime 40 números).

**Medido depois, mornas, mesma máquina e mesma metodologia de antes:**

| Rota | Antes | Depois | Ganho |
|---|---|---|---|
| `/artigos` | 3.359.639 B · 3,159 s | **391.149 B · 0,335 s** | −88 % peso · −89 % tempo |
| `/noticias` | 1.938.436 B · 2,486 s | **269.392 B · 0,315 s** | −86 % peso · −87 % tempo |

As 9 rotas do app agora ficam **entre 23 KB e 391 KB** e **entre 0,041 s e 0,335 s** — todas dentro
de F5 (≤ 500 KB) e F6 (≤ 1,0 s), com folga mínima de 1,3× no pior caso.

Verificado além do peso: `aria-label="Paginação"` presente como landmark; links de página reais no
HTML; `?fonte=PubMed&page=2` preservando o filtro; 120 ocorrências de `.alchemia-card` por página
(60 itens × 2), consistente com o `PAGE_SIZE`.

**Escopo honesto — o que a paginação NÃO resolveu.** `fetchItemsByKind` continua com o teto de
`DEFAULT_ITEM_LIMIT = 500` (`lib/supabase.ts`), então `/noticias` pagina sobre os **500 mais
recentes**, não sobre os 2.103 do banco. Os rótulos seguem dizendo "Recentes (N)", nunca "Todos" —
correto, não uma omissão. Dar acesso ao histórico completo exige subir o teto, o que reintroduz o
estouro do limite de 2 MB por entrada do `unstable_cache` já documentado em 2026-08-20 — é a
pergunta **P6**, decisão de produto do fundador, deliberadamente não resolvida por um agente.

**Estado final deste alvo: 🔴 0 · 🟡 0 · 🟢 0 · ✅ F1–F10.**
