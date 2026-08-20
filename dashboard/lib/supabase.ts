import 'server-only';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { ItemKind, NewsItem } from './types';

// Leitura de `articles`/`news` (tabela única `items`, coluna `kind`) direto do
// Supabase -- substitui a leitura de pipeline/data/articles.json e news.json (ver
// lib/data.ts). É o que elimina a espera de redeploy: o script de sync do pipeline
// (pipeline/sync_supabase.py) escreve aqui logo após cada coleta, e este dashboard
// lê em tempo de requisição, sem rebuild. Empresas/editais/programas/newsletter
// continuam em arquivo -- escopo desta migração é só artigos e notícias.
//
// Chave `anon`/`publishable` -- pública por design, só permite SELECT (RLS da
// tabela `items`, ver supabase/migrations/). Nunca a service_role aqui.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

let cachedClient: SupabaseClient | null = null;

function getClient(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) return null;
  if (!cachedClient) {
    cachedClient = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
  }
  return cachedClient;
}

const ITEM_COLUMNS =
  'kind,title,url,source,source_type,published_date,collected_at,authors,summary,doi,company_slug,keywords_matched,extra,dedupe_key';

// O PostgREST limita cada resposta a 1000 linhas por padrão -- menor que o total
// real de `news` hoje (1.800+ e crescendo 3x/dia). Sem paginação, uma leitura
// perderia itens em silêncio à medida que a base cresce.
const PAGE_SIZE = 1000;

export async function fetchItemsByKind(kind: ItemKind): Promise<NewsItem[]> {
  const supabase = getClient();
  if (!supabase) {
    console.error(
      'Supabase não configurado (NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ausentes) -- ' +
        `retornando lista vazia para kind=${kind}.`
    );
    return [];
  }

  const rows: NewsItem[] = [];
  let from = 0;
  for (;;) {
    const { data, error } = await supabase
      .from('items')
      .select(ITEM_COLUMNS)
      .eq('kind', kind)
      .order('published_date', { ascending: false, nullsFirst: false })
      .range(from, from + PAGE_SIZE - 1);

    if (error) {
      console.error(`Supabase: falha ao ler items (kind=${kind}):`, error.message);
      break;
    }
    if (!data || data.length === 0) break;
    rows.push(...(data as unknown as NewsItem[]));
    if (data.length < PAGE_SIZE) break;
    from += PAGE_SIZE;
  }
  return rows;
}
