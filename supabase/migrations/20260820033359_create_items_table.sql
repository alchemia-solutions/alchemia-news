-- Tabela única `items`, espelhando Item (pipeline/collectors/common.py) e NewsItem
-- (dashboard/lib/types.ts). Escopo inicial: só artigos e notícias (kind), não
-- empresas/editais/programas/newsletter -- esses continuam só em arquivo.
--
-- dedupe_key é a mesma chave de deduplicação já usada nos JSONs locais
-- (common.dedupe_key: doi > url normalizada > hash de titulo+fonte) -- upsert do
-- pipeline usa on_conflict=dedupe_key.
--
-- Aplicada automaticamente pela integração GitHub<->Supabase ao dar `git push` para
-- main (le a pasta supabase/ na raiz deste repo). Nenhum agente roda isto direto no
-- projeto -- ver AGENTS.md deste setor.

create table if not exists items (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  kind text not null check (kind in ('article', 'news')),
  title text not null,
  url text not null,
  source text not null,
  source_type text not null,
  published_date date,
  collected_at timestamptz not null,
  authors text[] not null default '{}',
  summary text not null default '',
  doi text,
  company_slug text,
  keywords_matched text[] not null default '{}',
  extra jsonb not null default '{}',
  inserted_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists items_kind_idx on items (kind);
create index if not exists items_collected_at_idx on items (collected_at desc);

alter table items enable row level security;

create policy "Public read access" on items for select using (true);
-- Sem policy de insert/update/delete para `anon`/`authenticated` -- só a service_role
-- (que ignora RLS por padrão no Supabase) escreve, e só o script de sync do pipeline
-- tem essa chave.
