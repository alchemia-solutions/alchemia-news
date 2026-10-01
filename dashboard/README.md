# dashboard/ — congelado, sem deploy desde 2026-09-28

> **Sem deploy desde 2026-09-28.** A visualização do Radar é do **Alchemia System**, na rota
> `/science/radar` (`alchemia-ai/softwares/internos/alchemia-system/apps/web/app/(app)/science/radar/`).
> Este painel Next.js fica no disco como referência e não recebe manutenção.

Decisão do fundador em 2026-09-28, com o Radar ainda pelo nome antigo: *"não vamos ter mais deploy na
vercel para o alchemia-news"*. O Radar passou a ser o back-end da visualização no System. Spec aprovada:
`alchemia-ai/ai-engineering/docs/specs/2026-09-28-nova-arvore-da-empresa.md`. Índice do Radar:
[`../AGENTS.md`](../AGENTS.md).

## O que fica e o que é do fundador

- **O código fica**, inclusive o `vercel.json`: nada foi apagado. Remoção, se um dia houver, é pela
  Lixeira e por decisão do fundador.
- **Desligar o projeto na Vercel é ação do fundador.** Último registro (2026-08-26,
  `../docs/HISTORY.md`): a produção seguia no ar, congelada numa versão anterior e lendo o Supabase
  ao vivo, e build novo era recusado (*"Cannot deploy from a private GitHub organization repository
  on the Hobby plan"*). O estado de hoje não foi medido. Enquanto o projeto existir, pode haver um
  painel do Radar publicado fora do System, atrás do Basic Auth de `proxy.ts`.
- A migração deste painel para o tema escuro e o design system vigente (addendum de 2026-09-22 do
  `../docs/HISTORY.md`) deixa de se aplicar: quem segue a regra só-escuro é o System.

## Se precisar rodar localmente

Para comparar com o System ou recuperar algum comportamento:

```bash
cd alchemia-ai/softwares/internos/alchemia-radar/dashboard
npm run dev    # http://localhost:3000, sem gate de acesso
```

Com `.env.local` configurado, os getters de `lib/data.ts` leem o Supabase e caem para
`../pipeline/data` e `../pipeline/config` quando a tabela vem vazia. `node_modules` e `.next` são
junções para `alchemia-workdata`, fora do Drive: nunca rode `npm install` dentro do Drive.

## O que não mudar sem motivo

- As chaves de `localStorage` e o `name` do `package.json` mantêm o nome antigo de propósito
  (`alchemia-news:document-checklist`, `alchemia-news:opportunity-status:<slug>`, `alchemia-news`).
  São identificadores, não nome de produto: trocar a chave apaga o que o navegador guardou, e o
  `package-lock.json` usa o mesmo `name`.
- `AGENTS.md` e `CLAUDE.md` desta pasta são o bloco de regras que o `next dev` escreve, não o índice
  do Radar.
