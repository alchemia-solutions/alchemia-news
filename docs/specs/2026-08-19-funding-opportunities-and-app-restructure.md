# Spec: Editais de Fomento, Programas Corporativos e Reestruturação do App (Fase 2 do alchemia-news)

**Setor:** alchemia-news
**Data:** 2026-08-19
**Status:** aprovado

## Propósito

A spec fundacional (`2026-08-17-alchemia-news-intelligence-platform.md`, aprovada) definiu a Fase 1
do setor: radar determinístico de notícias/artigos/empresas do nicho CADD/AI Drug Discovery. Ela já
previa uma Fase 2 de "funcionalidades adicionais", em backlog.

O fundador pediu explicitamente esta Fase 2 hoje, com três pedidos concretos:

1. Adicionar ao app **editais de fomento à pesquisa** (federal/estadual/saúde/universidades/
   fundações privadas/internacional) e **programas corporativos para startups** (créditos de nuvem,
   SaaS para startups, aceleradoras, parques tecnológicos, hubs de inovação), usando como fonte dois
   guias de referência que ele mesmo compilou: `guia-captacao-programas-corporativos-startups.md` e
   `canais-editais-fomento-brasil.md` (ambos datados agosto/2026, fornecidos nesta conversa).
2. Reestruturar as páginas e a informação do app para ficarem mais claras e objetivas, com mais
   assets interativos, consolidando o `alchemia-news` como ferramenta de uso da **empresa inteira**
   (não só um radar de nicho para o setor que o mantém).
3. Confirmação de contexto: o fundador criou um repositório GitHub **privado** para hospedar o
   aplicativo (`alchemia-solutions/alchemia-news`, mesmo remoto já encontrado configurado localmente
   nesta auditoria) e já fez o primeiro commit/push — ação dele mesmo, fora de qualquer sessão de
   agente, consistente com a política de git da empresa. O deploy real com acesso privado via URL
   fica para uma fase posterior (ver Roadmap, Fase 4) — **não é parte do escopo de implementação
   desta spec**, só é preparado por ela.

## Estado Atual

Verificado por leitura direta nesta sessão (não presumido):

- **Pipeline:** 8 arquivos de coletor (`pubmed`, `biorxiv`, `arxiv`, `chemrxiv_via_crossref`,
  `scielo_via_crossref`, `feed` — rodando 2x, para `nature_feeds` e `newsletter_feeds` —,
  `googlenews`, `companies`), todos alimentando um schema único `common.Item` (`kind: "article"|"news"`,
  ~14 campos, `extra: dict` livre por coletor). Dedupe por `dedupe_key` (DOI > URL normalizada >
  hash `source|title`), merge incremental, zero LLM na coleta (confirmado por grep — a única
  chamada de modelo de toda a árvore de `pipeline/` é no anúncio do Discord, fora deste repositório).
- **Config viva:** `sources.yaml`, `keywords.yaml`, `companies.yaml` (20 empresas),
  `resources.yaml` (9 entradas — bancos/ferramentas, schema `slug/name/full_name/url/type/
  description/license_note`, **sem coleta**, só catálogo estático lido em tempo de requisição).
  `resources.yaml` é o precedente direto para o design desta spec (ver "Arquitetura/Stack").
- **Dashboard:** Next.js 16.3.1 / React 19.2.8 / Tailwind 3.4.19, 7 caminhos servidos (`/`,
  `/noticias`, `/artigos`, `/empresas`, `/empresas/[slug]`, `/bancos-ferramentas`, `/sobre`),
  todos `force-dynamic`, lendo `pipeline/data/*.json` e os YAMLs de config em tempo de requisição
  (sem rebuild). Sidebar fixa, 6 itens de navegação. Identidade visual: fundo escuro, acento ciano,
  tipografia mono para metadado.
- **Disponibilidade real hoje:** o app **não roda como serviço** — é subido à mão
  (`npm run start`) por sessão, e morre com a árvore de processo daquela sessão a menos que suba via
  `Win32_Process`/WMI (sobrevive ao fim da sessão, não a reboot). Não há hospedagem externa nem
  acesso remoto configurado.
- **Duas specs já existem no setor:** a fundacional (aprovada) e
  `2026-08-18-research-library-integration.md` (implementada, Portão de Revisão **não** marcado —
  decisão pendente é especificamente sobre baixar PDF em texto completo automaticamente, não afeta
  esta spec).
- **Nada no schema atual distingue "categoria de conteúdo" além de `kind`** (2 valores) e
  `source_type` (6 valores, todos sobre proveniência editorial). Não existe hoje nenhuma noção de
  prazo/deadline, valor de benefício, elegibilidade ou órgão financiador em nenhuma estrutura de
  dado do setor.

## Estado Alvo

Ao final da Fase 1 desta spec, o `alchemia-news`:

1. Tem dois catálogos novos, estáticos e curados — `pipeline/config/funding_channels.yaml`
   (editais/fomento público: CNPq, FINEP, FAPESP, CAPES, EMBRAPII, BNDES, Sebrae, MDIC, agências
   reguladoras, universidades/ICTs, saúde/PROADI-SUS, fundações privadas, internacional) e
   `pipeline/config/corporate_programs.yaml` (créditos de nuvem, SaaS para startups, aceleradoras
   com e sem equity, parques tecnológicos, hubs corporativos, habitats de inovação nacionais) —
   transcritos dos dois guias de referência, no mesmo espírito de `resources.yaml` (dado curado, não
   coletado, cada entrada com link para a fonte oficial).
2. Tem duas rotas novas no dashboard, `/fomento` e `/programas`, seguindo exatamente o padrão já
   validado de `/bancos-ferramentas` (leitura de YAML em tempo de requisição, agrupamento por
   categoria, sem coleta nem LLM).
3. Tem uma seção "Recomendado para a Alchemia" em cada rota nova, reproduzindo — sem inventar nada
   novo — a priorização que os próprios guias já fazem para o perfil de biotech/CADD/oncologia
   molecular da empresa (guia 1 §10, guia 2 §9).
4. Tem pelo menos três assets interativos reais (não estáticos): filtro/busca por categoria e
   prioridade, checklist de documentos (guia 1 §11), e um tracker de status por oportunidade (não
   aplicado / em preparação / submetido / aprovado / rejeitado), persistido localmente no navegador
   (sem backend novo nesta fase).
5. Tem a sidebar reorganizada em dois grupos — "Inteligência de Mercado" (Notícias, Artigos,
   Empresas, Bancos & Ferramentas) e "Captação de Recursos" (Fomento, Programas) — e a página
   `/sobre` reescrita para descrever o app como ferramenta de uso da empresa inteira, preservando o
   mesmo padrão de transparência sobre fontes/limitações já em vigor.
6. Continua com **zero coleta automática de status "aberto agora"** — nenhuma alegação de que um
   edital está aberto hoje sem verificação na própria execução (mesma disciplina de "nunca fabricar"
   já aplicada ao resto do setor). Monitoramento ativo de chamadas reais é Fase 2 desta mesma spec,
   não implementada agora (ver Roadmap).

## Critérios de Sucesso

- [ ] `pipeline/config/funding_channels.yaml` existe, com todos os canais primários dos dois guias
      (mínimo: CNPq, CAPES, FINEP, MCTI, EMBRAPII, BNDES, Sebrae/InovAtiva, agências reguladoras,
      FAPESP + modalidades PIPE/PITE/CEPID, USP/AUSPIN, PROADI-SUS + 7 hospitais, Serrapilheira,
      Horizon Europe, NIH/Fogarty), cada entrada com `source_guide: canais-editais-fomento-brasil.md`
      e link oficial verificado nesta conversa.
- [ ] `pipeline/config/corporate_programs.yaml` existe, com todos os programas primários do guia 1
      (mínimo: Google for Startups Cloud, AWS Activate, Microsoft Founders Hub, NVIDIA Inception,
      CNPEM/LNBio, SUPERA, Eretz.bio, Cubo Itaú, InovAtiva Brasil), cada entrada com
      `source_guide: guia-captacao-programas-corporativos-startups.md`.
- [ ] Rotas `/fomento` e `/programas` retornam 200 e exibem dado lido dos YAMLs (não hardcoded no
      componente) — verificável comparando uma edição no YAML com o que a página renderiza.
- [ ] Sidebar mostra 8 itens de navegação em 2 grupos; `npm run typecheck` e `npm run build` limpos
      dentro de `dashboard/`.
- [ ] Filtro por categoria/prioridade, checklist de documentos e tracker de status funcionam de
      ponta a ponta no navegador (testado manualmente: clicar, marcar, recarregar a página e
      confirmar persistência via `localStorage`).
- [ ] `/sobre` menciona explicitamente que o app é ferramenta de uso da empresa inteira e preserva o
      aviso "valores/prazos mudam — confirmar na fonte oficial" para toda entrada de fomento/programa.
- [ ] Nenhum teto de crédito, prazo ou valor aparece na UI sem o mesmo qualificador "direcional" que
      os guias originais já carregam.
- [ ] `alchemia-ai/alchemia-agents/harness/check_runtime_integrity.py` continua passando depois da
      mudança (nenhuma quebra de contrato do harness).

## Arquitetura / Stack

**Decisão de modelagem de dado — catálogo estático, não `common.Item`.** Editais e programas
corporativos têm forma diferente de artigo/notícia: são entradas de referência de vida longa
(tier/elegibilidade mudam por edição, não por "nova publicação"), não eventos datados que se
acumulam e deduplicam. Forçá-los em `kind: "opportunity"` dentro de `common.Item` economizaria a
reutilização de `merge_items()`/dedupe, mas exigiria que o dashboard aprendesse a interpretar campos
estruturados dentro de `extra: dict` — perdendo tipagem e clareza. O precedente já validado no
próprio setor é `resources.yaml`: catálogo curado, YAML simples, lido direto por `getResources()` em
`lib/data.ts`, sem coletor, sem dedupe, sem LLM. Esta spec estende exatamente esse padrão, duas
vezes, em vez de sobrecarregar `common.Item` com uma terceira natureza de dado.

**Schema de `funding_channels.yaml`** (uma entrada por canal/agência):
```yaml
- slug: cnpq
  name: "CNPq"
  full_name: "Conselho Nacional de Desenvolvimento Científico e Tecnológico"
  scope: federal            # federal | estadual_sp | saude | universidade_ict | fundacao_privada | internacional
  portal_url: "https://www.gov.br/cnpq/pt-br"
  calls_url: "https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao"
  programs:
    - name: "RHAE — Pesquisador na Empresa"
      note: "Bolsas de RH para empresas — muito relevante para startups"
    - name: "Chamada Universal"
      note: "A mais ampla; ciclos historicamente bienais"
  priority_alchemia: alta    # alta | media | complementar — herdado das seções 9/10 dos guias
  priority_note: "Chamadas CNPq/Decit-SCTIE/MS — Saúde das Mulheres tem linha explícita de câncer de mama"
  requires: ["ICT parceira formalizada", "proponente com doutorado"]
  source_guide: canais-editais-fomento-brasil.md
  last_reviewed: "2026-08-19"
```

**Schema de `corporate_programs.yaml`** (uma entrada por programa):
```yaml
- slug: nvidia-inception
  name: "NVIDIA Inception"
  category: cloud_credits    # cloud_credits | saas_discount | accelerator_no_equity | accelerator_equity | habitat_nacional | hub_corporativo
  region: global              # global | brasil | sp
  portal_url: "https://www.nvidia.com/en-us/startups/"
  benefit_summary: "Créditos DLI, preço preferencial em hardware/software, acesso a NIM/BioNeMo/Clara, sem equity, sem prazo"
  eligibility_summary: "Empresa constituída, <10 anos, ≥1 dev no time, site funcional — candidatar-se como empresa de produto, nunca serviço"
  priority_alchemia: alta
  priority_note: "Stack BioNeMo/Clara é diretamente aplicável a CADD — prioridade máxima do guia"
  source_guide: guia-captacao-programas-corporativos-startups.md
  last_reviewed: "2026-08-19"
```

**Leitura no dashboard:** duas funções novas em `lib/data.ts` — `getFundingChannels()` e
`getCorporatePrograms()` — mesmo padrão de `readYamlSafe` já usado por `getResources()`.
`types.ts` ganha `FundingChannel`/`CorporateProgram` (interfaces TypeScript, não union type de
`ItemKind` — reforça que não é a mesma família de dado).

**Rotas novas:** `app/fomento/page.tsx` e `app/programas/page.tsx`, mesmo padrão de
`app/bancos-ferramentas/page.tsx` (agrupamento por categoria, `PageHeader`, cards). Componentes
novos: `OpportunityFilterBar` (client component, filtro por categoria/prioridade/busca textual),
`DocumentChecklist` (client component, `localStorage`, a partir da lista fixa do guia 1 §11),
`StatusTracker` (client component, `localStorage`, 5 estados por `slug` de oportunidade).

**Navegação:** `Sidebar.tsx` reorganizada em dois grupos com um `<h3>` de seção — sem framework de
navegação novo, é HTML/CSS dentro do componente já existente.

**Sem LLM em nenhuma parte desta spec.** Toda transcrição dos guias para YAML é curadoria humana
(feita nesta implementação, uma vez, revisável), não geração de texto em tempo de execução.

## Dependências

- **De outros setores:** `alchemia-bots` (a spec companheira,
  `alchemia-ai/alchemia-bots/docs/specs/2026-08-19-axel-newsletter-upgrade.md`, depende do schema
  definido aqui para poder citar oportunidades de fomento na newsletter do Axel — se esta spec não
  for implementada primeiro, a newsletter sobe sem essa seção, não é bloqueante para ela).
  `alchemia-brain` recebe o write-back de changelog padrão.
- **De serviços externos:** nenhum novo nesta fase — os dois YAMLs são dado estático, sem chamada
  HTTP em tempo de execução. Fase 2 (backlog) dependeria de acesso HTTP às páginas de chamadas dos
  órgãos.
- **De licenciamento:** nenhum dado de terceiro com licença restritiva é redistribuído — só nomes de
  programas, URLs oficiais e resumos curtos escritos por curadoria própria (não cópia de parágrafo
  inteiro dos guias, para não acumular texto extenso de fonte externa dentro do repositório).

## Riscos e Efeitos de Segunda Ordem

1. **Licenciamento e proveniência:** não aplicável a dado molecular. Risco adjacente real: os dois
   guias de referência são "documento de referência" do próprio fundador — mesmo assim, a
   transcrição para YAML deve ser resumo estruturado em palavras próprias, não cópia extensa
   verbatim, para não acumular um bloco grande de texto de terceiro (mesmo que o próprio guia seja
   compilação de fontes públicas) dentro de um repositório que pode um dia ser tornado mais aberto.
2. **LGPD:** nenhum dado pessoal envolvido nesta fase — só nomes de instituições/programas públicos.
   Se o tracker de status evoluir para multiusuário com login (Fase 3, backlog), LGPD entra em jogo
   ali, não aqui.
3. **Teto de hardware:** não aplicável — conteúdo estático + Next.js, sem processamento pesado.
4. **Acoplamento entre setores:** `alchemia-bots` passa a depender deste schema (ver Dependências).
   Qualquer mudança futura na estrutura dos dois YAMLs precisa avisar aquele setor antes de aplicar.
   Também: como o app não roda como serviço persistente hoje, "sempre atualizado para a empresa
   inteira" depende de alguém manter o processo no ar até a Fase 4 (deploy real) — isso deve ser
   comunicado ao time como "melhor esforço" nesta fase, não como disponibilidade garantida.

## Roadmap

**Fase 1 (esta spec, Portão de Revisão pendente):** dois catálogos estáticos, duas rotas novas,
reestruturação de navegação, três assets interativos client-side (sem persistência multiusuário),
atualização de copy institucional em `/sobre`.

**Fase 2 (backlog, spec própria futura, gated no fundador):** monitoramento ativo de "chamadas
abertas" para as fontes mais estáveis (CNPq, FINEP, FAPESP, EMBRAPII têm HTML estável e paginado,
per o próprio guia 2 §7.2) — cada verificação carimbada com timestamp de "última checagem", nunca
afirmando "aberto agora" sem confirmação na mesma execução. Mesmo padrão de disciplina já usado no
gate de PDF do `research_export.py` (2026-08-18): decisão de licenciamento/escopo de scraping de
site institucional pendente de aprovação explícita antes de implementar.

**Fase 3 (backlog):** persistência real e multiusuário do tracker de status (banco leve local ou
reaproveitamento de infraestrutura existente, a decidir) — hoje é só `localStorage` por navegador.

**Fase 4 (backlog, gated no fundador, explicitamente fora de escopo desta spec por pedido dele):**
deploy privado com acesso via URL para a empresa inteira. Opções a apresentar quando essa fase for
aberta: Vercel Deployment Protection (senha ou SSO por time, zero código novo) para o gate de
acesso; e, para manter o dado sempre atualizado sem expor o Postgres/máquina local, um Vercel Deploy
Hook disparado ao final de `run_alchemia_news.cmd` (redeploy automático 3x/dia) como alternativa mais
simples a servir dado ao vivo de uma máquina local. Nenhuma dessas decisões é tomada nesta spec.

## Agente Responsável (Owner Agent)

`alchemia-news` (`.claude/agents/alchemia-news.md`). Sem dependência de criação de sub-agente novo
— o setor já existe e já é dono deste diretório.

## Portão de Revisão

`[x]` Revisado e aprovado pelo fundador em 2026-08-19.
