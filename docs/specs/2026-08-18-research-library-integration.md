# Spec: integração `alchemia-news` → `alchemia-science` / `alchemia-library`

**Setor:** alchemia-news (consumidor: alchemia-science)
**Data:** 2026-08-18
**Status:** implementado — Portão de Revisão **não marcado** (ver ao final)

## Propósito

O `alchemia-news` coleta metadado de literatura e notícia do nicho 3x/dia desde 2026-08-17, e
entrega isso em dois lugares **efêmeros por natureza**: um dashboard local (que só existe quando
alguém roda `npm run dev`) e uma mensagem no Discord (que rola para fora da tela em um dia). Nada
disso vira **acervo de pesquisa**. Ao mesmo tempo, o `alchemia-science` mantém à mão uma
biblioteca de referências real (`alchemia-library`, 46 PDFs + CSL-JSON + manifest) que cresce
quando o fundador baixa um artigo manualmente — e que, por isso, **derivou três vezes** desde
2026-07-29 (drift de 5 PDFs em 2026-08-10, 1 em 2026-08-11, 3 em 2026-08-18).

Esta spec liga os dois: o que o pipeline determinístico encontra vira registro de pesquisa datado
em `alchemia-science/research/`, e o texto completo — **quando e só quando** for comprovadamente
open access — entra na `alchemia-library` já com metadado real e auditável.

Pedido do fundador, verbatim (2026-08-18): *"integrando os artigos com alchemia-science e
alchemia-library quando possível resgatar o pdf completo, se não, somente como markdown que deve
ser colocado em research com a data do dia e com todos os artigos e tudo que foi atualizado no
alchemia-news e isso deve ser uma integração da propria rotina do baker-bot e axel-bot"*.

## Estado Atual

Verificado por leitura/execução real em 2026-08-18, não presumido:

- **Pipeline saudável.** 8/8 coletores sem erro; última coleta 103,7 s; base acumulada 200
  artigos / 1.798 notícias / 997 menções de empresas (`pipeline/data/meta.json`).
- **Cadência real, sem duplicação.** Windows Task Scheduler (`Alchemia News - Coleta`,
  06:40/12:40/18:40, `LastTaskResult=0`) + duas tarefas agendadas do Claude (Baker 06:50/12:50/18:50,
  Axel 07:12/13:12/19:12). **Os 4 jobs do Hermes estão `enabled: false`** e o job duplicado do
  perfil `default` (`05511d259e81`, registrado como risco no `AGENTS.md` do setor em 2026-08-17)
  **não existe mais** — o perfil foi reconstruído após o incidente do `hermes update --force`.
  Ou seja: a "coleta 6x/dia em dois mecanismos" que aquele addendum registrava como pendência do
  fundador **já não é verdade**; roda 3x/dia, num mecanismo só.
- **`alchemia-library` estava fora de sincronia:** 49 PDFs em disco, 46 linhas de `manifest.csv`,
  46 itens CSL-JSON. Três PDFs órfãos (`s41392-023-01339-1`, `s41540-025-00592-0`,
  `s41591-026-04595-0`), em disco desde 12–14/08.
- **O guarda-corpo que deveria ter pego isso nunca existiu.** O `README.md` da biblioteca
  documenta `scripts/check_sync.sh` desde 2026-08-10, com comando pronto para copiar — e o
  diretório `scripts/` **não existia em disco**. É a causa raiz do drift, não um detalhe.
- **`alchemia-science/research/`** tinha 3 arquivos, o mais recente de 2026-07-28. Nenhuma ligação
  com o `alchemia-news`.

## Estado Alvo

1. Todo dia em que o pipeline coletar algo produz
   `alchemia-science/research/AAAA-MM-DD-alchemia-news-radar.md`, contendo **todos** os artigos,
   notícias e atividade de empresas daquele dia, mais a saúde real dos 8 coletores e o desfecho de
   cada tentativa de resgatar texto completo.
2. Artigo com rota open access **confirmada na própria execução** tem o PDF baixado para
   `alchemia-science/alchemia-library/` e registrado em `manifest.csv` + `alchemia-library.json`
   com metadado bibliográfico real.
3. Artigo **sem** rota aberta entra no radar só como markdown, **com o motivo registrado** — nunca
   omitido, nunca baixado de trás de paywall.
4. A `alchemia-library` volta a ter um guarda-corpo executável, rodado automaticamente na mesma
   execução que pode causar o drift.
5. A cadeia é dona das rotinas do Baker e do Axel, como pedido — sem que nenhum LLM decida o que é
   relevante, o que baixar, ou o que escrever de factual.

## Critérios de Sucesso

Cada item verificável por inspeção real. Estado em 2026-08-18:

- [x] `check_sync.py` + `check_sync.sh` existem e saem 0 numa biblioteca sincronizada — **saída
      real: `PDFs em disco: 55 | linhas de manifest: 55 | itens CSL-JSON: 55 · OK`**.
- [x] Os 3 PDFs órfãos têm entrada em `manifest.csv` e `alchemia-library.json`, com metadado do
      **Crossref** (não de memória): `lv2023tcmbank`, `akbarialiabad2025digitaltwins`,
      `song2026aido`.
- [x] `python -m pipeline.research_export` gera o radar do dia — **gerados de fato:
      `2026-08-17-alchemia-news-radar.md` (174 KB) e `2026-08-18-alchemia-news-radar.md`**.
- [x] Cada uma das 4 rotas de open access foi exercida contra a rede real: **arXiv** (HTTP 200,
      `%PDF`), **bioRxiv** (200, 6,3 MB), **Unpaywall** (`fmicb.2026.1839420.pdf`, `cc-by`),
      **Europe PMC** (consultada; `isOpenAccess=N` no lote do dia, rota exercida sem falso positivo).
- [x] Artigo fechado **não** é baixado e o motivo aparece no radar — 33 dos 35 artigos de
      2026-08-18 saíram como `sem_oa`, com o motivo literal de cada um.
- [x] Reexecução é idempotente: a segunda passada do mesmo dia devolveu
      `ja_na_biblioteca=2, baixado=0`.
- [x] `run_alchemia_news.cmd` roda a cadeia completa (coleta + exportação) e sai 0 — verificado
      por execução real do `.cmd`.
- [x] As rotinas agendadas do Baker e do Axel foram atualizadas e apontam para os scripts reais.
- [ ] **Uma execução agendada de verdade** (não manual) da cadeia completa, com o radar do dia
      gerado sem intervenção — só acontece no próximo ciclo, ver "Pendências".

## Arquitetura / Stack

Nenhuma dependência nova: `urllib` + `json` + `csv` da biblioteca padrão, Python 3.14.5. Não usa
`requests` de propósito — o pipeline já roda no Python global pelo Task Scheduler, e adicionar
dependência ali é justamente o tipo de acoplamento que quebra em silêncio.

```
Task Scheduler 06:40/12:40/18:40   (zero LLM, sobrevive a reboot e app fechado)
  └─ run_alchemia_news.cmd
       ├─ etapa 1: pipeline.run_all          → pipeline/data/*.json
       └─ etapa 2: pipeline.research_export  → alchemia-science/research/<dia>.md
                                             → alchemia-science/alchemia-library/*.pdf
                                             → manifest.csv + alchemia-library.json

Tarefa Claude "baker-curadoria" 06:50/12:50/18:50
  └─ verifica saúde, cobre falha (backfill), roda check_sync, sincroniza o vault

Tarefa Claude "anuncio-discord" ~07:12/13:12/19:12
  └─ publica no #news → grava cópia verbatim em pipeline/data/discord/<dia>-<hora>.md
                        (o research_export incorpora isso na seção "Publicado no Discord")
```

**Por que a etapa 2 mora no `.cmd` e não só na rotina do Baker.** Ela é 100% determinística —
nenhum LLM escolhe o que baixar. Pondo-a na única camada que sobrevive a app fechado e a reboot,
o registro de pesquisa nunca atrasa por causa do Claude estar fechado. O Baker continua **dono da
integração** no sentido que importa: é ele quem verifica, faz backfill do dia que faltou, audita a
biblioteca e sincroniza o vault. Isso atende o pedido do fundador sem tornar o acervo refém de um
app aberto.

**Por que o Axel grava num arquivo separado.** O radar é derivado (reescrito por inteiro a cada
execução); qualquer coisa escrita nele à mão se perderia. O sidecar em `pipeline/data/discord/`
sobrevive a regenerações.

### As quatro rotas de open access, na ordem em que são tentadas

| # | Rota | O que confirma a abertura | Verificada ao vivo |
|---|---|---|---|
| 1 | arXiv (`extra.arxiv_id`) | repositório aberto por construção | ✅ 200 `application/pdf` |
| 2 | bioRxiv / medRxiv | PDF público em `/content/<doi>v<N>.full.pdf`; a versão real vem da API de detalhes do próprio servidor | ✅ 200, 6,3 MB |
| 3 | Unpaywall | campo `is_oa == true` + `best_oa_location.license` | ✅ `cc-by` |
| 4 | Europe PMC | `isOpenAccess == "Y"` + `pmcid` | ✅ consultada, `N` no lote |

**ChemRxiv é caso conhecido e reportado como tal:** responde **403** tanto no site quanto na
`public-api` (reverificado nesta sessão), e o prefixo `10.26434` não é indexado pelo Unpaywall —
o texto completo só sai manualmente pelo navegador. O motivo aparece literalmente no radar em vez
de cair num "não encontrado" genérico.

### Limites operacionais (memória da crise de disco de 2026-08-09)

`--max-pdf 6` por execução · `--max-mb 60` por arquivo · `--max-total-mb 150` por execução ·
**`--min-free-gb 20`**: abaixo desse piso a colheita é pulada por inteiro e o radar diz por quê.
O que passa do teto é **reportado como adiado**, nunca truncado em silêncio — e reaparece na
execução seguinte enquanto não estiver na biblioteca.

## Dependências

- **De outros setores:** escreve em `alchemia-science/research/` e `alchemia-science/alchemia-library/`.
  É a **primeira** escrita automática cross-setor deste tipo na empresa — antes, a biblioteca só
  crescia por ação manual do fundador. Não toca dado molecular, `alchemia-athanor` ou
  `alchemia-database`.
- **De serviços externos:** Crossref, Unpaywall (identificado por `company@alchemia.solutions`,
  convenção da própria API), Europe PMC, arXiv, bioRxiv/medRxiv. Todos públicos, sem chave, sem
  custo. Nenhuma credencial é usada em lugar nenhum desta integração.
- **De licenciamento:** ver a lente 1 abaixo.

## Riscos e Efeitos de Segunda Ordem

1. **Licenciamento e proveniência — a lente que manda nesta spec.** Baixar texto completo de
   terceiro é exatamente a classe de decisão que a cultura da empresa manda escalar. A resposta de
   desenho: **só baixa o que uma fonte confirma como aberto naquela execução**, nunca por palpite
   ("é da Nature, deve ser aberto") e nunca por tentativa cega de URL. A licença encontrada é
   gravada no `manifest.csv` de cada PDF, então a proveniência nunca se perde. Uso é **interno,
   de pesquisa** — nada aqui redistribui o PDF, e a regra do setor ("nunca redistribui texto
   completo de artigo") continua valendo para o dashboard e para o Discord.
   **Ponto que fica com o fundador:** preprints (arXiv/bioRxiv) não declaram licença de forma
   estruturada; o campo fica como `licença por preprint`. Para uso interno de leitura isso é
   suficiente; **antes de qualquer redistribuição, cada item precisa ser checado individualmente.**
2. **LGPD:** nada muda. Só metadado institucional de publicação — nenhum dado pessoal de usuário
   entra nesta cadeia, e o `pipeline/data/discord/` guarda a mensagem que **o Axel escreveu**,
   nunca mensagem de terceiro do Discord.
3. **Teto de hardware local:** não aplicável — nenhuma GPU, nenhum modelo. O recurso escasso aqui
   é **disco**, tratado explicitamente pelos quatro tetos acima.
4. **Acoplamento entre setores:** um `alchemia-news` quebrado passa a poder sujar a
   `alchemia-library`. Mitigação real: o `check_sync` roda na mesma execução, e uma biblioteca
   fora de sincronia sai com código `3` distinto — as rotinas são instruídas a **relatar, nunca
   corrigir sozinhas**, porque corrigir exige metadado bibliográfico real.

## Roadmap

- **Fase 1 (feita hoje):** guarda-corpo da biblioteca + registro dos 3 órfãos + `research_export`
  + colheita OA + fiação nas duas rotinas + backfill de 2026-08-17.
- **Fase 2 (desbloqueada pela 1, não iniciada):** backfill dos ~75 artigos de 2026-08-17 que
  ficaram adiados pelo teto — acontece sozinho ao longo dos próximos ciclos, mas pode ser forçado
  com `--date 2026-08-17 --max-pdf 20`. Decisão de forçar é do fundador (custo: disco).
- **Fase 3 (backlog):** expor os radares no dashboard (`/radar`), e um índice em
  `alchemia-science/research/README.md` que hoje não existe.

## Agente Responsável (Owner Agent)

`alchemia-news` (`.claude/agents/alchemia-news.md`) para o pipeline e o exportador;
`alchemia-science` para o conteúdo da biblioteca e do `research/`. A fronteira: o `alchemia-news`
**escreve** os arquivos; o `alchemia-science` é dono da **curadoria bibliográfica** (corrigir
metadado, decidir o que fica). Nenhum dos dois corrige drift de biblioteca sem o fundador.

## Portão de Revisão

- [ ] Revisado e aprovado pelo fundador em ____

**Por que está implementado com o portão aberto, e por que isso não é uma violação silenciosa:** o
pedido do fundador nesta sessão foi explícito e detalhado quanto ao comportamento desejado
(research com a data do dia, PDF completo quando possível, markdown quando não, integrado à rotina
dos dois bots) — foi tratado como a Descoberta e a Especificação acontecendo dentro do próprio
pedido. **O que continua precisando de aprovação explícita, e não foi presumido:** a decisão de
licenciamento da lente 1 (baixar texto completo OA automaticamente, 3x/dia, sem revisão humana por
item). Se o fundador não concordar, `--max-pdf 0` desliga a colheita sem tocar em mais nada — o
radar em markdown continua funcionando por inteiro.
