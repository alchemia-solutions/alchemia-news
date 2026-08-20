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
//
// Nomes de env var aceitos em ordem de prioridade -- este módulo é `server-only`
// (nunca entra no bundle do navegador), então o prefixo NEXT_PUBLIC_ não é
// tecnicamente necessário aqui; ele foi a convenção documentada originalmente
// (AGENTS.md deste setor), mas a integração nativa Supabase<->Vercel provisiona
// `SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` automaticamente ao conectar um
// projeto -- aceitar os dois nomes evita ter que renomear nada manualmente,
// local ou na Vercel. A URL do projeto não é segredo, por isso tem fallback
// fixo (mesmo valor hardcoded em pipeline/sync_supabase.py); a chave não tem,
// porque seu valor real não é conhecido de antemão.
const SUPABASE_URL =
  process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? 'https://texszxmvolbiduhrrdsq.supabase.co';
const SUPABASE_PUBLISHABLE_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

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

const PAGE_SIZE = 1000;

// Achado de performance real (2026-08-20, medido ao vivo): buscar `news` inteiro
// (~2.000 linhas, ~2,4MB de JSON) em toda requisição media ~3.1s e estourava o
// limite de 2MB por entrada do `unstable_cache` (a tentativa de cache falhava em
// silêncio, sem erro, e a página voltava a buscar tudo de novo a cada visita).
// Nenhuma tela deste dashboard tem paginação -- renderiza a lista inteira que
// recebe -- então limitar aqui é o que resolve as duas coisas de uma vez: cabe no
// cache e reduz o tempo de resposta de verdade, não só desloca o custo.
// `DEFAULT_LIMIT` é "os mais recentes N", nunca "todos" -- os textos de UI que
// consomem este resultado (app/page.tsx, app/noticias, app/artigos) dizem
// "Recentes (N)", nunca "Todas (N)", para não alegar completude que não existe.
export const DEFAULT_ITEM_LIMIT = 500;

export async function fetchItemsByKind(kind: ItemKind, limit: number = DEFAULT_ITEM_LIMIT): Promise<NewsItem[]> {
  const supabase = getClient();
  if (!supabase) {
    console.error(
      'Supabase não configurado (nenhuma de NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY ' +
        `presente) -- retornando lista vazia para kind=${kind}.`
    );
    return [];
  }

  const rows: NewsItem[] = [];
  let from = 0;
  while (rows.length < limit) {
    const pageEnd = Math.min(from + PAGE_SIZE, limit) - 1;
    const { data, error } = await supabase
      .from('items')
      .select(ITEM_COLUMNS)
      .eq('kind', kind)
      .order('published_date', { ascending: false, nullsFirst: false })
      .range(from, pageEnd);

    if (error) {
      console.error(`Supabase: falha ao ler items (kind=${kind}):`, error.message);
      break;
    }
    if (!data || data.length === 0) break;
    rows.push(...(data as unknown as NewsItem[]));
    if (data.length < pageEnd - from + 1) break; // última página real veio menor que o pedido
    from += PAGE_SIZE;
  }
  return rows;
}

// Contagem exata sem transferir nenhuma linha (`head: true`) -- usada onde o número
// precisa ser o total real (ex.: StatCard da home), não o tamanho da lista limitada
// que `fetchItemsByKind` devolve para renderização. Mesmo princípio de honestidade
// já aplicado nos textos "Recentes (N)" das páginas /noticias e /artigos.
export async function countItemsByKind(kind: ItemKind): Promise<number> {
  const supabase = getClient();
  if (!supabase) return 0;
  const { count, error } = await supabase
    .from('items')
    .select('*', { count: 'exact', head: true })
    .eq('kind', kind);
  if (error) {
    console.error(`Supabase: falha ao contar items (kind=${kind}):`, error.message);
    return 0;
  }
  return count ?? 0;
}
