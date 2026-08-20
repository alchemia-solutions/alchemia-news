import 'server-only';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type {
  CompanyConfig,
  CorporateProgram,
  FundingChannel,
  ItemKind,
  NewsItem,
  PipelineMeta,
  ResourceConfig,
} from './types';

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

// Fase 2 (2026-08-20, mais tarde) -- expande a leitura do Supabase para o resto do
// dashboard. `companies_activity` NÃO tem tabela própria: seus itens já são o mesmo
// formato de `items` (kind='news', company_slug preenchido), sincronizados junto de
// news.json. Aqui é só um filtro sobre a mesma tabela (índice
// `items_company_slug_idx`, ver migração `*_expand_remaining_tables.sql`).
export async function fetchCompanyActivity(limit: number = DEFAULT_ITEM_LIMIT): Promise<NewsItem[]> {
  const supabase = getClient();
  if (!supabase) return [];
  const { data, error } = await supabase
    .from('items')
    .select(ITEM_COLUMNS)
    .not('company_slug', 'is', null)
    .order('published_date', { ascending: false, nullsFirst: false })
    .limit(limit);
  if (error) {
    console.error('Supabase: falha ao ler atividade de empresas:', error.message);
    return [];
  }
  return (data as unknown as NewsItem[]) ?? [];
}

// Contagem real de itens com company_slug preenchido -- usada no StatCard da home,
// que antes mostrava `companiesActivity.length` (capado em DEFAULT_ITEM_LIMIT=500)
// como se fosse o total, quando o total real já passa de 500. Achado ao inspecionar
// visualmente a home renderizada com dado real (2026-08-20).
export async function countCompanyActivity(): Promise<number> {
  const supabase = getClient();
  if (!supabase) return 0;
  const { count, error } = await supabase
    .from('items')
    .select('*', { count: 'exact', head: true })
    .not('company_slug', 'is', null);
  if (error) {
    console.error('Supabase: falha ao contar atividade de empresas:', error.message);
    return 0;
  }
  return count ?? 0;
}

async function fetchCatalog<T>(table: string, orderBy: string): Promise<T[]> {
  const supabase = getClient();
  if (!supabase) return [];
  const { data, error } = await supabase.from(table).select('*').order(orderBy, { ascending: true });
  if (error) {
    console.error(`Supabase: falha ao ler ${table}:`, error.message);
    return [];
  }
  return (data as unknown as T[]) ?? [];
}

export async function fetchCompanies(): Promise<CompanyConfig[]> {
  return fetchCatalog<CompanyConfig>('companies', 'name');
}

export async function fetchResources(): Promise<ResourceConfig[]> {
  return fetchCatalog<ResourceConfig>('resources', 'name');
}

export async function fetchFundingChannels(): Promise<FundingChannel[]> {
  return fetchCatalog<FundingChannel>('funding_channels', 'name');
}

export async function fetchCorporatePrograms(): Promise<CorporateProgram[]> {
  return fetchCatalog<CorporateProgram>('corporate_programs', 'name');
}

export async function fetchPipelineMeta(): Promise<PipelineMeta | null> {
  const supabase = getClient();
  if (!supabase) return null;
  const { data, error } = await supabase.from('pipeline_meta').select('*').eq('id', 'singleton').maybeSingle();
  if (error || !data) {
    if (error) console.error('Supabase: falha ao ler pipeline_meta:', error.message);
    return null;
  }
  return {
    last_run_started: data.last_run_started,
    last_run_finished: data.last_run_finished,
    duration_seconds: data.duration_seconds,
    collectors: data.collectors,
    totals: data.totals,
  } as PipelineMeta;
}

export interface NewsletterRow {
  date: string;
  content: string;
}

// Escrita pela rotina do Axel em `newsletters` (chave primária `date`), não pelo
// pipeline determinístico. Ver alchemia-ai/alchemia-bots/scripts/sync_newsletter.py.
// 2026-08-20 (mais tarde) -- lista todas as edições, não só a mais recente: a rota
// /newsletter virou uma lista navegável por data (achado do fundador: "não ter o
// texto inteiro no começo, só quando clicar"). Quantidade de linhas é pequena (uma
// por dia), então não precisa de paginação/limite como `items`.
export async function fetchAllNewsletters(): Promise<NewsletterRow[]> {
  const supabase = getClient();
  if (!supabase) return [];
  const { data, error } = await supabase
    .from('newsletters')
    .select('date,content')
    .order('date', { ascending: false });
  if (error) {
    console.error('Supabase: falha ao ler newsletters:', error.message);
    return [];
  }
  return (data as NewsletterRow[]) ?? [];
}

export async function fetchNewsletterByDate(date: string): Promise<NewsletterRow | null> {
  const supabase = getClient();
  if (!supabase) return null;
  const { data, error } = await supabase
    .from('newsletters')
    .select('date,content')
    .eq('date', date)
    .maybeSingle();
  if (error || !data) {
    if (error) console.error(`Supabase: falha ao ler newsletters/${date}:`, error.message);
    return null;
  }
  return data as NewsletterRow;
}
