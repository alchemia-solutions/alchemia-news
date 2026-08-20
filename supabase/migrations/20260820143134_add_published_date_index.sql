-- Achado real de performance (2026-08-20): dashboard/lib/supabase.ts ordena por
-- `published_date` (fetchItemsByKind), mas a migração original só indexou `kind` e
-- `collected_at` -- toda consulta fazia sort completo sem índice. Medido ao vivo
-- antes desta correção: /noticias ~3.1s por requisição (tabela `news`, ~2.000
-- linhas), repetido, sem melhora entre chamadas.
--
-- nulls last porque a query já usa `nullsFirst: false` do lado do cliente
-- (@supabase/supabase-js) -- o índice replica a mesma ordem, senão o planner do
-- Postgres não o usa para essa consulta específica.
create index if not exists items_published_date_idx
  on items (published_date desc nulls last);
