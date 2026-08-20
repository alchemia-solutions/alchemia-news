-- Fase 2 da migração para Supabase (2026-08-20, mais tarde): expande o que já foi feito para
-- articles/news (tabela `items`) para todo o resto do dashboard, a pedido do fundador ("quero
-- tudo... atualizado diariamente... sem precisar commitar nada depois").
--
-- `companies_activity` NÃO ganha tabela nova de propósito -- confirmado por leitura direta que
-- seus itens já são o mesmo formato de `items` (kind='news', company_slug preenchido) e já
-- chegam à tabela `items` pela sincronização existente de news.json (o pipeline já deposita todo
-- item de empresa em news.json E companies_activity.json, de propósito -- ver
-- pipeline/run_all.py). Criar uma tabela paralela duplicaria dado sem necessidade. Só falta um
-- índice para a consulta "todo item com company_slug preenchido" ser rápida.

create index if not exists items_company_slug_idx
  on items (company_slug)
  where company_slug is not null;

-- Catálogo de empresas monitoradas (espelha pipeline/config/companies.yaml). Editado
-- ocasionalmente pela rotina do Baker (Passo 4) -- passa a sincronizar junto do resto, 3x/dia.
create table if not exists companies (
  slug text primary key,
  name text not null,
  url text not null,
  category text not null,
  method text not null,
  query text,
  filter_relevance boolean not null default false,
  logo_hint text,
  updated_at timestamptz not null default now()
);
alter table companies enable row level security;
create policy "Public read access" on companies for select using (true);

-- Catálogo de bancos/ferramentas de referência (espelha pipeline/config/resources.yaml).
create table if not exists resources (
  slug text primary key,
  name text not null,
  full_name text not null,
  url text not null,
  type text not null,
  description text not null,
  license_note text not null,
  updated_at timestamptz not null default now()
);
alter table resources enable row level security;
create policy "Public read access" on resources for select using (true);

-- Catálogo de editais de fomento (espelha pipeline/config/funding_channels.yaml, Fase 2 de
-- 2026-08-19). `programs`/`requires` como jsonb/text[] porque são listas de estrutura variável.
create table if not exists funding_channels (
  slug text primary key,
  name text not null,
  full_name text not null,
  scope text not null,
  portal_url text not null,
  calls_url text,
  programs jsonb not null default '[]',
  priority_alchemia text not null,
  priority_note text not null,
  requires text[] not null default '{}',
  source_guide text not null,
  last_reviewed date not null,
  updated_at timestamptz not null default now()
);
alter table funding_channels enable row level security;
create policy "Public read access" on funding_channels for select using (true);

-- Catálogo de programas corporativos (espelha pipeline/config/corporate_programs.yaml).
create table if not exists corporate_programs (
  slug text primary key,
  name text not null,
  category text not null,
  region text not null,
  portal_url text not null,
  benefit_summary text not null,
  eligibility_summary text not null,
  priority_alchemia text not null,
  priority_note text not null,
  source_guide text not null,
  last_reviewed date not null,
  updated_at timestamptz not null default now()
);
alter table corporate_programs enable row level security;
create policy "Public read access" on corporate_programs for select using (true);

-- Newsletter diária do Axel -- escrita pela Tarefa Agendada `alchemia-news-anuncio-discord`
-- (conteúdo interpretativo, gerado por LLM sobre dado real -- ver cron/axel-newsletter-prompt.md),
-- não pelo pipeline determinístico. `date` como chave primária -- uma edição por dia, a mesma
-- lógica de "funde, nunca sobrescreve perdendo achado" já usada no arquivo local se aplica aqui
-- também (upsert com o conteúdo acumulado do dia, nunca um upsert parcial).
create table if not exists newsletters (
  date date primary key,
  content text not null,
  updated_at timestamptz not null default now()
);
alter table newsletters enable row level security;
create policy "Public read access" on newsletters for select using (true);

-- Metadados da última execução do pipeline (espelha pipeline/data/meta.json) -- linha única
-- (id fixo), sobrescrita a cada sincronização. Usado pelo painel ("status dos coletores").
create table if not exists pipeline_meta (
  id text primary key default 'singleton',
  last_run_started timestamptz,
  last_run_finished timestamptz,
  duration_seconds numeric,
  collectors jsonb not null default '{}',
  totals jsonb not null default '{}',
  updated_at timestamptz not null default now()
);
alter table pipeline_meta enable row level security;
create policy "Public read access" on pipeline_meta for select using (true);

-- Nenhuma das seis tabelas acima tem policy de insert/update/delete para anon/authenticated --
-- só a service_role (que ignora RLS) escreve, mesmo princípio já usado em `items`.
